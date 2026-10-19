# GremoVOD — настройка моста MiniMax → KIE Gemini 4 Argon (Windows)

**Статус реализации:** ЭТАП A, 100% OFFLINE. Код, тесты и примеры готовы.
**Платные запросы KIE не выполнялись.** LIVE включается владельцем вручную, по инструкции ниже.

Связанные документы: `docs/experiments/MINIMAX_ARGON_KIE_BRIDGE_METHOD_RU.md` (методичка),
`docs/ai-review/MINIMAX_ARGON_KIE_IMPLEMENTATION_PROMPT_RU.md` (задание),
`docs/ai-review/ARGON_KIE_MINIMAX_REPORT_RU.md` (отчёт о реализации).

---

## 1. Что где лежит

| Файл | Роль |
|---|---|
| `tools/ai_review/argon_review.py` | существующий ручной ревьюер (PR #22). Добавлен общий транспорт KIE и `fetch_credits`; старые контракты не сломаны |
| `tools/ai_review/build_review_packet.py` | **новый.** Собирает замороженный evidence-пакет из реального Git diff |
| `tools/ai_review/review_gate.py` | **новый.** Бюджетный шлюз: OFFLINE/LIVE, лимиты, ledger, учёт кредитов, отчёт |
| `tests/test_argon_review_gate.py` | **новый.** Офлайн-тесты шлюза (сеть не используется) |
| `scripts/make_argon_examples.py` | **новый.** Пересоздаёт санитизированные примеры в `docs/ai-review/examples/` |
| `docs/ai-review/examples/` | **новый.** Пример запроса, пример ответа KIE, пример санитизированного отчёта |

`argon_review.py` не переписан: `snapshot()`, `make_prompt()`, `ask_argon()` и `write_report()` сохранили
прежнее поведение. Добавлены `snapshot_wide()`, `ask_argon_detailed()`, `fetch_credits()`, `ProviderError`.

---

## 2. Установка (Windows)

Нужен Python 3.11+ и Git. Всё работает из корня репозитория, без установки пакетов.

```powershell
cd C:\Users\BLOWKA\Documents\Minimax\gremovod-argon-bridge
python -X utf8 -m unittest discover -s tests -p "test_*.py"
```

Ожидаемый результат: `Ran 41 tests ... OK`. Ни один тест не обращается в сеть.

---

## 3. Переменные окружения (только имена, значения не в репозитории)

| Имя | Назначение | По умолчанию |
|---|---|---|
| `KIE_API_KEY` | ключ KIE. Только локально, никогда в чат и никогда в коммит | нет → LIVE заблокирован |
| `ARGON_REVIEW_STATE_DIR` | каталог ledger, пакетов и слотов | `~\.gremovod\argon-review` |
| `ARGON_MAX_CALLS_PER_PR` | максимум вызовов Argon на один PR | `1` |
| `ARGON_MAX_CALLS_PER_DAY` | максимум вызовов в сутки (UTC) | `2` |
| `ARGON_MAX_CALLS_PER_WEEK` | максимум вызовов за 7 суток | `5` |
| `ARGON_MAX_CONCURRENT` | одновременных платных вызовов | `1` |
| `ARGON_MAX_PACKET_BYTES` | потолок сериализованного user payload | `6144` (6 КиБ) |
| `ARGON_MAX_PACKET_FILES` | максимум файлов в пакете | `4` |
| `ARGON_RETRY_COUNT` | **всегда 0.** Значение ≠ 0 блокирует запуск | `0`, изменить нельзя |
| `ARGON_MAX_KIE_CREDITS_PER_DAY` | потолок кредитов KIE за сутки | **не задан → LIVE заблокирован** |
| `ARGON_MAX_KIE_CREDITS_PER_CALL` | оценка максимальной цены одного вызова | **не задан → LIVE заблокирован** |
| `ARGON_MIN_KIE_BALANCE` | неснижаемый остаток кредитов | **не задан → LIVE заблокирован** |
| `ARGON_CREDIT_DELTA_TOLERANCE` | допуск расхождения «списал ответ» / «увидел баланс» | `1.0` |
| `ARGON_EMERGENCY_STOP` | аварийный стоп без файла | `0` |

Три кредитных лимита не имеют значений по умолчанию **намеренно**: без тарифа нельзя честно выбрать
число, а «цену неизвестна» означает, что LIVE заблокирован. Кредиты — не USD; `usd_amount` в ledger
всегда `null`, пока владелец не подтвердит тариф.

---

## 4. Офлайн-команды (расход 0, сети нет)

### 4.1 Собрать пакет и посмотреть, что уйдёт провайдеру

```powershell
python -X utf8 tools/ai_review/build_review_packet.py `
  --repo . --base origin/main --head HEAD `
  --pr-url "https://github.com/gremoled77-droid/gremovod/pull/33" `
  --task-id "ARGON-BRIDGE" `
  --scope "Проверь реализацию офлайн-моста: лимиты, ledger, отсутствие сетевых вызовов" `
  --summary "MiniMax: добавлены build_review_packet/review_gate + тесты" `
  --test "python -X utf8 -m unittest discover -s tests -p test_*.py" `
  --link "https://github.com/gremoled77-droid/gremovod/pull/33/files" `
  --out "$env:TEMP\argon-packet.json"
```

Печатает `base_sha`, `head_sha`, `diff_sha256`, число файлов/hunks, `payload bytes` и `payload_sha256`.
Если `payload bytes` больше 6144 — пакет не соберётся, это защита, а не ошибка.

### 4.2 Прогнать шлюз в режиме OFFLINE (по умолчанию)

```powershell
python -X utf8 tools/ai_review/review_gate.py `
  --repo . --base origin/main --head HEAD `
  --pr-url "https://github.com/gremoled77-droid/gremovod/pull/33" `
  --task-id "ARGON-BRIDGE" --scope "..." `
  --mode offline `
  --state-dir "$env:LOCALAPPDATA\GremoVOD\argon-review" `
  --report "$env:TEMP\argon-report.md"
```

Результат: `status: OFFLINE`, `network calls: 0`. Снимок пакета кладётся в
`<state-dir>\packets\<payload_sha256>.json` — **вне репозитория**.

### 4.3 Пересоздать примеры

```powershell
python -X utf8 scripts/make_argon_examples.py
```

Детерминированно: фиксированные автор, дата и содержимое синтетического репозитория.

---

## 5. Включение LIVE (этап B) — только после отдельного разрешения владельца

Порядок обязателен. Каждый шаг можно выполнить отдельно и посмотреть на результат.

### Шаг 1. Владелец задаёт бюджет

```powershell
$env:ARGON_MAX_KIE_CREDITS_PER_DAY = "20"    # потолок за сутки
$env:ARGON_MAX_KIE_CREDITS_PER_CALL = "5"    # оценка цены одного вызова
$env:ARGON_MIN_KIE_BALANCE      = "50"       # не опускать баланс ниже этого
```

Без этих трёх переменных LIVE не запустится — шлюз вернёт `BLOCKED / no_budget_policy`.

### Шаг 2. Ключ в локальное окружение

```powershell
$env:KIE_API_KEY = "<ключ из менеджера секретов>"
```

Ключ не передаётся в чат, не пишется в `.env` репозитория, не попадает в коммит и в отчёт.

### Шаг 3. Одобрение владельца на конкретный PR и SHA

Файл `approval.json` (например `%LOCALAPPDATA%\GremoVOD\argon-review\approval.json`):

```json
{
  "approved": true,
  "pr": "https://github.com/gremoled77-droid/gremovod/pull/33",
  "head_sha": "<полный 40-символьный SHA текущего head PR>"
}
```

Одобрение одноразовое и привязано к SHA. Поле `head_sha` **обязательно**: одобрение без него
не проходит (`PENDING_APPROVAL / approval_stale`), иначе ревью прошло бы по любому коммиту.
Новый коммит делает одобрение недействительным. Сам шлюз никогда не выдаёт себе разрешения.

### Шаг 4. Один проверочный запрос

```powershell
python -X utf8 tools/ai_review/review_gate.py `
  --repo . --base origin/main --head HEAD `
  --pr-url "https://github.com/gremoled77-droid/gremovod/pull/33" `
  --task-id "ARGON-BRIDGE" --scope "..." --summary "..." `
  --test "python -X utf8 -m unittest discover -s tests -p test_*.py" `
  --mode live `
  --approval "$env:LOCALAPPDATA\GremoVOD\argon-review\approval.json" `
  --expected-head-sha "<полный SHA, который одобрил владелец>" `
  --state-dir "$env:LOCALAPPDATA\GremoVOD\argon-review" `
  --report "$env:TEMP\argon-report.md"
```

Один запуск = **не более одного** платного запроса. Повторный запуск на том же PR/SHA вернёт
`BLOCKED / no_new_call` и новых кредитов не потратит.

### Шаг 5. Разбор замечаний без цикла

Замечания Argon разбираются в новом коммите. Повторное платное ревью — **только по новому SHA** и
**только с новым одобрением**. Автоматической перезапроса нет: `RETRY_COUNT` принудительно 0,
повтор того же пакета дедуплицируется по `(repo, PR, head_sha, payload_sha256)`.

Если Argon вернул `NEED_CONTEXT`, шлюз пишет `BLOCKED / need_context` и **не** делает второй вызов.
Эскалация (уровень B) — отдельный пакет по указанным путям, отдельное одобрение, новый
`payload_sha256` и отдельное решение владельца по повышению `ARGON_MAX_CALLS_PER_PR`.

---

## 6. Аварийный стоп

Любой из двух способов останавливает все LIVE-вызовы мгновенно:

```powershell
# 1. файл-флаг в каталоге состояния
New-Item -ItemType File -Force "$env:LOCALAPPDATA\GremoVOD\argon-review\STOP"

# 2. переменная окружения
$env:ARGON_EMERGENCY_STOP = "1"
```

Результат: `BLOCKED / emergency_stop`, сеть не трогается. Снять стоп: удалить файл `STOP` и
снять переменную.

Дополнительно: `python -X utf8 tools/ai_review/review_gate.py --mode live ...` никогда не
повторяет запрос после 429, 5xx, тайм-аута или обрыва. Такой исход фиксируется как
`HALTED_UNKNOWN` с одной попыткой и без ретрая.

---

## 7. Где лежат артефакты

| Артефакт | Путь | В репозиторий? |
|---|---|---|
| Ledger записей о вызовах | `<state-dir>\ledger.json` | нет |
| Снимок отправленного пакета | `<state-dir>\packets\<payload_sha256>.json` | нет |
| Сырой ответ Argon | `<state-dir>\answers\<ledger_id>.txt` | нет |
| Слоты одновременных вызовов | `<state-dir>\inflight\slot-N.json` | нет |
| Флаг аварийного стопа | `<state-dir>\STOP` | нет |
| Санитизированный отчёт | куда укажет `--report` | **да**, это единственное, что можно коммитить |

Отчёт не содержит тела diff, сырого ответа провайдера, ключа и кредитов в денежном выражении.
В отчёте остаются только разобранные findings (путь, строка, severity, короткая цитата, исправление,
тест). Перед записью текст проходит через регулярку секретов и через маскирование длинных
непрозрачных токенов; git SHA и дайджесты остаются читаемыми.

---

## 8. Таблица статусов

| Ситуация | Статус | Сеть? |
|---|---|---|
| Режим OFFLINE, пакет собран | `OFFLINE` | нет |
| Пакет не влезает в 6 КиБ | `BLOCKED / packet_too_large` | нет |
| В diff найден секрет | `BLOCKED / unsafe_diff` | нет |
| Пустой diff | `BLOCKED / empty_diff` | нет |
| Нет одобрения или оно устарело | `PENDING_APPROVAL` | нет |
| Сменился head SHA | `BLOCKED / pr_head_drift` | нет |
| Нет `KIE_API_KEY` | `BLOCKED / no_api_key` | нет |
| Не заданы кредитные лимиты | `BLOCKED / no_budget_policy` | нет |
| Баланс ниже пола или не читается | `BLOCKED / insufficient_balance` / `balance_unknown` | нет |
| Исчерпан лимит или повтор пакета | `BLOCKED / no_new_call` | нет |
| Уже есть один вызов в полёте | `BLOCKED / no_new_call: concurrency limit` | нет |
| Включён аварийный стоп | `BLOCKED / emergency_stop` | нет |
| Ответ Argon: `PASS` | `PASS` | 1 запрос |
| Ответ Argon: `FINDINGS` | `FINDINGS` | 1 запрос |
| Ответ Argon: `NEED_CONTEXT` | `BLOCKED / need_context` | 1 запрос |
| Ответ Argon: `UNSURE` | `HALTED_UNKNOWN / model_unsure` | 1 запрос |
| `PASS`, но в ответе есть findings | `HALTED_UNKNOWN / contradictory_verdict` | 1 запрос |
| Ответ не JSON / пустой / неизвестный вердикт | `HALTED_UNKNOWN` | 1 запрос |
| HTTP 429, 5xx, тайм-аут, обрыв | `HALTED_UNKNOWN` | 1 попытка, **0 ретраев** |
| HTTP 401/403 | `BLOCKED / auth_failed` | 1 попытка, 0 ретраев |
| Списания не сходятся с балансом или выше потолка за вызов | `HALTED_UNKNOWN / credit_accounting_mismatch` | 1 запрос |

`PASS` от Argon — это не PASS тестов и не разрешение на merge. Решение принимает владелец.

---

## 9. Как включить контролируемый автоматический режим (этап D)

Автоматика включается **владельцем** и только внутри жёстких лимитов. Модель не может поднять лимит
и не может выдать себе разрешение: лимиты читаются из окружения, одобрение — из файла, который
готовит человек.

1. Владелец фиксирует числа лимитов (шаг 1 раздела 5) и держит их в своём окружении, а не в репозитории.
2. На каждое одобрение ставится срок: одобрение привязано к SHA, и новый коммит его гасит.
3. Один процесс-исполнитель запускает `review_gate.py --mode live` на выбранном PR.
   Второй параллельный запуск того же PR отсекается ledger'ом и слотом одновременности.
4. Исполнитель **не** вызывает шлюз повторно автоматически: следующий шаг требует нового коммита,
   нового SHA и нового одобрения.
5. Отчёты складываются в Draft PR в разделе Conversation. Секреты и тело diff в PR не попадают.
6. Уведомление (в будущем n8n Cloud) — только витрина: короткий `run-summary` со ссылками на PR и
   отчёт. n8n не вызывает KIE, не хранит ключи и не может поднять лимит.

Ожидаемый расход при значениях по умолчанию: **не более 1 вызова на PR, 2 в сутки, 5 в неделю,
1 одновременно, 0 ретраев**. Это верхняя граница, а не цель.

---

## 10. Чего этот PR не делает

- Не вызывает KIE и не тратит кредиты.
- Не меняет `main`, GPT-6 Sol / KIE Proxy v2 (порт 8767), рабочие SQLite, медиа и канон.
- Не подключает n8n Cloud и не создаёт workflow.
- Не автоматически повторяет платные вызовы и не поднимает лимиты.
- Не даёт Argon права писать в репозиторий: провайдер получает только текстовый запрос.
