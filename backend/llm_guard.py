"""Защита денег на платном LLM: маршрут через шлюз, подписанная оценка, резерв, лимиты, журнал вызовов.

Маршрут выбирается через backend/llm_gateway.py. Резерв берётся из тарифа маршрута-исполнителя;
тарифный ориентир (Kie/PiAPI) в резерве не участвует и хранится в журнале отдельно, как сравнение.

Исход вызова различается по правилу «неизвестное списание не равно нулю»:
- подтверждённый факт — actual_status='confirmed', резерв снят;
- бесплатный маршрут — 'free', факт 0, резерв снят;
- неопределённый исход (таймаут, 429, 5xx, 1010, нет usage) — 'unknown', суммы нет, резерв остаётся;
- отказ провайдера со ссылкой «списания не было» — 'not_charged', факт 0, резерв снят.

Без подписанной оценки (/api/llm/estimate) и явного подтверждения вызов не уходит к провайдеру."""
import hashlib
import json
import math
import uuid
from dataclasses import replace
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field

from backend import llm_gateway
from backend.llm_gateway import ModelEntry, Route, Usage

# USD за 1 млн токенов (piapi.ai/docs/llm-api/completions, акционные цены на 2026-10-16). GPT-6 Astra дорогая: её предлагает только экран «Идея», в узлах Воркфлоу её нет.
PRICES = {'gpt-5.6-luna': (0.02, 0.12), 'gpt-5.6-terra': (0.2, 1.2), 'gpt-5.6-sol': (0.5, 3.0), 'gpt-6-astra': (2.0, 10.0)}
MAX_OUTPUT_TOKENS = 2000
MAX_INPUT_CHARS = 30000
ROLES = {'system', 'user', 'assistant'}

LEGACY_PROVIDER = 'piapi'
GATEWAY_PROVIDERS = {'kie', 'minimax', 'deepseek', 'openrouter'}

# Новые колонки журнала вызовов (interfaces.md §3). Добавляются аддитивно: старые колонки и строки остаются.
CALL_COLUMNS = (
    ('execution_provider', 'TEXT'),
    ('execution_model', 'TEXT'),
    ('actual_cost_usd', 'REAL'),
    ('actual_status', 'TEXT'),
    ('reserved_usd', 'REAL'),
    ('billing_source', 'TEXT'),
    ('reference_provider', 'TEXT'),
    ('reference_model', 'TEXT'),
    ('reference_kind', 'TEXT'),
    ('reference_rate_snapshot_id', 'TEXT'),
    ('reference_cost_usd', 'REAL'),
    ('reference_cost_status', 'TEXT'),
    ('cached_input_tokens', 'INTEGER'),
    ('reasoning_tokens', 'INTEGER'),
    ('price_snapshot_id', 'TEXT'),
    ('route_mode', 'TEXT'),
    ('fallback_from', 'TEXT'),
    ('error_kind', 'TEXT'),
    ('provider_request_id', 'TEXT'),
)

INSERT_COLUMNS = ('id', 'request_id', 'project_id', 'model', 'status', 'usd', 'estimated_usd', 'input_tokens',
                  'output_tokens', 'created_at', 'execution_provider', 'execution_model', 'actual_cost_usd',
                  'actual_status', 'reserved_usd', 'billing_source', 'reference_provider', 'reference_model',
                  'reference_kind', 'reference_rate_snapshot_id', 'reference_cost_usd', 'reference_cost_status',
                  'cached_input_tokens', 'reasoning_tokens', 'price_snapshot_id', 'route_mode', 'fallback_from',
                  'error_kind', 'provider_request_id')


class Estimate(BaseModel):
    project_id: str
    model: str
    messages: list[dict] = Field(min_length=1, max_length=50)
    max_tokens: int = Field(default=MAX_OUTPUT_TOKENS, ge=16, le=MAX_OUTPUT_TOKENS)
    route_mode: str = 'manual'
    task: str | None = None
    allow_free: bool = False
    tools: list[dict] = Field(default_factory=list)
    settings: dict = Field(default_factory=dict)
    max_cost_usd: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)


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


