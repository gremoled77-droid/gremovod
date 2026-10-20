# LLM-шлюз студии: архитектура, границы денег и dry-run для n8n

Дата: 2026-10-20 · ветка `minimax/llm-gateway` · шлюз собран из шести коммитов (`94d294a` → `c33635c`) плюс `d7e3e15` (панели и документация) и ремонтный круг F1 (правки в рабочем дереве, коммит за оркестратором).

Документ описывает, как студия считает деньги за LLM-вызовы. Он не содержит ключей и значений ключей — только имена переменных и файлов.

---

## 1. Где что лежит

| Слой | Файлы | Что делает |
|---|---|---|
| Реестр и тарифы | `backend/llm_gateway.py`, `config/llm_gateway.prices.example.json` | реестр маршрутов, тарифный ориентир, фактическое списание, сводка расходов |
| Транспорт | `backend/llm_adapters.py`, `backend/connections.py` | три протокола, классификация сбоев, чтение ключей |
| Деньги и подпись | `backend/llm_guard.py`, `backend/security.py`, `backend/main.py` | оценка, подпись, резерв, лимиты, `/api/llm/estimate` и `/api/llm/chat` |
| Итоги | `backend/economics.py`, `backend/series_economics.py` | сводка по проекту и по серии |
| Интерфейс | `frontend/src/llmDisplay.ts`, `frontend/src/LlmCostCard.tsx`, `frontend/src/LlmApprovalDialog.tsx`, `frontend/src/Dock.tsx`, `frontend/src/EconomicsPanel.tsx`, `frontend/src/BudgetPanel.tsx`, `frontend/src/SeriesEconomics.tsx` | карточка вызова и разбивка бюджета |
| Агентский путь | `backend/native_chat.py` | вызовы агента (`codex_chat`) журналируются в тот же `llm_calls` |

Изображения и видео (Kie/PiAPI image, video) в шлюз **не входят** и не переписывались.

---

## 2. Реестр и конфигурация

Реестр — один JSON-файл маршрутов. В Git лежит пример `config/llm_gateway.prices.example.json`; рабочий файл владельца — `config/llm_gateway.prices.json` (в Git не попадает, добавлен в `.gitignore`). Если рабочего файла нет, берётся пример.

Структура:

```
rates[]                  маршруты: provider, model, model_id, role,
                         input / output (USD за 1 000 000 токенов),
                         cached_input_per_mtok, source, as_of,
                         protocol, base_url, path_prefix,
                         capabilities {tools, streaming, reasoning},
                         max_input_tokens, rate_limit, upstream_version,
                         free, opt_in, promotion, quota_limited,
                         requires_dynamic_tier_check,
                         enabled, verified_at
comparison_display       правила показа: card_primary, budget_primary,
                         reference_provider_allowlist, match_priority,
                         default_baseline, alternative_baseline,
                         small_amount_precision (6 знаков)
sample_limits_only       пример лимитов (0.1 / 1 / 10 USD) —
                         НЕ применяется поверх лимитов владельца
```

Ключевые поля включения:

- `enabled: true` — маршрут вообще можно выбрать. В примере и в рабочем файле владельца **все маршруты выключены**.
- `verified_at` — дата живой сверки тарифа. Сейчас пуст у всех маршрутов.
- `free: true` — маршрут бесплатный (OpenRouter Free): его можно брать только с `allow_free: true`.
- `opt_in: true` — маршрут с оптином: тоже только по явному разрешению.
- `capabilities` — что умеет модель (tools / streaming / reasoning). Сейчас заполнено `false` у всех: не подтверждено.

Пока `enabled=false`, шлюз **закрыт по умолчанию**: `/api/llm/estimate` и `/api/llm/chat` отвечают 400 («Эта модель недоступна для платного вызова: нет проверенной цены»), и ни одного сетевого запроса не уходит.

Лимиты владельца (`/api/budgets/limits`, таблица `spending_limits`) живут отдельно от реестра и примеру `sample_limits_only` не подменяются.

---

## 3. Ориентир и факт — это разные числа

| | Что это | Где живёт | Деньги? |
|---|---|---|---|
| **Ориентир** | сколько стоил бы вызов по тарифу Kie/PiAPI | `reference_cost_usd` + `reference_provider/model/kind` в `llm_calls`, блок `reference` в ответе API | **Нет.** Не входит ни в один итог и не влияет на лимиты |
| **Факт** | сколько списали на самом деле по usage провайдера | `actual_cost_usd` + `actual_status` в `llm_calls`, блок `actual` в ответе API | Да, если `actual_status` = `confirmed` или `free` |

Правила:

