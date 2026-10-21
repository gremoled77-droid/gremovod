# Предлагаю дополнить твой `CLAUDE.md`

Ниже — только **дополнения**: каждая строка готова к вставке в `CLAUDE.md`. То, что в `CLAUDE.md` уже есть, не повторяю.

Проверено в этом worktree: `C:\Users\BLOWKA\Documents\Minimax\_wt\gremovod-llm-gateway`, ветка `minimax/llm-gateway`, коммит `f1c4250`.
Пути в командах — для этого worktree; в рабочей копии `C:\AI_Workflow_Studio` подставь свой корень.

## Команды

**Зависимости фронтенда — один раз на каждый worktree, нужен интернет (из `frontend/`):**
`npm ci`

**Тесты бэкенда — единственный проверенный интерпретатор, из корня репозитория:**
`C:\AI_Workflow_Studio\.venv\Scripts\python.exe -X utf8 -m unittest discover -s backend -p "test_*.py"`

**Один тестовый файл бэкенда:**
`C:\AI_Workflow_Studio\.venv\Scripts\python.exe -X utf8 -m unittest backend.test_llm_gateway`
`C:\AI_Workflow_Studio\.venv\Scripts\python.exe -X utf8 -m unittest discover -s backend -p "test_llm_adapters.py"`

**Один тестовый файл фронтенда (из `frontend/`):**
`node --experimental-strip-types --test src/llmDisplay.test.mjs`

**Полная проверка перед коммитом — копипаст, останавливается на первом провале:**
```powershell
$ErrorActionPreference='Continue'
cd C:\Users\BLOWKA\Documents\Minimax\_wt\gremovod-llm-gateway
& 'C:\AI_Workflow_Studio\.venv\Scripts\python.exe' -X utf8 -m unittest discover -s backend -p 'test_*.py'
if ($LASTEXITCODE -ne 0) { 'СТОП: тесты бэкенда упали'; return }
cd frontend
npm test
if ($LASTEXITCODE -ne 0) { 'СТОП: тесты фронтенда упали'; return }
npm run build
if ($LASTEXITCODE -ne 0) { 'СТОП: сборка упала'; return }
'ПРОВЕРКА ПРОЙДЕНА'
```

**Свой стенд бэкенда — своя база и свои файлы, порты владельца не занимаются:**
```powershell
$env:STUDIO_DATA_DIR='C:\путь\к\своей\папке'
& 'C:\AI_Workflow_Studio\.venv\Scripts\python.exe' -X utf8 -m uvicorn backend.main:app --host 127.0.0.1 --port 8021
```
Здоровье: `Invoke-RestMethod http://127.0.0.1:8021/api/health` → `ok=True`, `version=0.3.0`, `mode=local`.

**Фронтенд в dev-режиме на свободном порту (из `frontend/`):**
`npm run dev -- --port 5180 --strictPort`

**Проверка добавляемых файлов перед коммитом (из корня репозитория):**
`C:\AI_Workflow_Studio\.venv\Scripts\python.exe scripts\check_git_files.py --staged`

## Переменные окружения (имена; значения — только в файлах ключей и `.env`)

- `MINIMAX_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY` — ключи новых провайдеров шлюза, по образцу `PIAPI_API_KEY`/`KIE_API_KEY`; фолбэк — файл `<ПРОВАЙДЕР>_API_KEY.txt` в корне репозитория; наличие видно в `GET /api/connections` (`configured`), значения не попадают в ответы, логи и SQLite.
- `STUDIO_DATA_DIR` — уводит весь рабочий набор данных из репозитория: база → `<папка>/studio.sqlite3`, медиа → `<папка>/media`, постановки → `<папка>/projects`.
- `STUDIO_REMOTE_HOSTS` — хосты через запятую; читает только `frontend/vite.config.ts` (доступ с телефона в dev-режиме).
- `config/llm_gateway.prices.json` — рабочий реестр маршрутов и тарифов владельца: в `.gitignore`, в Git не попадает, читается шлюзом при старте.

## Подводные камни

