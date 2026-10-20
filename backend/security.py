"""Loopback browser session and signed, short-lived generation quotes."""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from urllib.parse import urlsplit

from backend import spend_ledger

LAUNCH_TOKEN = secrets.token_urlsafe(32)
SIGNING_KEY = secrets.token_bytes(32)
# Ключ подписи измерений мастера: с перезапуском студии отчёт перестаёт проверяться,
# если ключ не задан в окружении (GREMOVOD_QC_SIGNING_KEY).
QC_SIGNING_KEY = os.environ.get('GREMOVOD_QC_SIGNING_KEY', '').strip().encode() or SIGNING_KEY
ORIGINS = {'http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:8000', 'http://localhost:8000'}
MOSCOW = timezone(timedelta(hours=3))


def quote(project_id, payload, cost):
    data = json.dumps({'project_id':project_id, 'payload':payload, 'cost':cost, 'expires':int(time.time())+600}, sort_keys=True, separators=(',', ':'))
    return data + '.' + hmac.new(SIGNING_KEY, data.encode(), hashlib.sha256).hexdigest()


def verify_quote(token, project_id, payload, cost):
    try:
        data, signature = token.rsplit('.', 1)
        expected = hmac.new(SIGNING_KEY, data.encode(), hashlib.sha256).hexdigest()
        value = json.loads(data)
        valid = hmac.compare_digest(signature, expected) and value['expires'] >= time.time()
        valid = valid and value['project_id'] == project_id and value['payload'] == payload and value['cost'] == cost
    except (ValueError, TypeError, KeyError, AttributeError):
        valid = False
    if not valid:
        raise HTTPException(400, 'Оценка отсутствует, устарела или параметры изменены. Получи новую оценку и подтверди запуск.')