- Ориентир считается по тарифу **Kie/PiAPI** (`reference_provider_allowlist`), при отсутствии точной модели — по базовой линии (`default_baseline` — Kie GPT-6 Luna, `alternative_baseline` — PiAPI GPT-5.6 Luna). Вид ориентира: `exact_model` или `reference_model` («другая модель, сравнение по объёму токенов»).
- Ориентир **никогда** не складывается с фактом и не вычитается из него. В карточке он показан первым, но с пометкой «не деньги».
- **Фактически потрачено** собирается только из `actual_cost_usd` при `actual_status` = `confirmed` (сумма по usage) или `free` (ноль у подтверждённо бесплатного маршрута). Подтверждённого нуля у платного маршрута не бывает.
- Значение `llm_guard.summary()['usd']` — это **экспозиция** (факт + удерживаемые резервы + неизвестные списания), а не расход. Её проверяют лимиты. Старые экраны читали её как «расход» — поэтому «Фактически потрачено» собирается из `actual_cost_usd`, а не из `summary()['usd']`.

Единая форма сводки (её используют бэкенд, интерфейс и документация):

```ts
type BudgetSummary = {
  actual_cost_usd: number      // подтверждённое фактическое списание
  reserved_usd: number         // зарезервировано, ещё не подтверждено
  unknown_cost_usd: number     // списание возможно, но не подтверждено
  reference_cost_usd: number   // эквивалент по Kie/PiAPI — НЕ деньги
  calls: number
}
```

Где отдаётся: `/api/economics` (блок `llm`), `/api/productions/{pid}/series/{sid}/economics` (блок `llm`), `/api/budgets/{project_id}` (поля `actual_cost_usd`, `reserved_usd`, `unknown_cost_usd`, `reference_cost_usd` верхнего уровня). Прежние поля (`usd`, `actual_usd`, `estimated_usd`, `today_usd`, `by_model`, `llm_project_usd`, `llm_daily_usd`, `llm_calls_project`) сохранены.

---

## 4. Поток вызова

**Шаг 1. Оценка — `POST /api/llm/estimate`.** Тело: `project_id`, `model`, `messages`, `max_tokens` (16…2000), `route_mode` (`manual` | `auto`), `task`, `allow_free`, `max_cost_usd`, `tools`, `settings`.

Шлюз строит цепочку маршрутов (`plan_routes`), считает предвызовную оценку по тарифу маршрута-исполнителя (`route_estimate`, токены ≈ `длина текста / 2 + 20 на сообщение`, выход = `max_tokens`), берёт **максимум** по цепочке и подписывает оценку (`security.quote`: HMAC + `extra` с провайдером, моделью, версией цены, запасными маршрутами, максимумом платежа и хешем tools). Токен живёт 10 минут.

Ответ:

```json
{
  "estimated_usd": 0.00027,
  "quote_token": "<подпись>",
  "max_tokens": 500, "model": "MiniMax-M3.1-Flash",
  "reference": {"provider": "kie", "model": "gpt-6-luna", "kind": "reference_model",
                "cost_usd": 0.00006, "status": "estimated",
                "rate_source": "https://kie.ai/gpt-6-sol-and-luna", "rate_as_of": "2026-10-20",
                "rate_verified": false, "label": "..."},
  "execution": {"provider": "minimax", "model": "MiniMax-M3.1-Flash", "status": "paid"},
  "actual": {"cost_usd": null, "status": "estimated", "max_cost_usd": 0.00027},
  "route_chain": [{"provider": "minimax", "model": "MiniMax-M3.1-Flash", "free": false}]
}
```

**Шаг 2. Вызов — `POST /api/llm/chat`.** Тело добавляет `approved: true`, `quote_token`, `max_cost_usd` и `request_id`. Сервер проверяет: подпись (проект, payload, оценка, `extra`), `max_cost_usd` ≥ оценка, лимиты проекта и суток, затем **создаёт резерв** и только после этого обращается к провайдеру.

**Шаг 3. Журнал.** До сети в `llm_calls` появляется строка `status='reserved'`, `reserved_usd = оценка`, `actual_cost_usd = NULL`. После ответа провайдера строка обновляется:

| Исход | `actual_status` | `actual_cost_usd` | Резерв | Попадает в «Фактически потрачено» | Попадает в «Неизвестные списания» |
|---|---|---|---|---|---|
| usage пришёл | `confirmed` | сумма по usage | снят | да | нет |
| подтверждённо бесплатный маршрут | `free` | 0 | снят | да (ноль) | нет |
| ответ без usage | `unknown` | нет числа | **держится** | нет | **да** |
| провайдер отказал (401, явный отказ) | `not_charged` | 0 | снят | нет | нет |
| вызов в полёте | `estimated` | нет числа | держится | нет | нет |

