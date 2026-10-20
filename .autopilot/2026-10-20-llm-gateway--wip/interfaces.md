# Границы, решённые в спецификации

Каждый модуль: что **владеет**, что **отдаёт наружу** (имена и формы, не реализация), что **прячет**. Имена — на английском, как в коде.

## 1. `backend/llm_gateway.py` — ядро шлюза (новый)

**Владеет:** загрузкой реестра, расчётом тарифного ориентира, расчётом фактической стоимости, выбором маршрута по роли и режиму, формой записи в журнал `llm_calls`, сводкой расходов для бюджета.

**Отдаёт наружу:**

```python
@dataclass(frozen=True)
class Rate:
    provider: str            # 'kie' | 'piapi' | 'minimax' | 'deepseek' | 'openrouter'
    model: str               # id модели в реестре
    input_per_mtok: float | None    # USD за 1 000 000 входных токенов
    output_per_mtok: float | None   # USD за 1 000 000 выходных токенов
    source: str              # URL источника тарифа
    as_of: str               # дата тарифа, ISO
    protocol: str            # 'responses' | 'anthropic_messages' | 'openai_chat'
    enabled: bool
    verified_at: str | None
    quota_limited: bool
    promotion: bool

@dataclass(frozen=True)
class Route:
    provider: str
    model: str               # id в реестре
    model_id: str            # upstream model id
    protocol: str
    role: str                # 'simple' | 'editorial' | 'coding' | 'backup' | 'extra'
    base_url: str
    free: bool               # маршрут подтверждённо бесплатный
    opt_in: bool             # требует явного разрешения владельца

@dataclass(frozen=True)
class ReferenceQuote:
    provider: str | None     # 'kie' | 'piapi' | None
    model: str | None
    kind: str                # 'exact_model' | 'reference_model' | 'unavailable'
    cost_usd: float | None
    status: str              # 'estimated' | 'confirmed' | 'unavailable'
    rate_source: str | None
    rate_as_of: str | None
    rate_verified: bool
    label: str               # готовая строка для карточки

@dataclass(frozen=True)
class ActualQuote:
    cost_usd: float | None
    status: str              # 'confirmed' | 'free' | 'unknown' | 'estimated'
    provider: str
    model: str
    billing_source: str      # 'provider_usage' | 'route_tariff' | 'free_quota'

@dataclass(frozen=True)
class Usage:
    input_tokens: int | None
    output_tokens: int | None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    estimated: bool = False   # True — расход предвызовный (оценка), False — подтверждённый провайдером

@dataclass(frozen=True)
class Capabilities:
    tools: bool = False
    streaming: bool = False
    reasoning: bool = False

@dataclass(frozen=True)
class ModelEntry:
    provider: str
    model: str
    model_id: str
    input_per_mtok: float | None
    output_per_mtok: float | None
    cached_input_per_mtok: float | None
    source: str
    as_of: str
    protocol: str
    enabled: bool
    verified_at: str | None
    quota_limited: bool
    promotion: bool
    role: str
    free: bool
    opt_in: bool
    base_url: str
    capabilities: Capabilities

@dataclass(frozen=True)
class Registry:
    entries: list[ModelEntry]
    reference_providers: list[str]
    default_baseline: ModelEntry | None
    alternative_baseline: ModelEntry | None
    precision: int
    source: str            # путь к файлу конфигурации
    # + методы: entry(provider, model), baseline(name)

def load_registry(path: str | None = None) -> Registry
def reference_quote(registry: Registry, route: Route, usage: Usage | None = None) -> ReferenceQuote
def actual_quote(registry: Registry, route: Route, usage: Usage | None = None, *, charge_possible: bool = True) -> ActualQuote
def select_route(registry: Registry, task: str, mode: str, *, allow_free: bool = False) -> Route | None
def summarize_spend(db, project_ids: list[str]) -> dict   # actual_cost_usd / reserved_usd / unknown_cost_usd / reference_cost_usd / calls
```

**Поведение, зафиксированное таском 01:**

