# Архитектура режиссура v2 (P0)

Статус: инкременты №1 и №2 закрыты в ветке `codex/work`. Документ описывает
состояние «как есть» на дату 2026-10-27 и план до P1.

## 1. Границы P0

В P0 входит только то, что можно проверить локально, без платных вызовов и без
второй базы данных:

- схема режиссёрского контракта кадра и проверяемые правила;
- проверка непрерывности по текстовым метаданным состояния;
- ревизии, отпечатки состояния и точечный ремонт;
- компиляция промпта под профиль модели (без сети);
- интеграция контрактов в существующую доску и план серии.

В P0 **нет**: платных генераций, vision-QC картинки, локальных моделей,
переноса кода сторонних проектов, второго хранилища.

## 2. Как есть (AS-IS)

Студия — FastAPI + SQLite + React. Решения человека хранятся рядом с медиа:

| Что | Где | Состояние |
|---|---|---|
| План серии | `backend/story_plan.py`, таблица `story_plans` | есть, ревизия целым числом |
| Предложения ИИ по плану | `backend/story_plan.py`, `story_suggestions` | есть, с защитой от повторной оплаты |
| Доска сцен и кадров | `backend/storyboard.py`, `production_nodes` | есть, ревизия — sha256 |
| Импорт сценария | `backend/storyboard.py`, `storyboard_imports` | есть, идемпотентно по `request_id` |
| Постановка кадра | `backend/shot_direction.py` | есть, свободный текст и размер плана |
| Каталог моделей | `backend/model_catalog.py`, `adapters.py` | есть, без профиля возможностей |
| Оценка и запуск платных вызовов | `backend/llm_guard.py` | есть, только через оценку и подтверждение |
| Файлы и библиотека ассетов | `backend/main.py`, `library_assets` | есть |

Чего не было: явного контракта кадра, проверки непрерывности, отпечатка
состояния кадра, разделения «что человек видел» и «что предлагает агент».

## 3. Как должно стать (TO-BE)

```
сценарий ──► реестр событий (SourceEvent)
                 │
                 ▼
             ShotContract  ◄── PhysicalFact (состояние предметов)
                 │                  PhysicalState (opening/transitions/closing)
                 │                  CameraPlan, TimeJump, FilmOrder
                 │
     ┌───────────┴───────────┐
     ▼                       ▼
 непрерывность          компиляция промпта
 (continuity.py)         (prompt_compiler.py) ──► CapabilityProfile
     │                                              │
     ▼                                              ▼
 Issue[] ──► инспектор контракта (фронт)      запрос к провайдеру (P1)
```

Правило системы: **решение принимает человек**. Контракт хранится как
редактируемая автором сущность, агент может только предложить точечную правку,
а утвердить контракт с ошибками нельзя.

## 4. Gap assessment

| Возможность | AS-IS | TO-BE | Статус | Где |
|---|---|---|---|---|
| Режиссёрский контракт кадра | нет | `ShotContract` | закрыто | `backend/director_contracts/schemas.py` |
| Реестр событий сценария | только текст сцены | `SourceEvent` + `event_ledger` | закрыто | `backend/director_contracts/event_ledger.py` |
| Непрерывность внутри кадра | нет | `check_continuity` | закрыто | `backend/director_contracts/continuity.py` |
| Непрерывность между кадрами | нет | `check_chain` | закрыто | `backend/director_contracts/continuity.py` |
| Скачки времени и флешбек | нет | `continuity_mode`, `TimeJump`, `FilmOrder` | закрыто (схема) | `schemas.py`, `continuity.py` |
| Неизменяемые авторские факты | нет | `LOCKED_PREDICATES` | закрыто | `schemas.py` |
| Отпечаток состояния | только у доски | `fingerprint`, `is_stale`, `changed_paths` | закрыто | `backend/director_contracts/revisions.py` |
| Точечный ремонт | нет | `build_patch`, `apply_patch`, `repair`, `diff` | закрыто | `backend/director_contracts/repair.py` |
| Профиль возможностей модели | плоский `MODEL_SPECS` | `CapabilityProfile` + `profile_from_catalog` | закрыто: реестр возможностей `capability.py` с подтверждёнными фактами | `backend/director_contracts/capability.py`, `backend/model_catalog.py` |
| Компиляция промпта под профиль | текст вручную | `compile_prompt` | закрыто (не подключён к адаптеру — P1) | `backend/director_contracts/prompt_compiler.py` |
| Хранение контрактов | нет | таблица `shot_contracts` | закрыто | `backend/storyboard.py` |
| Инспектор контракта в UI | нет | `ShotContractInspector` | закрыто | `frontend/src/ShotContractInspector.tsx` |
| Учёт расхода по контрактам | нет | требуется `spend_ledger.py` | P1 | отсутствует в ветке |
| Vision-QC картинки по контракту | нет | требуется `media_qc.py` | P1 | отсутствует в ветке |
| Планировщик задач провайдера | частично (`jobs`) | требуется `p0_provider_dispatch.py` | P1 | отсутствует в ветке |
| Политика запуска и утверждения | частично (`security.py`, `llm_guard.py`) | требуется `p0_control.py` | P1 | отсутствует в ветке |