Отказ транспорта различается **структурно**, а не по тексту: `ProviderCallFailed` несёт `error_kind` (`http_401`, `http_403`, `http_429`, `http_5xx`, `cloudflare_1010`, `bad_body`, `timeout`, `no_usage`) и признак `charged_possible`. `False` — запрос не обработан, списания не было; `True` — списание возможно.

**Шаг 4. Ответ.** `/api/llm/chat` отдаёт прежние поля (`choices`, `usage`, `provider`, `model`, `cost_usd`, `estimated_usd`) **плюс** поля карточки (`reference`, `execution`, `actual`). Интерфейс показывает карточку: ориентир → исполнитель → статус → фактический платёж.

---

## 5. Цепочка запасных маршрутов и её границы

Цепочка строится только в автоматическом режиме (`route_mode: "auto"` + `task`): сначала бесплатные маршруты роли (если `allow_free: true`), затем **не больше одного платного** маршрута; роль отката — `backup`. В ручном режиме цепочка — один маршрут по имени модели.

Бесплатным считается маршрут с подтверждённо нулевым тарифом (флаг `free` или тариф 0/0). Платный маршрут по оптину — тоже платный: он занимает единственное платное место цепочки, а не встаёт перед ним вторым платным маршрутом.

Границы:

1. **Не больше одной платной попытки на запрос.** Бесплатный маршрут может быть провален, платный за ним — один.
2. **Лимит проверяется на каждом шаге.** Если лимита не хватает на платный запасной маршрут, цепочка останавливается (`stop_error`), лишнего платежа не происходит.
3. **Идемпотентность по `request_id`.** Повтор того же `request_id` → 409 «Этот запрос уже отправлялся…», повторного платежа не будет. Запасной маршрут пишется с `request_id` вида `<request_id>-fallback1`, в колонке `fallback_from` — предыдущий маршрут.
4. **Ориентир цепочки** — по тарифу Kie/PiAPI для модели-ориентира; факт — по тарифу того маршрута, который реально выполнил вызов.
5. **Отказы до сети** (маршрут вне реестра, ненастроенный ключ, `enabled=false`, `opt_in` без разрешения, ненулевой тариф с `verified_at=null`) дают 400 **без сетевого вызова**.

---

## 6. Границы денег

- **Резерв создаётся до обращения к провайдеру** и держится, пока списание не подтверждено или не доказано, что его не было. Это потолок, а не расход.
- **Резерв снимается** только когда провайдер точно отказал (401, явный отказ, `charged_possible = False`).
- **Лимиты** (`/api/budgets/limits`, лимит серии) проверяются по экспозиции: факт + удерживаемые резервы + неизвестные списания. Поэтому неизвестное списание занимает лимит до сверки — так его нельзя спрятать.
- **В «Фактически потрачено» попадает только** `actual_cost_usd` при `actual_status` = `confirmed` или `free`.
- **В «Неизвестные списания / нужна сверка» попадает** сумма строк со `actual_status = 'unknown'`.
- **В «Зарезервировано» попадают** строки `actual_status = 'estimated'` (вызов в полёте) и любые строки с ненулевым `reserved_usd` и неподтверждённым списанием.
- **Ориентир по Kie/PiAPI** — неденежная величина: ни в один итог не входит, лимиты не двигает.
- **Ноль у платного маршрута невозможен**: без usage списание `unknown`, а не ноль.
- **Нулевой тариф — это тариф, а не его отсутствие**: маршрут 0/0 (подтверждённо бесплатный) даёт `actual_status='free'`, факт 0, резерв 0; подтверждённого $0.00 у платного маршрута не бывает.
- Агентский путь (`codex_chat`) журналируется в тот же `llm_calls` по тем же правилам: расход назван → `confirmed`; не назван → `unknown` с удержанием резерва; тариф 0/0 → `free`, а не `unknown`.
- **Резерв работы агента держит только платный маршрут с тарифом.** Нулевой тариф (0/0) денег под неподтверждённое списание не даёт, поэтому в запасной источник резерва он не попадает; платного тарифа в реестре нет — работа агента не ставится (400). Так каждая строка `actual_status='unknown'` имеет ненулевой `reserved_usd`, попадает в «неизвестные списания» и занимает лимит.

---

## 7. Dry-run для n8n: пошагово

Цель — увидеть, как шлюз считает деньги, **не потратив их**. Шаг 4 (реальный вызов) платный и без отдельного одобрения владельца не выполняется.

Студия поднимается на `http://127.0.0.1:8000`; n8n должен быть на той же машине ( middleware студии принимает только loopback-хост и `X-Studio-Session`).

**Шаг 1. Сессия студии.**

