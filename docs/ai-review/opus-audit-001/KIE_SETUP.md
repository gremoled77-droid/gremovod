# KIE_SETUP — подключение Claude Opus 5.5 через KIE

**Дата проверки:** 2026-10-20. Все маршруты и цены сверены с официальной документацией
KIE и проверены живыми запросами **без ключа** (см. §6).
**Платных вызовов при подготовке не выполнено. Расход: 0.**

---

## 1. Официальные данные по модели

| Параметр | Значение |
|---|---|
| Модель (KIE id) | `claude-opus-5-5` |
| KIE doc id | `market/claude/claude-opus-5-5` |
| Контекст | 1 000 000 токенов |
| Макс. выход | 128 000 токенов |
| Вход (KIE) | **320 кредитов / 1M токенов** (≈ $1.60) |
| Выход (KIE) | **1 600 кредитов / 1M токенов** (≈ $8.00) |
| Вход (Anthropic, upstream) | $4.00 / 1M |
| Выход (Anthropic, upstream) | $20.00 / 1M |

Тариф KIE = **1 кредит = $0.005** (проверка: 320 × 0.005 = 1.60; 1600 × 0.005 = 8.00).
KIE дешевле upstream примерно на 60 %.

Источники: официальная страница модели KIE и раздел цен KIE
(`kie.ai` → модели → Claude Opus 5.5).

---

## 2. Два маршрута — выбрать ОДИН, не смешивать

### Маршрут A. Прямой Messages API (рекомендуется для аудита)

```
POST https://api.kie.ai/claude/v1/messages
```

| Заголовок | Значение |
|---|---|
| `Authorization` | `Bearer <KIE_API_KEY>` |
| `Content-Type` | `application/json` |
| `anthropic-version` | необязателен |

Тело запроса (Anthropic-совместимое):

```json
{
  "model": "claude-opus-5-5",
  "max_tokens": 16000,
  "messages": [
    { "role": "user", "content": "..." }
  ]
}
```

Дополнительно поддерживаются: `stream` (bool), `thinkingFlag` (bool), `tools`
(с `input_schema`).

**Важно для Anthropic SDK:** клиент, который отправляет ключ в `x-api-key`, должен
положить туда значение вида `Bearer <KIE_API_KEY>` — с префиксом `Bearer`. Это отличие
от привычного «ключ в x-api-key без Bearer».

**Стриминг** — SSE с событиями:
`message_start` → `content_block_start` → `content_block_delta` → `message_delta` → `message_stop`.

### Маршрут B. Claude Code через Anthropic-совместимый слой

```
ANTHROPIC_BASE_URL=https://api.kie.ai/anthropic
```

> **Без `/v1/messages` в `BASE_URL`.** Клиент сам дописывает `/v1/messages`.

| Переменная | Значение |
|---|---|
| `ANTHROPIC_BASE_URL` | `https://api.kie.ai/anthropic` |
| `ANTHROPIC_AUTH_TOKEN` | `<KIE_API_KEY>` — **сырой ключ, без `Bearer`** |
| *или* `ANTHROPIC_API_KEY` | `Bearer <KIE_API_KEY>` — **с префиксом** |

Официальный список моделей для этого слоя:
```
GET https://api.kie.ai/anthropic/v1/models
```

### Сводка маршрутов

| Маршрут | Base / URL | Авторизация |
|---|---|---|
| A. Messages API | `https://api.kie.ai/claude/v1/messages` | `Authorization: Bearer <KEY>` |
| B. Claude Code | `https://api.kie.ai/anthropic` + `/v1/messages` клиентом | `ANTHROPIC_AUTH_TOKEN=<KEY>` или `ANTHROPIC_API_KEY=Bearer <KEY>` |
| Список моделей (B) | `GET https://api.kie.ai/anthropic/v1/models` | тот же ключ |

---

## 3. Что выбрать для этого аудита

**Маршрут A** — для первого и последующих запросов аудита. Причины:
1. Не требует настройки CLI-агента — достаточно одного HTTP-вызова.
2. Позволяет точно контролировать `max_tokens` и, следовательно, **бюджет**.
3. Легко приложить к пакету сырой JSON-ответ как доказательство.

**Маршрут B** — если владелец захочет использовать Claude Code в интерактивном режиме
для многошагового диалога. Плюс: официальный список моделей по ключу, что полезно
для проверки доступности.

> ⚠️ **Не смешивать:** префикс `Bearer` в `ANTHROPIC_AUTH_TOKEN` — частая ошибка,
> из-за которой маршрут B отвечает 401. В маршруте A, наоборот, префикс `Bearer`
> в `Authorization` обязателен.

---

## 4. Переменные окружения

```powershell
# Подставьте значение вручную. Литерал-значение в этом файле НЕ пишите.
$env:KIE_API_KEY = $env:PASTE_KEY_HERE
$env:ANTHROPIC_BASE_URL = "https://api.kie.ai/anthropic"   # только для маршрута B
$env:ANTHROPIC_AUTH_TOKEN = $env:KIE_API_KEY              # только для маршрута B
```

