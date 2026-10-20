# Карта кода (этап A, аудит)

Источник: фактический чтение репозитория в worktree `C:\Users\BLOWKA\Documents\Minimax\_wt\gremovod-llm-gateway`, ветка `minimax/llm-gateway` (HEAD `1d6b53a`). Ветка содержит **только документы** — кода шлюза нет.

Проверено: `python -X utf8 -m unittest discover -s backend -p "test_*.py"` → **Ran 242 tests — OK** (системный Python 3.13; pytest не установлен, но есть в `C:\AI_Workflow_Studio\.venv\Scripts\python.exe` — pytest 9.1.1, fastapi 0.143.1). Фронтенд-проверки не выполнялись: `frontend/node_modules` отсутствует, нужен `npm ci`.

## Точные имена сущностей, которых касается работа

### backend/llm_guard.py (166 строк) — текущее ядро
- `PRICES: dict[str, tuple[float, float]]` — цены USD **за 1 млн токенов**, ключ = модель без провайдера: `'gpt-5.6-luna': (0.02, 0.12)`, `'gpt-5.6-terra': (0.2, 1.2)`, `'gpt-5.6-sol': (0.5, 3.0)`, `'gpt-6-astra': (2.0, 10.0)`. PiAPI подразумевается.
- `MAX_OUTPUT_TOKENS = 2000`, `MAX_INPUT_CHARS = 30000`, `ROLES = {'system','user','assistant'}`.
- `class Estimate(BaseModel)`: `project_id`, `model`, `messages` (1..50), `max_tokens` (16..2000, default 2000).
- `clean_messages(messages) -> list[dict]` — фильтр по ролям, 400 при пустом тексте или >30000 символов.
- `price_of(model) -> tuple[float,float]` — 400 «нет проверенной цены», если модели нет в `PRICES`.
- `estimate_usd(model, messages, max_tokens) -> float` — верхняя оценка: `input_tokens = ceil(chars/2) + 20*len(messages)`, `cost = round((in*price_in + max_tokens*price_out)/1_000_000, 6)`.
- `payload_of(model, messages, max_tokens) -> dict` — `{'kind':'llm','model','max_tokens','messages': sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False))}`.
- `spent(db, project_id) -> tuple[float,float]` — сумма `usd` по `status IN ('reserved','done')`: всего и за сегодня (МСК, `security.MOSCOW`).
- `summary(db, projects=None) -> dict` — `{calls, usd, estimated_usd, today_usd, by_model{model:{calls,usd}}}`; при отсутствии таблицы — пустой dict.
- `check_budget(db, project_id, cost) -> None` — сначала `series_economics.check_budget`, затем `security.budget_state`; `project_reserved_usd + project_llm + cost` vs `project_limit_usd`, `daily_reserved_usd + daily_llm + cost` vs `daily_limit_usd` (допуск 1e-9).
- `register(app, studio)` — `on_event('startup')` создаёт таблицу; `POST /api/llm/estimate` → `{estimated_usd, quote_token, max_tokens, model}`.
- `guarded_chat(studio, body, key) -> dict` — единственный путь платного LLM-вызова; `body.provider != 'piapi'` → 400; резерв `BEGIN IMMEDIATE` + проверка дубля `request_id` + `INSERT`; ошибка провайдера → `UPDATE llm_calls SET status='failed', usd=0`.

### Таблица `llm_calls` (текущая, 10 колонок)
`id TEXT PK, request_id TEXT UNIQUE, project_id TEXT NOT NULL, model TEXT NOT NULL, status TEXT NOT NULL, usd REAL NOT NULL, estimated_usd REAL NOT NULL, input_tokens INTEGER, output_tokens INTEGER, created_at TEXT NOT NULL`
- `usd` перегружен: `reserved` → оценка, `done` → факт, `failed` → 0.
- Колонок `actual_cost_usd` / `reserved_usd` / `provider` / `reference_*` **нет**.
- Вставка **позиционная**: `INSERT INTO llm_calls VALUES(?,?,?,?,?,?,?,?,?,?)` — добавление колонки её сломает.

### backend/security.py (137 строк)
- `SIGNING_KEY = secrets.token_bytes(32)` — новый на каждый запуск процесса, quote не переживает рестарт.
- `quote(project_id, payload, cost) -> str` — `json.dumps({'project_id','payload','cost','expires': now+600}, sort_keys=True, separators=(',',':'))` + `'.'` + `HMAC-SHA256(SIGNING_KEY, data)`.
- `verify_quote(token, project_id, payload, cost) -> tuple[bool, str]` — `compare_digest`, срок ≤ 600 с, совпадение `project_id`, `payload` (model + max_tokens + хеш messages) и `cost`. В подписи **нет**: provider, версии/даты тарифа, выбора fallback, tools, cached/reasoning tokens.
- `budget_state(db, project_id) -> dict` — `project_reserved_usd`, `project_limit_usd`, `daily_reserved_usd`, `daily_limit_usd`; лимиты в `spending_limits(id=1)`: `project_usd` (1), `daily_usd` (2).
- `released(db, ...)` — снятие резерва.
- Middleware: `POST /api/chat`, `/api/compose`, `/api/agents/run` → 503 (платные обходные пути закрыты).

