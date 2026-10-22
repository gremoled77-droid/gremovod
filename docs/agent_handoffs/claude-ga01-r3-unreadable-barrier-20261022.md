# claude — GA-01 R3: нечитаемая сумма в общем денежном барьере

- Статус: `READY_FOR_OWNER_REVIEW`. Merge не выполнялся. GA-02 не начинался.
- Сделано: перенесён без изменений `R3_POINT_FIX.patch` из ретеста PR #77 (`docs/audits/claude-review-ga01-pr76-20261022/`,
  коммит `25e7423`) на точный HEAD PR #76 `8fb6b76e3bc8dee0f305c0298d510599beba26e2`; добавлен штатный тест
  `backend/test_ga01_unreadable_barrier.py`. Бюджетная архитектура не переписывалась.
- Разрешение владельца: расширение области на `spend_ledger.py`, `economics.py`, `series_economics.py` дано
  в задаче «GA-01 R3» 22.10.2026 (OWNER_DECISION 1 из ретеста).
- Файлы: `backend/spend_ledger.py`, `backend/economics.py`, `backend/series_economics.py`,
  `backend/test_ga01_unreadable_barrier.py`, этот handoff.
- Следующий шаг: владелец смотрит Draft PR (база `minimax/ga-01-money-p0`) и решает, вливать ли его в #76.
- Блокировки для Codex: нет.

## Что меняет правка

| Путь | До (`8fb6b76`) | После |
|---|---|---|
| Медиа проекта с нечитаемой строкой (голос идёт через тот же `security.check_budget` — по коду, без теста) | `TypeError` → 500 | 400 «Учёт расходов повреждён…», провайдер не вызывается |
| LLM проекта с нечитаемой строкой | 409 (R2) | 409 (без изменений) |
| Сегодняшняя нечитаемая строка, любой другой проект (медиа, LLM) | `TypeError` → 500 | 400, траты остановлены по дневному лимиту |
| Старая нечитаемая строка, другой проект | проходит | проходит (изоляция проектов) |
| `GET /api/budgets/{id}` | `TypeError` → 500 | 200, поля `llm_unreadable_project`, `llm_unreadable_daily` |
| `GET /api/economics` | `llm.usd=0.0`, `costs_complete=true` | `costs_complete=false`, `llm_unreadable_calls` |
| Лимит серии, нечитаемая строка соседнего кадра | соседний кадр тратит (сумма не считается) | 409 «Учёт расходов серии повреждён…» |

## Проверки

- `pytest backend/test_ga01_unreadable_barrier.py`: 6 passed с правкой; без правки (на `8fb6b76`) 5 failed, 1 passed
  (охранный тест изоляции проходит в обоих случаях — так задумано).
- `pytest backend` целиком: 554 passed, 39 subtests, rc=0 (198 с) — 548 прежних + 6 новых, падений нет.
- Область файлов: `tools/check_agent_scope.py --branch build/claude/... --base minimax/ga-01-money-p0` — локально `AGENT_SCOPE: role=claude, changed=5, forbidden=0`; `tools.test_agent_coordination` + `tools.test_agent_scope` — 14 OK.
- Production SQLite не использовалась (временный `STUDIO_DATA_DIR`), платных вызовов и сети нет.

## Остаточные риски

- Экран «Экономика» и панель бюджета не читают новые поля `llm_unreadable_*`: отказ и признак «итог неполный»
  видны, отдельной строки «нечитаемые суммы» в интерфейсе нет (frontend не менялся, P2).
- Решения владельца из ретеста остаются открытыми: что делать со строкой без оценки и токенов (сумма, потолок или
  ноль), остановка трат всех проектов при сегодняшней нечитаемой строке (реализовано: да), исход `done`
  подтверждает всю удержанную сумму.
- Бэкенд-тесты в CI для этой цепочки PR не запускаются: полный прогон только локальный.
