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
import uuid
from datetime import datetime

from fastapi import HTTPException
from pydantic import BaseModel, Field

# USD за 1 млн токенов (piapi.ai/docs/llm-api/completions, акционные цены на 2026-10-16). GPT-6 Astra дорогая: её предлагает только экран «Идея», в узлах Воркфлоу её нет.
PRICES = {'gpt-5.6-luna': (0.02, 0.12), 'gpt-5.6-terra': (0.2, 1.2), 'gpt-5.6-sol': (0.5, 3.0), 'gpt-6-astra': (2.0, 10.0)}
MAX_OUTPUT_TOKENS = 2000
MAX_INPUT_CHARS = 30000
ROLES = {'system', 'user', 'assistant'}

# Статусы, при которых деньги удерживаются: резерв, подтверждённый факт, неопределённый исход.
# Только 'failed' означает «провайдер ничего не списал» — резерв снят.
HOLDING_STATUSES = ('reserved', 'done', 'submission_unknown')
HOLDING_SQL = 'status IN (' + ','.join('?' * len(HOLDING_STATUSES)) + ')'


class Estimate(BaseModel):
    project_id: str
    model: str
    messages: list[dict] = Field(min_length=1, max_length=50)
    max_tokens: int = Field(default=MAX_OUTPUT_TOKENS, ge=16, le=MAX_OUTPUT_TOKENS)


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


def estimate_usd(model, messages, max_tokens):
    """Оценка запроса: вход ≈ 1 токен на 1,5 символа с запасом, выход — весь max_tokens.

    Это оценка, а не потолок: по возвращённым токенам факт может оказаться больше,
    и тогда превышение видно в учёте, а не прячется под оценкой."""
    price_in, price_out = price_of(model)
    chars = sum(len(m['content']) for m in messages)
    input_tokens = math.ceil(chars / 1.5) + 24 * len(messages)
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


def register(app, studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS llm_calls(id TEXT PRIMARY KEY,request_id TEXT UNIQUE,project_id TEXT NOT NULL,model TEXT NOT NULL,
                status TEXT NOT NULL,usd REAL NOT NULL,estimated_usd REAL NOT NULL,input_tokens INTEGER,output_tokens INTEGER,created_at TEXT NOT NULL)''')
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


def _settle(studio, call_id, status, usd, note=None):
    """Записать судьбу вызова: сколько денег он удерживает и почему."""
    with studio.connect() as db:
        db.execute('UPDATE llm_calls SET status=?,usd=?,note=COALESCE(?,note) WHERE id=?', (status, usd, note, call_id))


async def guarded_chat(studio, body, key):
    """Единственный путь платного LLM-вызова. Резерв в бюджете создаётся до обращения к провайдеру."""
    from backend import security
    if body.provider != 'piapi':
        raise HTTPException(400, 'Платный LLM доступен только через PiAPI')
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
    with studio.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM llm_calls WHERE request_id=?', (request_id,)).fetchone():
            raise HTTPException(409, 'Этот запрос уже отправлялся. Проверь результат, повтор платного вызова не выполняется автоматически.')
        check_budget(db, body.project_id, cost)
        db.execute('INSERT INTO llm_calls(id,request_id,project_id,model,status,usd,estimated_usd,input_tokens,output_tokens,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (call_id, request_id, body.project_id, body.model, 'reserved', cost, cost, None, None, studio.now()))
    try:
        value = await studio.request_piapi('POST', '/v1/chat/completions', key, {'model': body.model, 'messages': messages, 'max_tokens': body.max_tokens})
    except HTTPException as exc:
        # Отказ 4xx — провайдер не исполнил запрос, деньги не списаны: резерв освобождаем.
        # Всё остальное (5xx, таймаут, обрыв) — исход неизвестен: резерв держим до ручной сверки.
        if getattr(exc, 'status_code', 500) < 500:
            _settle(studio, call_id, 'failed', 0, f'отказ провайдера: {exc.detail}')
        else:
            _settle(studio, call_id, 'submission_unknown', cost, f'исход неизвестен: {exc.detail}')
        raise
    except Exception as exc:
        _settle(studio, call_id, 'submission_unknown', cost, f'исход неизвестен: {exc}')
        raise
    try:
        text = studio.chat_text(value)
    except Exception as exc:
        # Ответ получен, но разобрать его не удалось: запрос мог быть исполнен и оплачен.
        if _not_charged(value):
            _settle(studio, call_id, 'failed', 0, 'провайдер сообщил нулевое потребление')
        else:
            _settle(studio, call_id, 'submission_unknown', cost, f'ответ не разобран: {exc}')
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
    return {'choices': [{'message': {'role': 'assistant', 'content': text}}], 'usage': usage, 'provider': 'piapi', 'model': body.model,
            'cost_usd': actual, 'estimated_usd': cost, 'status': 'done', 'over_estimate': over_estimate,
            'over_estimate_usd': round(actual - cost, 6) if over_estimate else 0.0}