### backend/main.py (835 строк)
- `class UnifiedChatRequest(BaseModel)`: `provider='openai'`, `model='gpt-4.1-mini'`, `messages` (1..50), `max_tokens` (16..8000), `project_id`, `approved`, `quote_token`, `max_cost_usd` (0..100), `request_id` (8..100, `^[a-zA-Z0-9_-]+$`).
- `POST /api/llm/chat` → `llm_guard.guarded_chat(...)`; ответ `{choices:[{message:{role,content}}], usage, provider:'piapi', model, cost_usd, estimated_usd}` — тарифа, даты цены, источника и reference-cost в ответе нет.
- `request_piapi(path, payload, key)` — `/v1/` → `Authorization: Bearer`, иначе `X-API-KEY`; `BASE='https://api.piapi.ai'`; таймаут 120 с; ретраев нет.
- `POST /api/model-jobs/estimate` → `{quote_token, expires_in_seconds, model_id, kind, estimated_usd, images, payload, lines, source, verified_at, note}` — образец богатого контракта.

### backend/connections.py (117 строк)
- `PROVIDERS`: `piapi` (`PIAPI_API_KEY` / `PIAPI_API_KEY.txt`, `https://api.piapi.ai/account/info`, `X-API-Key`), `openai`, `elevenlabs`, `fish`, `kie` (`KIE_API_KEY` / `KIE_API_KEY.txt`, `https://api.kie.ai/api/v1/chat/credit`).
- `credential(provider, header=None, file_override=None)` — приоритет: заголовок запроса → env → файл в корне репо → (kie) DPAPI (`KIE_DPAPI_FILES`, `dpapi_decrypt`, `dpapi_key`).
- `connection_info(provider) -> dict` → `{id, name, filename, docs, configured, source, status, message, checked_at}`; `GET /api/connections`, `POST /api/connections/{provider}/check` (классификация 403/1010/401/429).
- MINIMAX / DEEPSEEK / OPENROUTER **в коде отсутствуют**.

### backend/economics.py (96) / backend/series_economics.py (71)
- `economics.py`: таблицы `clip_costs(job_id PK, actual_usd, note, updated_at)`, `asset_outcomes`. `GET /api/economics?project_id=` → `attempts` из 4 источников; LLM — отдельным ключом `llm = llm_guard.summary(db, {project_id})`. `actual_usd_known` LLM **не включает**. Есть `unknown_cost_count`, `llm_calls_unpriced` (это `prompt_versions`, не `llm_calls`).
- `series_economics.py`: `production_series_limits(series_id PK, limit_usd)`; `check_budget` = `security.reservations` по проектам серии **+ `llm_guard.summary(db, owned)['usd']`**; `GET/PUT /api/productions/{pid}/series/{sid}/economics|budget` → `{actual_usd_known, estimated_usd, reserved_usd, unknown_cost_count, costs_complete, attempts, used_generations, success_percent, chat_api_equivalent_usd, llm, limit_usd, jobs}`.

### backend/model_catalog.py (224) и backend/kie.py (69)
- `MODEL_SPECS` — паттерн полей: `launch_enabled`, `verified_at`, `kind`, `model`, `task_type`, `adapter`, `submit_path`, `provider` (по умолчанию `'piapi'`), `docs`, `options`; цены в разных схемах (`price_usd`, `price_by_size`, `price_by_quality`, `price_by_tier`, `price_per_second_usd`, `price_per_mpx_usd`). Единой схемы цен нет.
- `kie.py` — **только очередь заданий** (`createTask` / `recordInfo`), приведение ответа к форме PiAPI, `credits_consumed`. Текстовых/chat-вызовов нет.

### Миграции
Фреймворка миграций нет. Схема создаётся в `on_event('startup')` через `CREATE TABLE IF NOT EXISTS`. Аддитивная колонка — идемпотентно через `PRAGMA table_info` + `ALTER TABLE ... ADD COLUMN` (пример: `main.py:53-54` — колонка `revision` в `projects`; `reference_upload.py:75-76` — `public_references.provider`).

### Тесты
44 файла `backend/test_*.py`. По теме: `test_llm_guard.py` (148), `test_budget_release.py` (58), `test_series_economics.py` (35), `test_llm_response.py` (67), `test_smoke.py`, `test_story_plan.py`, `test_adapters.py`, `test_video_delivery.py`.
- Раннер — `unittest` (`unittest.TestCase`), pytest-совместимы. Заглушки внешних вызовов: `unittest.mock.patch.object(main,'request_piapi', AsyncMock(...))`, `patch.object(kie,'request', AsyncMock(...))`. `httpx.MockTransport` применён ровно один раз (загрузка в tempfile, `test_smoke.py:230-242`) — **для провайдеров заглушек нет**.
- Фронтенд-тесты: `frontend/src/createDraft.test.mjs`, раннер `node --experimental-strip-types --test`.

