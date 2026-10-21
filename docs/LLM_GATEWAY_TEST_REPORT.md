# Отчёт о прогонах: LLM-шлюз

Дата: 2026-10-20 · ветка `minimax/llm-gateway` · worktree `C:\Users\BLOWKA\Documents\Minimax\_wt\gremovod-llm-gateway`

Только фактические прогоны. Каждое число ниже — вывод команды, приведённый как есть. Ничего не запускалось «в принципе».

---

## 1. Бэкенд — полный прогон

Команда (из корня репозитория):

```
C:\AI_Workflow_Studio\.venv\Scripts\python.exe -X utf8 -m unittest discover -s backend -p "test_*.py"
```

Вывод (после круга F4):

```
----------------------------------------------------------------------
Ran 377 tests in 147.763s

OK
```

Полный прогон выполнялся трижды (до и после правки документации): 103.917 с, 121.961 с и 114.604 с — все **OK**, результат одинаковый. После ремонтного круга F1 — **360 тестов, OK, 133.973 с** (добавлено 7 тестов на находки ревью; регрессий нет). После круга F2 — **359 тестов, OK, 121.415 с**: дублирующий тест на отказ по исчерпанному лимиту проекта удалён, его сценарий слит с переименованным и усиленным `test_agent_job_is_refused_when_the_project_limit_is_exhausted_even_with_a_free_route`; кода бэкенда F2 не менял, новых серверных тестов не добавлено — правка окна подтверждения проверяется фронтенд-тестом. После круга F4 — **377 тестов, OK, 147.763 с** (прогоны круга F4: 130.381 с и 147.763 с — оба OK): добавлено 6 тестов (4 в `backend/test_llm_guard.py`, класс `LlmRouteReachabilityTests`; 2 в новом `backend/test_llm_docs_numbers.py`); кода бэкенда тронул один файл, `backend/llm_guard.py` — маршрут реестра, который адаптер всё равно отверг бы (включён владельцем, но тариф не подтверждён вживую), больше не попадает в цепочку и не выключает вызовы студии. Регрессий нет: остальные 375 тестов прошли без правок.

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
ℹ tests 121
ℹ suites 0
ℹ pass 121
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 8036.1252
```

```
npm run build      # tsc --noEmit && vite build
```

```
✓ 1876 modules transformed.
dist/index.html                          0.54 kB │ gzip:   0.36 kB
dist/assets/StoryboardDemo-n5wXCZ3v.css  5.43 kB │ gzip:   1.80 kB
dist/assets/index-kXYFNmIR.css           129.95 kB │ gzip:  24.09 kB
dist/assets/StoryboardDemo-bKgH8kl-.js   19.50 kB │ gzip:   7.20 kB
dist/assets/WorkflowPanel-IFXHL_rk.js    221.66 kB │ gzip:  72.07 kB
dist/assets/index-B2fdLHu6.js            652.39 kB │ gzip: 196.94 kB
✓ built in 5.16s
```

В логе сборки — 6 файлов `dist` (плюс каталог `dist/assets`), а не 3: сборка отдаёт отдельные чанки `StoryboardDemo` и `WorkflowPanel`.

Состояние на старте таска 06: 115 pass, сборка успешна. После изменений таска 06 — то же (115 pass, сборка успешна). После ремонтного круга F1 — **118 pass, сборка успешна**. После круга F2 — **119 pass, сборка успешна** (добавлен тест окна подтверждения: под «Максимальный одобренный расход» показывается лимит владельца, а не оценка узла). После круга F4 — **121 pass, сборка успешна** (добавлен `frontend/src/llmAsk.test.mjs`, 2 теста: окно LLM передаёт серверу задачу и режим маршрутизации, а не провайдера). Типизация (`tsc --noEmit`) проходит: новых полей сводки в типах панелей и в `llmDisplay.ts` согласованы.

Отдельный файл: `node --experimental-strip-types --test src/llmDisplay.test.mjs` — чистые функции карточки и сводки (`budgetLines` уже покрыта существующим тестом; новых чистых функций таск 06 не добавлял). В круге F2 добавлена чистая функция `ownerLimitUsd()` (разбор лимита владельца из выбора), а `approvalMoney()` переведена с числа-оценки узла на лимит владельца: `frontend/src/WorkflowPanel.tsx` передаёт в неё значение выбора лимита, а не `actual.max_cost_usd`. В круге F4 добавлен `frontend/src/llmAsk.test.mjs` — тест клиентского слоя LLM: тело запроса к `/api/llm/estimate` и `/api/llm/chat` содержит `route_mode`, `task` и `allow_free` и не содержит `provider`.

---

## 5. Круг F4 — маршруты реестра из интерфейса (красный → зелёный)

### 5.1 Бэкенд: `backend/test_llm_guard.py::LlmRouteReachabilityTests` (4 теста)

**Прогон ДО реализации** (реестр с маршрутом, который адаптер всё равно отверг бы):

```
C:\AI_Workflow_Studio\.venv\Scripts\python.exe -X utf8 -m unittest backend.test_llm_guard.LlmRouteReachabilityTests -v

