"""Loopback browser session and signed, short-lived generation quotes."""
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from urllib.parse import urlsplit

LAUNCH_TOKEN = secrets.token_urlsafe(32)
SIGNING_KEY = secrets.token_bytes(32)
ORIGINS = {'http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:8000', 'http://localhost:8000'}
MOSCOW = timezone(timedelta(hours=3))


def quote(project_id, payload, cost, extra=None):
    """Подписанная оценка. extra — необязательная привязка (провайдер, модель, версия цены, запасной маршрут,
    максимум платежа, хеш tools). Без extra подпись выглядит как прежняя — старые токены остаются годными."""
    body = {'project_id':project_id, 'payload':payload, 'cost':cost, 'expires':int(time.time())+600}
    if extra is not None:
        body['extra'] = extra
    data = json.dumps(body, sort_keys=True, separators=(',', ':'))
    return data + '.' + hmac.new(SIGNING_KEY, data.encode(), hashlib.sha256).hexdigest()


def verify_quote(token, project_id, payload, cost, extra=None):
    """Проверка подписи оценки. Возвращает (True, 'ok') или поднимает HTTPException(400) — как раньше.

    Токен без extra принимается как прежняя подпись; токен с extra отклоняется при любом несовпадении.
    """
    try:
        data, signature = token.rsplit('.', 1)
        expected = hmac.new(SIGNING_KEY, data.encode(), hashlib.sha256).hexdigest()
        value = json.loads(data)
        valid = hmac.compare_digest(signature, expected) and value['expires'] >= time.time()
        valid = valid and value['project_id'] == project_id and value['payload'] == payload and value['cost'] == cost
        # привязка extra: в токене без extra поле отсутствует, в проверке ожидается None
        valid = valid and value.get('extra') == extra
    except (ValueError, TypeError, KeyError, AttributeError):
        valid = False
    if not valid:
        raise HTTPException(400, 'Оценка отсутствует, устарела или параметры изменены. Получи новую оценку и подтверди запуск.')
    return True, 'ok'


class BudgetLimits(BaseModel):
    project_usd: float = Field(default=1, ge=0, le=1000, allow_inf_nan=False)
    daily_usd: float = Field(default=2, ge=0, le=1000, allow_inf_nan=False)


def released(status, response):
    """Резерв снимается только с заданий, которые точно ничего не стоили: провайдер отклонил заявку до создания
    задачи (в ответе только detail) или сам сообщил списание 0 (PiAPI: meta.usage.consume). Всё неясное остаётся в резерве."""
    if status not in {'failed', 'cancelled'}:
        return False
    try:
        value = json.loads(response or '{}')
    except (TypeError, ValueError):
        return False
    if not isinstance(value, dict):
        return False
    task = value.get('data')
    if task is None:
        return 'detail' in value and 'task_id' not in value
    usage = ((task.get('meta') or {}).get('usage') or {}) if isinstance(task, dict) else {}
    consume = usage.get('consume')
    return isinstance(consume, (int, float)) and not isinstance(consume, bool) and consume == 0


def reservations(db):
    """Одобренные запуски, которые держат бюджет: без заданий, чей резерв уже снят."""
    rows = db.execute('SELECT a.estimated_usd,j.project_id,j.created_at,j.status,j.response FROM generation_approvals a JOIN jobs j ON j.id=a.job_id').fetchall()
    return [r for r in rows if not released(r['status'], r['response'])]


def budget_state(db, project_id):
    config = db.execute('SELECT project_usd,daily_usd FROM spending_limits WHERE id=1').fetchone()
    today = datetime.now(MOSCOW).date().isoformat()
    rows = reservations(db)
    project_used = sum(r['estimated_usd'] for r in rows if r['project_id'] == project_id)
    daily_used = sum(r['estimated_usd'] for r in rows if datetime.fromisoformat(r['created_at']).astimezone(MOSCOW).date().isoformat() == today)
    return {'project_limit_usd':config['project_usd'], 'daily_limit_usd':config['daily_usd'], 'project_reserved_usd':round(project_used,6), 'daily_reserved_usd':round(daily_used,6), 'day_moscow':today}