### Фронтенд
- `frontend/src/llmPricing.ts` (27) — `LLM_MODELS` (luna/terra/sol, **без astra**), `LLM_MAX_TOKENS=2000`, `llmEstimate(model, inputChars, maxTokens)` (вход `ceil(chars/2.5)+50`), `IDEA_LLM_MODELS` + `ideaEstimate` — **дубликат `llm_guard.PRICES` с другой формулой** (сервер `/2 + 20*n`).
- `frontend/src/llmAsk.ts` (48) — `estimateLlm(projectId, model, messages) -> LlmQuote{token,usd,projectId,model,messages}`; `runLlm(quote) -> {text, cost}`; `request_id: crypto.randomUUID()`.
- Точки вызова LLM: `IdeaBrief.tsx:135,142`, `WorldFromBrief.tsx:61,72`, `WorkflowPanel.tsx:746,760` + клиентский превью `llmEstimate` (`WorkflowPanel.tsx:692`), `OutlineDialog.tsx:57,62` (через `llmAsk`).
- `frontend/src/GenerationReview.tsx` (197) — карточка подтверждения **только image/video**: `type Estimate{quote_token, estimated_usd, images, source, verified_at, note, lines}`; `POST /api/model-jobs/estimate` → `POST /api/model-jobs` с `quote_token, approved:true, max_cost_usd, request_id`; `LimitPicker` + чекбокс. **LLM-варианта нет.**
- `frontend/src/Dock.tsx` (83) — «Очередь и бюджет»: `GET /api/budgets/{projectId}`, поллинг 15 с; показывает `project_reserved_usd/project_limit_usd` и `daily_reserved_usd/daily_limit_usd`. **`llm_project_usd`/`llm_daily_usd` из ответа не отображаются.**
- `frontend/src/BudgetPanel.tsx` (124) — `GET/PUT /api/budgets/*`; строка про LLM со `smallUsd`.
- `frontend/src/EconomicsPanel.tsx` (318) — `GET /api/economics?project_id=`; блок LLM (`:201-210`) — «LLM-запросы из воркфлоу: N · $X по токенам (оценка $Y), сегодня $Z» — смесь оценки и факта; блок «Без цены» (`:211-219`).
- `frontend/src/SeriesEconomics.tsx` (107) — `GET/PUT .../series/{sid}/economics|budget`, строка LLM (`:51-53`).
- `frontend/src/usdFormat.ts` (3) — `smallUsd` (6 знаков при <$0.01). `frontend/src/spendLimit.ts` (24) — `DEFAULT_LIMIT_USD=2`, `limitAllowed`. `frontend/src/LimitPicker.tsx` (77). `frontend/src/api.ts` (49) — `apiFetch` + `X-Studio-Session`; **`export const PAID_LLM_ENABLED = false;`**.
- Отдельной карточки LLM-вызова нет; n8n в `backend/` и `frontend/src/` не упоминается.

## Риски, найденные аудитом

1. **Смешение резерва и факта.** «Потрачено» для LLM = `summary()['usd']` = сумма `usd` по `status IN ('reserved','done')`. Отдельного «фактически потрачено» нет ни в одной таблице.
2. **Обнуление при сбое.** `llm_guard.py:154` ставит `usd=0, status='failed'` — при таймауте/5xx/1010 списание могло произойти. Политика «unknown ≠ 0» нарушена.
3. **Идемпотентность только по клиентскому `request_id`;** при его отсутствии генерируется `uuid4().hex` — повторная отправка = новая оплата. Счётчика платных попыток нет.
4. **Подпись слабее ТЗ:** нет provider, версии тарифа, fallback, tools. `SIGNING_KEY` пересоздаётся при рестарте.
5. **Дубликат цен клиент↔сервер** в `llmPricing.ts` с другой формулой токенизации — источник расхождений; гейт «ориентир vs факт» обязан считаться на сервере.
6. **`config/llm_gateway.prices.example.json` не читается ни одной строкой кода** — готовая схема не подключена.
7. **Позиционный `INSERT INTO llm_calls VALUES(...)`** — перед добавлением колонок перевести на именованные.
8. **Kie — только image/video:** протоколы `responses` (GPT-6 Luna) и `anthropic_messages` (Haiku) не реализованы.
9. **Асимметрия лимитов:** `llm_guard.check_budget` складывает LLM + генерации, `security.check_budget` — только генерации.
10. **Параллельные ветки:** `minimax/paid-llm-guard` (26ef242, 500 строк diff по `llm_guard.py`/`main.py`/`security.py`) и `feature/minimax-m3-1-flash-20261019` — не слиты в main, конфликтуют по тем же файлам при будущем слиянии.