- `reference_quote` на записи реестра с **незаполненным тарифом** (`input`/`output` = null) не падает, а отдаёт `kind='unavailable'`, `cost_usd=None`, `status='unavailable'`, label «Тариф не подтверждён». Ноль не подставляется никогда.
- **Ветка `unavailable` заполняет `provider`, `model`, `rate_source`, `rate_as_of` записью без тарифа.** Это НЕ значит «ориентир есть»: ориентир есть только при `kind` = `exact_model` или `reference_model`. Проверять наличие ориентира — по `kind`, а не по `provider is not None`.
- **Правило выбора тарифа-ориентира** — берётся **первый кандидат с заполненным тарифом**, в таком порядке:
  1. записи «та же модель» у провайдеров из списка ориентиров (`kie`, `piapi`) — если модель маршрута у них есть, берётся запись с тарифом, `kind='exact_model'`; если такие записи есть, но тариф не заполнен ни у одной — `unavailable`: цену другой модели для этой же модели подставлять нельзя;
  2. если записей «та же модель» нет вовсе — обход базовых линий конфигурации: `default_baseline`, затем `alternative_baseline`; берётся первая с заполненным тарифом, `kind='reference_model'`; если тариф не заполнен ни у одной — `unavailable` без числа.

  Альтернативная линия — именно запасная: у владельца в первом рабочем состоянии конфигурации подтверждён будет один тариф, а не два, и карточка обязана показать число по заполненной линии, а не «Тариф не подтверждён».
- `actual_quote` на том же входе отдаёт `status='unknown'`, `cost_usd=None`.
- Статусы `reference`: `exact_model` / `reference_model` / `unavailable`. Статусы `actual`: `confirmed` / `free` / `unknown` / `estimated`.
- `Usage.estimated=True` — расход предвызовный; `status` тогда `estimated`, а не `confirmed`.
- `allow_free=True` открывает и маршруты с `free`, и маршруты с `opt_in`.
- Старые записи журнала со статусом `failed` считаются как 0 — старая схема их уже обнуляла, восстановить факт нельзя.
- Цены в реестре — USD за 1 000 000 токенов, точность `small_amount_precision` (6).

**Файлы конфигурации реестра:**

- `config/llm_gateway.prices.json` — **реальный** конфиг владельца. В `.gitignore`, в Git не попадает. Если файла нет — шлюз читает пример.
- `config/llm_gateway.prices.example.json` — приложенный пример: все маршруты `enabled: false`, `verified_at: null`, тарифы minimax/deepseek/openrouter частично `null` (их заполняет владелец после живой проверки).

**Прячет:** разбор JSON конфигурации, выбор базовой линии ориентира, SQL по `llm_calls`, округление до 6 знаков.

## 2. `backend/llm_adapters.py` — HTTP-адаптеры (новый)

**Владеет:** протоколами обмена с провайдерами: `responses` (Kie GPT-6 Luna), `anthropic_messages` (Kie Claude Haiku 5.5), `openai_chat` (PiAPI, MiniMax, DeepSeek, OpenRouter). Сбором usage из ответа, распознаванием ошибок провайдера.

**Отдаёт наружу:**

```python
@dataclass(frozen=True)
class ProviderResult:
    ok: bool
    text: str
    usage: Usage
    error_kind: str | None   # 'timeout' | 'http_401' | 'http_403' | 'http_429' | 'http_5xx' | 'cloudflare_1010' | 'bad_body' | 'no_usage'
    charged_possible: bool   # True для timeout/429/5xx/1010 — списание могло произойти
    provider_request_id: str | None

async def complete(route: Route, messages: list[dict], max_tokens: int, *, client: httpx.AsyncClient | None = None) -> ProviderResult
```

**Прячет:** URL, заголовки, форму ответа каждого провайдера, разбор `usage`.

**Шов для тестов:** `client` — внедряемый `httpx.AsyncClient`. Все провайдеры закрываются `httpx.MockTransport`; ни один тест не ходит в сеть.

## 3. `backend/llm_guard.py` — существующий, меняется

**Владеет:** подписью оценки, резервированием бюджета, проверкой лимитов, эндпоинтами `/api/llm/estimate` и `/api/llm/chat`, записью строки `llm_calls`.

