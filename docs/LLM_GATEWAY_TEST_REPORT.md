# Отчёт о прогонах: LLM-шлюз

Дата: 2026-10-20 · ветка `minimax/llm-gateway` · worktree `C:\Users\BLOWKA\Documents\Minimax\_wt\gremovod-llm-gateway`

Только фактические прогоны. Каждое число ниже — вывод команды, приведённый как есть. Ничего не запускалось «в принципе».

---

## 1. Бэкенд — полный прогон

Команда (из корня репозитория):

```
C:\AI_Workflow_Studio\.venv\Scripts\python.exe -X utf8 -m unittest discover -s backend -p "test_*.py"
```

Вывод:

```
----------------------------------------------------------------------
Ran 353 tests in 114.604s

OK
```

Полный прогон выполнялся трижды (до и после правки документации): 103.917 с, 121.961 с и 114.604 с — все **OK**, результат одинаковый.

Состояние на старте таска 06 было **349 тестов, OK**. Стало 353: добавлен новый файл `backend/test_budget_breakdown.py` (4 теста). Регрессий нет.

Интерпретатор: `C:\AI_Workflow_Studio\.venv\Scripts\python.exe` (Python 3.13, тот же venv, что и у студии; отдельного venv в ветке нет).

---

## 2. Бэкенд — новый тест таска 06 (красный → зелёный)

Файл: `backend/test_budget_breakdown.py` (4 теста).

**Прогон ДО реализации** (код `/api/budgets/{project_id}` ещё не отдавал четыре величины):

```
C:\AI_Workflow_Studio\.venv\Scripts\python.exe -X utf8 -m unittest backend.test_budget_breakdown -v

test_project_budget_returns_four_amounts_next_to_old_fields ... ERROR
test_project_without_llm_calls_returns_zero_amounts ... ERROR
test_reserved_call_in_flight_is_not_actual ... ERROR
test_unknown_charge_is_separate_amount_not_actual ... ERROR

KeyError: 'actual_cost_usd'   (в двух тестах — KeyError: 'reserved_usd')
----------------------------------------------------------------------
Ran 4 tests in 1.433s

FAILED (errors=4)
```

Красный по нужной причине: поля `actual_cost_usd` / `reserved_usd` в ответе `/api/budgets/{project_id}` отсутствовали.

**Прогон ПОСЛЕ реализации:**

```
C:\AI_Workflow_Studio\.venv\Scripts\python.exe -X utf8 -m unittest backend.test_budget_breakdown -v

test_project_budget_returns_four_amounts_next_to_old_fields ... ok
test_project_without_llm_calls_returns_zero_amounts ... ok
test_reserved_call_in_flight_is_not_actual ... ok
test_unknown_charge_is_separate_amount_not_actual ... ok
----------------------------------------------------------------------
Ran 4 tests in 1.479s

OK
```

Что проверяет каждый тест:

| Тест | Проверяет |
|---|---|
| `test_project_budget_returns_four_amounts_next_to_old_fields` | `/api/budgets/{project_id}` отдаёт `actual_cost_usd = 0.00027`, `reserved_usd = 0`, `unknown_cost_usd = 0`, `reference_cost_usd = 0.00006`; прежние поля (`llm_project_usd`, `llm_daily_usd`, `llm_calls_project`, `project_limit_usd`, `daily_limit_usd`, `project_reserved_usd`, `daily_reserved_usd`) на месте; экспозиция = факт + резерв + неизвестные |
| `test_unknown_charge_is_separate_amount_not_actual` | при ответе провайдера без usage: `actual_cost_usd = 0`, `unknown_cost_usd > 0`, `reserved_usd = 0` — неизвестное списание не попадает в факт |
| `test_reserved_call_in_flight_is_not_actual` | вызов в полёте: `reserved_usd = 0.0005`, `actual_cost_usd = 0`, `unknown_cost_usd = 0` — резерв и факт разные строки |
| `test_project_without_llm_calls_returns_zero_amounts` | проект без вызовов: все четыре величины — 0, `llm_calls_project = 0` |

---

## 3. Бэкенд — две обязательные ситуации

Обе проверяются существующими тестами, отдельный прогон:

```
C:\AI_Workflow_Studio\.venv\Scripts\python.exe -X utf8 -m unittest \
  backend.test_llm_cost_display.FourAmountsTests.test_free_call_is_zero_actual_with_nonzero_reference \
  backend.test_llm_guard.LlmJournalTests.test_free_route_is_journaled_with_zero_actual_and_nonzero_reference \
  backend.test_llm_guard.LlmJournalTests.test_estimate_and_chat_responses_keep_old_fields_and_add_card -v

----------------------------------------------------------------------
Ran 3 tests in 1.092s

OK
```

- **Бесплатный маршрут даёт ненулевой тарифный ориентир при нулевом бюджете** — `test_free_call_is_zero_actual_with_nonzero_reference` и `test_free_route_is_journaled_with_zero_actual_and_nonzero_reference`: факт 0, ориентир по Kie/PiAPI > 0.
- **Платный маршрут показывает ориентир и фактическую сумму до подтверждения** — `test_estimate_and_chat_responses_keep_old_fields_and_add_card`: ответы `/api/llm/estimate` и `/api/llm/chat` сохраняют прежние поля и добавляют карточку (`reference`, `execution`, `actual`).

---

## 4. Фронтенд

Команды (из `frontend/`):

```
npm test
```

```
ℹ tests 115
ℹ suites 0
ℹ pass 115
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 6915.6908
```

```
npm run build      # tsc --noEmit && vite build
```

```
✓ 1876 modules transformed.
dist/index.html                   0.54 kB │ gzip:  0.36 kB
dist/assets/index-kXYFNmIR.css  129.95 kB │ gzip: 24.09 kB
dist/assets/index-eJ7e6FD5.js  651.70 kB │ gzip:196.72 kB
✓ built in 3.94s
```

Состояние на старте таска 06: 115 pass, сборка успешна. После изменений — то же (115 pass, сборка успешна). Типизация (`tsc --noEmit`) проходит: новых полей сводки в типах панелей и в `llmDisplay.ts` согласованы.

Отдельный файл: `node --experimental-strip-types --test src/llmDisplay.test.mjs` — чистые функции карточки и сводки (`budgetLines` уже покрыта существующим тестом; новых чистых функций таск 06 не добавлял).

---

## 5. Что НЕ запускалось и не проверялось

1. **Живые платные вызовы провайдеров — 0.** Этап E требует отдельного одобрения владельца на конкретные расходы; одобрения не было. Все тесты работают на моках транспорта.
2. **Живая сверка тарифов и адресов — 0.** `verified_at` пуст у всех маршрутов реестра.
3. **Работающая студия не перезапускалась.** Процессы на 8000 и 5173 не трогались, поэтому новые панели в живом интерфейсе глазами не просматривались: проверка фронтенда — только тесты и сборка.
4. **Dry-run для n8n по факту не выполнялся.** Инструкция (`docs/LLM_GATEWAY_ARCHITECTURE.md`, §7) составлена по коду и контракту API; фактического прогона с живым сервером на этой ветке не было. Часть шага 3 упирается в то, что маршруты в рабочем файле реестра выключены (`enabled: false`) — это ожидаемое поведение «закрыт по умолчанию», а не сбой.
5. **pytest не использовался** — проектная команда проверки одна, `unittest discover` (§11 `interfaces.md`).
6. **Линтера в проекте нет** (ruff-конфига в ветке нет) — выдумывать проверки не нужно.

---

## 6. Итог одним списком

| Проверка | Результат |
|---|---|
| `unittest discover -s backend -p "test_*.py"` | 353 теста, OK (прогоны: 103.917 / 121.961 / 114.604 с) |
| `unittest backend.test_budget_breakdown` (до реализации) | 4 теста, FAILED (errors=4) — `KeyError: 'actual_cost_usd'` |
| `unittest backend.test_budget_breakdown` (после реализации) | 4 теста, OK, 1.479 с |
| Две обязательные ситуации (3 теста) | OK, 1.092 с |
| `npm test` | 115 pass / 0 fail, 6.9 с |
| `npm run build` | успешно, 3.94 с, 1876 модулей |
| Живые платные вызовы | не выполнялись (нужно одобрение владельца) |
| Живая сверка тарифов | не выполнялась |
| Ручная проверка панелей в браузере | не выполнялась (студия не перезапускалась) |
