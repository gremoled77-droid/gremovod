"""Платный LLM через PiAPI с серверными ограничениями: цена, потолок токенов, подписанная оценка, бюджет, учёт.

Без подписанной оценки (/api/llm/estimate) и явного подтверждения вызов не уходит к провайдеру.

Денежные правила:
- резерв создаётся до обращения к провайдеру и держит бюджет проекта и дня;
- резерв освобождается только когда известно, что провайдер не исполнил запрос и не списал деньги;
- неизвестный исход (таймаут, обрыв, неразбираемый ответ) держит резерв до ручной сверки;
- фактическая стоимость записывается полностью и никогда не урезается оценкой."""
import hashlib
import json
import math
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import Header, HTTPException
from pydantic import BaseModel, Field

from backend.model_catalog import LLM_MODELS, llm_spec, llm_resolve, llm_wire_model
from backend import spend_ledger

# USD за 1 млн токенов (piapi.ai/docs/llm-api/completions, акционные цены на 2026-10-16).
# Цены не дублируются: они берутся из единого реестра backend/model_catalog.py::LLM_MODELS.
def _prices(scopes):
    return {key:(spec['price_in'],spec['price_out']) for key,spec in LLM_MODELS.items() if set(scopes)&set(spec['scopes'])}

PRICES = _prices(('workflow','idea'))
MINIMAX_PRICES = _prices(('task',))
MINIMAX_PROVIDER_MODELS = {key:spec['provider_model'] for key,spec in LLM_MODELS.items() if spec.get('provider_model')}
MAX_OUTPUT_TOKENS = 2000
MAX_INPUT_CHARS = 30000
# Оценка входных токенов. Фронтенд (frontend/src/llmPricing.ts) повторяет эти
# константы для предпросмотра; backend/test_llm_registry.py сверяет копии.
INPUT_CHARS_PER_TOKEN = 1.5
INPUT_TOKENS_PER_MESSAGE = 24
MINIMAX_INPUT_CHARS_PER_TOKEN = 2
MINIMAX_INPUT_TOKENS_PER_MESSAGE = 20
ROLES = {'system', 'user', 'assistant'}
TASK_TTL_SECONDS = 3600
PERMIT_TTL_SECONDS = 600

# Статусы, при которых деньги удерживаются: резерв, подтверждённый факт, неопределённый исход.
# Только 'failed' означает «провайдер ничего не списал» — резерв снят.
# Определение одно на оба контура: журнал вызовов и общий счётчик денег не должны
# решать, какие вызовы держат деньги, по-разному.
HOLDING_STATUSES = spend_ledger.LLM_HOLDING_STATUSES
HOLDING_SQL = 'status IN (' + ','.join('?' * len(HOLDING_STATUSES)) + ')'


class Estimate(BaseModel):
    project_id: str
    model: str
    messages: list[dict] = Field(min_length=1, max_length=50)
    max_tokens: int = Field(default=MAX_OUTPUT_TOKENS, ge=16, le=MAX_OUTPUT_TOKENS)


class ApprovedInput(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=30000)
    approved: Literal[True]


