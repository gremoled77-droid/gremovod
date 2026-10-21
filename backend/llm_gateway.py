"""Ядро LLM-шлюза: реестр маршрутов и тарифов, тарифный ориентир, фактическое списание.

Модуль не ходит в сеть и ничего не пишет в базу — только расчёт и выбор маршрута.
Тарифы хранятся в USD за 1 000 000 входных или выходных токенов (единица проекта не меняется).

Два независимых числа для одного вызова:
- тарифный ориентир — сколько вызов стоил бы по тарифу Kie.ai/PiAPI, даже если выполнил его
  бесплатный маршрут (сравнительная оценка, не деньги);
- фактическое списание — сколько реально списано по тарифу провайдера-исполнителя.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from backend import network_guard

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / 'config'
REAL_CONFIG_PATH = CONFIG_DIR / 'llm_gateway.prices.json'
EXAMPLE_CONFIG_PATH = CONFIG_DIR / 'llm_gateway.prices.example.json'
TEST_MODE_ENV = network_guard.TEST_MODE_ENV

PROVIDER_TITLES = {'kie': 'Kie.ai', 'piapi': 'PiAPI', 'minimax': 'MiniMax', 'deepseek': 'DeepSeek',
                   'openrouter': 'OpenRouter'}
REFERENCE_PROVIDERS_DEFAULT = ('kie', 'piapi')
PRECISION_DEFAULT = 6
TOKENS_PER_UNIT = 1_000_000


@dataclass(frozen=True)
class Capabilities:
    """Что умеет маршрут: tools, streaming, reasoning."""
    tools: bool = False
    streaming: bool = False
    reasoning: bool = False


@dataclass(frozen=True)
class Rate:
    """Тариф одной модели: USD за 1 млн входных/выходных токенов."""
    provider: str
    model: str
    input_per_mtok: float | None
    output_per_mtok: float | None
    source: str
    as_of: str
    protocol: str
    enabled: bool
    verified_at: str | None
    quota_limited: bool
    promotion: bool
    cached_input_per_mtok: float | None = None
    max_input_tokens: int | None = None


@dataclass(frozen=True)
class Route:
    """Маршрут исполнения: провайдер, upstream-модель, протокол, роль, признаки платности."""
    provider: str
    model: str
    model_id: str
    protocol: str
    role: str
    base_url: str
    free: bool
    opt_in: bool
    enabled: bool = True
    verified_at: str | None = None
    capabilities: Capabilities = Capabilities()
    max_input_tokens: int | None = None
    cached_input_per_mtok: float | None = None
    rate_limit: str | None = None
    upstream_version: str | None = None
    path_prefix: str = ''
    source: str = ''
    as_of: str = ''


@dataclass(frozen=True)
class Usage:
    """Расход токенов по ответу провайдера."""
    input_tokens: int | None
    output_tokens: int | None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    estimated: bool = False


@dataclass(frozen=True)
class ReferenceQuote:
    """Тарифный ориентир: стоимость по тарифу Kie/PiAPI для карточки вызова."""
    provider: str | None
    model: str | None
    kind: str
    cost_usd: float | None
    status: str
    rate_source: str | None
    rate_as_of: str | None
    rate_verified: bool
    label: str


@dataclass(frozen=True)
class ActualQuote:
    """Фактическое списание: единственное число, которому место в бюджете."""
    cost_usd: float | None
    status: str
    provider: str
    model: str
    billing_source: str


@dataclass(frozen=True)
class ModelEntry:
    """Полная запись реестра: маршрут и его тариф."""
    provider: str
    model: str
    model_id: str
    protocol: str
    role: str
    base_url: str
    input_per_mtok: float | None
    output_per_mtok: float | None
    cached_input_per_mtok: float | None
    source: str
    as_of: str
    enabled: bool
    verified_at: str | None
    quota_limited: bool
    promotion: bool
    free: bool
    opt_in: bool
    requires_dynamic_tier_check: bool
    capabilities: Capabilities
    max_input_tokens: int | None
    rate_limit: str | None
    upstream_version: str | None
    path_prefix: str = ''

    def rate(self) -> Rate:
        return Rate(provider=self.provider, model=self.model, input_per_mtok=self.input_per_mtok,
                    output_per_mtok=self.output_per_mtok, source=self.source, as_of=self.as_of,
                    protocol=self.protocol, enabled=self.enabled, verified_at=self.verified_at,
                    quota_limited=self.quota_limited, promotion=self.promotion,
                    cached_input_per_mtok=self.cached_input_per_mtok, max_input_tokens=self.max_input_tokens)

    def route(self) -> Route:
        return Route(provider=self.provider, model=self.model, model_id=self.model_id, protocol=self.protocol,
                     role=self.role, base_url=self.base_url, free=self.free, opt_in=self.opt_in,
                     enabled=self.enabled, verified_at=self.verified_at, capabilities=self.capabilities,
                     max_input_tokens=self.max_input_tokens, cached_input_per_mtok=self.cached_input_per_mtok,
                     rate_limit=self.rate_limit, upstream_version=self.upstream_version,
                     source=self.source, as_of=self.as_of, path_prefix=self.path_prefix)


@dataclass(frozen=True)
class Registry:
    """Реестр шлюза: маршруты, тарифы и правила показа стоимости."""
    schema_version: int
    as_of: str
    currency: str
    unit: str
    status: str
    entries: tuple[ModelEntry, ...]
    comparison: dict = field(default_factory=dict)
    sample_limits: dict = field(default_factory=dict)
    source_path: str = ''

    @property
    def rates(self) -> tuple[Rate, ...]:
        return tuple(entry.rate() for entry in self.entries)

    @property
    def routes(self) -> tuple[Route, ...]:
        return tuple(entry.route() for entry in self.entries)

    def entry(self, provider: str | None, model: str | None) -> ModelEntry | None:
        if not model:
            return None
        for entry in self.entries:
            if provider and entry.provider != str(provider).strip().lower():
                continue
            if _norm(entry.model) != _norm(model) and _norm(entry.model_id) != _norm(model):
                continue
            return entry
        return None

    def rate(self, provider: str | None, model: str | None) -> Rate | None:
        entry = self.entry(provider, model)
        return entry.rate() if entry is not None else None

    def route(self, provider: str | None, model: str | None) -> Route | None:
        entry = self.entry(provider, model)
        return entry.route() if entry is not None else None

    def entries_for_role(self, role: str | None) -> tuple[ModelEntry, ...]:
        key = _norm(role)
        return tuple(entry for entry in self.entries if _norm(entry.role) == key)

    def find_by_model(self, model: str | None) -> tuple[ModelEntry, ...]:
        key = _norm(model)
        if not key:
            return ()
        found = tuple(entry for entry in self.entries
                      if key in (_norm(entry.model), _norm(entry.model_id)))
        if found:
            return found
        if '/' in str(model):
            provider, _, rest = str(model).partition('/')
            rest_key = _norm(rest)
            found = tuple(entry for entry in self.entries
                          if entry.provider == provider.strip().lower()
                          and rest_key in (_norm(entry.model), _norm(entry.model_id)))
            if found:
                return found
        return ()

    @property
    def reference_providers(self) -> tuple[str, ...]:
        allow = self.comparison.get('reference_provider_allowlist') or REFERENCE_PROVIDERS_DEFAULT
        return tuple(str(provider) for provider in allow)

    @property
    def precision(self) -> int:
        try:
            return int(self.comparison.get('small_amount_precision') or PRECISION_DEFAULT)
        except (TypeError, ValueError):
            return PRECISION_DEFAULT

    def baseline(self, name: str = 'default_baseline') -> ModelEntry | None:
        spec = self.comparison.get(name) or {}
        return self.entry(spec.get('provider'), spec.get('model'))


def _norm(value) -> str:
    """Ключ сравнения моделей: регистр, пробелы и подчёркивания не важны."""
    if value is None:
        return ''
    text = str(value).strip().lower().replace('_', '-').replace(' ', '-')
    while '--' in text:
        text = text.replace('--', '-')
    return text


def _price(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value) -> str | None:
    return None if value is None else str(value)


def _entry_from(raw: dict, default_as_of: str) -> ModelEntry:
    caps = raw.get('capabilities') or {}
    return ModelEntry(
        provider=str(raw.get('provider') or '').strip().lower(),
        model=str(raw.get('model') or ''),
        model_id=str(raw.get('model_id') or raw.get('model') or ''),
        protocol=str(raw.get('protocol') or ''),
        role=str(raw.get('role') or ''),
        base_url=str(raw.get('base_url') or ''),
        input_per_mtok=_price(raw.get('input')),
        output_per_mtok=_price(raw.get('output')),
        cached_input_per_mtok=_price(raw.get('cached_input_per_mtok')),
        source=str(raw.get('source') or ''),
        as_of=str(raw.get('as_of') or default_as_of or ''),
        enabled=bool(raw.get('enabled', False)),
        verified_at=_optional_str(raw.get('verified_at')),
        quota_limited=bool(raw.get('quota_limited', False)),
        promotion=bool(raw.get('promotion', False)),
        free=bool(raw.get('free', False)),
        opt_in=bool(raw.get('opt_in', False)),
        requires_dynamic_tier_check=bool(raw.get('requires_dynamic_tier_check', False)),
        capabilities=Capabilities(tools=bool(caps.get('tools', False)),
                                  streaming=bool(caps.get('streaming', False)),
                                  reasoning=bool(caps.get('reasoning', False))),
        max_input_tokens=(int(raw['max_input_tokens']) if raw.get('max_input_tokens') is not None else None),
        rate_limit=_optional_str(raw.get('rate_limit')),
        upstream_version=_optional_str(raw.get('upstream_version')),
        path_prefix=str(raw.get('path_prefix') or ''),
    )


def _registry_from(data: dict, source: str) -> Registry:
    entries = tuple(_entry_from(raw, data.get('as_of') or '') for raw in (data.get('rates') or []))
    return Registry(schema_version=int(data.get('schema_version') or 1),
                    as_of=str(data.get('as_of') or ''),
                    currency=str(data.get('currency') or 'USD'),
                    unit=str(data.get('unit') or ''),
                    status=str(data.get('status') or ''),
                    entries=entries,
                    comparison=dict(data.get('comparison_display') or {}),
                    sample_limits=dict(data.get('sample_limits_only') or {}),
                    source_path=source)


def test_mode() -> bool:
    """Процесс тестов: рабочий реестр владельца не подхватывается, внешняя сеть закрыта.

    В студии режим тестов не включается: её реестр — рабочий файл владельца, маршруты в нём
    включает сам владелец, а сеть шлюзу нужна.
    """
    return network_guard.test_mode()


# Защита сети ставится один раз в процессе тестов — и под pytest, и под unittest discover.
network_guard.install_if_test_mode()


def load_registry(path: str | None = None) -> Registry:
    """Читает реестр из файла конфигурации. Файла нет — берётся приложенный пример (все маршруты выключены).

    В процессе тестов рабочий файл владельца не подхватывается: реестр тестов задаётся явно —
    приложенным примером (все маршруты выключены) или файлом, который задаёт сам тест.
    """
    if path:
        candidate = Path(path)
    elif test_mode():
        candidate = EXAMPLE_CONFIG_PATH
    else:
        candidate = REAL_CONFIG_PATH
    source = candidate if candidate.exists() else EXAMPLE_CONFIG_PATH
    data = json.loads(source.read_text(encoding='utf-8'))
    return _registry_from(data, str(source))


def _has_tariff(entry: ModelEntry) -> bool:
    """Тариф пригоден для расчёта: заполнены обе цены."""
    return entry.input_per_mtok is not None and entry.output_per_mtok is not None


def _cost_of(entry: ModelEntry, usage: Usage | None, precision: int) -> float | None:
    """Сумма по тарифу записи реестра. Нет тарифа или usage — сумма неизвестна, ноль не подставляется."""
    if usage is None:
        return None
    tokens_in, tokens_out = usage.input_tokens, usage.output_tokens
    if tokens_in is None or tokens_out is None:
        return None
    if not _has_tariff(entry):
        return None
    cached = max(0, min(usage.cached_input_tokens or 0, tokens_in))
    billable_in = tokens_in - cached
    cached_price = entry.cached_input_per_mtok if entry.cached_input_per_mtok is not None else entry.input_per_mtok
    # токены размышления входят в output_tokens провайдера — отдельно не начисляем
    total = billable_in * entry.input_per_mtok + cached * cached_price + tokens_out * entry.output_per_mtok
    return round(total / TOKENS_PER_UNIT, precision)


def _exact_reference_candidates(registry: Registry, route: Route) -> tuple[ModelEntry, ...]:
    """Записи «та же модель» у провайдеров из списка ориентиров (kie, piapi)."""
    keys = {_norm(route.model), _norm(route.model_id)} - {''}
    found: list[ModelEntry] = []
    for provider in registry.reference_providers:
        for entry in registry.entries:
            if entry.provider != provider:
                continue
            if keys & {_norm(entry.model), _norm(entry.model_id)}:
                found.append(entry)
    return tuple(found)


def _reference_label(entry: ModelEntry, kind: str, cost: float | None, status: str, verified: bool) -> str:
    """Готовая строка для карточки вызова: тариф, дата источника, сумма."""
    title = PROVIDER_TITLES.get(entry.provider, entry.provider)
    amount = f'${cost:.{6}f}' if cost is not None else 'сумма не рассчитана'
    if status != 'confirmed':
        amount = '≈ ' + amount
    if verified:
        note = f'тариф от {entry.as_of}' if entry.as_of else 'тариф подтверждён'
    else:
        note = f'тариф от {entry.as_of}, не подтверждён вживую' if entry.as_of else 'тариф не подтверждён вживую'
    if kind == 'exact_model':
        return f'По тарифу {title} — {entry.model} ({note}): {amount}'
    return (f'Ценовой ориентир {title} {entry.model} '
            f'(другая модель, сравнение по объёму токенов; {note}): {amount}')


def _reference_entry(registry: Registry, route: Route) -> tuple[ModelEntry | None, str]:
    """Выбор тарифа-ориентира по приоритету конфигурации: берётся первый кандидат с заполненным тарифом.

    1. Кандидаты «та же модель» — записи провайдеров из списка ориентиров (kie, piapi) с совпадающей
       моделью. Есть такая запись с заполненным тарифом — она и есть ориентир, kind='exact_model'.
       Такие записи есть, но тариф не заполнен ни у одной — 'unavailable': цену ДРУГОЙ модели для этой
       же модели подставлять нельзя, это выдало бы один тариф за другой.
    2. Записей «та же модель» нет вовсе — обход базовых линий конфигурации: сначала default_baseline,
       затем alternative_baseline. Берётся первая с заполненным тарифом, kind='reference_model'.
       Заполненного тарифа нет ни у одной — 'unavailable' без числа.
    """
    exact = _exact_reference_candidates(registry, route)
    if exact:
        for entry in exact:
            if _has_tariff(entry):
                return entry, 'exact_model'
        return exact[0], 'unavailable'
    for name in ('default_baseline', 'alternative_baseline'):
        baseline = registry.baseline(name)
        if baseline is not None and _has_tariff(baseline):
            return baseline, 'reference_model'
    return None, 'unavailable'


def reference_quote(registry: Registry, route: Route, usage: Usage | None = None) -> ReferenceQuote:
    """Тарифный ориентир: сколько вызов стоил бы по тарифу Kie.ai/PiAPI, даже если выполнил его бесплатный маршрут.

    Тарифа нет или он не заполнен — результат «Тариф не подтверждён» без числа; ноль не подставляется никогда.
    """
    entry, kind = _reference_entry(registry, route)
    if entry is None or kind == 'unavailable':
        return ReferenceQuote(provider=(entry.provider if entry is not None else None),
                              model=(entry.model if entry is not None else None),
                              kind='unavailable', cost_usd=None, status='unavailable',
                              rate_source=((entry.source or None) if entry is not None else None),
                              rate_as_of=((entry.as_of or None) if entry is not None else None),
                              rate_verified=False, label='Тариф не подтверждён')
    cost = _cost_of(entry, usage, registry.precision)
    confirmed = usage is not None and not usage.estimated and cost is not None
    status = 'confirmed' if confirmed else 'estimated'
    verified = bool(entry.verified_at)
    return ReferenceQuote(provider=entry.provider, model=entry.model, kind=kind, cost_usd=cost,
                          status=status, rate_source=entry.source or None, rate_as_of=entry.as_of or None,
                          rate_verified=verified, label=_reference_label(entry, kind, cost, status, verified))


def is_free_entry(entry: ModelEntry | None) -> bool:
    """Маршрут подтверждённо бесплатный: флаг free или тариф 0/0.

    Нулевой тариф — это тариф, а не его отсутствие: запись есть и цены известны,
    просто платить не нужно. Отсутствие записи или null-цены — это уже отсутствие тарифа.
    """
    return bool(entry is not None
                and (entry.free or (entry.input_per_mtok == 0 and entry.output_per_mtok == 0)))


def actual_quote(registry: Registry, route: Route, usage: Usage | None = None, *,
                 charge_possible: bool = True) -> ActualQuote:
    """Фактическое списание: строго по тарифу провайдера-исполнителя.

    Ноль бывает только у подтверждённо бесплатного маршрута. У платного маршрута без usage
    списание неизвестно (cost_usd=None, status='unknown') — подтверждённых $0.00 не бывает.
    Ноль у платного маршрута возможен, только если usage есть и сам даёт ноль биллябельных токенов.

    charge_possible на расчёт не влияет. Это флаг для журнала: «точно не списано» — резерв
    освобождается; «возможно списано» — резерв остаётся и попадает в «неизвестные списания /
    нужна сверка».
    """
    entry = registry.entry(route.provider, route.model)
    if route.free or is_free_entry(entry):
        return ActualQuote(cost_usd=0.0, status='free', provider=route.provider, model=route.model,
                           billing_source='free_quota')
    if entry is None or entry.input_per_mtok is None or entry.output_per_mtok is None:
        return ActualQuote(cost_usd=None, status='unknown', provider=route.provider, model=route.model,
                           billing_source='route_tariff')
    cost = _cost_of(entry, usage, registry.precision)
    if cost is None:
        # usage нет: списание неизвестно, подтверждённого нуля у платного маршрута не бывает
        return ActualQuote(cost_usd=None, status='unknown', provider=route.provider, model=route.model,
                           billing_source='route_tariff')
    status = 'estimated' if (usage is not None and usage.estimated) else 'confirmed'
    return ActualQuote(cost_usd=cost, status=status, provider=route.provider, model=route.model,
                       billing_source='provider_usage')


def _has_tariff(entry: ModelEntry | None) -> bool:
    """Тариф есть: цены заполнены. Ноль (0/0) — тоже тариф, отсутствие записи — не тариф."""
    return entry is not None and entry.input_per_mtok is not None and entry.output_per_mtok is not None


def _has_paid_tariff(entry: ModelEntry | None) -> bool:
    """Тариф платный: цены заполнены и не нулевые.

    Нулевой тариф (0/0) — тоже тариф, но резерв он не держит: подтверждённо бесплатный маршрут
    не может прикрыть неподтверждённое списание.
    """
    return bool(entry is not None and entry.input_per_mtok is not None and entry.output_per_mtok is not None
                and (entry.input_per_mtok > 0 or entry.output_per_mtok > 0))


def _agent_reserve_entry(registry: Registry, provider: str | None, model: str | None) -> ModelEntry | None:
    """Запись реестра, по тарифу которой держится резерв работы агента.

    Порядок: названная модель → базовая линия владельца → любой платный маршрут с тарифом.
    Названная модель прикрывает сама себя: её тариф — это и есть её списание, а у маршрута 0/0
    списание подтверждённо нулевое. Для остальных случаев источник резерва — только платный
    маршрут: резерв прикрывает неподтверждённое списание, а нулевой тариф денег под это не даёт.
    Платного тарифа нет — работа агента не ставится, иначе списание ушло бы мимо лимитов.
    """
    entry = registry.entry(provider, model)
    if _has_tariff(entry):
        return entry
    baseline = registry.baseline('default_baseline')
    if _has_paid_tariff(baseline):
        return baseline
    for item in registry.entries:
        if _has_paid_tariff(item):
            return item
    return None


def paid_reserve_entry(registry: Registry, provider: str | None = None, model: str | None = None) -> ModelEntry | None:
    """Запись платного маршрута, по тарифу которой держится резерв под неподтверждённое списание.

    Только платный тариф: нулевой тариф (0/0) деньгами резерв не прикрывает — подтверждённо
    бесплатный маршрут не может держать деньги под возможное списание. Порядок тот же, что в
    агентском пути: названная модель → базовая линия владельца → любой платный маршрут с тарифом.
    Платного маршрута нет — резерв взять негде, работа не принимается.
    """
    entry = registry.entry(provider, model)
    if _has_paid_tariff(entry):
        return entry
    baseline = registry.baseline('default_baseline')
    if _has_paid_tariff(baseline):
        return baseline
    for item in registry.entries:
        if _has_paid_tariff(item):
            return item
    return None


def agent_has_tariff(registry: Registry, provider: str | None, model: str | None) -> bool:
    """Есть ли в реестре тариф, по которому работа агента посчитана и придержана.

    Резерв работы агента прикрывает неподтверждённое списание, поэтому источник резерва —
    платный маршрут с тарифом: нулевой тариф (0/0) денег под это не даёт. Такого маршрута нет —
    работа агента не ставится (400), иначе неизвестное списание ушло бы мимо лимитов.
    """
    return _agent_reserve_entry(registry, provider, model) is not None


def agent_quote(registry: Registry, provider: str | None, model: str | None,
                 usage: Usage | None = None) -> ActualQuote:
    """Фактическое списание вызова агента: по тарифу реестра для названного провайдера и модели.

    Агент назвал расход — сумма подтверждена его usage. Не назвал — списание неизвестно
    (cost_usd=None, status='unknown'), а не ноль: работа агента стоила денег, но сколько — неизвестно.
    """
    entry = registry.entry(provider, model)
    if entry is None:
        return ActualQuote(cost_usd=None, status='unknown', provider=provider or 'unknown',
                           model=model or 'unknown', billing_source='route_tariff')
    return actual_quote(registry, entry.route(), usage)


def agent_reference(registry: Registry, provider: str | None, model: str | None,
                    usage: Usage | None = None) -> ReferenceQuote | None:
    """Неденежный ориентир вызова агента по Kie/PiAPI; модели агента в реестре нет — ориентира нет."""
    entry = registry.entry(provider, model)
    if entry is None:
        return None
    return reference_quote(registry, entry.route(), usage)


def agent_estimate_usage(context_text: str, prompt_text: str) -> Usage:
    """Оценка расхода токенов вызова агента: вход — объём контекста, выход — объём ответа."""
    return Usage(input_tokens=max(1, len(context_text or '') // 2) + 20,
                 output_tokens=max(1, len(prompt_text or '') // 2) + 20, estimated=True)


def agent_reserve(registry: Registry, provider: str | None, model: str | None, usage: Usage) -> float:
    """Сумма под риском вызова агента: оценка по тарифу маршрута.

    Модели агента в реестре нет — за оценку берётся базовая линия владельца: иначе неизвестное
    списание не попало бы ни в один итог и прошло бы мимо лимитов. Источник резерва — платный
    маршрут с тарифом: нулевой тариф (0/0) не прикрывает неподтверждённое списание.
    """
    entry = _agent_reserve_entry(registry, provider, model)
    if entry is None:
        return 0.0
    quote = actual_quote(registry, entry.route(), usage)
    return float(quote.cost_usd or 0.0) if quote is not None else 0.0


def _eligible(entry: ModelEntry, allow_free: bool) -> bool:
    """Маршрут можно взять: включён владельцем, тариф известен, бесплатный — только по разрешению."""
    if not entry.enabled:
        return False
    if entry.free or entry.opt_in:
        return bool(allow_free)
    return entry.input_per_mtok is not None and entry.output_per_mtok is not None


def select_route(registry: Registry, task: str, mode: str, *, allow_free: bool = False) -> Route | None:
    """Выбор маршрута: в ручном режиме — запрошенный, в автоматическом — по роли задачи."""
    if mode == 'manual':
        candidates = registry.find_by_model(task)
    elif mode == 'auto':
        candidates = registry.entries_for_role(task)
    else:
        return None
    for entry in candidates:
        if _eligible(entry, allow_free):
            return entry.route()
    return None


def _cell(row, index: dict, name: str, default=None):
    position = index.get(name)
    if position is None:
        return default
    value = row[position]
    return default if value is None else value


def summarize_spend(db, project_ids: list[str] | None = None) -> dict:
    """Сводка расходов по журналу llm_calls: факт, резерв, неизвестные списания и неденежный ориентир.

    Ориентир по Kie/PiAPI в фактические расходы не входит и денег не представляет.
    """
    summary = {'actual_cost_usd': 0.0, 'reserved_usd': 0.0, 'unknown_cost_usd': 0.0,
               'reference_cost_usd': 0.0, 'calls': 0}
    try:
        columns = {str(row[1]) for row in db.execute('PRAGMA table_info(llm_calls)')}
    except Exception:
        return summary
    if not columns:
        return summary
    wanted = ('project_id', 'status', 'usd', 'actual_cost_usd', 'actual_status', 'reserved_usd',
              'reference_cost_usd')
    have = [name for name in wanted if name in columns]
    if 'project_id' not in have:
        return summary
    try:
        rows = db.execute('SELECT ' + ','.join(have) + ' FROM llm_calls').fetchall()
    except Exception:
        return summary
    index = {name: position for position, name in enumerate(have)}
    wanted_projects = None if project_ids is None else set(project_ids)
    for row in rows:
        if wanted_projects is not None and _cell(row, index, 'project_id') not in wanted_projects:
            continue
        summary['calls'] += 1
        status = _cell(row, index, 'status', '')
        actual_status = _cell(row, index, 'actual_status')
        actual = _cell(row, index, 'actual_cost_usd')
        reserved = _cell(row, index, 'reserved_usd')
        reference = _cell(row, index, 'reference_cost_usd')
        legacy = float(_cell(row, index, 'usd', 0.0) or 0.0)
        if reference is not None:
            summary['reference_cost_usd'] += float(reference)
        if actual_status in ('confirmed', 'free'):
            summary['actual_cost_usd'] += float(actual if actual is not None else 0.0)
        elif actual_status == 'estimated':
            # резерв в полёте: деньги заняты, но списания ещё нет — это зарезервировано
            summary['reserved_usd'] += float(reserved if reserved is not None else legacy)
        elif actual_status == 'unknown':
            # списание возможно, но не подтверждено: резерв удерживается до сверки
            summary['unknown_cost_usd'] += float(reserved if reserved is not None else legacy)
        elif actual_status == 'not_charged':
            # провайдер прямо отказал: списания не было, резерв снят
            pass
        elif status == 'done':
            # строка старой схемы: факт списания лежит в usd
            summary['actual_cost_usd'] += legacy
        elif status == 'reserved':
            summary['reserved_usd'] += float(reserved if reserved is not None else legacy)
    for key in ('actual_cost_usd', 'reserved_usd', 'unknown_cost_usd', 'reference_cost_usd'):
        summary[key] = round(summary[key], 6)
    return summary