**Что меняется (границы, не реализация):**
- `estimate_usd` и `price_of` остаются **как есть** — существующие тесты не должны сломаться; новый расчёт живёт в `llm_gateway`.
- `guarded_chat` перестаёт быть привязан к `provider == 'piapi'`; маршрут выбирается через `llm_gateway.select_route`.
- Ответ `/api/llm/chat` **дополняется** новыми полями (старые `cost_usd`, `estimated_usd`, `usage`, `provider`, `model` остаются).
- Ответ `/api/llm/estimate` **дополняется** полями карточки (старые `estimated_usd`, `quote_token`, `max_tokens`, `model` остаются).

**Схема `llm_calls` — новая колонка добавляется только здесь.** Список и владелец:

| Колонка | Тип | Смысл |
|---|---|---|
| `execution_provider` | TEXT | кто выполнил |
| `execution_model` | TEXT | что выполнил |
| `actual_cost_usd` | REAL | подтверждённое фактическое списание |
| `actual_status` | TEXT | `confirmed` / `free` / `unknown` / `estimated` |
| `reserved_usd` | REAL | зарезервировано (не деньги, потолок) |
| `billing_source` | TEXT | откуда взята сумма |
| `reference_provider` | TEXT | `kie` / `piapi` |
| `reference_model` | TEXT | модель-ориентир |
| `reference_kind` | TEXT | `exact_model` / `reference_model` |
| `reference_rate_snapshot_id` | TEXT | снимок тарифа |
| `reference_cost_usd` | REAL | условная стоимость |
| `reference_cost_status` | TEXT | `estimated` / `confirmed` / `unavailable` |
| `cached_input_tokens` | INTEGER | кеш-токены |
| `reasoning_tokens` | INTEGER | токены размышления |
| `price_snapshot_id` | TEXT | версия тарифа исполнения |
| `route_mode` | TEXT | `manual` / `auto` |
| `fallback_from` | TEXT | предыдущий маршрут цепочки |
| `error_kind` | TEXT | классификация сбоя |
| `provider_request_id` | TEXT | id запроса у провайдера |

Колонка `usd` **сохраняет прежний смысл** (оценка при `reserved`, факт при `done`, 0 при `failed`) — обратная совместимость. Позиционный `INSERT INTO llm_calls VALUES(...)` **переводится на именованные колонки**.

**Прячет:** SQL резервирования, формирование подписи, проверку лимитов.

## 4. `backend/security.py` — подпись

**Меняется только `quote` и `verify_quote`:** необязательное поле `extra` в подписи.

```python
def quote(project_id: str, payload: dict, cost: float, extra: dict | None = None) -> str
def verify_quote(token: str, project_id: str, payload: dict, cost: float, extra: dict | None = None) -> tuple[bool, str]
```

Правило совместимости: токен **без** `extra` принимается как прежний (это старые подписи); токен **с** `extra` отклоняется при любом несовпадении `extra`. В `extra` для LLM входят: `provider`, `model`, `price_version`, `fallback`, `max_payment_usd`, `tools_hash`.

**Прячет:** устройство HMAC, формат конверта.

## 5. `backend/connections.py` — ключи

**Владеет:** списком провайдеров и чтением ключей. Расширяется записями `minimax`, `deepseek`, `openrouter` по образцу `piapi`/`kie`: env-переменная `MINIMAX_API_KEY` / `DEEPSEEK_API_KEY` / `OPENROUTER_API_KEY`, файл `*_API_KEY.txt` в корне репозитория, `configured` в `GET /api/connections`.

**Прячет:** DPAPI-расшифровку, приоритет источников. Значения ключей **не попадают** в ответы, логи и Git.

## 6. `backend/economics.py` и `backend/series_economics.py` — итоги

**Владеют:** агрегацией расходов. В `/api/economics` появляется блок LLM с четырьмя раздельными величинами: `actual_cost_usd`, `reserved_usd`, `unknown_cost_usd`, `reference_cost_usd` (явно помечен как неденежный). Имена совпадают с колонками `llm_calls`, чтобы бюджет и карточка не расходились. Старые поля ответа не удаляются. В серии — та же структура.