- `SIGNING_KEY` в `backend/security.py` генерируется при каждом старте процесса → токен оценки из прошлого процесса не проходит проверку (400), и оценки не переживают перезапуск бэкенда: после рестарта оценку надо получить заново.
- `config/llm_gateway.prices.json` читается молча, без предупреждений; если файла нет — берётся `config/llm_gateway.prices.example.json`. Сейчас в обоих файлах все маршруты `enabled: false` и `verified_at: null`, поэтому шлюз закрыт по умолчанию и `POST /api/llm/estimate` отвечает 400 «Эта модель недоступна для платного вызова: нет проверенной цены». Какой файл реально загружен — `llm_gateway.load_registry().source_path`.
- Старый `POST /api/chat` отключён и отвечает 503 «Платный LLM-резерв временно отключён…» — живой путь шлюза это `POST /api/llm/chat` и `POST /api/llm/estimate`.
- `.venv` внутри репозитория нет, манифеста Python-зависимостей на верхнем уровне тоже нет (есть только `backend/requirements.txt`) — свой venv не создавать и пакеты не ставить: работает `C:\AI_Workflow_Studio\.venv\Scripts\python.exe` (Python 3.13.14) из любого worktree.
- `unittest` пишет прогресс в stderr — при `$ErrorActionPreference='Stop'` PowerShell 5.1 обрывает прогон на первой же строке; в проверках использовать `Continue` и смотреть `$LASTEXITCODE`.
- `.gitignore` должен остаться в UTF-8 без BOM: `Set-Content -Encoding UTF8` в PowerShell 5.1 добавляет BOM, и первая строка `.venv/` перестаёт совпадать (venv уедет в коммит). Правки — точечно, в существующей кодировке.
- Локальный pre-commit-хук `.githooks/pre-commit` не подключён (`core.hooksPath` не задан) — проверку `scripts/check_git_files.py --staged` запускать руками перед коммитом.
- Порты 8000/5173 — рабочая студия владельца, не трогать; свой стенд — например 8021 (бэкенд) и 5180 (фронтенд), 5173/5174 в этой сессии были заняты другими worktree'ами.
- Правило `ORIGINS` из `backend/security.py` для фронтенда в dev-режиме: страница на порту ≠5173 получит 403 «Запрос с постороннего сайта запрещён» — Origin должен быть 5173 или 8000.
- Прокси vite в `frontend/vite.config.ts` жёстко указывает на `http://127.0.0.1:8000`, переменной окружения для цели нет: фронтенд на порту 5180 всё равно ходит в 8000, а если там ничего нет — `/api/*` отдаёт 500 «http proxy error … ECONNREFUSED 127.0.0.1:8000».
- Линтера в проекте нет (ruff-конфига нет) — придумывать проверки не нужно; `npm test` = `node --experimental-strip-types --test` (нужен Node ≥ 22.6, здесь 24.16.0) и браузер не нужен.

## Указатели

- Ядро шлюза: `backend/llm_gateway.py` — реестр, тарифный ориентир и факт; `backend/llm_adapters.py` — протоколы провайдеров; `backend/llm_guard.py` — резерв, лимиты, запись в `llm_calls` и эндпоинты шлюза; `backend/security.py` — подпись оценки (поле `extra`).
- Единственный общий шов модулей — форма строки `llm_calls` и поля ответов `/api/llm/estimate` и `/api/llm/chat`; владеет ими `llm_guard.py`, остальные читают.
- Деньги сходятся в `backend/economics.py` и `backend/series_economics.py`: «Фактически потрачено» собирается из `actual_cost_usd` и `free`, а не из `llm_guard.summary()['usd']` — это экспозиция (факт + резерв + неизвестные списания).
- Фронтенд шлюза: `frontend/src/llmDisplay.ts` (чистые подписи и формат), `frontend/src/LlmCostCard.tsx`, `frontend/src/LlmApprovalDialog.tsx`, `frontend/src/llmAsk.ts`; карточка стоит в «Идее», «Мире», узлах и диалоге сценария.
- Правки чаще всего приземляются здесь: `config/llm_gateway.prices.json` (включить маршрут, проставить `verified_at`), `backend/llm_gateway.py` (правила тарифа и выбора маршрута), `backend/llm_guard.py` (журнал и подпись), `frontend/src/llmDisplay.ts` (тексты карточки).
- Документация шлюза уже в репозитории: `docs/LLM_GATEWAY_ARCHITECTURE.md`, `docs/LLM_GATEWAY_PROVIDER_MATRIX.md`, `docs/LLM_GATEWAY_TEST_REPORT.md`, `docs/HANDOFF_MINIMAX_LLM_GATEWAY.md`, решения — `docs/adr/0001…0006`.

## Правка без автопилота

- Мелкие правки, известные баги и договорённости — в `.autopilot/PROGRESS.md`: это файл уровня папки `.autopilot`, рядом с `README.md` («что осталось после последней сборки… Мелкие правки без автопилота дописываются сюда же»).
- Внутри папки прогона `.autopilot/<дата>-<проект>/` лежат только `brief.md`, `manifest.md`, `spec.md` и `tickets/` — свой `PROGRESS.md` туда не класть.
- Если папки прогона ещё нет — создать `.autopilot/<дата>-<проект>/`; следующая сборка подхватит состояние оттуда («продолжи автопилот»).
- Коммит такой правки — обычный, с точными путями в `git add` (никакого `git add .`); в сообщении — что поправил и где.

## История git

- Связь коммита с требованием — трейлеры в сообщении коммита; соглашение уже в истории (10 коммитов прогона `2026-10-20`):
  ```
  Autopilot-Run: 2026-10-20-llm-gateway
  Requirements: R33, R49
  ```
  `Autopilot-Run` — папка прогона без суффикса `--wip`; `Requirements` — id требований из `manifest.md` прогона (`R##`, с дробными вроде `R05.1` и одиночными буквами вроде `R60i`).
- Перед коммитом — `python scripts/check_git_files.py --staged`, затем `git add <точные пути>`.

## Архитектура

- `docs/architecture.md` — поток данных, границы модулей и принятые соглашения по шлюзу (файл готовит владелец; пока смотреть `docs/LLM_GATEWAY_ARCHITECTURE.md` и `docs/adr/`).
