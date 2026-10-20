# TEST_RESULTS — реально выполненные прогоны

**Дата:** 2026-10-20 · **Среда:** Windows 10.0.19044 x64, PowerShell 5.1, Python 3.13.14,
Node v24.16.0, Git 2.56.0 · **Платных API-вызовов: 0** · **Сетевых вызовов к провайдерам: 0**

Все команды выполнены в **изолированных worktree** (`git worktree add --detach`) на
конкретных SHA. Рабочая копия владельца не затрагивалась.

---

## 1. Подготовка окружения

```powershell
# Изолированное venv ВНЕ репозитория (репозиторий не пачкается)
cd C:\Users\BLOWKA\Documents\Minimax
python -m venv .venv-audit
.\.venv-audit\Scripts\python.exe -m pip install -r gremovod\backend\requirements.txt pytest
# → fastapi 0.150.0, pytest 9.1.1, httpx 0.28.1, Pillow 12.3.0
```

```powershell
# Worktree на каждый исследуемый SHA
cd C:\Users\BLOWKA\Documents\Minimax\gremovod
git worktree add --detach C:\Users\BLOWKA\Documents\Minimax\_wt\wt29 pr/29
git worktree add --detach C:\Users\BLOWKA\Documents\Minimax\_wt\wt34 pr/34
git worktree add --detach C:\Users\BLOWKA\Documents\Minimax\_wt\wt35 pr/35
git worktree add --detach C:\Users\BLOWKA\Documents\Minimax\_wt\wt08 origin/feature/qa-text-audit-fixes-20261019
```

```powershell
# Защита от записи в рабочую БД — путь БД по умолчанию ВНУТРИ репозитория:
#   backend/main.py:22-24  DB=(DATA or ROOT)/'studio.sqlite3'
# поэтому STUDIO_DATA_DIR всегда указывался на временный каталог
$env:STUDIO_DATA_DIR = "C:\Users\BLOWKA\Documents\Minimax\_testdata"
```

> ⚠️ Это не формальность. Без `STUDIO_DATA_DIR` pytest создал бы
> `backend/studio.sqlite3` **внутри репозитория** и изменил бы рабочее состояние
> Git-дерева. Это зафиксировано как находка OI-10.

---

## 2. Сводная таблица прогонов

| # | Ref | Команда | Результат | Exit |
|---|---|---|---|---|
| T1 | `main` `82adb2d` | `pytest backend -q` | **242 passed**, 16 subtests passed, 39 warnings, 76.49 s | **0** |
| T2 | `main` `82adb2d` | `npm test` (frontend, 26 файлов `.test.mjs`) | **104 tests, 104 pass, 0 fail**, 7003 ms | **0** |
| T3 | PR #29 `c082829` | `pytest backend -q` | **345 passed**, 26 subtests passed, 39 warnings, 86.78 s | **0** |
| T4 | PR #29 `c082829` | `pytest backend -q -k "p0 or budget or authz or ledger or idempot"` | **78 passed**, 267 deselected, 10 subtests passed, 13.34 s | **0** |
| T5 | PR #29 `c082829` | `pytest tools -q` | **14 passed**, 7 subtests passed, 0.07 s | **0** |
| T6 | PR #29 `c082829` | `node --test tests/test_p0_state.js` | **7 tests, 7 pass, 0 fail**, 2567 ms | **0** |
| T7 | PR #34 `b3183d2` | `pytest tests -q` | **76 passed**, 73.16 s | **0** |
| T8 | PR #35 `051ab3a` | `pytest tests -q` | **108 passed**, 29.54 s | **0** |
| T9 | PR #8 `3979390` | `pytest backend/test_qa_text_precheck.py backend/test_qa_text_app_integration.py -q` | **19 passed**, 67 warnings, 8.49 s | **0** |
| T10 | PR #8 `3979390` | `pytest backend -q` | **261 passed**, 16 subtests passed, 67 warnings, 107.85 s | **0** |

**Итого: 10 прогонов, все зелёные, exit code 0.**

---

## 3. Точные команды и вывод

### T1 — `main` @ `82adb2d28efa05bf8face168485fe07ae340e0bc`

```
cd C:\Users\BLOWKA\Documents\Minimax\gremovod
$env:STUDIO_DATA_DIR = "C:\Users\BLOWKA\Documents\Minimax\_testdata"
C:\Users\BLOWKA\Documents\Minimax\.venv-audit\Scripts\python.exe -X utf8 -m pytest backend -q
```

```
242 passed, 39 warnings, 16 subtests passed in 76.49s (0:01:16)
EXITCODE=0
```
Предупреждения — только `DeprecationWarning: on_event is deprecated, use lifespan
event handlers instead` (FastAPI ≥ 0.109), в 5 модулях: `character_voice.py:91`,
`sound.py:134`, `temp_cleanup.py:231`, `story_plan.py:134`, `camera_movements.py`.

### T2 — фронтенд `main`

