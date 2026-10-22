# GA-01 R3 — нечитаемая сумма в общем денежном барьере (облако, 2026-10-22)

База: `minimax/ga-01-money-p0` @ `8fb6b76`. Правка: `R3_POINT_FIX.patch` (PR #77), применён без конфликтов.
Файлы: `backend/spend_ledger.py`, `backend/economics.py`, `backend/series_economics.py`, `backend/test_ga01_unreadable_barrier.py` (пять тестов R3 перенесены из probe76_r3).

Дефект: запись `llm_calls` с `usd=UNREADABLE_AMOUNT` давала TypeError (HTTP 500) в `spend_ledger.state`, `/api/budgets/{id}`, а `/api/economics` показывал `costs_complete=True`.
Поведение теперь: нечитаемая сумма считается отдельно (не ноль и не слагаемое); проект с такой записью и все проекты при записи «сегодняшнего» дня получают контролируемый отказ 400; старая запись другого проекта не блокирует; серия — 409; экономика `costs_complete=False`.

Red → green: на базе 4 из 5 тестов падают, с правкой 5/5 PASS.
Проверки (облако, без сети/платных вызовов): `pytest backend` — 553 passed, exit 0; `unittest backend.test_llm_settlement` — 61 OK; probe76/r2_restart/r2_matrix — 15 passed, 2 skipped.
Не проверялось: CI GitHub Actions, миграция рабочей SQLite (не выполнялась и не разрешена).

OWNER_DECISION_REQUIRED: как владелец закрывает нечитаемую запись (ручная сверка) — обход не реализован; блокировка остаётся до решения.
Статус: READY_FOR_OWNER_REVIEW (не принято владельцем).
