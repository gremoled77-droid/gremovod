# Ретест GA-01 PR #76 после MiniMax R2

**Вердикт: CHANGES_REQUESTED (узкий, один круг, R3).** Четыре замечания из PR #77 закрыты; денежный барьер fail-closed, обхода не найдено. Но новый маркер `UNREADABLE_AMOUNT` ломает барьер и отчёты вне `llm_guard.py` — воспроизводимо, есть тест и готовая правка.

- PR #76: `minimax/ga-01-money-p0` → `minimax/ga-01-llm-settlement` (#58). Base `c634c0c`.
- Проверяемый HEAD: `8fb6b76e3bc8dee0f305c0298d510599beba26e2` (ранее `481f798`; коммиты `e01aaeb` fix, `8fb6b76` handoff).
- CI на #76: validate-agent-handoff SUCCESS, check-agent-scope SKIPPED, backend tests не запускаются в CI.
- Область файлов: `backend/llm_guard.py`, `backend/test_llm_settlement.py`, один handoff — в рамках. Production SQLite не трогалась, платных вызовов нет, merge нет.

## Исходные негативные тесты (те же контракты, без ослабления)

| Замечание | Результат на `8fb6b76` |
|---|---|
| P1-A: `done` без суммы | закрыто: 422 «нужна названная сумма», резерв не становится фактом |
| P1-B: битый `estimated_usd`/`usd` | закрыто: старт не падает (`'bad'`, NULL, −5, inf, `'nan'`), повторный старт идемпотентен |
| P1-C: `done` с `usd` > `confirmed_usd` | закрыто: `summary`: `usd 0.5 = confirmed 0.1 + unknown 0.4`, `unknown_calls 1` |
| P2-A: дробные/огромные токены | закрыто: `token_count(1.5, 1e30, inf, nan, -1, True, '12', 120.0)` → `None`, `confirmed_usd ≤ usd` |
| PR #65 контракты (GA-01 runtime+migration) | 7/8; красный только GA-02 `prepare_task` (не GA-01, вне задачи) |

## Тесты

| Проверка | Результат |
|---|---|
| `unittest backend.test_llm_settlement` | 61 OK |
| `pytest backend` на `8fb6b76` | **548 passed**, 39 subtests, rc=0 (211 с) |
| Те же + мои 5 тестов R3 + правка | 553 passed, rc=0 |
| Перезапуск и миграция (временная база, 3 запуска подряд, полное приложение) | health 200 ×3, записи после 1-го запуска не меняются; `neg-est` → резерв 0.25 по оценке, `text-usd` → по токенам, `neg-bad` → `unreadable` + `OWNER_DECISION_REQUIRED`, старая заметка сохранена |

## Новый блокер: `UNREADABLE_AMOUNT` во внешних потребителях (P1)

Два проекта на временной базе, A — строка `submission_unknown`, `usd='unreadable'`; B — чистый.

| Путь | A (строка есть) | B (строка старше суток) | B (строка сегодняшняя) |
|---|---|---|---|
| LLM `agents/run` | **409** контролируемо | 200 | **TypeError → 500** |
| Медиа `model-jobs` | **TypeError → 500** | дошло до провайдера (ожидаемо) | **TypeError → 500** |
| `GET /api/budgets/{id}` | **TypeError → 500** | 200 | **TypeError → 500** |
| `GET /api/economics` | `llm.usd=0.0`, **`costs_complete=True`** | чисто | чисто |

Причина: `spend_ledger.state` складывает `r["usd"]` (`'unreadable'`) → `TypeError`; `security.check_budget` ловит только `BudgetExceeded`. Экономика берёт `llm['usd']` без `unreadable_calls`, а `costs_complete` считается только по генерациям.

Что это значит:
- Деньги **не уходят**: ни одна платная операция не прошла (fail-closed подтверждён).
- Но отказ — необработанный 500, а не понятная причина; экран бюджета владельца падает ровно тогда, когда должен показать строку, ждущую его решения; сегодняшняя строка роняет все проекты без объяснения.
- Отчёт «Экономика» показывает повреждённую запись как `$0.0` и «все расходы известны» — это и есть «ноль вместо неизвестного».
- Тесты R2 проверяют только `llm_guard.spent/check_budget` для того же проекта (`test_unreadable_amount_blocks_spending_until_the_owner_decides`), поэтому дыры не видят.

## Воспроизведение и правка (R3)

- Красные тесты: `tests/probe76_r3_unreadable_barrier.py` (5 тестов: 3 ERROR TypeError, 1 FAIL `costs_complete`, 1 охранный — старая строка не останавливает другой проект). Скопировать в `backend/test_ga01_unreadable_barrier.py` или перенести в `test_llm_settlement.py`.
- Правка: `R3_POINT_FIX.patch` (+18/−2): `spend_ledger.state` отделяет нечитаемые строки и отдаёт `llm_unreadable_project/daily`; `spend_ledger.check` отказывает контролируемо (`BudgetExceeded` → 400); `economics.report` — `costs_complete=False` и `llm_unreadable_calls`; `series_economics.check_budget` — 409. Дневной блок только для сегодняшней строки; проект с чистой/старой историей не страдает.
- Проверено: красные → зелёные, `unittest backend.test_llm_settlement` 61 OK, `pytest backend` 553 passed.
- **Правка выходит за разрешённую область MiniMax** (`spend_ledger.py`, `economics.py`, `series_economics.py`): нужно явное разрешение владельца на эти три файла.

## Остаётся (не блокирует R3)

- Экран «Экономика» не читает `llm_unreadable_calls` (frontend не менялся) — P2: показать предупреждение.
- `series_economics.check_budget` без лимита серии строку не учитывает — покрывает общий барьер.
- GA-02 `prepare_task` NameError (`task_identity`) — не GA-01, блокирует GA-02.
- Тесты бэкенда не входят в CI #76 (`NOT_RUN`).

## OWNER_DECISION_REQUIRED

1. Разрешить правку `spend_ledger.py`, `economics.py`, `series_economics.py` в #76 (R3) — **иначе** маркер `unreadable` оставит 500/«нулевую» экономику.
2. Что делать с реальной строкой, у которой нет оценки и токенов (`usd='unreadable'`): владелец называет сумму или потолок резерва; без решения траты проекта остановлены.
3. Принять ли сегодняшнюю нечитаемую строку как глобальную остановку трат (рекомендую: да, пока сумма неизвестна).

Остальные решения GA-01 (D1–D4) не затронуты. Принятие GA-01 владельцем — за ним; здесь не заявляется.