class SelectedSkill(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    instructions: str = Field(min_length=1, max_length=10000)


class SelectedStage(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    revision: str = Field(min_length=1, max_length=200)
    instruction: str = Field(min_length=1, max_length=20000)


class TextTask(BaseModel):
    project_id: str
    stage: SelectedStage
    model: str
    inputs: list[ApprovedInput] = Field(min_length=1, max_length=50)
    skills: list[SelectedSkill] = Field(default_factory=list, max_length=30)
    max_tokens: int = Field(default=MAX_OUTPUT_TOKENS, ge=16, le=MAX_OUTPUT_TOKENS)
    response_format: Literal['text', 'json'] = 'text'
    request_id: str | None = Field(default=None, min_length=16, max_length=100, pattern=r'^[A-Za-z0-9:_-]+$')


class TaskPermitRequest(BaseModel):
    revision: str
    approved: Literal[True]
    request_id: str | None = Field(default=None, min_length=1, max_length=120)


class TaskExecution(BaseModel):
    revision: str
    permit_token: str = Field(min_length=1, max_length=20000)
    request_id: str | None = Field(default=None, min_length=1, max_length=120)


class TaskIdentity(BaseModel):
    task_id: str
    request_id: str = Field(min_length=1, max_length=120)
    revision: str


class TaskReceipt(TaskIdentity):
    status: str
    estimated_usd: float
    max_tokens: int
    model: str
    expires_at: int


class TaskPermitResponse(TaskIdentity):
    permit_token: str
    expires_at: int
    estimated_usd: float


class TaskResult(TaskIdentity):
    model: str
    content: str
    data: Any | None = None
    valid: bool
    validation_error: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    cost_usd: float
    estimated_usd: float
    result_revision: str


def clean_messages(messages):
    out = [{'role': m.get('role'), 'content': str(m.get('content', ''))} for m in messages if m.get('role') in ROLES]
    if not out or not any(m['content'].strip() for m in out):
        raise HTTPException(400, 'Нет текста для LLM')
    if sum(len(m['content']) for m in out) > MAX_INPUT_CHARS:
        raise HTTPException(400, f'Вход LLM длиннее {MAX_INPUT_CHARS} символов')
    return out


def price_of(model):
    if model not in PRICES:
        raise HTTPException(400, 'Эта модель недоступна для платного вызова: нет проверенной цены (разрешены Luna, Terra, Sol)')
    return PRICES[model]


def minimax_price_of(model):
    normalized = model.lower()
    if normalized not in MINIMAX_PRICES:
        raise HTTPException(400, 'Выбери поддерживаемую модель MiniMax: M2, M2.1, M2.5, M3.1 Flash или Text-01')
    return MINIMAX_PRICES[normalized]


def canonical_minimax_model(model):
    return MINIMAX_PROVIDER_MODELS.get(model.lower(), model)


def estimate_usd(model, messages, max_tokens):
    """Оценка запроса: вход ≈ 1 токен на 1,5 символа с запасом, выход — весь max_tokens.

    Это оценка, а не потолок: по возвращённым токенам факт может оказаться больше,
    и тогда превышение видно в учёте, а не прячется под оценкой."""
    price_in, price_out = price_of(model)
    chars = sum(len(m['content']) for m in messages)
    input_tokens = math.ceil(chars / INPUT_CHARS_PER_TOKEN) + INPUT_TOKENS_PER_MESSAGE * len(messages)
    return round((input_tokens * price_in + max_tokens * price_out) / 1_000_000, 6)


def minimax_estimate_usd(model, messages, max_tokens):
    price_in, price_out = minimax_price_of(model)
    chars = sum(len(m['content']) for m in messages)
    input_tokens = math.ceil(chars / MINIMAX_INPUT_CHARS_PER_TOKEN) + MINIMAX_INPUT_TOKENS_PER_MESSAGE * len(messages)
    return round((input_tokens * price_in + max_tokens * price_out) / 1_000_000, 6)


def payload_of(model, messages, max_tokens):
    digest = hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {'kind': 'llm', 'model': model, 'max_tokens': max_tokens, 'messages': digest}


def spent(db, project_id):
    """(проект, сегодня по Москве) уже занято на LLM: резерв, подтверждённый факт и неопределённые вызовы."""
    from backend.security import MOSCOW
    today = datetime.now(MOSCOW).date().isoformat()
    total = daily = 0.0
    for r in db.execute(f"SELECT project_id,usd,created_at FROM llm_calls WHERE {HOLDING_SQL}", HOLDING_STATUSES):
        if r['project_id'] == project_id:
            total += r['usd']
        if datetime.fromisoformat(r['created_at']).astimezone(MOSCOW).date().isoformat() == today:
            daily += r['usd']
    return total, daily


def summary(db, projects=None):
    """Расход на LLM по таблице llm_calls: вызовов, USD, по моделям, за сегодня (МСК). projects=None — вся студия.

    В счёт входят вызовы с неопределённым исходом: их резерв держится до сверки."""
    from backend.security import MOSCOW
    today = datetime.now(MOSCOW).date().isoformat()
    out = {'calls': 0, 'usd': 0.0, 'estimated_usd': 0.0, 'today_usd': 0.0, 'by_model': {},
           'unknown_calls': 0, 'unknown_usd': 0.0, 'over_estimate_calls': 0, 'over_estimate_usd': 0.0}
    try:
        rows = db.execute(f"SELECT project_id,model,status,usd,estimated_usd,created_at FROM llm_calls WHERE {HOLDING_SQL}", HOLDING_STATUSES).fetchall()
    except Exception:  # таблица появляется при запуске сервера
        return out
    for r in rows:
        if projects is not None and r['project_id'] not in projects:
            continue
        out['calls'] += 1
        out['usd'] += r['usd']
        out['estimated_usd'] += r['estimated_usd']
        if datetime.fromisoformat(r['created_at']).astimezone(MOSCOW).date().isoformat() == today:
            out['today_usd'] += r['usd']
        if r['status'] == 'submission_unknown':
            out['unknown_calls'] += 1
            out['unknown_usd'] += r['usd']
        if r['usd'] > r['estimated_usd']:
            out['over_estimate_calls'] += 1
            out['over_estimate_usd'] += r['usd'] - r['estimated_usd']
        item = out['by_model'].setdefault(r['model'], {'calls': 0, 'usd': 0.0})
        item['calls'] += 1
        item['usd'] += r['usd']
    for key in ('usd', 'estimated_usd', 'today_usd', 'unknown_usd', 'over_estimate_usd'):
        out[key] = round(out[key], 6)
    for item in out['by_model'].values():
        item['usd'] = round(item['usd'], 6)
    return out


def check_budget(db, project_id, cost):
    """Единый барьер денег: LLM и генерации проходят по одному лимиту проекта и дня."""
    from backend import security
    security.check_budget(db, project_id, cost)


class Reconcile(BaseModel):
    """Ручная сверка вызова с неопределённым исходом."""
    outcome: str = Field(pattern='^(done|failed)$')
    usd: float | None = Field(default=None, ge=0, le=1000, allow_inf_nan=False)
    note: str = Field(min_length=3, max_length=500)
    approved: bool = False


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def task_revision(task):
    return hashlib.sha256(canonical_json(task.model_dump(mode='json')).encode()).hexdigest()


def validate_text_task(task):
    if task.model.lower() not in MINIMAX_PRICES:
        raise HTTPException(400, 'Выбери поддерживаемую модель MiniMax: M2, M2.1, M2.5, M3.1 Flash или Text-01')
    if task.model != task.model.strip():
        raise HTTPException(400, 'Имя модели не должно содержать пробелы по краям')
    if not task.stage.id.strip() or not task.stage.instruction.strip():
        raise HTTPException(400, 'Выбранный этап должен содержать идентификатор и инструкцию')
    input_ids = [item.id for item in task.inputs]
    if any(not value.strip() for value in input_ids):
        raise HTTPException(400, 'Идентификатор входа не может быть пустым')
    if len(set(input_ids)) != len(input_ids):
        raise HTTPException(400, 'Идентификаторы входов должны быть уникальными')
    if any(not item.content.strip() for item in task.inputs):
        raise HTTPException(400, 'Утверждённый вход не может быть пустым')
    skill_ids = [skill.id for skill in task.skills]
    if any(not value.strip() for value in skill_ids):
        raise HTTPException(400, 'Идентификатор skill не может быть пустым')
    if len(set(skill_ids)) != len(skill_ids):
        raise HTTPException(400, 'Каждый skill можно выбрать только один раз')
    if any(not skill.instructions.strip() for skill in task.skills):
        raise HTTPException(400, 'Выбранный skill не может быть пустым')


def task_messages(task):
    system = f'[stage:{task.stage.id}@{task.stage.revision}]\n{task.stage.instruction}'
    if task.skills:
        system += '\n\n' + '\n\n'.join(f'[skill:{skill.id}]\n{skill.instructions}' for skill in task.skills)
    user = '\n\n'.join(f'[input:{item.id}]\n{item.content}' for item in task.inputs)
    return clean_messages([{'role': 'system', 'content': system}, {'role': 'user', 'content': user}])


def validate_task_result(content, response_format):
    if response_format == 'text':
        if not content.strip():
            return False, None, 'Провайдер вернул пустой текстовый результат'
        return True, None, None
    try:
        data = json.loads(content)
    except (TypeError, ValueError) as error:
        return False, None, f'Результат не является корректным JSON: {error}'
    if not isinstance(data, (dict, list)):
        return False, None, 'JSON-результат должен быть объектом или массивом'
    return True, data, None


def minimax_actual_cost(model, usage, estimated_usd):
    price_in, price_out = minimax_price_of(model)
    tokens_in = usage.get('prompt_tokens')
    tokens_out = usage.get('completion_tokens')
    if isinstance(tokens_in, int) and not isinstance(tokens_in, bool) and isinstance(tokens_out, int) and not isinstance(tokens_out, bool):
        actual = (tokens_in * price_in + tokens_out * price_out) / 1_000_000
        return round(min(estimated_usd, actual), 6)
    return estimated_usd


def provider_key(authorization, direct):
    if direct and direct.strip():
        return direct.strip()
    if authorization:
        value = authorization.strip()
        if value.lower().startswith('bearer '):
            return value[7:].strip()
        return value
    return ''


def load_task(studio, task_id):
    with studio.connect() as db:
        row = db.execute('SELECT * FROM llm_tasks WHERE id=?', (task_id,)).fetchone()
    if row is None:
        raise HTTPException(404, 'Задание не найдено')
    return row


def reserve_minimax_task(studio, row, revision):
    call_id = uuid.uuid4().hex
    call_request_id = f"llm:{task_request_id(row)}:{revision}"
    with studio.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        check_budget(db, row['project_id'], row['estimated_usd'])
        changed = db.execute(
            "UPDATE llm_tasks SET status='running' WHERE id=? AND revision=? AND status='permitted' AND permit_expires>=?",
            (row['id'], revision, int(time.time())),
        ).rowcount
        if changed != 1:
            raise HTTPException(409, 'Разрешение уже использовано или задание запущено')
        db.execute('INSERT INTO llm_calls VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (call_id, call_request_id, row['project_id'], row['model'], 'reserved', row['estimated_usd'], row['estimated_usd'], None, None, studio.now()))
    return call_id


async def execute_minimax_task(studio, task_id, body, key):
    from backend import security
    row = load_task(studio, task_id)
    studio.project(row['project_id'])
    request_id = task_request_id(row)
    if body.request_id and body.request_id != request_id:
        raise HTTPException(409, 'Идентификатор запроса не совпадает с заданием')
    if body.revision != row['revision']:
        raise HTTPException(400, 'Ревизия задания не совпадает')
    if row['status'] == 'done':
        if not row['result']:
            raise HTTPException(500, 'Результат задания не найден')
        result = json.loads(row['result'])
        result.setdefault('request_id', request_id)
        return TaskResult.model_validate(result)
    if row['status'] != 'permitted':
        raise HTTPException(409, 'Задание не разрешено к исполнению или уже запущено')
    security.verify_execution_permit(
        body.permit_token, row['id'], row['revision'], row['project_id'], row['model'], row['estimated_usd'])
    task = TextTask.model_validate(json.loads(row['spec']))
    messages = task_messages(task)
    if not key:
        raise HTTPException(400, 'Передай API-ключ провайдера в заголовке Authorization или X-PiAPI-Key')
    spec = llm_resolve(task.model)
    if spec is None:
        raise HTTPException(400, f'Модель {task.model} не найдена в реестре LLM.')
    call_id = reserve_minimax_task(studio, row, body.revision)
    provider_body = {'model': llm_wire_model(task.model), 'messages': messages, 'max_tokens': task.max_tokens}
    if task.response_format == 'json':
        provider_body['response_format'] = {'type': 'json_object'}
    try:
        value = await studio.provider_chat(spec['provider'], key, provider_body, spend=('llm_call', call_id, row['model']))
        content = studio.chat_text(value)
        if not isinstance(content, str):
            raise ValueError('Провайдер вернул результат не строкой')
    except Exception:
        with studio.connect() as db:
            db.execute("UPDATE llm_calls SET status='failed',usd=0 WHERE id=?", (call_id,))
            db.execute("UPDATE llm_tasks SET status='failed' WHERE id=?", (task_id,))
        raise
    usage = value.get('usage') if isinstance(value, dict) and isinstance(value.get('usage'), dict) else {}
    tokens_in = usage.get('prompt_tokens')
    tokens_out = usage.get('completion_tokens')
    if not isinstance(tokens_in, int) or isinstance(tokens_in, bool):
        tokens_in = None
    if not isinstance(tokens_out, int) or isinstance(tokens_out, bool):
        tokens_out = None
    estimated_usd = float(row['estimated_usd'])
    actual_usd = minimax_actual_cost(task.model, usage, estimated_usd)
    valid, data, validation_error = validate_task_result(content, task.response_format)
    result_revision = hashlib.sha256(canonical_json({'content': content, 'data': data, 'valid': valid}).encode()).hexdigest()
    result = TaskResult(
        task_id=task_id,
        request_id=request_id,
        revision=row['revision'],
        model=task.model,
        content=content,
        data=data,
        valid=valid,
        validation_error=validation_error,
        usage=usage,
        cost_usd=actual_usd,
        estimated_usd=estimated_usd,
        result_revision=result_revision,
    )
    with studio.connect() as db:
        db.execute("UPDATE llm_calls SET status='done',usd=?,input_tokens=?,output_tokens=? WHERE id=?",
                   (actual_usd, tokens_in, tokens_out, call_id))
        db.execute("UPDATE llm_tasks SET status='done',result=?,valid=? WHERE id=?",
                   (canonical_json(result.model_dump(mode='json')), 1 if valid else 0, task_id))
    return result


def register(app, studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS llm_calls(id TEXT PRIMARY KEY,request_id TEXT UNIQUE,project_id TEXT NOT NULL,model TEXT NOT NULL,
                status TEXT NOT NULL,usd REAL NOT NULL,estimated_usd REAL NOT NULL,input_tokens INTEGER,output_tokens INTEGER,created_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS llm_tasks(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,revision TEXT NOT NULL,model TEXT NOT NULL,
                spec TEXT NOT NULL,estimated_usd REAL NOT NULL,status TEXT NOT NULL,permit_expires INTEGER,result TEXT,valid INTEGER,
                created_at TEXT NOT NULL,expires_at INTEGER NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS llm_task_requests(request_id TEXT PRIMARY KEY,task_id TEXT NOT NULL UNIQUE,
                revision TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(task_id) REFERENCES llm_tasks(id) ON DELETE CASCADE)''')
            if 'note' not in {r['name'] for r in db.execute('PRAGMA table_info(llm_calls)')}:
                db.execute('ALTER TABLE llm_calls ADD COLUMN note TEXT')

    @app.post('/api/llm/estimate')
    def estimate(body: Estimate):
        studio.project(body.project_id)
        messages = clean_messages(body.messages)
        cost = estimate_usd(body.model, messages, body.max_tokens)
        from backend import security
        token = security.quote(body.project_id, payload_of(body.model, messages, body.max_tokens), cost)
        return {'estimated_usd': cost, 'quote_token': token, 'max_tokens': body.max_tokens, 'model': body.model}

    @app.post('/api/llm/tasks', response_model=TaskReceipt)
    def prepare_task(body: TextTask):
        studio.project(body.project_id)
        validate_text_task(body)
        body = body.model_copy(update={'model': canonical_minimax_model(body.model)})
        messages = task_messages(body)
        cost = minimax_estimate_usd(body.model, messages, body.max_tokens)
        task_id = uuid.uuid4().hex
        revision = task_revision(body)
        request_id = body.request_id or f"auto:{revision}"
        body = body.model_copy(update={'request_id': request_id})
        spec = canonical_json(body.model_dump(mode='json'))
        expires_at = int(time.time()) + TASK_TTL_SECONDS
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            mapping = db.execute('SELECT * FROM llm_task_requests WHERE request_id=?', (request_id,)).fetchone()
            if mapping:
                if mapping['revision'] != revision:
                    raise HTTPException(409, 'Этот request_id уже принадлежит другому заданию')
                existing = db.execute('SELECT * FROM llm_tasks WHERE id=?', (mapping['task_id'],)).fetchone()
                if not existing:
                    raise HTTPException(500, 'Идемпотентное задание повреждено')
                if json.loads(existing['spec']) != json.loads(spec):
                    raise HTTPException(409, 'Этот request_id уже принадлежит другому заданию')
                existing_spec = json.loads(existing['spec'])
                return {**task_identity(existing), 'status': existing['status'], 'estimated_usd': existing['estimated_usd'],
                        'max_tokens': existing_spec.get('max_tokens', MAX_OUTPUT_TOKENS), 'model': existing['model'],
                        'expires_at': existing['expires_at']}
            db.execute('INSERT INTO llm_tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                       (task_id, body.project_id, revision, body.model, spec, cost,
                        'prepared', None, None, None, studio.now(), expires_at))
            db.execute('INSERT INTO llm_task_requests VALUES(?,?,?,?)',
                       (request_id, task_id, revision, studio.now()))
        return {**task_identity({'id': task_id, 'request_id': request_id, 'revision': revision}), 'status': 'prepared',
                'estimated_usd': cost, 'max_tokens': body.max_tokens, 'model': body.model, 'expires_at': expires_at}

    @app.post('/api/llm/tasks/{task_id}/permit', response_model=TaskPermitResponse)
    def permit_task(task_id: str, body: TaskPermitRequest):
        from backend import security
        now = int(time.time())
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM llm_tasks WHERE id=?', (task_id,)).fetchone()
            if row is None:
                raise HTTPException(404, 'Задание не найдено')
            studio.project(row['project_id'])
            if body.request_id and body.request_id != task_request_id(row):
                raise HTTPException(409, 'Идентификатор запроса не совпадает с заданием')
            if body.revision != row['revision']:
                raise HTTPException(400, 'Ревизия задания не совпадает')
            if row['expires_at'] < now:
                raise HTTPException(410, 'Срок подготовки задания истёк')
            if row['status'] not in {'prepared', 'permitted'}:
                raise HTTPException(409, 'Для этого задания уже нельзя выдать разрешение')
            if row['status'] == 'permitted' and row['permit_expires'] >= now:
                raise HTTPException(409, 'Разрешение уже выдано')
            check_budget(db, row['project_id'], row['estimated_usd'])
            permit_expires = now + PERMIT_TTL_SECONDS
            token = security.execution_permit(
                row['id'], row['revision'], row['project_id'], row['model'], row['estimated_usd'])
            db.execute("UPDATE llm_tasks SET status='permitted',permit_expires=? WHERE id=?", (permit_expires, task_id))
        return {**task_identity(row), 'permit_token': token,
                'expires_at': permit_expires, 'estimated_usd': row['estimated_usd']}

    @app.post('/api/llm/tasks/{task_id}/execute', response_model=TaskResult)
    async def execute_task(task_id: str, body: TaskExecution, authorization: str | None = Header(default=None),
                           x_piapi_key: str | None = Header(default=None)):
        key = provider_key(authorization, x_piapi_key)
        return await execute_minimax_task(studio, task_id, body, key)

    @app.get('/api/llm/tasks/{task_id}')
    def task_status(task_id: str):
        row = load_task(studio, task_id)
        studio.project(row['project_id'])
        result = json.loads(row['result']) if row['result'] else None
        if result:
            result.setdefault('request_id', task_request_id(row))
        spec = json.loads(row['spec'])
        return {
            **task_identity(row),
            'project_id': row['project_id'],
            'model': row['model'],
            'max_tokens': spec.get('max_tokens', MAX_OUTPUT_TOKENS),
            'status': row['status'],
            'estimated_usd': row['estimated_usd'],
            'created_at': row['created_at'],
            'expires_at': row['expires_at'],
            'permit_expires': row['permit_expires'],
            'valid': None if row['valid'] is None else bool(row['valid']),
            'result': result,
        }
    @app.get('/api/llm/calls')
    def calls(project_id: str | None = None, status: str | None = None):
        """Журнал платных LLM-вызовов: видно, где резерв держится и где факт выше оценки."""
        where, args = [], []
        if project_id:
            where.append('project_id=?')
            args.append(project_id)
        if status:
            where.append('status=?')
            args.append(status)
        sql = 'SELECT id,request_id,project_id,model,status,usd,estimated_usd,input_tokens,output_tokens,note,created_at FROM llm_calls'
        if where:
            sql += ' WHERE ' + ' AND '.join(where)
        sql += ' ORDER BY created_at DESC LIMIT 200'
        with studio.connect() as db:
            rows = db.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    @app.post('/api/llm/calls/{call_id}/reconcile')
    def reconcile(call_id: str, body: Reconcile):
        """Сверка неопределённого вызова: подтвердить факт или снять резерв с записью причины."""
        if not body.approved:
            raise HTTPException(400, 'Нужно подтверждение сверки: она меняет учёт расхода')
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM llm_calls WHERE id=?', (call_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Вызов не найден')
            if row['status'] != 'submission_unknown':
                raise HTTPException(409, 'Сверка доступна только для вызова с неопределённым исходом')
            if body.outcome == 'failed':
                db.execute("UPDATE llm_calls SET status='failed',usd=0,note=? WHERE id=?", (body.note, call_id))
                result = {'status': 'failed', 'usd': 0.0}
            else:
                usd = row['usd'] if body.usd is None else round(body.usd, 6)
                db.execute("UPDATE llm_calls SET status='done',usd=?,note=? WHERE id=?", (usd, body.note, call_id))
                result = {'status': 'done', 'usd': usd}
        return {'id': call_id, **result, 'note': body.note, 'estimated_usd': row['estimated_usd']}


def _not_charged(value):
    """Провайдер явно сообщил, что ничего не списал: нулевое потребление токенов."""
    usage = value.get('usage') if isinstance(value, dict) and isinstance(value.get('usage'), dict) else {}
    if not usage:
        return False
    total = usage.get('total_tokens')
    if isinstance(total, int) and not isinstance(total, bool) and total == 0:
        return True
    prompt, completion = usage.get('prompt_tokens'), usage.get('completion_tokens')
    return (isinstance(prompt, int) and not isinstance(prompt, bool) and prompt == 0
            and isinstance(completion, int) and not isinstance(completion, bool) and completion == 0)


def settle_call(studio, call_id, status, usd, note=None, tokens=None):
    """Записать судьбу вызова: сколько денег он удерживает и почему."""
    with studio.connect() as db:
        if tokens:
            db.execute('UPDATE llm_calls SET status=?,usd=?,note=COALESCE(?,note),input_tokens=?,output_tokens=? WHERE id=?',
                       (status, usd, note, tokens[0], tokens[1], call_id))
        else:
            db.execute('UPDATE llm_calls SET status=?,usd=?,note=COALESCE(?,note) WHERE id=?', (status, usd, note, call_id))


def resolve_provider(model, provider=''):
    """Провайдера выбирает реестр.

    Пустой `provider` — это «возьми провайдера этой модели», а не «PiAPI»: вендор
    в коде вызова не прибит. Явный провайдер проверяется на совпадение с реестром.
    """
    if provider:
        spec = llm_spec(model, provider)
        if spec is None:
            raise HTTPException(400, f'Модель {model} не найдена в реестре или её не обслуживает провайдер {provider}.')
        return spec
    spec = llm_spec(model)
    if spec is None:
        raise HTTPException(400, f'Модель {model} не найдена в реестре.')
    return spec


def reserve_call(studio, project_id, model, request_id, cost):
    """Резерв в журнале расходов до обращения к провайдеру. Возвращает id записи.

    Повтор того же request_id — 409: платный вызов не повторяется автоматически.
    """
    call_id = uuid.uuid4().hex
    with studio.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM llm_calls WHERE request_id=?', (request_id,)).fetchone():
            raise HTTPException(409, 'Этот запрос уже отправлялся. Проверь результат, повтор платного вызова не выполняется автоматически.')
        check_budget(db, project_id, cost)
        db.execute('INSERT INTO llm_calls(id,request_id,project_id,model,status,usd,estimated_usd,input_tokens,output_tokens,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (call_id, request_id, project_id, model, 'reserved', cost, cost, None, None, studio.now()))
    return call_id


async def guarded_chat(studio, body, key):
    """Единственный путь платного LLM-вызова. Резерв в бюджете создаётся до обращения к провайдеру."""
    from backend import security
    spec = resolve_provider(body.model, body.provider)
    provider = spec['provider']
    if not body.project_id:
        raise HTTPException(400, 'Укажи проект для учёта расхода')
    studio.project(body.project_id)
    if not body.approved:
        raise HTTPException(400, 'Нужно подтверждение платного LLM-запроса')
    if not body.max_tokens or body.max_tokens > MAX_OUTPUT_TOKENS:
        raise HTTPException(400, f'max_tokens обязателен и не больше {MAX_OUTPUT_TOKENS}')
    messages = clean_messages(body.messages)
    cost = estimate_usd(body.model, messages, body.max_tokens)
    security.verify_quote(body.quote_token or '', body.project_id, payload_of(body.model, messages, body.max_tokens), cost)
    if body.max_cost_usd is None or body.max_cost_usd + 1e-9 < cost:
        raise HTTPException(400, 'Лимит стоимости ниже оценки запроса')
    call_id = uuid.uuid4().hex
    request_id = body.request_id or call_id
    call_id = reserve_call(studio, body.project_id, body.model, request_id, cost)
    try:
        value = await studio.provider_chat(provider, key, {'model': llm_wire_model(body.model), 'messages': messages, 'max_tokens': body.max_tokens}, spend=('llm', request_id, body.model))
    except HTTPException as exc:
        # Отказ 4xx — провайдер не исполнил запрос, деньги не списаны: резерв освобождаем.
        # Всё остальное (5xx, таймаут, обрыв) — исход неизвестен: резерв держим до ручной сверки.
        if getattr(exc, 'status_code', 500) < 500:
            settle_call(studio, call_id, 'failed', 0, f'отказ провайдера: {exc.detail}')
        else:
            settle_call(studio, call_id, 'submission_unknown', cost, f'исход неизвестен: {exc.detail}')
        raise
    except Exception as exc:
        settle_call(studio, call_id, 'submission_unknown', cost, f'исход неизвестен: {exc}')
        raise
    try:
        text = studio.chat_text(value)
    except Exception as exc:
        # Ответ получен, но разобрать его не удалось: запрос мог быть исполнен и оплачен.
        if _not_charged(value):
            settle_call(studio, call_id, 'failed', 0, 'провайдер сообщил нулевое потребление')
        else:
            settle_call(studio, call_id, 'submission_unknown', cost, f'ответ не разобран: {exc}')
        raise
    usage = value.get('usage') if isinstance(value, dict) and isinstance(value.get('usage'), dict) else {}
    price_in, price_out = price_of(body.model)
    tokens_in, tokens_out = usage.get('prompt_tokens'), usage.get('completion_tokens')
    actual = cost
    over_estimate = False
    if isinstance(tokens_in, int) and isinstance(tokens_out, int):
        # Факт писытся полностью: оценка не потолок, превышение должно быть видно, а не спрятано под min().
        actual = round((tokens_in * price_in + tokens_out * price_out) / 1_000_000, 6)
        over_estimate = actual > cost
    with studio.connect() as db:
        db.execute("UPDATE llm_calls SET status='done',usd=?,input_tokens=?,output_tokens=? WHERE id=?",
                   (actual, tokens_in if isinstance(tokens_in, int) else None, tokens_out if isinstance(tokens_out, int) else None, call_id))
    return {'choices': [{'message': {'role': 'assistant', 'content': text}}], 'usage': usage, 'provider': provider, 'model': body.model,
            'cost_usd': actual, 'estimated_usd': cost, 'status': 'done', 'over_estimate': over_estimate,
            'over_estimate_usd': round(actual - cost, 6) if over_estimate else 0.0}