**Прячет:** разбор `attempts` по источникам.

## 7. `frontend/src/llmDisplay.ts` — чистые функции (новый)

**Владеет:** только форматированием и подписями. Без React, без сети.

```ts
export type LlmCard = {
  reference: { provider: string | null; model: string | null; kind: string; cost_usd: number | null;
               status: string; rate_source: string | null; rate_as_of: string | null; rate_verified: boolean }
  execution: { provider: string; model: string; status: string }
  actual: { cost_usd: number | null; status: string; max_cost_usd: number | null }
}
export function referenceLine(card: LlmCard): string      // «По тарифу Kie.ai — GPT-6 Luna: ≈ $0.000300»
export function referenceNote(card: LlmCard): string       // «(другая модель, сравнение по объёму токенов)» или подтверждение
export function executionLine(card: LlmCard): string      // «Исполняет: OpenRouter — MiniMax M3.1 Flash Free»
export function statusLine(card: LlmCard): string         // «Бесплатный API» / «Платный» / «Неизвестное списание»
export function actualLine(card: LlmCard): string         // «Реальный платёж: $0.000300» / «Бесплатный API»
export function budgetLines(summary: BudgetSummary): string[]  // четыре итога раздельными строками
```

**Шов для тестов:** чистые функции — `node --experimental-strip-types --test` на `frontend/src/llmDisplay.test.mjs`, без DOM и без сети.

## 8. `frontend/src/LlmCostCard.tsx` — карточка (новая)

**Владеет:** только отображением. Вход — `LlmCard` из ответа API, выход — карточка в порядке: тариф → исполнитель → статус → фактический платёж.

**Прячет:** разметку, классы, иконки.

## 9. `frontend/src/llmAsk.ts` — клиентский слой

**Меняется:** тип `LlmQuote` дополняется полями карточки; `runLlm` возвращает `LlmCard`. Существующий вызов `estimateLlm` сохраняет сигнатуру и дополняется полями (старые поля остаются). `frontend/src/llmPricing.ts` **не удаляется** и остаётся превью — но ни одно денежное значение из него не показывается как итог.

## 10. Кто какие файлы трогает

| Модуль | Файлы |
|---|---|
| Ядро шлюза | `backend/llm_gateway.py`, `backend/test_llm_gateway.py`, `config/llm_gateway.prices.example.json`, `.gitignore` |
| Адаптеры | `backend/llm_adapters.py`, `backend/test_llm_adapters.py`, `backend/connections.py` |
| Защита денег и схема | `backend/llm_guard.py`, `backend/security.py`, `backend/main.py`, `backend/test_llm_guard.py`, `backend/test_llm_quote.py` |
| Бюджет и экономика | `backend/economics.py`, `backend/series_economics.py`, `backend/test_llm_cost_display.py` |
| Карточка в интерфейсе | `frontend/src/llmDisplay.ts`, `frontend/src/llmDisplay.test.mjs`, `frontend/src/LlmCostCard.tsx`, `frontend/src/LlmApprovalDialog.tsx`, `frontend/src/llmAsk.ts`, `frontend/src/IdeaBrief.tsx`, `frontend/src/WorldFromBrief.tsx`, `frontend/src/WorkflowPanel.tsx`, `frontend/src/OutlineDialog.tsx` |
| Бюджет в интерфейсе | `frontend/src/Dock.tsx`, `frontend/src/EconomicsPanel.tsx`, `frontend/src/BudgetPanel.tsx`, `frontend/src/SeriesEconomics.tsx` |
| Документация | `docs/LLM_GATEWAY_ARCHITECTURE.md`, `docs/LLM_GATEWAY_PROVIDER_MATRIX.md`, `docs/LLM_GATEWAY_TEST_REPORT.md`, `docs/HANDOFF_MINIMAX_LLM_GATEWAY.md` |