def _digest_of(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def payload_of(model, messages, max_tokens, tools=None, settings=None):
    """Тело подписи оценки. Форма прежняя (модель, потолок токенов, хеш сообщений);
    tools и settings добавляются в подпись, только если их прислали."""
    digest = hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    payload = {'kind': 'llm', 'model': model, 'max_tokens': max_tokens, 'messages': digest}
    if tools:
        payload['tools'] = _digest_of(tools)
    if settings:
        payload['settings'] = _digest_of(settings)
    return payload


def ensure_schema(db):
    """Журнал вызовов: базовая таблица и новые колонки. Миграция аддитивная — история не теряется."""
    db.execute('''CREATE TABLE IF NOT EXISTS llm_calls(id TEXT PRIMARY KEY,request_id TEXT UNIQUE,project_id TEXT NOT NULL,model TEXT NOT NULL,
        status TEXT NOT NULL,usd REAL NOT NULL,estimated_usd REAL NOT NULL,input_tokens INTEGER,output_tokens INTEGER,created_at TEXT NOT NULL)''')
    have = {str(row['name']) for row in db.execute('PRAGMA table_info(llm_calls)')}
    for name, kind in CALL_COLUMNS:
        if name not in have:
            db.execute('ALTER TABLE llm_calls ADD COLUMN ' + name + ' ' + kind)


def _confirmed_of(row):
    """Подтверждённое списание строки — только факт по usage. Неподтверждённое списание нулём не считается."""
    actual_status = row['actual_status']
    if actual_status == 'confirmed':
        return float(row['actual_cost_usd'] or 0.0)
    if actual_status == 'free':
        return 0.0
    if actual_status is None:
        # строка старой схемы: факт лежал в usd при status='done'
        return float(row['usd'] or 0.0) if row['status'] == 'done' else 0.0
    return 0.0


def _exposure_of(row):
    """Деньги под риском строки: подтверждённый факт, удерживаемый резерв и неизвестные списания."""
    actual_status = row['actual_status']
    if actual_status == 'confirmed':
        return float(row['actual_cost_usd'] or 0.0)
    if actual_status == 'free':
        return 0.0
    if actual_status in ('unknown', 'estimated'):
        return float(row['reserved_usd'] or 0.0)
    if actual_status == 'not_charged':
        return 0.0
    # строка старой схемы: и факт, и резерв лежали в usd
    if row['status'] in ('done', 'reserved'):
        return float(row['usd'] or 0.0)
    return 0.0


def spent(db, project_id):
    """(проект, сегодня по Москве) экспозиция: подтверждённый факт, удерживаемый резерв и неизвестные списания.
    Это разные величины с «фактически потрачено» (summary()['actual_usd']): в проверку лимита входит всё."""
    from backend.security import MOSCOW
    today = datetime.now(MOSCOW).date().isoformat()
    total = daily = 0.0
    for r in db.execute('SELECT project_id,usd,status,actual_status,actual_cost_usd,reserved_usd,created_at FROM llm_calls'):
        if r['project_id'] != project_id:
            continue
        money = _exposure_of(r)
        total += money
        if datetime.fromisoformat(r['created_at']).astimezone(MOSCOW).date().isoformat() == today:
            daily += money
    return total, daily


def summary(db, projects=None):
    """Расход на LLM по таблице llm_calls: вызовов, USD, по моделям, за сегодня (МСК). projects=None — вся студия.

    'usd' — экспозиция (факт + удерживаемые резервы + неизвестные списания): её проверяет лимит.
    'actual_usd' — фактически потрачено: подтверждённый факт по usage и бесплатные вызовы.
    """
    from backend.security import MOSCOW
    today = datetime.now(MOSCOW).date().isoformat()
    out = {'calls': 0, 'usd': 0.0, 'actual_usd': 0.0, 'estimated_usd': 0.0, 'today_usd': 0.0, 'by_model': {}}
    try:
        rows = db.execute('SELECT project_id,model,status,usd,estimated_usd,actual_status,actual_cost_usd,reserved_usd,created_at FROM llm_calls').fetchall()
    except Exception:  # таблица появляется при запуске сервера
        return out
    for r in rows:
        if projects is not None and r['project_id'] not in projects:
            continue
        money = _exposure_of(r)
        out['calls'] += 1
        out['usd'] += money
        out['actual_usd'] += _confirmed_of(r)
        out['estimated_usd'] += float(r['estimated_usd'] or 0.0)
        if datetime.fromisoformat(r['created_at']).astimezone(MOSCOW).date().isoformat() == today:
            out['today_usd'] += money
        item = out['by_model'].setdefault(r['model'], {'calls': 0, 'usd': 0.0})
        item['calls'] += 1
        item['usd'] += money
    for key in ('usd', 'actual_usd', 'estimated_usd', 'today_usd'):
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


def current_registry():
    """Реестр шлюза: файл владельца, иначе приложенный пример (все маршруты выключены)."""
    return llm_gateway.load_registry()


def legacy_route(model):
    """Совместимый маршрут PiAPI по старым проверенным ценам — для клиентов, пришедших с provider='piapi'."""
    if model not in PRICES:
        return None
    return Route(provider=LEGACY_PROVIDER, model=model, model_id=model, protocol='openai_chat', role='extra',
                 base_url='https://api.piapi.ai', free=False, opt_in=False, enabled=True, verified_at='legacy',
                 capabilities=llm_gateway.Capabilities(), source='llm_guard.PRICES', as_of='')


def is_legacy_route(route):
    """Совместимый маршрут PiAPI по старым проверенным ценам (для клиентов, пришедших с provider='piapi')."""
    return route.provider == LEGACY_PROVIDER and route.verified_at == 'legacy'


def registry_with_route(registry, route):
    """Реестр с тарифом маршрута: у совместимого маршрута PiAPI тариф — старые проверенные цены."""
    if not is_legacy_route(route) or route.model not in PRICES:
        return registry
    price_in, price_out = PRICES[route.model]
    entry = ModelEntry(provider=route.provider, model=route.model, model_id=route.model, protocol=route.protocol,
                       role=route.role, base_url=route.base_url, input_per_mtok=price_in, output_per_mtok=price_out,
                       cached_input_per_mtok=None, source=route.source, as_of=route.as_of, enabled=True,
                       verified_at=route.verified_at, quota_limited=False, promotion=False, free=False, opt_in=False,
                       requires_dynamic_tier_check=False, capabilities=route.capabilities,
                       max_input_tokens=None, rate_limit=None, upstream_version=None)
    entries = tuple(item for item in registry.entries
                    if not (item.provider == route.provider and item.model == route.model)) + (entry,)
    return replace(registry, entries=entries)


def snapshot_id(provider, model, as_of):
    """Снимок тарифа: провайдер, модель и дата тарифа."""
    return f'{provider}/{model}@{as_of or "legacy"}'


def estimated_usage(messages, max_tokens):
    """Предвызовная оценка расхода токенов — та же формула, что у estimate_usd."""
    chars = sum(len(m['content']) for m in messages)
    input_tokens = math.ceil(chars / 2) + 20 * len(messages)
    return Usage(input_tokens=input_tokens, output_tokens=max_tokens, estimated=True)


def route_estimate(registry, route, messages, max_tokens):
    """Оценка реальной стоимости по тарифу маршрута-исполнителя (не по тарифному ориентиру)."""
    if is_legacy_route(route) and route.model in PRICES:
        return llm_gateway.ActualQuote(cost_usd=estimate_usd(route.model, messages, max_tokens), status='estimated',
                                       provider=route.provider, model=route.model, billing_source='route_tariff')
    return llm_gateway.actual_quote(registry_with_route(registry, route), route,
                                    estimated_usage(messages, max_tokens))


def reference_of(registry, route, usage):
    """Тарифный ориентир для карточки: сколько вызов стоил бы по тарифу Kie/PiAPI."""
    ref = llm_gateway.reference_quote(registry, route, usage)
    return {'provider': ref.provider, 'model': ref.model, 'kind': ref.kind, 'cost_usd': ref.cost_usd,
            'status': ref.status, 'rate_source': ref.rate_source, 'rate_as_of': ref.rate_as_of,
            'rate_verified': ref.rate_verified, 'label': ref.label,
            'rate_snapshot_id': snapshot_id(ref.provider or '', ref.model or '', ref.rate_as_of or '')}


def resolve_route(registry, provider, model, allow_free=False):
    """Маршрут выбирается через шлюз. Старый клиент с provider='piapi' получает совместимый маршрут по старым ценам."""
    route = llm_gateway.select_route(registry, task=model, mode='manual', allow_free=allow_free)
    if route is not None:
        if provider in GATEWAY_PROVIDERS and provider != route.provider:
            raise HTTPException(400, 'Провайдер не соответствует модели: маршрут ' + route.provider + '/' + route.model)
        return route
    if provider in ('', LEGACY_PROVIDER):
        return legacy_route(model)
    return None


def _route_is_free(registry, route):
    """Маршрут подтверждённо бесплатный: флаг free или тариф 0/0 по записи реестра."""
    if route.free:
        return True
    return llm_gateway.is_free_entry(registry.entry(route.provider, route.model))


def quota_limited(registry, route):
    """Маршрут под квотным ограничением: бесплатная квота может перейти в платную."""
    entry = registry.entry(route.provider, route.model)
    return bool(entry is not None and entry.quota_limited)


def charge_possible(registry, route, reported):
    """Может ли маршрут списать деньги по исходу вызова.

    У маршрута с нулевым тарифом без квотного ограничения списать нечего: там не за что платить,
    поэтому исход «возможно списано» невозможен и цепочка продолжается на платный маршрут.
    У маршрута с нулевым тарифом под квотным ограничением бесплатная квота может перейти в платное:
    списание возможно, цепочка останавливается. У платного маршрута исход провайдера решает.
    """
    if not reported:
        return False
    if not _route_is_free(registry, route):
        return True
    return quota_limited(registry, route)


def paid_reserve(registry, chain, estimates, index, messages, max_tokens):
    """Резерв под возможное списание на маршруте с нулевым тарифом: с платного маршрута.

    Сначала платный маршрут цепочки — тот, что был бы следующим, — затем любой платный маршрут
    реестра (как в агентском пути). Платного маршрута нет: резерв взять негде.
    """
    for position in range(index + 1, len(chain)):
        amount = float(estimates[position].cost_usd or 0.0)
        if amount > 0:
            return amount
    entry = llm_gateway.paid_reserve_entry(registry)
    if entry is None:
        return None
    quote = route_estimate(registry, entry.route(), messages, max_tokens)
    amount = float(quote.cost_usd or 0.0)
    return amount if amount > 0 else None


def plan_chain(registry, task, allow_free=False):
    """Цепочка маршрутов задачи: сначала бесплатные, затем не больше одного платного.

    Бесплатный маршрут — подтверждённо нулевой тариф (флаг free или тариф 0/0). Платный маршрут
    по оптину тоже платный: он занимает единственное платное место цепочки, а не встаёт перед ним
    вторым платным маршрутом (две платные попытки на один запрос не делается).
    """
    chain = []
    paid = None
    for role in (task, 'backup'):
        for entry in registry.entries_for_role(role):
            if not entry.enabled:
                continue
            if llm_gateway.is_free_entry(entry):
                # бесплатный маршрут денег не стоит; opt-in требует разрешения владельца
                if allow_free or not (entry.free or entry.opt_in):
                    chain.append(entry.route())
                continue
            if entry.opt_in and not allow_free:
                continue
            if entry.input_per_mtok is None or entry.output_per_mtok is None:
                continue
            if paid is None:
                paid = entry.route()
        if paid is not None:
            break
    if paid is not None:
        chain.append(paid)
    return chain


def plan_routes(registry, body, mode, allow_free):
    """Маршруты вызова: ручной режим — маршрут по модели, автоматический — цепочка по роли задачи."""
    model = str(getattr(body, 'model', '') or '')
    provider = str(getattr(body, 'provider', '') or '').strip().lower()
    if mode == 'auto':
        task = str(getattr(body, 'task', '') or 'simple').strip().lower()
        chain = plan_chain(registry, task, allow_free)
        if chain:
            return chain
    route = resolve_route(registry, provider, model, allow_free)
    return [route] if route is not None else []


def extra_of(chain, cost, tools):
    """Привязка подписи: провайдер, модель, версия цены, запасной маршрут, максимум платежа, хеш tools."""
    primary = chain[0]
    return {'provider': primary.provider, 'model': primary.model,
            'price_version': snapshot_id(primary.provider, primary.model, primary.as_of),
            'fallback': ([route.provider + '/' + route.model for route in chain[1:]] or None),
            'max_payment_usd': cost,
            'tools_hash': _digest_of(tools or [])}


def verify_token(security, token, project_id, payload, cost, extra):
    """Старая подпись (без extra) принимается как прежняя; новая проверяется со всеми привязками."""
    try:
        security.verify_quote(token, project_id, payload, cost)
    except HTTPException:
        security.verify_quote(token, project_id, payload, cost, extra)


def _classify_failure(exc):
    """Вид сбоя и признак «списания не было» — по структуре исключения, а не по тексту сообщения.

    Транспорт поднимает ProviderCallFailed с готовыми error_kind и charged_possible
    (backend/main.py). Любое другое исключение — исход неопределённый: списание возможно,
    резерв удерживается до сверки.
    """
    kind = getattr(exc, 'error_kind', None)
    charged = getattr(exc, 'charged_possible', None)
    if kind is None or charged is None:
        return 'provider_error', True
    return str(kind), bool(charged)


def usage_dict(usage):
    """Расход токенов в форме ответа — как у провайдера OpenAI-формы."""
    out = {}
    if usage.input_tokens is not None:
        out['prompt_tokens'] = usage.input_tokens
    if usage.output_tokens is not None:
        out['completion_tokens'] = usage.output_tokens
    if usage.input_tokens is not None and usage.output_tokens is not None:
        out['total_tokens'] = usage.input_tokens + usage.output_tokens
    if usage.cached_input_tokens is not None:
        out['cached_tokens'] = usage.cached_input_tokens
    if usage.reasoning_tokens is not None:
        out['reasoning_tokens'] = usage.reasoning_tokens
    return out


def provider_key_for(route, key):
    """Ключ провайдера: у PiAPI — из запроса (как раньше), у остальных — по схеме backend/connections.py (её читает адаптер)."""
    if route.provider == LEGACY_PROVIDER:
        return key
    return None


def _network_forbidden(request):
    """Обработчик транспорта в тестах: наружу не идём — явная ошибка вместо сетевого вызова."""
    raise AssertionError('Тест попытался выйти в сеть к провайдеру: ' + str(request.url))


def provider_client():
    """Клиент транспорта адаптера. В процессе тестов сеть закрыта: попытка живого вызова — явная ошибка.

    Вне тестов клиент не подменяется: адаптер создаёт свой (backend/llm_adapters.py).
    """
    if not llm_gateway.test_mode():
        return None
    return httpx.AsyncClient(transport=httpx.MockTransport(_network_forbidden))


async def call_provider(studio, route, messages, max_tokens, key, registry, allow_free):
    """Вызов провайдера по маршруту. Возвращает общую форму: текст, расход токенов, вид сбоя, могло ли списаться."""
    if is_legacy_route(route):
        try:
            value = await studio.request_piapi('POST', '/v1/chat/completions', key,
                                               {'model': route.model, 'messages': messages, 'max_tokens': max_tokens})
        except HTTPException as exc:
            error_kind, charged = _classify_failure(exc)
            return {'ok': False, 'text': '', 'usage': Usage(None, None, estimated=True), 'usage_raw': {},
                    'error_kind': error_kind, 'charged_possible': charged, 'provider_request_id': None,
                    'status_code': int(getattr(exc, 'status_code', 502) or 502), 'detail': exc.detail,
                    'answered': False}
        raw = value.get('usage') if isinstance(value, dict) and isinstance(value.get('usage'), dict) else {}
        usage = Usage(input_tokens=raw.get('prompt_tokens'), output_tokens=raw.get('completion_tokens'), estimated=False)
        try:
            text = studio.chat_text(value)
        except HTTPException as exc:
            # провайдер ответил, но без пригодного текста: вызов закрыт, расход решается по usage
            return {'ok': False, 'text': '', 'usage': usage, 'usage_raw': raw,
                    'error_kind': 'bad_body', 'charged_possible': True,
                    'provider_request_id': (value.get('id') if isinstance(value, dict) else None),
                    'status_code': int(getattr(exc, 'status_code', 502) or 502), 'detail': exc.detail,
                    'answered': True}
        return {'ok': True, 'text': text, 'usage': usage, 'usage_raw': raw,
                'error_kind': None, 'charged_possible': False,
                'provider_request_id': (value.get('id') if isinstance(value, dict) else None),
                'status_code': 200, 'detail': None, 'answered': True}
    from backend import llm_adapters
    client = provider_client()
    # подменённый транспорт передаётся адаптеру; вне тестов адаптер создаёт клиент сам
    transport = {'client': client} if client is not None else {}
    try:
        result = await llm_adapters.complete(route, messages, max_tokens,
                                             api_key=provider_key_for(route, key),
                                             registry=registry_with_route(registry, route),
                                             allow_free=allow_free, **transport)
    except HTTPException as exc:
        # отказ до сети: маршрут не включён или тариф не подтверждён — списания не было
        return {'ok': False, 'text': '', 'usage': Usage(None, None, estimated=True), 'usage_raw': {},
                'error_kind': 'route_rejected', 'charged_possible': False, 'provider_request_id': None,
                'status_code': int(getattr(exc, 'status_code', 400) or 400), 'detail': exc.detail,
                'answered': False}
    finally:
        if client is not None:
            await client.aclose()
    if not result.ok:
        # провайдер ответил и его usage разобран — ответ считается полученным:
        # по usage известен факт списания, даже если пригодного текста нет
        answered = (result.usage is not None
                    and (result.usage.input_tokens is not None or result.usage.output_tokens is not None))
        return {'ok': False, 'text': '', 'usage': result.usage, 'usage_raw': usage_dict(result.usage),
                'error_kind': result.error_kind, 'charged_possible': bool(result.charged_possible),
                'provider_request_id': result.provider_request_id, 'status_code': 502,
                'detail': 'Провайдер не вернул пригодный ответ: ' + str(result.error_kind),
                'answered': answered}
    return {'ok': True, 'text': result.text, 'usage': result.usage, 'usage_raw': usage_dict(result.usage),
            'error_kind': None, 'charged_possible': False, 'provider_request_id': result.provider_request_id,
            'status_code': 200, 'detail': None, 'answered': True}


def _detail_text(detail, fallback):
    """Текст ошибки провайдера для ответа: строкой или из тела ответа."""
    if isinstance(detail, str) and detail.strip():
        return detail
    if isinstance(detail, dict) and isinstance(detail.get('message'), str):
        return detail['message']
    return fallback


def _insert_call(db, values):
    """Вставка записи журнала по именованным колонкам: новая колонка больше не ломает вставку."""
    columns = ','.join(INSERT_COLUMNS)
    marks = ','.join('?' * len(INSERT_COLUMNS))
    db.execute('INSERT INTO llm_calls(' + columns + ') VALUES(' + marks + ')', values)


def _finish_call(db, row_id, values):
    """Обновление записи журнала после вызова."""
    db.execute('UPDATE llm_calls SET status=?,usd=?,actual_cost_usd=?,actual_status=?,billing_source=?,'
               'input_tokens=?,output_tokens=?,cached_input_tokens=?,reasoning_tokens=?,'
               'reference_provider=?,reference_model=?,reference_kind=?,reference_rate_snapshot_id=?,'
               'reference_cost_usd=?,reference_cost_status=?,error_kind=?,provider_request_id=?,'
               'reserved_usd=? WHERE id=?', values)


def register(app, studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            ensure_schema(db)

    @app.post('/api/llm/estimate')
    def estimate(body: Estimate):
        from backend import security
        studio.project(body.project_id)
        messages = clean_messages(body.messages)
        registry = current_registry()
        mode = 'auto' if str(body.route_mode or 'manual').lower() == 'auto' else 'manual'
        chain = plan_routes(registry, body, mode, bool(body.allow_free))
        if not chain:
            raise HTTPException(400, 'Эта модель недоступна для платного вызова: нет проверенной цены (разрешены Luna, Terra, Sol)')
        estimates = [route_estimate(registry, route, messages, body.max_tokens) for route in chain]
        cost = max(float(item.cost_usd or 0.0) for item in estimates)
        if body.max_cost_usd is not None and body.max_cost_usd + 1e-9 < cost:
            raise HTTPException(400, 'Лимит стоимости ниже оценки запроса')
        payload = payload_of(body.model, messages, body.max_tokens, tools=body.tools, settings=body.settings)
        extra = extra_of(chain, cost, body.tools)
        token = security.quote(body.project_id, payload, cost, extra)
        reference = reference_of(registry, chain[0], estimated_usage(messages, body.max_tokens))
        primary = chain[0]
        return {'estimated_usd': cost, 'quote_token': token, 'max_tokens': body.max_tokens, 'model': body.model,
                'reference': reference,
                'execution': {'provider': primary.provider, 'model': primary.model,
                              'status': 'free' if _route_is_free(registry, primary) else 'paid'},
                'actual': {'cost_usd': None, 'status': 'estimated', 'max_cost_usd': cost},
                'route_chain': [{'provider': route.provider, 'model': route.model,
                                 'free': _route_is_free(registry, route)} for route in chain]}


async def guarded_chat(studio, body, key=None):
    """Единственный путь платного LLM-вызова. Резерв в бюджете создаётся до обращения к провайдеру.

    Маршрут выбирает шлюз, резерв считается по тарифу маршрута-исполнителя, цепочка запасных маршрутов
    делает не больше одной платной попытки на запрос.
    """
    from backend import security
    if not body.project_id:
        raise HTTPException(400, 'Укажи проект для учёта расхода')
    studio.project(body.project_id)
    if not body.approved:
        raise HTTPException(400, 'Нужно подтверждение платного LLM-запроса')
    if not body.max_tokens or body.max_tokens > MAX_OUTPUT_TOKENS:
        raise HTTPException(400, f'max_tokens обязателен и не больше {MAX_OUTPUT_TOKENS}')
    messages = clean_messages(body.messages)
    registry = current_registry()
    mode = 'auto' if str(getattr(body, 'route_mode', 'manual') or 'manual').lower() == 'auto' else 'manual'
    allow_free = bool(getattr(body, 'allow_free', False))
    tools = list(getattr(body, 'tools', None) or [])
    settings = dict(getattr(body, 'settings', None) or {})
    chain = plan_routes(registry, body, mode, allow_free)
    if not chain:
        raise HTTPException(400, 'Эта модель недоступна для платного вызова: нет проверенной цены (разрешены Luna, Terra, Sol)')
    payload = payload_of(body.model, messages, body.max_tokens, tools=tools, settings=settings)
    estimates = [route_estimate(registry, route, messages, body.max_tokens) for route in chain]
    cost = max(float(item.cost_usd or 0.0) for item in estimates)
    extra = extra_of(chain, cost, tools)
    verify_token(security, body.quote_token or '', body.project_id, payload, cost, extra)
    if body.max_cost_usd is None or body.max_cost_usd + 1e-9 < cost:
        raise HTTPException(400, 'Лимит стоимости ниже оценки запроса')
    if is_legacy_route(chain[0]):
        if not key or not key.isascii() or any(c.isspace() for c in key):
            raise HTTPException(400, 'Введи корректный API-ключ PiAPI')
    request_id = body.request_id or uuid.uuid4().hex
    previous = None
    stop_error = None
    for index, (route, estimate) in enumerate(zip(chain, estimates)):
        reserve = float(estimate.cost_usd or 0.0)
        unknown_reserve = None
        if _route_is_free(registry, route) and quota_limited(registry, route):
            # бесплатная квота может перейти в платное: резерв под такое списание держит платный
            # маршрут. Платного маршрута нет — работа не принимается, иначе списание ушло бы мимо лимитов
            unknown_reserve = paid_reserve(registry, chain, estimates, index, messages, body.max_tokens)
            if unknown_reserve is None:
                raise HTTPException(400, 'Нет платного маршрута: резерв под возможное списание взять негде')
        # резерв под неподтверждённое списание: у платного маршрута — его собственный тариф,
        # у маршрута с нулевым тарифом под квотным ограничением — тариф платного маршрута
        held = unknown_reserve if unknown_reserve is not None else reserve
        row_id = uuid.uuid4().hex
        row_request_id = request_id if index == 0 else request_id + '-fallback' + str(index)
        reference = reference_of(registry, route, estimated_usage(messages, body.max_tokens))
        try:
            with studio.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if index == 0 and db.execute('SELECT 1 FROM llm_calls WHERE request_id=?', (request_id,)).fetchone():
                    raise HTTPException(409, 'Этот запрос уже отправлялся. Проверь результат, повтор платного вызова не выполняется автоматически.')
                check_budget(db, body.project_id, reserve)
                _insert_call(db, (row_id, row_request_id, body.project_id, body.model, 'reserved', reserve, reserve,
                                  None, None, studio.now(),
                                  route.provider, route.model, None, 'estimated', reserve, estimate.billing_source,
                                  reference['provider'], reference['model'], reference['kind'],
                                  reference['rate_snapshot_id'], reference['cost_usd'], reference['status'],
                                  None, None, snapshot_id(route.provider, route.model, route.as_of), mode,
                                  previous, None, None))
        except HTTPException as exc:
            if index == 0:
                raise
            stop_error = exc
            break  # лимита не хватило на запасной маршрут — цепочка останавливается
        previous = route.provider + '/' + route.model
        result = await call_provider(studio, route, messages, body.max_tokens, key, registry, allow_free)
        if result['ok']:
            usage = result['usage']
            actual = llm_gateway.actual_quote(registry_with_route(registry, route), route, usage)
            confirmed = reference_of(registry, route, usage)
            if actual.cost_usd is None:
                # провайдер не отдал расход токенов: факт неизвестен, резерв остаётся до сверки.
                # usd = оценка (тот же резерв): ноль под done читался бы как «успех за бесплатно».
                with studio.connect() as db:
                    _finish_call(db, row_id, ('done', reserve, None, 'unknown', 'route_tariff',
                                              usage.input_tokens, usage.output_tokens, usage.cached_input_tokens,
                                              usage.reasoning_tokens, confirmed['provider'], confirmed['model'],
                                              confirmed['kind'], confirmed['rate_snapshot_id'], confirmed['cost_usd'],
                                              confirmed['status'], None, result['provider_request_id'],
                                              reserve, row_id))
                return {'choices': [{'message': {'role': 'assistant', 'content': result['text']}}],
                        'usage': result['usage_raw'], 'provider': route.provider, 'model': body.model,
                        'cost_usd': None, 'estimated_usd': cost,
                        'reference': confirmed,
                        'execution': {'provider': route.provider, 'model': route.model, 'status': 'paid'},
                        'actual': {'cost_usd': None, 'status': 'unknown', 'max_cost_usd': cost}}
            with studio.connect() as db:
                _finish_call(db, row_id, ('done', actual.cost_usd, actual.cost_usd, actual.status, actual.billing_source,
                                          usage.input_tokens, usage.output_tokens, usage.cached_input_tokens,
                                          usage.reasoning_tokens, confirmed['provider'], confirmed['model'],
                                          confirmed['kind'], confirmed['rate_snapshot_id'], confirmed['cost_usd'],
                                          confirmed['status'], None, result['provider_request_id'],
                                          reserve, row_id))
            return {'choices': [{'message': {'role': 'assistant', 'content': result['text']}}],
                    'usage': result['usage_raw'], 'provider': route.provider, 'model': body.model,
                    'cost_usd': actual.cost_usd, 'estimated_usd': cost,
                    'reference': confirmed,
                    'execution': {'provider': route.provider, 'model': route.model,
                                  'status': 'free' if actual.status == 'free' else 'paid'},
                    'actual': {'cost_usd': actual.cost_usd, 'status': actual.status, 'max_cost_usd': cost}}
        usage = result.get('usage')
        usage_known = usage is not None and (usage.input_tokens is not None or usage.output_tokens is not None)
        actual = llm_gateway.actual_quote(registry_with_route(registry, route), route, usage) if usage_known else None
        if result.get('answered') and actual is not None and actual.cost_usd is not None:
            # провайдер ответил и тарифицировал: факт известен по usage, резерв освобождается
            confirmed = reference_of(registry, route, usage)
            if _route_is_free(registry, route) and charge_possible(registry, route, bool(result['charged_possible'])):
                # маршрут с нулевым тарифом, но списание возможно: бесплатная квота могла перейти
                # в платное — факта нет, сумму неизвестного сведения держит платный маршрут
                with studio.connect() as db:
                    _finish_call(db, row_id, ('done', held, None, 'unknown', 'route_tariff',
                                              usage.input_tokens, usage.output_tokens, usage.cached_input_tokens,
                                              usage.reasoning_tokens, confirmed['provider'], confirmed['model'],
                                              confirmed['kind'], confirmed['rate_snapshot_id'], confirmed['cost_usd'],
                                              confirmed['status'], result['error_kind'], result['provider_request_id'],
                                              held, row_id))
            else:
                with studio.connect() as db:
                    _finish_call(db, row_id, ('done', actual.cost_usd, actual.cost_usd, actual.status, actual.billing_source,
                                              usage.input_tokens, usage.output_tokens, usage.cached_input_tokens,
                                              usage.reasoning_tokens, confirmed['provider'], confirmed['model'],
                                              confirmed['kind'], confirmed['rate_snapshot_id'], confirmed['cost_usd'],
                                              confirmed['status'], result['error_kind'], result['provider_request_id'],
                                              reserve, row_id))
            raise HTTPException(result['status_code'] or 502,
                                _detail_text(result['detail'], 'Провайдер не вернул пригодный ответ'))
        if result.get('answered'):
            # провайдер ответил, но расход получить нельзя: вызов закрыт, в usd — оценка, резерв удерживается
            if _route_is_free(registry, route) and not charge_possible(registry, route, bool(result['charged_possible'])):
                # маршрут с нулевым тарифом и списать негде: подтверждённый ноль, а не неизвестное списание
                with studio.connect() as db:
                    _finish_call(db, row_id, ('done', 0.0, 0.0, 'free', 'free_quota',
                                              None, None, None, None,
                                              reference['provider'], reference['model'], reference['kind'],
                                              reference['rate_snapshot_id'], reference['cost_usd'],
                                              reference['status'], result['error_kind'], result['provider_request_id'],
                                              reserve, row_id))
            else:
                with studio.connect() as db:
                    _finish_call(db, row_id, ('done', held, None, 'unknown', 'route_tariff',
                                              None, None, None, None,
                                              reference['provider'], reference['model'], reference['kind'],
                                              reference['rate_snapshot_id'], reference['cost_usd'],
                                              reference['status'], result['error_kind'], result['provider_request_id'],
                                              held, row_id))
            raise HTTPException(result['status_code'] or 502,
                                _detail_text(result['detail'], 'Провайдер не вернул пригодный ответ'))
        charged = charge_possible(registry, route, bool(result['charged_possible']))
        actual_status = 'unknown' if charged else 'not_charged'
        with studio.connect() as db:
            _finish_call(db, row_id, ('failed', 0.0, None if charged else 0.0, actual_status,
                                      'provider_usage' if charged else 'route_tariff',
                                      None, None, None, None,
                                      reference['provider'], reference['model'], reference['kind'],
                                      reference['rate_snapshot_id'], reference['cost_usd'], reference['status'],
                                      result['error_kind'], result['provider_request_id'], held, row_id))
        if charged:
            # исход неопределён: платная попытка не повторяется, резерв удерживается до сверки
            raise HTTPException(result['status_code'] or 502,
                                _detail_text(result['detail'], 'Провайдер не вернул ответ') +
                                ' Списание не подтверждено: резерв удерживается до сверки.')
        if index + 1 >= len(chain):
            raise HTTPException(result['status_code'] or 502,
                                _detail_text(result['detail'], 'Провайдер отклонил запрос'))
        # списания точно не было: резерв снят, цепочка запасных маршрутов продолжается
    if stop_error is not None:
        raise stop_error
    raise HTTPException(502, 'Маршрут не выполнил вызов')
