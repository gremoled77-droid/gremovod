# ARCHITECTURE_MAP — GremoVOD

Проверено по коду на `main` @ `82adb2d28efa05bf8face168485fe07ae340e0bc`
и по PR #29 @ `c082829b11b968965600bdaf87c137b1485a0fa2`.
Все строки модулей — реальные `wc -l`, не оценка.

---

## 1. Топология рантайма

```
                    ┌─────────────────────────────────────────┐
  Браузер  ───────► │  FastAPI  backend/main.py  (764 строки)  │
                    │  21 модуль register(app, studio)          │
                    └───────┬──────────────────────┬───────────┘
                            │                      │
              ┌─────────────▼──────┐    ┌──────────▼──────────────┐
              │  SQLite (1 файл)   │    │  Файловые каталоги медиа │
              │  studio.sqlite3    │    │  media/, library/, ...  │
              └────────────────────┘    └─────────────────────────┘
                            │
        ┌───────────────────┼────────────────────┐
        │                   │                    │
   PiAPI / KIE      ElevenLabs / Fish      OpenAI-совместимый LLM
   (image, video)   (TTS, SFX, music)      (сценарий, чат)
```

### 1.1 Критично: путь к БД по умолчанию — внутри репозитория

`backend/main.py:22-24`:

```python
DATA=Path(os.environ['STUDIO_DATA_DIR']).resolve() if os.environ.get('STUDIO_DATA_DIR') else None
DB=(DATA or ROOT)/'studio.sqlite3'
```

Если `STUDIO_DATA_DIR` **не задан**, БД создаётся как `backend/studio.sqlite3` —
то есть **внутри рабочей копии Git**. Это не баг сам по себе (путь в `.gitignore`
есть: `backend/studio.sqlite3`), но это делает БД зависимой от расположения кода
и повышает риск коммита/копирования. В PR #29 добавлен `studio_db.resolve()` с
fail-closed проверкой пути — см. `P0_EVIDENCE.md` B-05.

### 1.2 Режим удалённого доступа

`backend/remote_access.py` (134 строки) — пароль, cookie-сессия, allowlist.
Регистрируется в `main.py:832`. `backend/security.py` (114 строк) — CORS, `ORIGINS`.
Регистрируется в `main.py:790`.

### 1.3 Связка с n8n

`backend/workflow_import.py` (84 строки, `main.py:818`) — импорт JSON-описаний воркфлоу.
То есть n8n-схемы **исполняются n8n**, а FastAPI обслуживает медиа-хранилище,
состояние и платные вызовы. Прямого исполнения графа воркфлоу внутри Python нет.

---

## 2. Backend: инвентарь модулей (45 модулей, 6 877 строк)

| Модуль | Строк | Роль | Живой? |
|---|---:|---|---|
| `main.py` | 764 | Точка входа, FastAPI, 21 `register()` | entry |
| `reel_recipes_data.py` | 824 | Статические рецепты рилсов (данные) | импорт. |
| `production_folders.py` | 355 | Файловая структура производства | `register` |
| `storyboard.py` | 302 | Раскадровка | `register` |
| `adapters.py` | 288 | Провайдерские адаптеры: build/cost/submit | импорт. |
| `sound.py` | 267 | TTS, SFX, музыка | `register` |
| `native_chat.py` | 248 | Нативный LLM-чат | `register` |
| `visual_plan.py` | 243 | Визуальный план | `register` |
| `story_plan.py` | 235 | Сценарный план | `register` |
| `temp_cleanup.py` | 211 | Уборка временных файлов | startup-hook |
| `model_catalog.py` | 204 | Каталог моделей и цен | импорт. |
| `edit_list.py` | 167 | Монтажный лист | `register` |
| `production_entities.py` | 161 | Сущности производства | `register` |
| `frame_analysis.py` | 146 | Анализ кадров | `register` |
| `character_voice.py` | 146 | Голоса персонажей | `register` |
| `llm_guard.py` | 142 | Ограничители LLM-вызовов | `register` |
| `external_generation.py` | 138 | Внешняя генерация | импорт. |
| `remote_access.py` | 134 | Удалённый доступ, пароль, cookie | `register` |
| `connections.py` | 109 | Соединения между сущностями | импорт. |
| `production_workspace.py` | 110 | Рабочее пространство | импорт. |
| `reel_recipes.py` | 106 | API рецептов рилсов | `register` |
| `motion.py` | 94 | Движение камеры/объектов | `register` |
| `frame_composition.py` | 90 | Композиция кадра | `register` |
| `activity.py` | 86 | Лента активности | импорт. |
| `reference_upload.py` | 85 | Загрузка референсов | `register` |
| `workflow_import.py` | 84 | Импорт n8n-воркфлоу | `register` |
| `character_versions.py` | 81 | Версии персонажей | импорт. |
| `prompt_rules.py` | 74 | Правила промптов | импорт. |
| `car_staging.py` | 73 | Студийная постановка | импорт. |
| `image_assets.py` | 72 | Изображения | импорт. |
| `clip_chain.py` | 61 | Цепочка клипов | `register` |
| `refinement.py` | 61 | Уточнение/рефайн | импорт. |
| `send_to_reference.py` | 61 | Отправка в референс | импорт. |
| `economics.py` | 88 | Экономика | `register` |
| `series_economics.py` | 60 | Экономика серий | `register` |
| `camera_movements.py` | 66 | Базовые движения камеры | `register` |
| `job_delivery.py` | 66 | Доставка результатов задач | импорт. |
| `character_description.py` | 56 | Описания персонажей | импорт. |
| `kie.py` | 56 | Клиент KIE | импорт. |
| `llm_response.py` | 43 | Разбор LLM-ответа | импорт. |
| `job_recovery.py` | 42 | Восстановление задач | импорт. |
| `prompt_setup.py` | 27 | Настройка промптов | импорт. |
| `image_pricing.py` | 21 | Расчёт цены изображений | импорт. |
| `idea_background.py` | 16 | Фон идеи | `register` |

