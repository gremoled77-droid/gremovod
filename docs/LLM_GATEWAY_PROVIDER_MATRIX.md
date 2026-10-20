# Матрица провайдеров LLM-шлюза

Дата среза: 2026-10-20 · источник тарифов: `config/llm_gateway.prices.json` (рабочий файл владельца) и `config/llm_gateway.prices.example.json` (пример в Git).

**Главное, что нужно знать про эту таблицу:** ни один тариф в ней **не подтверждён живой проверкой**. У всех маршрутов `verified_at: null` и `enabled: false`, то есть шлюз сейчас закрыт: пока владелец не проставит `enabled: true` и `verified_at`, ни один платный маршрут не выбирается и ни одного сетевого вызова не происходит. Цены взяты из ТЗ владельца на 2026-10-20 — это ориентир для расчётов, а не подтверждённая цена провайдера.

Ключи в документе не приводятся. Указаны только имена переменных и файлов.

---

## 1. Сводная таблица

| Провайдер | Модель | Роль | Протокол | Вход, $ за 1 млн | Выход, $ за 1 млн | Дата тарифа | Источник тарифа | Статус проверки | Имя ключа |
|---|---|---|---|---|---|---|---|---|---|
| Kie.ai | `gpt-6-luna` | simple | `responses` | 0.03 | 0.15 | 2026-10-20 | https://kie.ai/gpt-6-sol-and-luna | не подтверждён: `verified_at: null`, `enabled: false` | `KIE_API_KEY` |
| Kie.ai | `claude-haiku-5-5` | editorial | `anthropic_messages` | 0.06 | 0.30 | 2026-10-20 | https://kie.ai/claude-haiku-5-5 | не подтверждён: `verified_at: null`, `enabled: false` | `KIE_API_KEY` |
| PiAPI | `gpt-5.6-luna` | extra | `openai_chat` | 0.02 | 0.12 | 2026-10-20 | https://piapi.ai/docs/llm-api/completions | не подтверждён: `verified_at: null`, `enabled: false` | `PIAPI_API_KEY` |
| MiniMax | `MiniMax-M3.1-Flash` | coding | `openai_chat` | 0.15 | 0.60 | 2026-10-20 | https://www.minimax.io/blog/minimax-m31f | не подтверждён: `verified_at: null`, `enabled: false` | `MINIMAX_API_KEY` |
| DeepSeek | `deepseek-flash` | backup | `openai_chat` | — (не заполнено) | — (не заполнено) | 2026-10-20 | https://api-docs.deepseek.com/quick_start/pricing/ | тарифа нет: цены `null`, `enabled: false` | `DEEPSEEK_API_KEY` |
| OpenRouter | `minimax/minimax-m3.1-flash:free` | coding | `openai_chat` | 0 | 0 | 2026-10-20 | https://openrouter.ai/minimax/minimax-m3.1-flash:free | не подтверждён: `verified_at: null`, `enabled: false`; `free: true`, `opt_in: true`, квота | `OPENROUTER_API_KEY` |

Адреса и префиксы путей (из рабочего файла реестра):

| Провайдер | `base_url` | `path_prefix` | Итоговый адрес вызова |
|---|---|---|---|
| Kie.ai | `https://api.kie.ai` | `openai` | `POST https://api.kie.ai/openai/v1/responses` |
| Kie.ai | `https://api.kie.ai` | `claude` | `POST https://api.kie.ai/claude/v1/messages` |
| PiAPI | `https://api.piapi.ai` | — | `POST https://api.piapi.ai/v1/chat/completions` |
| MiniMax | `https://api.minimax.io` | — | `POST https://api.minimax.io/v1/chat/completions` |
| DeepSeek | `https://api.deepseek.com` | — | `POST https://api.deepseek.com/v1/chat/completions` |
| OpenRouter | `https://openrouter.ai/api` | — | `POST https://openrouter.ai/api/v1/chat/completions` |

---

## 2. Kie.ai

**Что подтверждено (по официальной документации `docs.kie.ai`, зафиксировано в `.autopilot/.../interfaces.md`):**

- базовый адрес — `https://api.kie.ai`;
- авторизация **всегда** `Authorization: Bearer` — заголовок с именем `apikey` отклоняется с 401;
- список моделей: `GET https://api.kie.ai/openai/v1/models` и `GET https://api.kie.ai/anthropic/v1/models`. Живая проба без ключа (2026-10-21): оба пути отвечают HTTP 401 (путь есть, нужен ключ), `/v1/models` на голом хосте тоже существует — HTTP 200 с телом `{"code":401,"msg":"Unauthorized …"}`; заведомо кривой путь → настоящий HTTP 404;
- форма ответа Responses: текст в `output[].content[].text` (`type: 'output_text'`); `usage` содержит `input_tokens`, `output_tokens`, `total_tokens`, `input_tokens_details.cached_tokens`;
- usage Anthropic: `input_tokens` **не включает** кеш — кеш идёт отдельно в `cache_read_input_tokens` и `cache_creation_input_tokens`.

**Что НЕ подтверждено:**

- **точные upstream model id** для `gpt-6-luna` и `claude-haiku-5-5`: их надо взять списком моделей у Kie (`GET /openai/v1/models`, `GET /anthropic/v1/models`), а не угадывать;
- **цены**: 0.03/0.15 и 0.06/0.30 взяты из ТЗ владельца на 2026-10-20, живой сверки не было;
- **префиксы путей**: в рабочем конфиге владельца стоят `openai` и `claude` (коммит `6756149`), в документации Kie упоминаются `codex`/`api` для Responses и `anthropic` для Messages — какой префикс верный для этих моделей, показывает только живой ответ. Расхождение зафиксировано, а не сглажено;
- `capabilities` (tools / streaming / reasoning), `max_input_tokens`, `rate_limit`, `upstream_version` — пустые, то есть неизвестные.