```
cd C:\Users\BLOWKA\Documents\Minimax\gremovod\frontend
npm ci
$env:STUDIO_PYTHON = "C:\Users\BLOWKA\Documents\Minimax\.venv-audit\Scripts\python.exe"
$env:STUDIO_DATA_DIR = "C:\Users\BLOWKA\Documents\Minimax\_testdata"
npm test
```

```
tests 104
suites 0
pass 104
fail 0
cancelled 0
skipped 0
todo 0
duration_ms 7003.1955
FRONTEND_EXITCODE=0
```

> **Важно о воспроизводимости.** Без `STUDIO_PYTHON` фронт-тесты падают (см. §5.1).
> Тест сам ищет интерпретатор: `process.env.STUDIO_PYTHON || findVenvPython(cwd) || 'python3'`
> (`frontend/directorState.test.mjs`). `findVenvPython` поднимается вверх по каталогам,
> ища `.venv/Scripts/python.exe` / `.venv/bin/python`. То есть фронт-тесты **требуют
> venv с установленным `fastapi`** — в любом CI это надо воспроизвести явно.

### T3 / T4 — PR #29 @ `c082829b11b968965600bdaf87c137b1485a0fa2`

```
cd C:\Users\BLOWKA\Documents\Minimax\_wt\wt29
python -X utf8 -m pytest backend -q
→ 345 passed, 39 warnings, 26 subtests passed in 86.78s (0:01:26)   EXITCODE=0

python -X utf8 -m pytest backend -q -k "p0 or budget or authz or ledger or idempot"
→ 78 passed, 267 deselected, 39 warnings, 10 subtests passed in 13.34s (0:01:13)  EXITCODE=0
```

Прирост к `main`: **+103 теста** (242 → 345). Это P0-контур PR #29.

### T5 / T6 — PR #29, координация

```
python -X utf8 -m pytest tools -q
→ 14 passed, 7 subtests passed in 0.07s          EXITCODE=0

node --test tests/test_p0_state.js
→ tests 7 | pass 7 | fail 0 | duration_ms 2567.6383   EXITCODE=0
```

Имена тестов T6 (Node test runner):
- `test_prompt_or_profile_changed_after_approval_is_rejected`
- `test_provider_success_charges_once_and_no_duplicate_callbacks`
- `test_no_legacy_job_overwrite_from_p0_submit`
- `test_source_changed_before_submit_blocks_billing`

### T7 — PR #34 @ `b3183d28a0e22d5414ab7eef70d62543aa991dfa`

```
cd C:\Users\BLOWKA\Documents\Minimax\_wt\wt34
python -X utf8 -m pytest tests -q
→ 76 passed in 73.16s (0:01:13)                   EXITCODE=0
```

### T8 — PR #35 @ `051ab3a1182c1ed954b53c9b64f85e8195dbcc91`

```
cd C:\Users\BLOWKA\Documents\Minimax\_wt\wt35
python -X utf8 -m pytest tests -q
→ 108 passed in 29.54s (0:00:29)                  EXITCODE=0
```

### T9 / T10 — PR #8 @ `3979390`

```
cd C:\Users\BLOWKA\Documents\Minimax\_wt\wt08
python -X utf8 -m pytest backend/test_qa_text_precheck.py backend/test_qa_text_app_integration.py -q
→ 19 passed, 67 warnings in 8.49s                 EXITCODE=0

python -X utf8 -m pytest backend -q
→ 261 passed, 67 warnings, 16 subtests passed in 107.85s (0:01:47)   EXITCODE=0
```

---

## 4. Что НЕ запускалось — и почему

| Что | Почему не запускалось | Как это влияет на аудит |
|---|---|---|
| **n8n-инстанс** `gremovod.app.n8n.cloud` | Требует сети и учётных данных; workflow не опубликованы (`runtime_status: DRAFT_MOCK_ONLY_NOT_PUBLISHED`, `published: false` у A6/A7/A8) | Все утверждения о поведении n8n — из JSON и документации, **не из исполнения** |
| **Живые вызовы провайдеров** (PiAPI, KIE, ElevenLabs, Fish) | Платные. Явного разрешения владельца на платные вызовы нет | Поведение платных путей **не проверено вовсе** |
| **KIE (Claude Opus 5.5)** | Платный маршрут; при подготовке выполнялись только запросы без ключа (§6 KIE_SETUP) | Фактическая стоимость аудита — оценка, а не факт |
| **Живой вызов A6 в n8n** | По `QA_FASTAPI_CONNECTION_HANDOFF.md:10` единственная попытка провалилась 3× с `AI_APICallError`; повтор не выполнялся | Работоспособность A6 **неизвестна** |
| **Реальный пользовательский MP4** | Его у владельца нет (`STATUS.md`: `MEDIA-01 → BLOCKED_NO_USER_MP4`) | A8 невозможно проверить в принципе — ни мной, ни Opus |
| **CI n8n Cloud** | Требует доступа к облачному n8n | Утверждение «CI зелёный» в гейте — **из документации**, не из прогона |
| **Миграция боевой схемы** | `production_schema_migrated: false` во всех ветках | Боевой БД не мигрирован — контур P0 в бою не работал |
| **Проверка живой базы владельца** | Принципиально не трогал; `working_db_accessed: false` в записях проекта | Рабочая БД не изучалась |