def execution_permit(task_id, revision, project_id, model, cost):
    """Подписывает короткоживущее разрешение на исполнение конкретной ревизии задания."""
    data = json.dumps({
        'purpose': 'minimax.text.execute',
        'task_id': task_id,
        'revision': revision,
        'project_id': project_id,
        'model': model,
        'cost': cost,
        'nonce': secrets.token_hex(16),
        'expires': int(time.time()) + 600,
    }, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    signature = hmac.new(SIGNING_KEY, data.encode(), hashlib.sha256).hexdigest()
    return data + '.' + signature


def verify_execution_permit(token, task_id, revision, project_id, model, cost):
    """Проверяет подпись, назначение, срок и неизменность параметров разрешения."""
    try:
        data, signature = token.rsplit('.', 1)
        expected = hmac.new(SIGNING_KEY, data.encode(), hashlib.sha256).hexdigest()
        value = json.loads(data)
        valid = hmac.compare_digest(signature, expected)
        valid = valid and value.get('purpose') == 'minimax.text.execute'
        valid = valid and value.get('task_id') == task_id
        valid = valid and value.get('revision') == revision
        valid = valid and value.get('project_id') == project_id
        valid = valid and value.get('model') == model
        valid = valid and value.get('cost') == cost
        valid = valid and value.get('expires', 0) >= time.time()
    except (ValueError, TypeError, KeyError, AttributeError):
        valid = False
    if not valid:
        raise HTTPException(400, 'Разрешение на исполнение отсутствует, устарело или параметры задания изменены.')


def qc_sign(payload) -> str:
    """Подпись измерений мастера (N34).

    Ключ берётся из окружения, чтобы отчёт воркера можно было проверить после
    перезапуска студии; без переменной ключ живёт только до перезапуска.
    """
    data = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hmac.new(QC_SIGNING_KEY, data.encode(), hashlib.sha256).hexdigest()


def qc_verify(payload, signature) -> bool:
    """Проверка подписи измерений. Подделанный или изменённый отчёт не проходит."""
    try:
        return hmac.compare_digest(qc_sign(payload), str(signature or '').strip())
    except (TypeError, ValueError):
        return False


class BudgetLimits(BaseModel):
    project_usd: float = Field(default=1, ge=0, le=1000, allow_inf_nan=False)
    daily_usd: float = Field(default=2, ge=0, le=1000, allow_inf_nan=False)


def released(status, response):
    """Резерв снимается только с заданий, которые точно ничего не стоили: провайдер отклонил заявку до создания
    задачи (в ответе только detail) или сам сообщил списание 0 (PiAPI: meta.usage.consume). Всё неясное остаётся в резерве."""
    return spend_ledger.released(status, response)


def reservations(db):
    """Одобренные запуски, которые держат бюджет: без заданий, чей резерв уже снят."""
    return spend_ledger.legacy_reservations(db)


def llm_reservations(db):
    """Платные LLM-вызовы, которые держат бюджет: резерв, подтверждённый факт и неопределённый исход.

    Деньги LLM и генераций считаются одним счётчиком. Раньше лимиты проекта и дня проверялись
    двумя разными счётчиками, и порядок «сначала LLM, потом медиа» или наоборот давал разный ответ."""
    return spend_ledger.llm_reservations(db)


def budget_state(db, project_id):
    """Единый счётчик: одобрения Studio и резервы P0-конвертов считаются вместе."""
    return spend_ledger.state(db, project_id)


def check_budget(db, project_id, cost):
    """Единый барьер для всех платных путей: генерации, голос и LLM считаются по одному лимиту."""
    from backend import series_economics
    series_economics.check_budget(db,project_id,cost)
    try:
        spend_ledger.check(db, project_id, cost)
    except spend_ledger.BudgetExceeded as exc:
        raise HTTPException(400, str(exc))


def spend_reserved(db, kind, ref, model=None):
    """Есть ли в журнале расходов резерв, оплачивающий конкретный платный вызов.

    Единственное основание для обращения к платному провайдеру: маршрут, который не
    оставил резерва, не может оплатить вызов — даже если его забыли закрыть.
    kind: 'llm' (по request_id), 'llm_call' (по id вызова), 'job' (по заданию).
    """
    try:
        if kind in ('llm','llm_call'):
            column = 'request_id' if kind == 'llm' else 'id'
            row = db.execute(f'SELECT model,status FROM llm_calls WHERE {column}=?', (ref,)).fetchone()
            if row is None or row['status'] != 'reserved':
                return False
            return model is None or row['model'] == model
        if kind == 'job':
            job = db.execute('SELECT status FROM jobs WHERE id=?', (ref,)).fetchone()
            if job is None or job['status'] not in ('submitting','submitted'):
                return False
            return db.execute('SELECT 1 FROM generation_approvals WHERE job_id=?', (ref,)).fetchone() is not None
    except Exception:
        return False
    return False


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
        from backend import service_auth
        machine = service_auth.machine_ok(request)
        request.state.service_scopes = service_auth.identify(request)[0]
        supplied = request.headers.get('x-studio-session') or request.cookies.get('studio_session', '')
        if not public and not worker and not machine and not secrets.compare_digest(supplied.encode(), LAUNCH_TOKEN.encode()):
            return JSONResponse({'detail':'Локальная сессия отсутствует. Обнови страницу студии.'}, status_code=401)
        # Платные маршруты /api/compose и /api/agents/run больше не заморожены:
        # у них появились серверная оценка, подпись, лимит бюджета и запись в
        # журнал расходов — тот же протокол, что у /api/llm/chat. Граница оплаты
        # не в этом списке, а в точке выхода к провайдеру
        # (backend/main.py::require_spend_reservation).
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
                    'llm_calls_project': llm_project['calls'], 'llm_unknown_calls': llm_project['unknown_calls'],
                    'llm_unknown_usd': llm_project['unknown_usd'], 'llm_over_estimate_usd': llm_project['over_estimate_usd']}

    @app.put('/api/budgets/limits')
    def limits(body: BudgetLimits):
        with studio.connect() as db:
            db.execute('UPDATE spending_limits SET project_usd=?,daily_usd=? WHERE id=1', (body.project_usd,body.daily_usd))
        return body.model_dump()