test_auto_chain_calls_routes_in_order_and_pays_once ... ok
test_old_client_without_new_fields_works_as_before ... ok
test_registry_without_a_fit_chain_calls_the_compatible_route ... FAIL
test_window_with_a_registry_route_calls_that_route ... ok
----------------------------------------------------------------------
Ran 4 tests in 1.552s

FAILED (failures=1)
```

Красный по нужной причине: `AssertionError: 400 != 200 : {"detail":"Тариф маршрута не подтверждён вживую: kie/claude-haiku-5-5"}` — маршрут реестра включён владельцем, но тариф не подтверждён вживую; адаптер отверг бы его до сети, и вызов студии падал бы с 400 вместо совместимого маршрута.

**Прогон ПОСЛЕ реализации:**

```
C:\AI_Workflow_Studio\.venv\Scripts\python.exe -X utf8 -m unittest backend.test_llm_guard.LlmRouteReachabilityTests -v

test_auto_chain_calls_routes_in_order_and_pays_once ... ok
test_old_client_without_new_fields_works_as_before ... ok
test_registry_without_a_fit_chain_calls_the_compatible_route ... ok
test_window_with_a_registry_route_calls_that_route ... ok
----------------------------------------------------------------------
Ran 4 tests in 1.851s

OK
```

| Тест | Проверяет |
|---|---|
| `test_registry_without_a_fit_chain_calls_the_compatible_route` | маршрут реестра включён, но тариф не подтверждён вживую → вызов идёт по совместимому маршруту PiAPI (не 400); в журнале `execution_provider = piapi`, `route_mode = auto` |
| `test_window_with_a_registry_route_calls_that_route` | включённый маршрут реестра под задачу `editorial` → вызов идёт по нему (`execution_provider = kie`), совместимый транспорт не трогается |
| `test_auto_chain_calls_routes_in_order_and_pays_once` | цепочка идёт по очереди (`start:openrouter → end:openrouter → start:kie → end:kie`), без параллельных вызовов, и платная попытка одна |
| `test_old_client_without_new_fields_works_as_before` | старый клиент (`provider: "piapi"`, без `route_mode`/`task`) → прежний маршрут, один вызов, `route_mode = manual` |

### 5.2 Фронтенд: `frontend/src/llmAsk.test.mjs` (2 теста)

**Прогон ДО реализации** (окно LLM ещё зашивало провайдера):

```
node --experimental-strip-types --test src/llmAsk.test.mjs

✖ оценка окна LLM уходит с задачей и режимом маршрутизации, без провайдера
✖ вызов окна LLM уходит с той же задачей и режимом, без провайдера
  AssertionError [ERR_ASSERTION]: Expected values to be strictly equal:
  + actual - expected
  + undefined
  - 'auto'
ℹ tests 2
ℹ pass 0
ℹ fail 2
```

Красный по нужной причине: в теле запроса не было `route_mode` (и не было `task`) — окно LLM передавало только `provider: "piapi"`.

**Прогон ПОСЛЕ реализации:**

```
node --experimental-strip-types --test src/llmAsk.test.mjs