## 5. Карта файлов

### Создано в инкременте №1

| Файл | Назначение |
|---|---|
| `backend/director_contracts/__init__.py` | публичный API пакета |
| `backend/director_contracts/schemas.py` | `SourceEvent`, `PhysicalFact`, `PhysicalState`, `CameraPlan`, `ShotContract`, `TimeJump`, `FilmOrder`, `CapabilityProfile`, реестр предикатов |
| `backend/director_contracts/validation.py` | `Issue`, детерминированный порядок, `validate_contracts` |
| `backend/director_contracts/event_ledger.py` | покрытие событий, стабильность ID, причинные связи |
| `backend/director_contracts/continuity.py` | `state_after`, `check_continuity`, `check_chain` |
| `backend/director_contracts/revisions.py` | `fingerprint`, `Revision`, `is_stale`, `changed_paths` |
| `backend/director_contracts/repair.py` | `PatchOp`, `RepairError`, `build_patch`, `apply_patch`, `repair`, `diff` |
| `backend/director_contracts/prompt_compiler.py` | `CompiledPrompt`, `ReferenceBinding`, `compile_prompt` |
| `backend/director_contracts/capability.py` | `CAPABILITY_FACTS`, `profile_for`, `registry`, `available_modes`, `mode_available` |
| `backend/test_director_contracts.py` | пилотный канон: Грэм, жёлтый ВАЗ-2106 VIP, раскрытие длины |
| `backend/test_director_revisions.py` | отпечатки, ревизии, ремонт |
| `backend/test_director_compiler.py` | компиляция промпта, режимы, привязка референсов |

### Инкремент №2 (тонкая интеграция)

| Файл | Изменение |
|---|---|
| `backend/storyboard.py` | таблица `shot_contracts`; `board_frames`, `plan_events`, `director_assets`, `stored_contracts`, `contract_issues`, `shot_of_path`, `director_view`; три маршрута `director/contracts` |
| `backend/story_plan.py` | `plan_events(cards, sid)`; в ответе `GET .../story-plan` появилось поле `director` |
| `backend/test_director_studio.py` | 8 тестов интеграции |
| `frontend/src/shotContract.ts` | чистая логика контракта: формы, сортировка замечаний, сборка запроса |
| `frontend/src/ShotContractInspector.tsx` | инспектор контракта кадра |
| `frontend/src/shotContract.css` | стили инспектора |
| `frontend/src/ProductionStoryboard.tsx` | кнопка «Контракт» в карточке кадра, рендер инспектора (+20 строк) |
| `frontend/shotContract.test.mjs` | 9 тестов чистой логики |

### Маршруты

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/productions/{pid}/series/{sid}/director/contracts` | контракты серии, события, замечания, реестр предикатов |
| POST | `/api/productions/{pid}/series/{sid}/director/contracts/check` | проверка контракта без сохранения |
| PUT | `/api/productions/{pid}/series/{sid}/director/contracts/{shot_id}` | сохранение контракта с проверкой ревизии |
| GET | `/api/productions/{pid}/series/{sid}/story-plan` | + поле `director` (события, предикаты) |

### Отсутствует в ветке `codex/work` (нужно для P1)

`spend_ledger.py`, `media_qc.py`, `p0_control.py`, `p0_provider_dispatch.py`,
`FrameTakes.tsx`, `CameraFramePanel.tsx`. Эти файлы есть в `main` и в другом
worktree; перенос их в ветку без решения владельца не выполнялся.

## 6. План миграции

1. **Инкремент №1 — контракты без интеграции.** Пакет `director_contracts` и
   тесты. Ничего не меняется в существующих модулях, БД и API не расширяются.
   Выполнено.
2. **Инкремент №2 — тонкая интеграция.** Хранение контрактов, маршруты,
   реестр событий из плана серии, инспектор в интерфейсе. Существующие
   маршруты не меняются, новые поля только добавляются. Выполнено.
3. **Синхронизация с `main` — выполнена.** `origin/main` слит в ветку
   `codex/work` внутри `.worktrees/codex` (по решению владельца). Ветка
   `main` и чужие worktrees не затронуты. Разрешение конфликтов описано в
   `docs/agent_handoffs/CODEX_V2_DIRECTOR2_REPORT.md`.
4. **P1 — профили возможностей и реальные запросы.** Наполнение
   `MODEL_SPECS` подтверждёнными данными, подключение `compile_prompt` к
   `adapters.wire_body`, планировщик задач, учёт расхода, QC по картинке.
   Требует отдельного согласования владельца.

## 7. Риски и ограничения

- Ветка синхронизирована с `main`: merge выполнен, конфликты разрешены,
  тесты бэкенда (326) и фронта (113) зелёные.
- Непрерывность проверяется по текстовым метаданным, а не по картинке.
  Vision-QC в P0 нет и не обещается.
- Реестр предикатов закрыт: неизвестный предикат — предупреждение, а не
  ошибка; новые свойства требуют миграции реестра.
- События в текущей интеграции порождаются карточками плана серии. Отдельного
  редактора событий нет — это P1.