---

## 5. Провалившиеся прогоны (зафиксированы, а не скрыты)

### 5.1 Фронтенд без установленных зависимостей — exit 1

```
cd frontend; npm test
→ ✖ createDraft.test.mjs, directorState.test.mjs, projectMerge.test.mjs,
  visualPlan.test.mjs, workspaceNavigation.test.mjs  (и ещё 21)
  Error [ERR_MODULE_NOT_FOUND]: Cannot find package 'typescript'
FRONTEND_EXITCODE=1
```

Причина: `node_modules/` отсутствовал. Устранено через `npm ci`.

### 5.2 Фронтенд с зависимостями, но без доступа к venv — exit 1

```
cd frontend; npm test   # интерпретатор не найден → fallback 'python3'
→ ModuleNotFoundError: No module named 'fastapi'
   File "...\backend\camera_movements.py", line 4, in <module>
   FRONTEND_EXITCODE=1
```

Причина: тест исполняет `python -c "from backend.camera_movements import basis…"`
через дочерний процесс, и ему нужен интерпретатор **с установленным `fastapi`**.
`findVenvPython` ищет `.venv/`, которого в репозитории нет. Устранено через
`STUDIO_PYTHON`.

> **Это не «зелёный тест не проходит из-за кода» — это тест, который требует
> согласованного окружения.** Но это же делает фронт-тесты хрупкими: в CI, где
> `backend`-зависимости не установлены, `npm test` упадёт. Фиксируется как OI-11.

### 5.3 `unittest discover` от корня репозитория — exit 5 (×3)

```
python -X utf8 -m unittest discover -s . -p "test_*.py" -t .
→ Ran 0 tests in 0.000s
   NO TESTS RAN
   EXITCODE=5
```

Причина: `unittest discover` не рекурсивно обходит вложенные каталоги без
`__init__.py`. Команда из `AGENTS.md` (`python -X utf8 -m unittest discover -s backend
-p "test_*.py"`) корректна для `backend/`, но **не** для `tests/` и `tools/` в
корне. Именно поэтому T5/T7/T8 выполнялись через `pytest` с явными путями.

> **Замечание владельцу:** `AGENTS.md` предписывает `unittest discover`, `CLAUDE.md` —
> `pytest`. Обе команды дают разный результат на разных каталогах. Для аудита
> использован `pytest` с явными путями, поскольку он одинаково работает везде.

---

## 6. Проверки без ключа (не платные, не тесты)

```powershell
Invoke-WebRequest "https://api.kie.ai/anthropic/v1/models"  → HTTP 401
  {"code":401,"msg":"Unauthorized – Authentication failed. Please check that your
   Authorization and Content-Type headers are correctly set."}

Invoke-WebRequest "https://api.kie.ai/claude/v1/messages"    → GET not supported
Invoke-WebRequest "https://api.kie.ai/anthropic/v1/messages" → GET not supported
```

Назначение: подтвердить существование и различие маршрутов KIE **без единого
списанного кредита**. Результат: все три маршрута живы.

---

## 7. Проверка чистоты рабочего дерева

После всех прогонов:

```
cd C:\Users\BLOWKA\Documents\Minimax\gremovod
git status --short
→ (пусто)
```

Ни один прогон не изменил отслеживаемые файлы. `node_modules/` — в `.gitignore`.
`backend/studio.sqlite3` не создавался (за счёт `STUDIO_DATA_DIR`).

---

## 8. Что эти результаты значат для аудита — и чего не значат

**Значат:**
- P0-контур PR #29 **реально покрыт тестами** (T3: +103 теста к `main`), и они зелёные.
- Fail-closed поведение проверяется на уровне состояний, а не только на уровне
  «функция не бросает исключение».
- Реализация A6/A7 из PR #8 покрыта 19 отдельными тестами (T9) и **они зелёные**.

**Не значат:**
- **Зелёный тест ≠ правильная архитектура.** T3/T4 доказывают, что заявленные
  сценарии не сломались, — и ничего больше.
- Тест `backend/test_mock_evidence.py` **успешно** проверяет, что все вердикты
  A6/A7/A8 равны `BLOCKED`. Тест зелёный, а проверочная способность критиков — нулевая.
  Это иллюстрация п.4 system prompt.
- Отсутствие `backend/studio.sqlite3` в репозитории при `main` и путь БД по умолчанию
  внутрь репозитория — две разные вещи. Тесты этого не покрывают.
- Ни один тест не проверяет **поведение провайдера** — платные пути не тестировались.
- Ни один тест не покрывает **согласованность** P0-контура с `main`-путём к провайдерам
  (`adapters` + `main.py:460-472`) — это несуществующая точка, а не упавший тест.