def check_budget(db, project_id, cost):
    from backend import series_economics
    series_economics.check_budget(db,project_id,cost)
    value = budget_state(db, project_id)
    if value['project_reserved_usd'] + cost > value['project_limit_usd'] + 1e-9:
        raise HTTPException(400, 'Превышен серверный бюджет проекта. Измени лимит в разделе «Экономика».')
    if value['daily_reserved_usd'] + cost > value['daily_limit_usd'] + 1e-9:
        raise HTTPException(400, 'Превышен дневной серверный бюджет. Измени лимит в разделе «Экономика».')


def register(app, studio):
    @app.middleware('http')
    async def local_session(request: Request, call_next):
        raw_host=request.headers.get('host','')
        try:
            host=urlsplit('//'+raw_host)
            from backend import remote_access
            valid=(host.hostname in {'127.0.0.1','localhost','::1'} or remote_access.allowed_host(host.hostname)) and host.username is None and host.password is None and not host.path and not host.query and not host.fragment and (host.port is None or 0<host.port<=65535)
        except ValueError:valid=False
        if not valid:return JSONResponse({'detail':'Недопустимый Host: студия принимает только локальные запросы'},status_code=403)
        origin = request.headers.get('origin')
        from backend import remote_access
        if origin and origin not in ORIGINS and not remote_access.allowed_origin(origin) or request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail':'Запрос с постороннего сайта запрещён'}, status_code=403)
        public = request.url.path in {'/api/health','/api/session','/api/login','/api/logout','/login'} or not (request.url.path.startswith('/api/') or request.url.path in {'/docs','/redoc','/openapi.json','/docs/oauth2-redirect'})
        worker = request.url.path.startswith('/api/chatgpt/worker/')
        supplied = request.headers.get('x-studio-session') or request.cookies.get('studio_session', '')
        if not public and not worker and not secrets.compare_digest(supplied.encode(), LAUNCH_TOKEN.encode()):
            return JSONResponse({'detail':'Локальная сессия отсутствует. Обнови страницу студии.'}, status_code=401)
        if request.method == 'POST' and request.url.path in {'/api/chat','/api/compose','/api/agents/run'}:
            return JSONResponse({'detail':'Платный LLM-резерв временно отключён: для него ещё нет проверенной серверной оценки и лимита стоимости. Используй основной чат Codex.'}, status_code=503)
        return await call_next(request)


    @app.get('/api/session')
    def session(request: Request):
        response = JSONResponse({'token':LAUNCH_TOKEN}, headers={'Cache-Control':'no-store'})
        response.set_cookie('studio_session', LAUNCH_TOKEN, httponly=True, samesite='strict', path='/', secure=request.headers.get('x-forwarded-proto')=='https')
        return response

    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS spending_limits(id INTEGER PRIMARY KEY,project_usd REAL NOT NULL,daily_usd REAL NOT NULL)')
            db.execute('INSERT OR IGNORE INTO spending_limits(id,project_usd,daily_usd) VALUES(1,1,2)')

    @app.get('/api/budgets/{project_id}')
    def budgets(project_id: str):
        studio.project(project_id)
        from backend import llm_guard
        with studio.connect() as db:
            llm_project = llm_guard.summary(db, {project_id})
            llm_all = llm_guard.summary(db)
            return {**budget_state(db, project_id), 'llm_project_usd': llm_project['usd'], 'llm_daily_usd': llm_all['today_usd'],
                    'llm_calls_project': llm_project['calls']}

    @app.put('/api/budgets/limits')
    def limits(body: BudgetLimits):
        with studio.connect() as db:
            db.execute('UPDATE spending_limits SET project_usd=?,daily_usd=? WHERE id=1', (body.project_usd,body.daily_usd))
        return body.model_dump()