**Мёртвых модулей нет.** Проверено: каждый из 45 либо вызывается через
`register(...)` в `main.py`, либо импортируется другим модулем. Проверка выполнена
по `import`-выражениям, а не по упоминанию имени в тексте.

### 2.1 Ключевые рёбра зависимостей

- `main.py` → `adapters`, `kie` (`main.py:17`) — единая точка доступа к провайдерам.
- `main.py` → `native_chat` (`main.py:774-776`), `economics` (`main.py:777`).
- `main.py:185` — результат провайдера `kie` забирается через `kie.fetch(...)`;
  `main.py:471-472` — отправка: `kie.submit(...)` либо `request_piapi(...)`.
- `adapters` обслуживает **все** внешние вызовы: `adapters.handles(spec)`,
  `adapters.build`, `adapters.cost`, `adapters.submit_path`, `adapters.wire_body`,
  `adapters.describe` (`main.py:384-441`).

> Аудитору: `adapters.py` + `main.py:384-472` — это **единственный** путь к платным
> провайдерам на `main`. P0-контур PR #29 добавляет второй, защищённый путь
> (`p0_provider_dispatch.py`). Это главный вопрос о дублировании денежных путей.

---

## 3. Frontend (React 18 + TS + Vite)

`frontend/package.json`: `react` 18, `react-dom` 18, `@xyflow/react` (граф воркфлоу),
`lucide-react` (иконки), `typescript` 5.7, `vite` 5.4. Скрипты: `dev`, `build`,
`preview`, `test` = `node --experimental-strip-types --test`.

Ключевые компоненты (все существуют, проверено по `frontend/src/`):

| Компонент | Файл | Назначение |
|---|---|---|
| `App.tsx` | `frontend/src/App.tsx` | Каркас приложения, маршрутизация экранов |
| `StageNav` | `frontend/src/components/StageNav.tsx` | Навигация по стадиям производства |
| `Dock` | `frontend/src/components/Dock.tsx` | Нижняя панель |
| `HomeScreen` | `frontend/src/HomeScreen.tsx` | Стартовый экран |
| `CreateScreen` | `frontend/src/CreateScreen.tsx` | Создание проекта |
| `ProductionStoryboard` | `frontend/src/components/ProductionStoryboard.tsx` | Раскадровка |
| `WorkflowPanel` | `frontend/src/components/WorkflowPanel.tsx` | Панель воркфлоу |
| `GenerationReview` | `frontend/src/components/GenerationReview.tsx` | Проверка генераций |
| `ActivityContext` / `useActivity` | `frontend/src/context/ActivityContext.tsx` | Лента активности |
| `GenerationWatcher` | `frontend/src/components/GenerationWatcher.tsx` | Наблюдение за задачами |

**Тесты фронтенда:** 26 файлов `*.test.mjs` в `frontend/` (в корне, не в `src/`):
`createDraft`, `directorState`, `projectMerge`, `visualPlan`, `workspaceNavigation`,
`attachments`, `boardOrder`, `cameraFrameCatalog`, `characterPrompt`, `directorPresets`,
`framePrompt`, `frameStatus`, `motionPrompt`, `operatorPrompt`, `outlinePlan`,
`reelRecipes`, `replaceCharacterPrompt`, `sheetShots`, `soundCues`, `spendLimit`,
`videoMode`, `workflowConnections`, `workflowLibrary`, `workflowNodes`, `worldBible`.