```
GET http://127.0.0.1:8000/api/session
→ {"token": "<LAUNCH_TOKEN>"}
```

Дальше во все запросы к `/api/*` нужно передавать заголовок `X-Studio-Session: <token>` (или cookie `studio_session`).

**Шаг 2. Проект для учёта.**

```
GET  http://127.0.0.1:8000/api/projects          → список, взять id
POST http://127.0.0.1:8000/api/projects
     {"title": "dry-run n8n", "state": {}}        → {"id": "<project_id>"}
```

**Шаг 3. Оценка — сети не будет, денег не будет.**

```
POST http://127.0.0.1:8000/api/llm/estimate
Headers: X-Studio-Session: <token>
Body:
{
  "project_id": "<project_id>",
  "model": "MiniMax-M3.1-Flash",
  "messages": [{"role": "user", "content": "Короткий тест шлюза"}],
  "max_tokens": 500,
  "route_mode": "auto",
  "task": "coding",
  "allow_free": false
}
```

Что видно в ответе (всё это — расчёт по реестру, ни одного запроса к провайдеру):

- `estimated_usd` — оценка по тарифу маршрута-исполнителя (потолок платежа);
- `reference` — ориентир по Kie/PiAPI: `provider`, `model`, `kind` (`exact_model` / `reference_model`), `cost_usd`, `status`, `rate_as_of`, `rate_verified`. **Это не деньги**; при `rate_verified: false` подпись под ним говорит «тариф не подтверждён вживую»;
- `execution` — кто выполнит: провайдер, модель, статус (`paid` / `free`);
- `actual` — `cost_usd: null`, `status: "estimated"`, `max_cost_usd` — ожидаемый реальный платёж **до** подтверждения;
- `route_chain` — цепочка маршрутов: сначала бесплатные (если `allow_free: true`), затем максимум один платный;
- `quote_token` — подпись, действует 10 минут.

Если маршруты выключены (`enabled: false` в рабочем файле владельца) — ответ 400 «Эта модель недоступна для платного вызова…». Это ожидаемое поведение «закрыт по умолчанию», а не ошибка.

**Шаг 4. Реальный вызов — только по отдельному одобрению владельца на конкретную сумму.** Если одобрение получено:

```
POST http://127.0.0.1:8000/api/llm/chat
Headers: X-Studio-Session: <token>
Body:
{
  "project_id": "<project_id>",
  "model": "MiniMax-M3.1-Flash",
  "messages": [{"role": "user", "content": "Короткий тест шлюза"}],
  "max_tokens": 500,
  "approved": true,
  "quote_token": "<quote_token из шага 3>",
  "max_cost_usd": <estimated_usd из шага 3>,
  "request_id": "n8n-dryrun-0001"
}
```

Что видно: `choices` и `usage` от провайдера, `provider` / `model` (кто выполнил), `cost_usd` (факт; `null`, если провайдер не отдал usage — тогда списание `unknown`, а не ноль), плюс блоки `reference` / `execution` / `actual` карточки.

Ключ провайдера n8n передавать не нужно: сервер берёт его сам по схеме `backend/connections.py` (`KIE_API_KEY`, `MINIMAX_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY`, `PIAPI_API_KEY` — переменная окружения или файл `*_API_KEY.txt` в корне репозитория). Исключение — совместимый маршрут PiAPI: там ключ передаётся в запросе заголовком `X-API-Key`.

**Шаг 5. Проверить учёт в интерфейсе.**

- «Очередь и бюджет» (правая панель) → блок «LLM в проекте»: фактически потрачено, зарезервировано, неизвестные списания, эквивалент по Kie/PiAPI (не деньги).
- «Экономика» → блок LLM с той же разбивкой и по моделям.
- Серия → «Экономика и бюджет серии» → та же разбивка по вызовам серии.

**Шаг 6. То же самое в n8n.** Узел **HTTP Request**: Method `POST`, URL `http://127.0.0.1:8000/api/llm/estimate`, Header `X-Studio-Session` = токен из шага 1, Body JSON = тело шага 3, Authentication = None. В ответе узла интересуют `estimated_usd`, `reference.cost_usd`, `actual.max_cost_usd` и `route_chain`. Если нужен и вызов — второй узел HTTP Request с телом шага 4, `quote_token` из ответа первого узла.

---

## 8. Чего в шлюзе нет

- Учёта image/video (вне рамок шлюза, см. `docs/HANDOFF_MINIMAX_LLM_GATEWAY.md`).
- Живой проверки тарифов: `verified_at` пуст у всех маршрутов, живой платный вызов не выполнялся.
- Автоматического включения маршрутов: пока владелец не проставит `enabled: true` и `verified_at`, шлюз закрыт.