**Единственный общий шов** — форма записи `llm_calls` и поля ответа `/api/llm/estimate` и `/api/llm/chat`. Их владеет таск 03 «Журнал, подпись и защита денег»; остальные таски читают, но не меняют. Если другому таску нужно поле ответа — он пишет его владельцу, а не правит файл сам. Форма сводки бюджета закреплена в §11.

## 11. Как проверять и что не трогать

**Стек:** Python 3.13 · FastAPI · SQLite (файл) · httpx · React + TypeScript + Vite. В этой ветке нет `pyproject.toml` и lock-файла Python — окружение берётся из готового venv студии.

**Интерпретатор (единственный, проверенный):**
`C:\AI_Workflow_Studio\.venv\Scripts\python.exe` — Python 3.13.14, pytest 9.1.1, fastapi 0.143.1. Venv не привязан к папке проекта, поэтому работает из любого worktree.

**Единственная команда проверки backend** (из корня репозитория):

```
C:\AI_Workflow_Studio\.venv\Scripts\python.exe -X utf8 -m unittest discover -s backend -p "test_*.py"
```

Проверено на стартовом коммите: `Ran 242 tests in 71.879s — OK`. Один файл: та же команда с `-p "test_llm_gateway.py"` либо `-m unittest backend.test_llm_gateway`. Pytest, если доступен: `... -m pytest backend`.

**Фронтенд** (из `frontend/`): `npm ci` — один раз, нужен интернет; `npm test` = `node --experimental-strip-types --test`; `npm run build` = `tsc --noEmit && vite build`. Один файл: `node --experimental-strip-types --test src/llmDisplay.test.mjs`. Сейчас `frontend/node_modules` отсутствует — установку делает таск 05.

**Отдельного линтера в проекте нет** (ruff-конфига в этой ветке нет) — выдумывать проверки не нужно.

**Что нельзя трогать:**
- `backend/kie.py`, `backend/adapters.py`, `backend/model_catalog.py`, media-часть — это image/video, они вне шлюза.
- Рабочую БД студии и файлы `.env` / `.env.example`.
- Корневую ветку `main` и чужие worktrees (`C:\AI_Workflow_Studio\.worktrees\*`).
- Процессы на 8000 и 5173 — работающая студия не перезапускается.

**Формат ответа бюджета** — общий для бэкенда, фронтенда и документации, чтобы числа не расходились:

```ts
type BudgetSummary = {
  actual_cost_usd: number      // подтверждённое фактическое списание
  reserved_usd: number         // зарезервировано, ещё не подтверждено
  unknown_cost_usd: number     // списание возможно, но не подтверждено
  reference_cost_usd: number   // эквивалент по Kie/PiAPI — НЕ деньги
  calls: number
}
```

## 13. Правила проекта, действующие для всех тасков

1. Общаться с владельцем по-русски; интерфейс студии — по-русски.
2. Не печатать, не коммитить и не показывать API-ключи.
3. Только аддитивные миграции; старую историю не удалять.
4. Image/video не переписывать.
5. Не подключать LangChain, Redis, Celery, Kafka, новую БД, облачные сервисы.
6. Ни одного платного API-запроса в тестах.
7. Не трогать корневую main и чужие worktrees; не останавливать процессы 8000/5173.
8. Не сливать в main и не делать force-push.
9. Перед кодом — блок `[PLAN]`; после правки — прогон проектных проверок.
10. Файлы добавлять в коммит точными путями, без `git add .`.
11. Перед правкой проверить `git status`, список worktrees и историю. При несовместимых незакоммиченных правках **остановить** затрагивающее их изменение и сообщить владельцу — не «чинить» через `reset --hard`.
12. Учитывать фактические более новые изменения репозитория: перед правкой сверить `git log` с картой из `notes.md`, расхождения зафиксировать в отчёте.
13. Прочитать и соблюдать `AGENTS.md`, `CLAUDE.md`, `README.md`, `TODO.md`, `docs/GIT_WORKFLOW.md`, `docs/HANDOFF_CLAUDE_CODE.md` — все они действуют и не перекрываются этой спецификацией.
14. Ключи — в принятой схеме проекта (передаются по запросу или лежат файлом в корне репозитория), **не пишутся в SQLite**, не печатаются, не коммитятся.
