"""Учёт расходов n8n-агентов в бюджете студии.

n8n платит провайдеру сам: у него свой credential (Kie/Anthropic), и студия не видит
его вызов и не может его перехватить. Значит, границу денег надо поставить ДО вызова:
платный шаг агента разрешён только после того, как студия зарезервировала деньги в
общем счётчике (`backend/spend_ledger.py`).

Потолок шага задаёт владелец в студии — «потолок роли». Агент присылает, какая роль
работает, и получает разрешение; сумму он не присылает, поэтому свой бюджет придумать
не может. После шага агент сообщает факт: студия списывает подтверждённую сумму и
освобождает остаток резерва. Если агент не отчитался, резерв остаётся в бюджете и
блокирует новые траты до ручной сверки — ровно как неопределённый исход платного
LLM-вызова.

Особая роль этого модуля: n8n-расходы не должны быть вторым счётчиком. Они живут в
том же `spend_ledger`, что медиа-генерации и платные LLM-вызовы, и то же правило
`budget_state` считает их вместе.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

from backend import service_auth, spend_ledger

# Статусы расхода n8n-агента. Смыслы те же, что у платных LLM-вызовов студии:
# резерв держит деньги, подтверждённый факт — это и есть потраченное, отказ — ноль.
HOLDING_STATUSES = ('reserved', 'unknown')
SETTLED_STATUSES = ('done', 'failed')

# Роли n8n-агентов, которым потолок заранее разрешён не нужен: без потолка платить
# нельзя (fail-closed). Пустой список — осознанный отказ, а не ошибка конфигурации.
ROLE_PATTERN = r'^[A-Za-z0-9_.-]{1,32}$'


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_tables(db):
    """Таблицы создаются лениво: модуль работает и без события старта сервера."""
    db.execute('''CREATE TABLE IF NOT EXISTS n8n_spend(permit_id TEXT PRIMARY KEY,request_id TEXT UNIQUE,
        project_id TEXT NOT NULL,role TEXT NOT NULL,stage TEXT,model TEXT,reserved_usd REAL NOT NULL,usd REAL,
        status TEXT NOT NULL,input_tokens INTEGER,output_tokens INTEGER,note TEXT,created_at TEXT NOT NULL,settled_at TEXT)''')
    db.execute('''CREATE TABLE IF NOT EXISTS n8n_allowances(role TEXT PRIMARY KEY,cap_usd REAL NOT NULL,
        model TEXT,note TEXT,updated_at TEXT NOT NULL)''')


# ---------------------------------------------------------------- потолки ролей

def allowances(db):
    """Все разрешённые потолки ролей: {роль: {cap_usd, model, note}}."""
    ensure_tables(db)
    rows = db.execute('SELECT role,cap_usd,model,note,updated_at FROM n8n_allowances ORDER BY role').fetchall()
    return [{'role': r['role'], 'cap_usd': round(float(r['cap_usd']), 6), 'model': r['model'] or '',
             'note': r['note'] or '', 'updated_at': r['updated_at']} for r in rows]


def allowance(db, role):
    """Потолок роли или None: без потолка платить нельзя."""
    ensure_tables(db)
    row = db.execute('SELECT role,cap_usd,model,note FROM n8n_allowances WHERE role=?', (role,)).fetchone()
    if row is None:
        return None
    return {'role': row['role'], 'cap_usd': round(float(row['cap_usd']), 6), 'model': row['model'] or '',
            'note': row['note'] or ''}


def set_allowance(db, role, cap_usd, model='', note=''):
    """Владелец задаёт потолок роли. Потолок — это потолок, а не факт расхода."""
    ensure_tables(db)
    db.execute('INSERT INTO n8n_allowances(role,cap_usd,model,note,updated_at) VALUES(?,?,?,?,?)'
               ' ON CONFLICT(role) DO UPDATE SET cap_usd=excluded.cap_usd,model=excluded.model,'
               'note=excluded.note,updated_at=excluded.updated_at',
               (role, round(float(cap_usd), 6), model or '', note or '', now()))
    return allowance(db, role)


# ------------------------------------------------------------------ резервы

def permit_view(row):
    """Вид резерва для агента и для владельца."""
    counted = spend_ledger.n8n_counted_usd(row['status'], row['reserved_usd'], row['usd'])
    return {'permit_id': row['permit_id'], 'request_id': row['request_id'], 'project_id': row['project_id'],
            'role': row['role'], 'stage': row['stage'] or '', 'model': row['model'] or '',
            'reserved_usd': round(float(row['reserved_usd']), 6), 'usd': None if row['usd'] is None else round(float(row['usd']), 6),
            'held_usd': round(counted, 6), 'status': row['status'],
            'input_tokens': row['input_tokens'], 'output_tokens': row['output_tokens'],
            'note': row['note'] or '', 'created_at': row['created_at'], 'settled_at': row['settled_at']}


def reserve(db, *, project_id, request_id, role, stage='', model='', note=''):
    """Резерв под платный шаг агента.

    Идемпотентно по request_id: повтор того же запроса возвращает тот же permit и
    не бронирует деньги дважды. Закрытый permit повторно не открывается.
    """
    ensure_tables(db)
    existing = db.execute('SELECT * FROM n8n_spend WHERE request_id=?', (request_id,)).fetchone()
    if existing is not None:
        if existing['status'] in SETTLED_STATUSES:
            raise HTTPException(409, 'Этот запрос уже закрыт: повторный резерв не открывает новые деньги')
        return permit_view(existing)
    cap = allowance(db, role)
    if cap is None:
        raise HTTPException(400, f'Для роли {role} не задан потолок расходов: '
                                 'владелец должен разрешить роль, иначе платить нельзя')
    amount = float(cap['cap_usd'])
    if amount <= 0:
        raise HTTPException(400, f'Потолок роли {role} нулевой: платить нельзя')
    try:
        spend_ledger.check(db, project_id, amount)
    except spend_ledger.BudgetExceeded as exc:
        raise HTTPException(400, str(exc))
    permit_id = 'n8n_' + uuid.uuid4().hex
    db.execute('INSERT INTO n8n_spend(permit_id,request_id,project_id,role,stage,model,reserved_usd,usd,status,'
               'input_tokens,output_tokens,note,created_at,settled_at) VALUES(?,?,?,?,?,?,?,NULL,?,NULL,NULL,?,?,NULL)',
               (permit_id, request_id, project_id, role, stage or '', model or '', amount, 'reserved', note or '', now()))
    row = db.execute('SELECT * FROM n8n_spend WHERE permit_id=?', (permit_id,)).fetchone()
    return permit_view(row)


def settle(db, *, permit_id, status, usd=None, input_tokens=None, output_tokens=None, note=''):
    """Факт расхода по резерву.

    done — подтверждённая сумма (может быть больше резерва: перерасход виден в счётчике);
    failed — провайдер ничего не списал, резерв освобождается;
    unknown — агент не отчитался, резерв удерживается до ручной сверки.
    """
    ensure_tables(db)
    row = db.execute('SELECT * FROM n8n_spend WHERE permit_id=?', (permit_id,)).fetchone()
    if row is None:
        raise HTTPException(404, 'Резерв не найден')
    if row['status'] in SETTLED_STATUSES:
        raise HTTPException(409, 'Резерв уже закрыт: повторная оплата невозможна')
    if status == 'failed':
        db.execute("UPDATE n8n_spend SET status='failed',usd=0,settled_at=?,note=? WHERE permit_id=?",
                   (now(), note or '', permit_id))
    elif status == 'unknown':
        db.execute("UPDATE n8n_spend SET status='unknown',note=? WHERE permit_id=?", (note or '', permit_id))
    elif status == 'done':
        if usd is None:
            raise HTTPException(400, 'Факт расхода обязателен: без суммы резерв остаётся в бюджете')
        if usd < 0:
            raise HTTPException(400, 'Факт расхода не может быть отрицательным')
        db.execute("UPDATE n8n_spend SET status='done',usd=?,input_tokens=?,output_tokens=?,settled_at=?,note=? "
                   'WHERE permit_id=?', (round(float(usd), 6), input_tokens, output_tokens, now(), note or '', permit_id))
    else:
        raise HTTPException(400, 'Неизвестный статус расхода: допустимы done, failed, unknown')
    row = db.execute('SELECT * FROM n8n_spend WHERE permit_id=?', (permit_id,)).fetchone()
    return permit_view(row)


def permit(db, permit_id):
    ensure_tables(db)
    row = db.execute('SELECT * FROM n8n_spend WHERE permit_id=?', (permit_id,)).fetchone()
    return None if row is None else permit_view(row)


# ------------------------------------------------------------------- HTTP

class ReserveBody(BaseModel):
    project_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    role: str = Field(min_length=1, max_length=32, pattern=ROLE_PATTERN)
    stage: str = Field(default='', max_length=64)
    model: str = Field(default='', max_length=120)
    note: str = Field(default='', max_length=500)


class SettleBody(BaseModel):
    permit_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    note: str = Field(default='', max_length=500)


class AllowanceBody(BaseModel):
    cap_usd: float = Field(ge=0, le=1000, allow_inf_nan=False)
    model: str = Field(default='', max_length=120)
    note: str = Field(default='', max_length=500)


def register(app, studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            ensure_tables(db)

    @app.post('/api/n8n/spend/reserve')
    def reserve_endpoint(body: ReserveBody, request: Request):
        """Резерв под платный шаг n8n-агента. Без резерва шаг запускать нельзя."""
        service_auth.require_project(request, body.project_id)
        studio.project(body.project_id)
        with studio.connect() as db:
            return reserve(db, project_id=body.project_id, request_id=body.request_id, role=body.role,
                           stage=body.stage, model=body.model, note=body.note)

    @app.post('/api/n8n/spend/settle')
    def settle_endpoint(body: SettleBody, request: Request):
        """Факт расхода по резерву: подтверждённая сумма, отказ или неизвестный исход."""
        service_auth.require_token(request)
        with studio.connect() as db:
            row = db.execute('SELECT project_id FROM n8n_spend WHERE permit_id=?', (body.permit_id,)).fetchone()
        if row is None:
            raise HTTPException(404, 'Резерв не найден')
        service_auth.require_project(request, row['project_id'])
        with studio.connect() as db:
            return settle(db, permit_id=body.permit_id, status=body.status, usd=body.usd,
                          input_tokens=body.input_tokens, output_tokens=body.output_tokens, note=body.note)

    @app.get('/api/n8n/spend/{permit_id}')
    def permit_endpoint(permit_id: str, request: Request):
        """Статус резерва: для сверки и для отладки шага агента."""
        service_auth.require_token(request)
        with studio.connect() as db:
            view = permit(db, permit_id)
        if view is None:
            raise HTTPException(404, 'Резерв не найден')
        service_auth.require_project(request, view['project_id'])
        return view

    @app.get('/api/n8n/allowances')
    def allowances_endpoint():
        """Потолки ролей: их задаёт владелец в браузере, машинный токен сюда не входит."""
        with studio.connect() as db:
            return {'allowances': allowances(db)}

    @app.put('/api/n8n/allowances/{role}')
    def set_allowance_endpoint(role: str, body: AllowanceBody):
        """Владелец разрешает роль и задаёт её потолок."""
        if not role or len(role) > 32 or any(ch not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-' for ch in role):
            raise HTTPException(400, 'Недопустимое имя роли')
        with studio.connect() as db:
            return set_allowance(db, role, body.cap_usd, body.model, body.note)