✔ оценка окна LLM уходит с задачей и режимом маршрутизации, без провайдера
✔ вызов окна LLM уходит с той же задачей и режимом, без провайдера
ℹ tests 2
ℹ pass 2
ℹ fail 0
```

### 5.3 Числа прогонов в документах: `backend/test_llm_docs_numbers.py` (2 теста)

**Прогон ДО правки документов:** `AssertionError: 'Ran 377 tests' not found in '# Передача: LLM-шлюз студии (MiniMax)…'` — в документах стояло `Ran 359 tests` при фактических 377.

**Прогон ПОСЛЕ правки документов:** `Ran 2 tests in 1.160s — OK`. Тест сверяет числа документов с фактом: число тестов бэкенда считается тем же `unittest discover`, что и в прогоне, число тестов фронтенда — по вызовам `test(` в файлах `*.test.mjs`. Расхождение ломает сборку, а не всплывает на приёмке.

---

## 6. Что НЕ запускалось и не проверялось

1. **Живые платные вызовы провайдеров — 0.** Этап E требует отдельного одобрения владельца на конкретные расходы; одобрения не было. Все тесты работают на моках транспорта.
2. **Живая сверка тарифов и адресов — 0.** `verified_at` пуст у всех маршрутов реестра.
3. **Работающая студия не перезапускалась.** Процессы на 8000 и 5173 не трогались, поэтому новые панели в живом интерфейсе глазами не просматривались: проверка фронтенда — только тесты и сборка.
4. **Dry-run для n8n по факту не выполнялся.** Инструкция (`docs/LLM_GATEWAY_ARCHITECTURE.md`, §7) составлена по коду и контракту API; фактического прогона с живым сервером на этой ветке не было. Часть шага 3 упирается в то, что маршруты в рабочем файле реестра выключены (`enabled: false`) — это ожидаемое поведение «закрыт по умолчанию», а не сбой.
5. **pytest не использовался на тасках 06 и F1–F3** — проектная команда проверки была одна, `unittest discover` (§11 `interfaces.md`). В круге F4 прогон выполнен обеими командами: `unittest discover` — `Ran 377 tests`, OK; `pytest backend -q` — 377 тестов, 27 подтестов, все прошли.
6. **Линтера в проекте нет** (ruff-конфига в ветке нет) — выдумывать проверки не нужно.

---

## 7. Итог одним списком

| Проверка | Результат |
|---|---|
| `unittest discover -s backend -p "test_*.py"` | 377 тестов, OK (прогоны: 103.917 / 121.961 / 114.604 с на таске 06; 133.973 с после ремонта F1; 121.415 с после круга F2; 130.381 / 147.763 с после круга F4) |
| `pytest backend -q` | 377 тестов, 27 подтестов, OK, 121.89 с |
| `unittest backend.test_budget_breakdown` (до реализации) | 4 теста, FAILED (errors=4) — `KeyError: 'actual_cost_usd'` |
| `unittest backend.test_budget_breakdown` (после реализации) | 4 теста, OK, 1.479 с |
| Две обязательные ситуации (3 теста) | OK, 1.092 с |
| `unittest backend.test_llm_guard.LlmRouteReachabilityTests` (F4) | 4 теста, OK, 1.851 с (до реализации — 1 падение: 400 вместо совместимого маршрута) |
| `unittest backend.test_llm_docs_numbers` (F4) | 2 теста, OK, 1.160 с (до правки документов — 2 падения: в документах было `Ran 359 tests`) |
| `npm test` | 121 pass / 0 fail, 8.04 с (на таске 06 было 115 pass, после F1 — 118, после F2 — 119) |
| `npm run build` | успешно, 5.16 с, 1876 модулей, 6 файлов `dist` в логе |
| Живые платные вызовы | не выполнялись (нужно одобрение владельца) |
| Живая сверка тарифов | не выполнялась |
| Ручная проверка панелей в браузере | не выполнялась (студия не перезапускалась) |
