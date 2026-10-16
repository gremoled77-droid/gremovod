"""Платный LLM через PiAPI с серверными ограничениями: цена, потолок токенов, подписанная оценка, бюджет, учёт.

Без подписанной оценки (/api/llm/estimate) и явного подтверждения вызов не уходит к провайдеру."""
import hashlib
import json
import math
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import BaseModel, Field

# USD за 1 млн токенов (piapi.ai/docs/llm-api/completions, акционные цены на 2026-10-16). GPT-6 Astra намеренно нет: дорого и без проверенной цены.
PRICES = {'gpt-5.6-luna': (0.02, 0.12), 'gpt-5.6-terra': (0.2, 1.2), 'gpt-5.6-sol': (0.5, 3.0)}
MAX_OUTPUT_TOKENS = 2000
MAX_INPUT_CHARS = 30000
ROLES = {'system', 'user', 'assistant'}


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
    """Верхняя оценка: вход ≈ 1 токен на 2 символа с запасом, выход — весь max_tokens."""
    price_in, price_out = price_of(model)
    chars = sum(len(m['content']) for m in messages)
    input_tokens = math.ceil(chars / 2) + 20 * len(messages)
    return round((input_tokens * price_in + max_tokens * price_out) / 1_000_000, 6)


def payload_of(model, messages, max_tokens):
    digest = hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {'kind': 'llm', 'model': model, 'max_tokens': max_tokens, 'messages': digest}


def spent(db, project_id):
    """(проект, сегодня по Москве) уже зарезервировано и потрачено на LLM."""
    from backend.security import MOSCOW
    today = datetime.now(MOSCOW).date().isoformat()
    total = daily = 0.0
    for r in db.execute("SELECT project_id,usd,created_at FROM llm_calls WHERE status IN ('reserved','done')"):
        if r['project_id'] == project_id:
            total += r['usd']
        if datetime.fromisoformat(r['created_at']).astimezone(MOSCOW).date().isoformat() == today:
            daily += r['usd']
    return total, daily


def summary(db, projects=None):
    """Расход на LLM по таблице llm_calls: вызовов, USD, по моделям, за сегодня (МСК). projects=None — вся студия."""
    from backend.security import MOSCOW
    today = datetime.now(MOSCOW).date().isoformat()
    out = {'calls': 0, 'usd': 0.0, 'estimated_usd': 0.0, 'today_usd': 0.0, 'by_model': {}}
    try:
        rows = db.execute("SELECT project_id,model,status,usd,estimated_usd,created_at FROM llm_calls WHERE status IN ('reserved','done')").fetchall()
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
        item = out['by_model'].setdefault(r['model'], {'calls': 0, 'usd': 0.0})
        item['calls'] += 1
        item['usd'] += r['usd']
    for key in ('usd', 'estimated_usd', 'today_usd'):
        out[key] = round(out[key], 6)
    for item in out['by_model'].values():
        item['usd'] = round(item['usd'], 6)
    return out


def check_budget(db, project_id, cost):
    from backend import security, series_economics
    series_economics.check_budget(db, project_id, cost)
    state = security.budget_state(db, project_id)
    project_llm, daily_llm = spent(db, project_id)
    if state['project_reserved_usd'] + project_llm + cost > state['project_limit_usd'] + 1e-9:
        raise HTTPException(400, 'Превышен серверный бюджет проекта. Измени лимит в разделе «Экономика».')
    if state['daily_reserved_usd'] + daily_llm + cost > state['daily_limit_usd'] + 1e-9:
        raise HTTPException(400, 'Превышен суточный серверный лимит. Измени его в разделе «Экономика».')


def register(app, studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS llm_calls(id TEXT PRIMARY KEY,request_id TEXT UNIQUE,project_id TEXT NOT NULL,model TEXT NOT NULL,
                status TEXT NOT NULL,usd REAL NOT NULL,estimated_usd REAL NOT NULL,input_tokens INTEGER,output_tokens INTEGER,created_at TEXT NOT NULL)''')

    @app.post('/api/llm/estimate')
    def estimate(body: Estimate):
        studio.project(body.project_id)
        messages = clean_messages(body.messages)
        cost = estimate_usd(body.model, messages, body.max_tokens)
        from backend import security
        token = security.quote(body.project_id, payload_of(body.model, messages, body.max_tokens), cost)
        return {'estimated_usd': cost, 'quote_token': token, 'max_tokens': body.max_tokens, 'model': body.model}


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
        db.execute('INSERT INTO llm_calls VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (call_id, request_id, body.project_id, body.model, 'reserved', cost, cost, None, None, studio.now()))
    try:
        value = await studio.request_piapi('POST', '/v1/chat/completions', key, {'model': body.model, 'messages': messages, 'max_tokens': body.max_tokens})
        text = studio.chat_text(value)
    except Exception:
        with studio.connect() as db:
            db.execute("UPDATE llm_calls SET status='failed',usd=0 WHERE id=?", (call_id,))
        raise
    usage = value.get('usage') if isinstance(value, dict) and isinstance(value.get('usage'), dict) else {}
    price_in, price_out = price_of(body.model)
    tokens_in, tokens_out = usage.get('prompt_tokens'), usage.get('completion_tokens')
    actual = cost
    if isinstance(tokens_in, int) and isinstance(tokens_out, int):
        actual = round(min(cost, (tokens_in * price_in + tokens_out * price_out) / 1_000_000), 6)
    with studio.connect() as db:
        db.execute("UPDATE llm_calls SET status='done',usd=?,input_tokens=?,output_tokens=? WHERE id=?",
                   (actual, tokens_in if isinstance(tokens_in, int) else None, tokens_out if isinstance(tokens_out, int) else None, call_id))
    return {'choices': [{'message': {'role': 'assistant', 'content': text}}], 'usage': usage, 'provider': 'piapi', 'model': body.model,
            'cost_usd': actual, 'estimated_usd': cost}