> **Нюанс окружения (влияет на воспроизводимость):** фронт-тесты подгружают модули
> `backend/*.py` через дочерний процесс. Интерпретатор выбирается так:
> `process.env.STUDIO_PYTHON || findVenvPython(cwd) || 'python3'`
> (`frontend/directorState.test.mjs`). Без `.venv` в корне и без `STUDIO_PYTHON`
> тесты падают с `ModuleNotFoundError: No module named 'fastapi'` — то есть
> **не из-за кода, а из-за окружения**. Это же делает фронт-тесты зависимыми от
> состояния Python-окружения CI. Подробности — `TEST_RESULTS.md`.

---

## 4. Зрелость реализации по доменам

| Домен | Модуль | Путь к провайдеру | Зрелость |
|---|---|---|---|
| Сценарий | `story_plan.py`, `native_chat.py` | LLM | **IMPLEMENTED** |
| Раскадровка | `storyboard.py` | локально | **IMPLEMENTED** |
| Визуальный план | `visual_plan.py` | локально | **IMPLEMENTED** |
| Изображения | `adapters.py` (`image_pricing`, `image_assets`) | PiAPI через `adapters` | **IMPLEMENTED** (цена — `image_pricing.py`, 21 строка) |
| Видео | `adapters.py`, `motion.py`, `clip_chain.py` | PiAPI | **IMPLEMENTED** на `main`; в n8n-конвейере — **MOCK** |
| Нативный звук | `sound.py` | PiAPI | **IMPLEMENTED** |
| TTS | `sound.py`, `character_voice.py` | ElevenLabs / Fish | **IMPLEMENTED** |
| SFX | `sound.py` | провайдер | **IMPLEMENTED** |
| Музыка | `sound.py` | провайдер | **IMPLEMENTED** |
| Монтаж | `edit_list.py`, `clip_chain.py` | локально | **IMPLEMENTED** |
| Релиз/экспорт | `main.py` (медиа-эндпоинты) | локально | **PARTIAL** — нет отдельной сущности «релиз» |
| **n8n-конвейер WF_00–WF_06** | `workflows/*.json` | — | **MOCK** (`MOCK ONLY (SOURCE EXPORT)`, `active=false`) |
| **Контракты production** | `docs/specs/n8n-production-2026-10-19/` | — | **SPEC-ONLY** (не исполняемый код) |
| **P0-бюджет/авторизация** | `backend/p0_*.py` (PR #29) | — | **IMPLEMENTED, но не в `main`** |
| **Ревьюер MiniMax** | `tools/ai_review/` (PR #35) | — | **MOCK** (адаптер `mock`) |

> Разделение `IMPLEMENTED / PARTIAL / MOCK / SPEC-ONLY` здесь существенно.
> В проекте зелёный n8n-execution в MOCK-режиме **не** означает рабочий конвейер —
> это прямо зафиксировано в `docs/AUTORUN_6_STAGES_REPORT.md:42`:
> «Зелёный n8n execution **не** означает production».

---

## 5. Покрытие тестами (факт, не оценка)

| Зона | Файлов | Строк |
|---|---:|---:|
| `backend/test_*.py` | 37 | 3 507 |
| `frontend/*.test.mjs` | 26 | — |
| PR #29: `tools/test_*.py` | 2 | — |
| PR #29: `tests/test_p0_state.js` | 1 | — |
| PR #34: `tests/test_*.py` | 2 | — |
| PR #35: `tests/test_*.py` | 8 | — |

**Пустой тест-файл:** `backend/test_production_entities.py` — **0 строк**.
Файл существует и участвует в discovery, но не проверяет ничего. Проверено
чтением файла.

**Без тестов (по инвентарю):** `production_workspace`, `connections`, `job_delivery`,
`job_recovery`, `reel_recipes_data` (данные), `car_staging`, `send_to_reference`,
`character_description`, `refinement`. Для части из них покрытие есть косвенное —
через `main`-уровневые тесты, — но собственных модульных тестов у них нет.

---

## 6. Гигиена репозитория

- `.gitignore` покрывает `.env`, `*_API_KEY.txt`, `backend/studio.sqlite3`,
  `backend/media/`, `projects/`, `runtime/`, `tools/`, `artifacts/`.
- ⚠️ **Правило `tools/` в `.gitignore` (строка ~47) делает весь каталог `tools/`
  неотслеживаемым.** PR #34 это исправляет (`!tools/` + `tools/*` + `!tools/ai_review/`),
  а **PR #35 — нет**: его 14 файлов `tools/ai_review/` в индексе есть (добавлены
  принудительно), но **любой новый файл под `tools/` на этой ветке будет молча
  проигнорирован**. См. `OPEN_ISSUES.md` OI-08.
- `node_modules/` в игноре — установка зависимостей не влияет на состояние Git
  (проверено: `git status --short` пуст после `npm ci`).