**Про ключ:** `KIE_API_KEY` (переменная окружения) либо `KIE_API_KEY.txt` в корне репозитория, либо DPAPI-файл `kie-access/api-key.dpapi` (только Windows, тот же пользователь). Приоритет: заголовок запроса → переменная окружения → файл проекта → DPAPI.

---

## 3. PiAPI

**Что подтверждено:**

- протокол `openai_chat`, адрес `https://api.piapi.ai`, документация — https://piapi.ai/docs/llm-api/completions;
- тарифы старых проверенных цен живут отдельно от реестра: `backend/llm_guard.py`, `PRICES = {'gpt-5.6-luna': (0.02, 0.12), 'gpt-5.6-terra': (0.2, 1.2), 'gpt-5.6-sol': (0.5, 3.0), 'gpt-6-astra': (2.0, 10.0)}`. Совместимый маршрут старых клиентов (`provider: 'piapi'`) помечается `verified_at: 'legacy'` и работает по этим ценам;
- PiAPI отдаёт фактическое потребление в `meta.usage.consume` — по этому признаку резерв снимается, когда провайдер прямо сообщил `consume = 0`.

**Что НЕ подтверждено:**

- тариф `gpt-5.6-luna` в реестре (0.02 / 0.12) совпадает с legacy-ценой, но живой сверки в этой сборке не было, `verified_at: null`;
- `capabilities`, `max_input_tokens`, `rate_limit` — пустые.

**Про ключ:** `PIAPI_API_KEY` или `PIAPI_API_KEY.txt`. Для совместимого маршрута PiAPI ключ передаётся **в самом запросе** заголовком `X-API-Key` — сервер берёт его из заголовка, иначе отвечает «Введи корректный API-ключ PiAPI».

---

## 4. MiniMax

**Что подтверждено:**

- протокол `openai_chat`, адрес `https://api.minimax.io`, тариф 0.15 / 0.60 — из ТЗ владельца на 2026-10-20, источник: https://www.minimax.io/blog/minimax-m31f;
- маршрут открыт только при явном разрешении: `free: false`, `opt_in: false` — берётся как обычный платный маршрут роли `coding`.

**Что НЕ подтверждено:**

- **путь чата MiniMax подтвердить не удалось**: ни одного живого POST с ключом владельца не выполнялось, `verified_at: null`;
- путь проверки ключа (`/v1/models` из `backend/connections.py`) документацией не подтверждён — владелец сверяет перед включением маршрута;
- `capabilities`, `max_input_tokens`, `rate_limit` — пустые.

**Про ключ:** `MINIMAX_API_KEY` или `MINIMAX_API_KEY.txt`.

---

## 5. DeepSeek

**Что подтверждено:**

- протокол `openai_chat`, адрес `https://api.deepseek.com`, роль `backup` — маршрут отката в цепочке;
- в реестре стоит `requires_dynamic_tier_check: true`: тариф зависит от уровня, фиксированной цены нет.

**Что НЕ подтверждено:**

- **цены не заполнены** (`input: null`, `output: null`). Маршрут без тарифа шлюз не выбирает — это осознанное поведение: «нет тарифа» ≠ «цена ноль». Пока владелец не впишет цену и `verified_at`, DeepSeek в цепочку не попадёт;
- `capabilities`, `max_input_tokens`, `rate_limit` — пустые.

**Про ключ:** `DEEPSEEK_API_KEY` или `DEEPSEEK_API_KEY.txt`.

---

## 6. OpenRouter

**Что подтверждено:**

- протокол `openai_chat`, адрес `https://openrouter.ai/api`, модель `minimax/minimax-m3.1-flash:free`, цена 0 / 0;
- маршрут помечен `free: true` и `opt_in: true`: берётся **только** при `allow_free: true` в запросе, иначе шлюз его не выбирает;
- `quota_limited: true`, `rate_limit: "free tier quota"` — квота бесплатного уровня;
- нулевой тариф в реестре считается тарифом: строка журнала получает `actual_status = 'free'` и факт 0, отказа по лимиту нет. Отказ (400) бывает только когда тарифа нет вовсе; для работы агента нужен платный маршрут с тарифом — держать резерв под неподтверждённое списание нулевым тарифом нельзя.

**Что НЕ подтверждено:**

- `verified_at: null` — живой проверки бесплатного маршрута не было;
- остаток бесплатной квоты в момент проверки не измерялся.

**Про ключ:** `OPENROUTER_API_KEY` или `OPENROUTER_API_KEY.txt`.

---

## 7. Общие незакрытые пункты по матрице

1. `verified_at` пуст у **всех** шести маршрутов; `enabled: false` у всех.
2. `capabilities` у всех заполнен как `false` — это «не подтверждено», а не «не умеет».
3. `max_input_tokens`, `rate_limit`, `upstream_version` — пустые у всех.
4. Точные upstream model id Kie берутся списком `GET /openai/v1/models` и `GET /anthropic/v1/models`, а не угадываются.
5. Цена записи кеша (Anthropic `cache_creation`) отдельно не тарифицируется: токены записи считаются по обычному входному тарифу. Если нужен отдельный тариф — владелец уточняет.
6. Ключ провайдера лежит открытым текстом в `~/.minimax/config.yaml` (`providers.*.apiKey`) — рекомендуется перевыпустить ключ и держать его в переменной окружения или в файле `*_API_KEY.txt` в корне репозитория. **Значения ключей в документации не приводятся.**
