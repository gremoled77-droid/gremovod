# GremoVOD — отчёт о реализации моста MiniMax → KIE Gemini 4 Argon

**Дата:** 2026-10-20 · **Ветка:** `experiment/minimax-kie-argon-bridge-impl-20261020`
**Коммит кода:** `7d625fb21eff9fb4f808b90f33c789308ed06ba0`
**Draft PR:** https://github.com/gremoled77-droid/gremovod/pull/34 (draft)
**База стека:** PR #33 `experiment/minimax-kie-argon-bridge-20261019` = `0ac4e916e274b4c75fde75edc1ddd0d5a3e376c1`
**Расход:** **0 кредитов. LIVE не запускался. Ключ KIE не использовался.**

---

## 1. Что есть, что сделано, что заблокировано

| Область | Состояние | Где |
|---|---|---|
| Ручной Argon-ревьюер, OFFLINE по умолчанию | **было** (PR #22) | `tools/ai_review/argon_review.py` |
| Методичка и задание | **было** (PR #33) | `docs/experiments/…METHOD_RU.md`, `docs/ai-review/…PROMPT_RU.md` |
| Общий транспорт KIE с классификацией ошибок | **сделано** | `argon_review.py`: `_post_chat`, `ProviderError`, `ask_argon_detailed`, `fetch_credits`, `snapshot_wide` |
| Сборка замороженного evidence-пакета | **сделано** | `tools/ai_review/build_review_packet.py` |
| Бюджетный шлюз OFFLINE/LIVE | **сделано** | `tools/ai_review/review_gate.py` |
| Атомарный ledger, резервирование до HTTP | **сделано** | `review_gate.Ledger` |
| Учёт кредитов, `usd_amount` всегда null | **сделано** | `review_gate._account`, `review_gate.Ledger.finalize` |
| Санитизированный отчёт + редакция секретов | **сделано** | `review_gate.render_report`, `review_gate.redact` |
| Офлайн-тесты (41 новый) | **сделано** | `tests/test_argon_review_gate.py` |
| Инструкция по настройке и включению LIVE | **сделано** | `docs/ai-review/ARGON_KIE_MINIMAX_SETUP_RU.md` |
| Воспроизводимые примеры запроса/ответа/отчёта | **сделано** | `docs/ai-review/examples/`, `scripts/make_argon_examples.py` |
| Один платный запрос Argon по выбранному PR/SHA | **заблокировано** | нет ключа, нет одобрения, нет кредитных лимитов, нет разрешения владельца |
| Уровень B (эскалация по `NEED_CONTEXT`) | **не автоматизировано** | нужен отдельный пакет, отдельное одобрение, новый hash и решение владельца по `ARGON_MAX_CALLS_PER_PR` |
| n8n Cloud как диспетчер/витрина | **отложено** | этап после B, отдельное разрешение |
| Тариф Argon в USD | **неизвестно** | без подтверждённого тарифа `usd_amount` остаётся `null` |

---

## 2. Файлы, коммиты, PR

Коммит кода: `7d625fb21eff9fb4f808b90f33c789308ed06ba0` — «feat: add budget-gated OFFLINE Argon KIE review bridge».

| Файл | Действие | Назначение |
|---|---|---|
| `tools/ai_review/build_review_packet.py` | новый | Замороженная пара SHA, реальные hunks реального diff, ранжирование критичности, потолок 6 КиБ и 4 файла |
| `tools/ai_review/review_gate.py` | новый | OFFLINE/LIVE, лимиты, ledger, учёт кредитов, санитизированный отчёт |
| `tools/ai_review/argon_review.py` | изменён | Общий транспорт вынесен наружу; `snapshot()`, `make_prompt()`, `ask_argon()`, `write_report()` не сломаны |
| `tests/test_argon_review_gate.py` | новый | 41 офлайн-тест |
| `scripts/make_argon_examples.py` | новый | Детерминированная генерация примеров |
| `docs/ai-review/ARGON_KIE_MINIMAX_SETUP_RU.md` | новый | Установка, офлайн-команды, безопасное включение LIVE, аварийный стоп, контролируемый автоматический режим |
| `docs/ai-review/examples/argon_review_request.example.json` | новый | Пример реального тела запроса |
| `docs/ai-review/examples/argon_review_response.example.json` | новый | Пример ответа KIE |
| `docs/ai-review/examples/argon_review_report.example.md` | новый | Пример санитизированного отчёта |
| `docs/ai-review/ARGON_KIE_MINIMAX_REPORT_RU.md` | новый | Этот отчёт |
| `.gitignore` | изменён | `tools/ai_review` возвращён под контроль версий |

### Почему тронут `.gitignore`

Правило `tools/` в `.gitignore` молча игнорировало новые файлы внутри `tools/ai_review/`:
`tools/ai_review/argon_review.py` из PR #22 попал в репозиторий только через принудительный `git add -f`.
Добавлена точечная инверсия (`!tools/` → `tools/downloads/` → `tools/ffmpeg/` → `!tools/ai_review/`), поэтому
новые файлы шлюза видны `git status`, а локальные бинарники (`tools/downloads/`, `tools/ffmpeg/`) и `__pycache__`
остались проигнорированными. Проверено: `git check-ignore` даёт «не игнорируется» для трёх новых файлов
и «игнорируется» для `__pycache__`, `tools/downloads/` и `tools/ffmpeg/`.

---

## 3. Тесты: что именно и с каким результатом

```
python -X utf8 -m unittest discover -s tests -p "test_*.py"
Ran 46 tests in 36s
OK
```

46 = 5 из PR #22 (не изменялись) + 41 новых. **Ни один тест не обращается в сеть:** провайдер
(`provider`) и чтение баланса (`credits_reader`) внедряются параметрами, ключ в тестах — фиктивный.

| Сценарий из методички | Тест | Ожидаемый статус |
|---|---|---|
| Два параллельных запроса | `test_parallel_requests_make_at_most_one_reservation` | одна резервация, один вызов провайдера, второй `BLOCKED / no_new_call` |
| Повтор того же PR/SHA | `test_repeated_pr_and_sha_is_no_new_call` | `BLOCKED / no_new_call`, провайдер не вызван второй раз |
| 429 | `test_rate_limit_is_halted_unknown_with_zero_retry` | `HALTED_UNKNOWN / rate_limited`, 1 попытка, 0 ретраев |
| Тайм-аут | `test_timeout_is_halted_unknown_with_zero_retry` | `HALTED_UNKNOWN / timeout`, 1 попытка, 0 ретраев |
| Нет ключа | `test_missing_key_budget_or_approval_makes_no_network_call` | `BLOCKED / no_api_key`, **0 сетевых вызовов** |
| Нет бюджета | то же | `BLOCKED / no_budget_policy`, 0 сетевых вызовов |
| Нет одобрения | то же | `PENDING_APPROVAL`, 0 сетевых вызовов |
| Пустой diff | `test_empty_diff_is_refused` | `BLOCKED / empty_diff` |
| Oversized packet | `test_oversized_packet_is_refused` | `BLOCKED / packet_too_large` |
| Секрет в diff | `test_secret_in_diff_is_refused` | `BLOCKED / unsafe_diff` |
| Смена head SHA | `test_pr_head_drift_is_a_hard_stop` | `BLOCKED / pr_head_drift` |
| Устаревшее одобрение | `test_stale_approval_for_another_sha_is_not_accepted` | `PENDING_APPROVAL / approval_stale` |
| Некорректный JSON | `test_malformed_json_is_never_pass` | `HALTED_UNKNOWN / response_not_json` |
| Заражённый ответ | `test_contaminated_provider_answer_is_redacted_from_the_report` | секрет заменён на `[REDACTED]` |
| Скачок баланса | `test_balance_jump_is_flagged_and_does_not_report_pass` | `accounting: MISMATCH`, статус `HALTED_UNKNOWN` |
| Отказ от записи | `test_the_gate_never_writes_to_the_repository` | `git status`, HEAD, refs и список файлов не изменились |

Дополнительно закрыты: битый ledger → fail-closed, каталог состояния внутри репозитория → отказ,
`ARGON_RETRY_COUNT ≠ 0` → отказ, слот одновременности освобождается и не блокирует навсегда,
аварийный стоп, дневной кредитный потолок, суммирование расхода за сутки, неизменность старого
контракта `ask_argon`.

### Что проверить не удалось

`python -X utf8 -m unittest discover -s backend -p "test_*.py"` **не запускается в этом окружении**:
не установлен `fastapi` (`ModuleNotFoundError: No module named 'fastapi'`). Это предсуществующий пробел
окружения, а не регрессия: коммит `7d625fb` не меняет ни одного файла в `backend/`. Проверка выполнялась
на чистом дереве без `fastapi` и падает так же до и после коммита.

---

## 4. Мок-пример запроса и ответа

Полные файлы: `docs/ai-review/examples/`. Детерминированно пересоздаются командой
`python -X utf8 scripts/make_argon_examples.py` (синтетический репозиторий в системном temp, фиксированные
автор и дата, никакой сети).

**Тело запроса** (ровно то, что уходит в KIE; поля `model` нет — маршрут фиксирован endpoint'ом,
`tools` нет, `stream: false`):

```json
{
  "messages": [
    {"role": "system", "content": "Ты — независимый строгий ревьюер GremoVOD. …"},
    {"role": "user", "content": "{\"base_sha\":\"…\",\"diff_sha256\":\"…\",\"hunks\":[…],\"head_sha\":\"…\", …}"}
  ],
  "stream": false
}
```

Пользовательский payload — 1172 байта из 6144; 1 hunk, 1 файл, поле `selection.partial_packet: true`
сообщает Argon'у, что пакет неполный.

**Ответ KIE** (мок):

```json
{
  "id": "chatcmpl-example-0001",
  "choices": [{"index": 0, "message": {"role": "assistant", "content": "{\"verdict\":\"FINDINGS\", …}"},
               "finish_reason": "stop"}],
  "usage": {"prompt_tokens": 1200, "completion_tokens": 180, "total_tokens": 1380},
  "credits_consumed": 1.5
}
```

**Отчёт шлюза** по этому ответу: `Status: FINDINGS`, `credits_before: 100.0`, `credits_after: 98.5`,
`credits_consumed: 1.5`, `usd_amount: None`, `accounting: OK`, `Network calls: 1`.

---

## 5. Риски и что нужно от владельца

### Риски

1. **Цена неизвестна.** Пока тариф не подтверждён, `usd_amount` = `null` и верхняя оценка цены одного
   вызова задаётся владельцем через `ARGON_MAX_KIE_CREDITS_PER_CALL`. Без неё LIVE заблокирован — это
   осознанный fail-closed.
2. **Пакет неполный.** Argon видит до 4 файлов и критические hunks. Об остальном он не знает и может
   выдать `NEED_CONTEXT` или `UNSURE`. Это не дефект вердикта, а свойство экономии; `selection.partial_packet`
   сообщает об этом явно.
3. **Эвристика критичности.** Ранжирование hunks — детерминированная эвристика по имени файла и по
   опасным конструкциям в добавленных строках. Она может пропустить неочевидный, но дорогой дефект.
   Компенсация: `files_omitted` в пакете и в отчёте показывает, что не попало в ревью.
4. **Ложный PASS.** Argon PASS означает «в переданном hunks обоснованных дефектов не нашёл», а не
   «код корректен». В отчёте это зафиксировано строкой «Argon PASS is not a test PASS and is not a
   permission to merge».
5. **Баланс KIE — общий с другими инструментами.** `MIN_KIE_BALANCE` защищает от выхода в ноль, но
   другие потребители кредитов из того же аккаунта в баланс не видны.
6. **Файловое состояние.** Ledger, пакеты и слоты лежат в `%LOCALAPPDATA%\GremoVOD\argon-review`.
   Очистка этого каталога вручную обнулит счётчики — ledger'ом нужно пользоваться, а не удалять его.
   Слоты, оставшиеся от упавшего процесса, устаревают через 15 минут и перестают блокировать вызовы.

### Что нужно от владельца (в порядке важности)

1. **Числа кредитных лимитов** — `ARGON_MAX_KIE_CREDITS_PER_DAY`, `ARGON_MAX_KIE_CREDITS_PER_CALL`,
   `ARGON_MIN_KIE_BALANCE`. Без них LIVE не запустится.
2. **Разрешение на один проверочный запрос** по выбранному PR и SHA (этап B). Одобрение — файл
   `approval.json`, привязанный к SHA; новый коммит его гасит.
3. **Подтверждение тарифа** Argon, чтобы `usd_amount` перестал быть `null`.
4. **Решение по автоматике** (этап D): поднять ли `ARGON_MAX_CALLS_PER_PR` до 2 для эскалации уровня B.
   По умолчанию остаётся 1 — то есть ровно один платный вызов на PR.
5. **Решение по n8n Cloud** — только диспетчер/витрина, без ключей и без `Execute Command`.

---

## 6. Передача Codex (25 октября)

1. Ветка `experiment/minimax-kie-argon-bridge-impl-20261020`, коммит кода `7d625fb`, Draft PR #34
   (база — head PR #33). Стек: **#33 → #34**. `main` не тронут.
2. Сначала прочитать `docs/ai-review/ARGON_KIE_MINIMAX_SETUP_RU.md` — там команды офлайн-режима,
   порядок включения LIVE, аварийный стоп и раздел 9 про контролируемый автоматический режим.
3. Проверка: `python -X utf8 -m unittest discover -s tests -p "test_*.py"` → `Ran 46 tests … OK`.
   Backend-тесты в этом окружении не идут (нет `fastapi`); на машине с `fastapi` — обязательно прогнать.
4. **Первый шаг к Argon — этап A, только OFFLINE.** Показать владельцу: список файлов, тесты, мок-пример
   запроса и отчёта, расход 0. Затем запросить одобрение на LIVE.
5. Никаких платных вызовов без одобрения владельца. Никаких автоматических повторов.
6. Если владелец включает автоматику — лимиты живут в окружении владельца, а не в репозитории;
   сам шлюз не может ни поднять лимит, ни выдать себе разрешение.

---

## 7. Чего этот PR не делает

- Не вызывает KIE и не тратит кредиты.
- Не меняет `main`, GPT-6 Sol / KIE Proxy v2 (порт 8767), рабочие SQLite, медиа и канон.
- Не подключает n8n Cloud и не создаёт workflow.
- Не автоматически повторяет платные вызовы и не поднимает лимиты.
- Не даёт Argon права писать: провайдер получает только текстовый запрос.