> 🔒 Ключ **не должен** попасть в `docs/ai-review/opus-audit-001/` — это публикуемый
> PR. Ключ хранить только в переменной окружения или в системном хранилище.
> `VALIDATION.json` проекта уже содержит правило
> «`common_token_pattern_scan`: no matches; not an exhaustive secret audit» — пакет
> аудита должен соответствовать тому же стандарту.

---

## 5. Ожидаемый расход на первый запрос (AUDIT-001A)

Пакет AUDIT-001A — самый объёмный из трёх. Оценка по фактическому размеру
материалов (см. §7):

| Сценарий | Вход | Выход | Кредиты | USD |
|---|---:|---:|---:|---:|
| Типичный | 20 000 ток. | 8 000 ток. | 6.4 + 12.8 = **19.2** | **≈ $0.096** |
| Верхняя граница | 25 000 ток. | 16 000 ток. | 8.0 + 25.6 = **33.6** | **≈ $0.168** |
| С запасом (план) | 30 000 ток. | 20 000 ток. | 9.6 + 32.0 = **41.6** | **≈ $0.208** |

Расчёт: вход = токены / 1 000 000 × 320; выход = токены / 1 000 000 × 1600.

**Планируемый максимум на весь аудит (3 пакета): ≤ $0.65 (≤ 130 кредитов).**
Это верхняя граница, а не ожидание. Фактическое списание пропорционально
возвращённым токенам.

> **Рекомендация владельцу:** выставить в KIE лимит баланса, покрывающий
> ~$1–2, и проверять остаток через `GET /anthropic/v1/models` либо через панель KIE
> **до** отправки AUDIT-001C. Это ровно тот же принцип fail-closed, который
> применяется в P0-контуре проекта.

---

## 6. Проверка подключения (без платного вызова)

### 6.1 Проверка маршрутов без ключа — уже выполнена, результат ниже

| URL | Метод | Результат (2026-10-20) | Вывод |
|---|---|---|---|
| `https://api.kie.ai/anthropic/v1/models` | GET | `HTTP 401` `{"code":401,"msg":"Unauthorized – Authentication failed…"}` | Маршрут **существует**, требует ключ |
| `https://api.kie.ai/claude/v1/messages` | GET | `{"code":404,"msg":"GET request not supported"}` | Маршрут **существует**, только POST |
| `https://api.kie.ai/anthropic/v1/messages` | GET | `{"code":404,"msg":"GET request not supported"}` | Маршрут **существует**, только POST |

**Все три маршрута живы и различаются.** Ни один платный вызов при этом не выполнен.

### 6.2 Минимальный платный тест (выполнять владельцу, отдельно от аудита)

Запускать **до** AUDIT-001A, чтобы отделить проблему подключения от проблемы аудита.
Стоимость — доли кредита.

**Маршрут A:**

```powershell
$headers = @{ 'Authorization' = "Bearer $env:KIE_API_KEY"; 'Content-Type' = 'application/json' }
$body = @{
  model      = 'claude-opus-5-5'
  max_tokens = 32
  messages   = @(@{ role = 'user'; content = 'Ответь одним словом: OK' })
} | ConvertTo-Json -Depth 5
$r = Invoke-RestMethod -Uri 'https://api.kie.ai/claude/v1/messages' -Method Post -Headers $headers -Body $body -TimeoutSec 120
$r.usage | Format-List
$r.content[0].text
```

Ожидаемый результат: `usage.input_tokens`, `usage.output_tokens`, текст ответа.

**Маршрут B (список моделей):**

```powershell
$h = @{ 'Authorization' = "Bearer $env:KIE_API_KEY" }
(Invoke-RestMethod -Uri 'https://api.kie.ai/anthropic/v1/models' -Headers $h -TimeoutSec 60).data |
  Where-Object { $_.id -like '*opus-5-5*' } | Format-Table id, display_name
```

### 6.3 Чек-лист перед AUDIT-001A

- [ ] `KIE_API_KEY` задан в окружении (не в файле репозитория)
- [ ] Минимальный тест §6.2 вернул `usage` и текст
- [ ] В ответе `model` = `claude-opus-5-5` (а не другая модель KIE по умолчанию)
- [ ] Баланс KIE достаточен (план: ≥ $1)
- [ ] `max_tokens` в первом запросе = 16 000 (это даёт верхнюю границу ~$0.21)

---

## 7. Фактический размер пакета (для оценки бюджета)

Измерено по файлам пакета `docs/ai-review/opus-audit-001/`:

| Пакет | Материал | Примерный вход |
|---|---|---|
| **AUDIT-001A** | `PROJECT_CONTEXT.md` + `ARCHITECTURE_MAP.md` + `P0_EVIDENCE.md` + разделы 1–4 `OPUS_FIRST_REQUEST.md` | 15 000–25 000 ток. |
| **AUDIT-001B** | `PROJECT_CONTEXT.md` (кратко) + `ARCHITECTURE_MAP.md` (разделы 1,4) + `WORKFLOW_EVIDENCE.md` + разделы 1–4 | 12 000–20 000 ток. |
| **AUDIT-001C** | `PROJECT_CONTEXT.md` (кратко) + `QA_EVIDENCE.md` + `TEST_RESULTS.md` + `OPEN_ISSUES.md` + разделы 1–4 | 20 000–30 000 ток. |

Оценка: 1 токен ≈ 3.2–3.5 символа для русского текста, ≈ 3.8 для кода и JSON.
Фактические числа в байтах приведены в `EVIDENCE_MANIFEST.json` → `packages[].estimated_input_tokens`.

---

## 8. Вложения: почему .md и .json не принимаются и что делать

### 8.1 Диагноз

KIE принимает файлы, но **отвергает расширения `.md` и `.json`**. Причина — не в
содержимом, а в **media_type**, который выводится из расширения:

| Расширение | media_type | Поддержка в Anthropic-совместимом Messages API |
|---|---|---|
| `.md` | `text/markdown` | **нет** — отклоняется |
| `.json` | `application/json` | **нет** — отклоняется |
| `.txt` | `text/plain` | **да** |
| `.pdf` | `application/pdf` | **да** |
| `.png` / `.jpg` | `image/*` | **да** |

То есть файл отвергается на этапе проверки типа, **до** чтения содержимого.

### 8.2 Решение

Тот же файл переименовать в `.txt` — и он принимается. Содержимое при этом **не
меняется**: те же байты, та же кодировка UTF-8, те же строки кода.

Готовые `.txt`-версии всех документов уже собраны:

```
packages/attachments/AUDIT-001A/   PROJECT_CONTEXT.txt  ARCHITECTURE_MAP.txt
                                   P0_EVIDENCE.txt      TEST_RESULTS.txt
                                   MANIFEST.txt
packages/attachments/AUDIT-001B/   ... свой набор ...
packages/attachments/AUDIT-001C/   ... свой набор ...
```

`MANIFEST.txt` в каждой папке перечисляет соответствие `.txt` → исходник.

### 8.3 Как прикрепить вручную (если инструмент — UI)

1. Открыть `packages/attachments/AUDIT-001A/`.
2. Прикрепить **все 5 `.txt`** (четыре документа + MANIFEST).
3. System prompt — из `OPUS_SYSTEM_PROMPT.md` (блок «Текст system prompt»).
4. Текст запроса — из `OPUS_FIRST_REQUEST.md` (блок «Текст запроса (копируется целиком)»).
5. Отправить.

### 8.4 Как отправить скриптом (правильный путь)

```powershell
cd docs\ai-review\opus-audit-001
python packages\build_payloads.py          # пересобрать payload и .txt-вложения
$env:KIE_API_KEY = $env:PASTE_KEY_HERE
python packages\send_audit.py AUDIT-001A --dry-run    # проверить, не отправляя
python packages\send_audit.py AUDIT-001A              # отправить
```

`send_audit.py` сам собирает запрос: system prompt в поле `system`, документы —
блоками `document` с `media_type: text/plain`, текст запроса — блоком `text`.
Ответ сохраняется в `responses/AUDIT-001A.response.json` и `.md`, печатается
`usage` и оценка стоимости в кредитах.

> **Автоматических повторов нет.** При таймауте или 5xx скрипт **не** повторяет
> запрос: неоднозначный исход — это ровно тот класс дефекта, который аудируется
> в самом проекте (`UNKNOWN` → никогда не переотправлять). Проверять исход надо
> вручную по логам KIE.

### 8.5 Готовый текстовый payload (если прикрепить нельзя вообще)

`packages/payloads/AUDIT-001A.payload.txt` — весь пакет **одним текстом**:
system prompt + материалы + запрос, в нужном порядке, с разделителями
`=== FILE: … ===`. Размеры:

| Payload | Символов | ~Токенов | В диапазоне 15–25k |
|---|---:|---:|---|
| `AUDIT-001A.payload.txt` | 63 166 | 18 856 | да |
| `AUDIT-001B.payload.txt` | 47 867 | 14 289 | чуть ниже |
| `AUDIT-001C.payload.txt` | 73 763 | 22 019 | да |

Оценка: символы / 3.35. Фактическое `usage.input_tokens` смотри в ответе KIE.

---

## 9. Ответственность и запреты

- Один вызов = один отправленный пакет. **Автоматических повторов при таймауте нет.**
  Таймаут/429/неизвестный исход = считать результат **неопределённым** и запросить
  новый раунд у владельца, а не повторять молча. Это ровно правило P0-контура
  (`UNKNOWN` → никогда не переотправлять), применённое к самому аудиту.
- Стоимость фиксируется **до** вызова: `max_tokens` и ожидаемый вход.
- Ключ никогда не попадает в пакет, в PR и в лог.
