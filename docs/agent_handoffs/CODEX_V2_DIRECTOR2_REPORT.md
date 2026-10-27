# Отчёт Codex: режиссура v2, инкременты №1 и №2

Дата: 2026-10-27. Ветка: `codex/work`. Рабочая копия:
`C:\AI_Workflow_Studio\.worktrees\codex`.

## 1. Baseline, ветка, статус

| Параметр | Значение |
|---|---|
| Репозиторий | `C:\AI_Workflow_Studio` (корень = main + рабочие данные) |
| Рабочая копия | `.worktrees/codex`, ветка `codex/work` |
| HEAD на момент начала | `2d4d94e` «Document staged design improvements and Claude Code handoff» |
| Отношение к `origin/main` на момент начала | отставал на 119 коммитов, опережал на 31 (`git fetch origin` выполнен, exit 0) |
| Merge `origin/main` | выполнен позже в этой же сессии по решению владельца («сливай только в свою папку»): слито в ветку `codex/work` внутри `.worktrees/codex`, main и чужие worktrees не тронуты |
| Состояние worktree до работы | ` M docs/HANDOFF_CLAUDE_CODE.md` и untracked `standalone/`, `.artifacts/`, `beta-generation-check.png`, два handoff-документа — **чужие правки, не тронуты**; перед merge чужую правку handoff убрали в stash и вернули после |
| Отправка в main | не выполнялась |
| Push | не выполнялся |

## 2. Что реально добавлено

### Инкремент №3 — реестр возможностей моделей

Закрывает требование внешнего аудита (`GremoVOD_FIGMA_COZYCLAY_COURSE_AUDIT_2026-10-27.md`):
«модель → возможности, цена, лимиты — не хардкод» и «выбор first/last-frame
недоступен у модели, которая этот способ не поддерживает».

| Файл | Изменение |
|---|---|
| `backend/director_contracts/capability.py` | `CAPABILITY_FACTS` (подтверждённые факты со ссылкой на источник), `facts_for`, `profile_for`, `registry`, `available_modes`, `mode_available` |
| `backend/director_contracts/schemas.py` | `profile_from_catalog(spec, facts=None, model_id=None)`; поле `capability_source`; режим `text_to_video` в `Mode` |
| `backend/director_contracts/prompt_compiler.py` | Видеомодель без подтверждённого стартового кадра → `text_to_video` (было `text_to_image`) |
| `backend/storyboard.py` | `GET /api/productions/{pid}/director/capabilities` — реестр для интерфейса, только чтение |
| `backend/test_director_capability.py` | 10 тестов реестра |
| `backend/test_director_studio.py` | 2 теста маршрута |
| `docs/director/V05_AUDIT_AND_DECISIONS.md` | Аудит по документу владельца: матрица реализовано/частично/нет и десять решений Р1–Р10 |

Источники фактов — документация провайдеров, уже разобранная в репозитории:
`docs/VIDEO_MODELS_PROMPTING_2026-10-17.md`, `skills/video-kling-3-start-end-frame`,
`skills/video-kling-3-omni`, `skills/video-minimax-h3`. Чего в источниках нет —
не подтверждено (fail-closed).

### Инкремент №1 — чисто контрактный слой, без интеграции

| Файл | Строк | Назначение |
|---|---|---|
| `backend/director_contracts/__init__.py` | 102 | публичный API пакета |
| `backend/director_contracts/schemas.py` | 235 | `SourceEvent`, `PhysicalFact`, `PhysicalState`, `CameraPlan`, `ShotContract`, `TimeJump`, `FilmOrder`, `CapabilityProfile`, `profile_from_catalog`, реестры `PREDICATES` / `LOCKED_PREDICATES` |
| `backend/director_contracts/validation.py` | 78 | `Issue`, `sort_issues`, `errors`, `has_errors`, `validate_contracts` |
| `backend/director_contracts/event_ledger.py` | 186 | `check_events`, `check_coverage`, `check_shots`, `check_asset_references`, `check_ids_stable`, `film_order`, `timeline_order` |
| `backend/director_contracts/continuity.py` | 152 | `state_after`, `check_continuity`, `check_chain` |
| `backend/director_contracts/revisions.py` | 143 | `payload_of`, `canonical`, `fingerprint`, `fingerprint_events`, `fingerprint_shot`, `Revision`, `current_revision`, `propose`, `is_stale`, `changed_paths` |
| `backend/director_contracts/repair.py` | 168 | `PatchOp`, `RepairError`, `build_patch`, `apply_patch`, `repair`, `diff` |
| `backend/director_contracts/prompt_compiler.py` | 221 | `CompiledPrompt`, `ReferenceBinding`, `compile_prompt` |
| `backend/test_director_contracts.py` | ~330 | пилотный канон: Грэм, жёлтый ВАЗ-2106 VIP, раскрытие длины |
| `backend/test_director_revisions.py` | ~180 | отпечатки, ревизии, точечный ремонт |
| `backend/test_director_compiler.py` | ~230 | компиляция промпта, выбор режима, привязка референсов |

### Инкремент №2 — тонкая интеграция

| Файл | Что изменено |
|---|---|
| `backend/storyboard.py` | таблица `shot_contracts`; функции `board_frames`, `plan_events`, `director_assets`, `stored_contracts`, `contract_issues`, `shot_of_path`, `director_view`; маршруты `GET/POST/PUT .../director/contracts` |
| `backend/story_plan.py` | функция `plan_events(cards, sid)`; в ответе `GET .../story-plan` добавлено поле `director` |
| `backend/test_director_studio.py` | 8 тестов интеграции |
| `frontend/src/shotContract.ts` | чистая логика: `emptyContract`, `addFact`/`removeFact`/`updateFact`, `sortIssues`, `issueCounts`, `validateDraft`, `contractPayload` |
| `frontend/src/ShotContractInspector.tsx` | инспектор контракта кадра |
| `frontend/src/shotContract.css` | стили инспектора |
| `frontend/src/ProductionStoryboard.tsx` | кнопка «Контракт» в карточке кадра + рендер инспектора (+20 строк, дифф точечный) |
| `frontend/shotContract.test.mjs` | 9 тестов чистой логики |

### Документация

`docs/director/DIRECTOR_V2_ARCHITECTURE.md`, `docs/director/SHOT_CONTRACT_V1.md`,
`docs/director/EVENT_CONTINUITY_RULES.md`,
`docs/director/EXTERNAL_RESEARCH_REFERENCES.md`, этот отчёт.

## 3. Схема, маршруты, совместимость

### Схема

Полное описание — `docs/director/SHOT_CONTRACT_V1.md`. Кратко: `ShotContract`
(shot_id, scene_id, source_event_ids, duration_sec, narrative_role,
character_ids, asset_reference_ids, camera, physical_state,
author_lock_version, status, locked_paths), `SourceEvent`, `PhysicalFact`,
`PhysicalState`, `CameraPlan`, `TimeJump`, `FilmOrder`, `CapabilityProfile`.
Все модели Pydantic v2 с `extra='forbid'`.

### Маршруты

| Метод | Путь | Поведение |
|---|---|---|
| GET | `/api/productions/{pid}/series/{sid}/director/contracts` | контракты серии, события, замечания по кадру и по серии, реестр предикатов |
| POST | `/api/productions/{pid}/series/{sid}/director/contracts/check` | проверка контракта без сохранения |
| PUT | `/api/productions/{pid}/series/{sid}/director/contracts/{shot_id}` | сохранение: `400` чужой кадр/сцена, `404` кадр не найден, `409` конфликт ревизии, `422` ошибка схемы |
| GET | `/api/productions/{pid}/series/{sid}/story-plan` | новое поле `director`: события плана и реестр предикатов |

Существующие маршруты не менялись; новые поля только добавляются.

### Совместимость

- Данные в новой таблице `shot_contracts`; существующие таблицы не тронуты.
- Контракт с ошибками сохраняется со статусом `draft` (в ответе
  `downgraded: true`) — утвердить нельзя, но и терять правку не нужно.
- Повреждённая запись контракта пропускается при чтении и не роняет раздел.
- Старые клиенты не ломаются: поля только добавляются.

## 4. Тесты и проверки

| Проверка | Команда | Результат |
|---|---|---|
| Полный бэкенд (после merge `origin/main`) | `python -X utf8 -m pytest backend -q` | **326 passed, 16 subtests passed**, 78.45 с, exit 0 (до merge было 260; main добавил 66) |
| Полный бэкенд (после инкремента №3) | `python -X utf8 -m pytest backend -q` | **338 passed, 16 subtests passed**, 83.25 с, exit 0 |
| Фронт (после merge) | `npm test` (в `frontend/`) | **113 passed**, 0 failed (до merge было 47) |
| Сборка фронта (после merge) | `npm run build` (`tsc --noEmit && vite build`) | **exit 0**, 1878 модулей, сборка 4.01 с |
| Полный бэкенд (до merge) | `python -X utf8 -m pytest backend -q` | 260 passed, 16 subtests passed, exit 0 |
| Тот же набор через unittest | `python -X utf8 -m unittest discover -s backend -p "test_*.py"` | Ran 260 tests — OK |
| Тесты режиссуры | `pytest backend/test_director_contracts.py backend/test_director_studio.py backend/test_director_revisions.py backend/test_director_compiler.py -q` | **78 passed** |
| Пробелы в диффе | `git diff --check` | exit 0 |
| Формат | `npx prettier --write` по новым фронт-файлам | применён |

Предупреждения (36) — только deprecation `on_event` FastAPI, существовали до
этой работы.

### Живая проверка на отдельном стенде

Бэкенд поднят из ветки на порту 8111 со своей `STUDIO_DATA_DIR` (рабочая
студия на 8000/5173 не затронута). Сценарий: проект → постановка → серия →
сцена → два кадра → план серии → маршруты режиссуры.

```
contracts=2 events=1 issues=1
issue codes: event_missing
shots: 1.1 Closeup | 1.2 Wide
check ok=True issues=
saved revision=1 downgraded=False status=approved
conflict status=409
after save: filled=1 issues=
plan director events=card-1 predicates=13
SMOKE OK
```

### Проверка в браузере

Интерфейс проверен вживую на стенде (бэкенд 8111 со своей БД, фронт 5199 с
прокси на него; рабочая студия на 8000/5173 не затронута):

- кнопка «Контракт» в карточке кадра открывает инспектор под доской;
- инспектор подхватывает сохранённый контракт: длительность 4, роль
  «Раскрытие», статус «Утверждён», кадр `medium`, движение `push_in`,
  событие сценария отмечено, три блока состояния заполнены;
- «Проверить» → «Нарушений не найдено.»;
- «Сохранить контракт» → «Контракт сохранён.», ревизия контракта выросла с 1
  до 2, статус остался `approved`.

Замечание по стенду: `ORIGINS` в `backend/security.py` жёстко ограничены
портами 5173 и 8000, поэтому POST с фронта на 5199 отбивался «Запрос с
постороннего сайта запрещён». Это ограничение стенда, а не дефект: рабочая
студия живёт на разрешённых портах. В стенде Origin подменяется на
разрешённый в конфиге vite, который лежит вне репозитория.

### Проверка после слияния с main

Тот же живой сценарий на слитом коде (стенд 8111, своя БД):

```
contracts=2 events=1 issues=1
issue codes: event_missing
check ok=True issues=
saved revision=1 downgraded=False status=approved
conflict status=409
after save: filled=1 issues=
plan director events=card-1 predicates=13
SMOKE OK
```

Режиссура работает на слитом коде без изменений. Чужую незакоммиченную правку
`docs/HANDOFF_CLAUDE_CODE.md` вернули ровно в прежнем виде: 8 добавленных
строк, без воскрешения блоков, которые main переписал.

### Найденный и исправленный дефект

Первый живой прогон показал ложную ошибку на законном контракте: «дверь
открывается внутри кадра» (`opening=closed`, переход `closed→open`,
`closing=open`) помечался `continuity_value_mismatch`. Причина — правило
сравнивало **начало** кадра с **концом**, а не состояние после переходов.

Исправлено в `backend/director_contracts/continuity.py`: конец кадра теперь
сверяется с состоянием после переходов, а факт, появившийся только в конце,
даёт предупреждение `continuity_undeclared_closing`. Добавлено 4 теста
(3 в `test_director_contracts.py`, 1 в `test_director_studio.py`) и обновлено
правило 5 в `docs/director/EVENT_CONTINUITY_RULES.md`.

### Доказательство, что тесты bite

Обе проверки были намеренно сломаны, тесты упали, после отката — снова зелёные:

```
# check_chain отключён → упал test_chain_break_between_neighbouring_shots_is_reported
# проверка ревизии отключена → упал test_contract_saves_once_and_conflicting_revision_is_rejected
2 failed, 6 passed   →   после отката: 20 passed (с story_plan и storyboard)
```

Правило непрерывности проверялось так же: до исправления 4 новых теста падали
(`test_change_declared_by_a_transition_is_not_a_mismatch`,
`test_closing_must_match_the_state_after_transitions`,
`test_fact_that_appears_only_at_the_end_is_a_warning`,
`test_state_change_inside_the_shot_saves_without_downgrade`), после — 78 passed.

## 5. Референсы → концепция → своя реализация → лицензия

Полная таблица с источниками — `docs/director/EXTERNAL_RESEARCH_REFERENCES.md`.
Кратко:

| Референс | Концепция | Своя реализация | Лицензия | Код перенесён |
|---|---|---|---|---|
| Maestro | источник, физические контракты, проверка схемы, чекпоинты | `director_contracts/schemas.py`, `validation.py`, `repair.py` | WanGP Non-Commercial Evaluation 1.1 (seed-vc внутри — GPL-3.0) | нет |
| Maestro | неизменяемые авторские свойства | `LOCKED_PREDICATES`, `continuity_locked_change` | та же | нет |
| Maestro | флешбек как расхождение порядков | `presentation_order`/`timeline_order`, `TimeJump`, `FilmOrder` | та же | нет |
| MoneyPrinterTurbo | машина состояний, идемпотентность, ревизии артефактов | `revisions.py`, `repair.py`, существующие `jobs` | MIT | нет |
| AI Video Production Editor | инспектор узла, каталог возможностей, права агента | `ShotContractInspector.tsx`, `CapabilityProfile`, `locked_paths` | GPL-3.0-or-later | нет |
| StoryBored | выбор дубля и утверждение человеком | `status` контракта `draft → proposed → approved` | не подтверждено (поиск привёл на другой продукт) | нет |

Ни одна внешняя зависимость не добавлена: в `backend/director_contracts/`
импортируются только `pydantic` и стандартная библиотека.

## 6. Финансы: платных вызовов — 0

Доказательство:

1. В `backend/director_contracts/` нет ни одного сетевого импорта. Полный
   список импортов пакета: `pydantic`, `hashlib`, `json`, `copy`, `re`,
   `dataclasses`, `typing`.
2. Поиск по новым файлам (`director_contracts/*.py`, `test_director_*.py`,
   `shotContract.ts`, `ShotContractInspector.tsx`) на `httpx|requests|aiohttp|
   urllib|guarded_chat|request_piapi|estimate_usd|quote|api_key` даёт
   единственные совпадения — строковый литерал `provider='piapi'` в
   `schemas.py:215` и тестовые фикстуры. Сетевых вызовов нет.
3. Новые маршруты (`director/contracts`) не вызывают `llm_guard.guarded_chat`
   и не требуют оценки стоимости: это чтение и запись локальных данных.
4. `compile_prompt` собирает текст и поля запроса, но ничего не отправляет.
   Подключение к адаптеру — P1.
5. Ключи провайдеров в коде отсутствуют, в тестах используются заглушки.

Платные генерации в этом инкременте не запускались.

## 7. Откат

Инкременты аддитивные: новая таблица + новые маршруты + новые файлы. Откат:

```powershell
cd C:\AI_Workflow_Studio\.worktrees\codex
git revert <commit-инкремента-1>   # или: git revert <commit-инкремента-2>
```

Отдельно, если нужно убрать только данные:

```sql
DELETE FROM shot_contracts;
```

Код других агентов, чужие worktree и main не затронуты. Данные в
`C:\AI_Workflow_Studio` (рабочие данные студии) не менялись: тесты работают на
изолированной временной базе.

## 8. Блокеры и что нужно от владельца

1. **Синхронизация с main — сделано.** `origin/main` слит в `codex/work` внутри
   `.worktrees/codex`. Конфликты (30 файлов) разрешены так:
   - навыки и документы — в пользу main (там версии на 2–4 строки новее);
   - фронт (`App.tsx`, `CreateScreen.tsx`, `HomeScreen.tsx`, `Lightbox.tsx`) — в
     пользу main: в main появилось новое семейство `Frame*` (`FrameActions`,
     `FrameTakes`, `FrameCast`, `CameraFramePanel`) вместо моего `mediaAsset`;
   - `ProductionStoryboard.tsx` — база main, поверх неё наложена интеграция
     режиссуры (импорт, состояние, кнопка «Контракт», рендер инспектора);
   - `story_plan.py` — моя версия (main = моя версия минус мои три добавления);
   - `storyboard.py` — обе стороны: контракты кадра + `outline`/`Reorder`/отправка;
   - `production_entities.py` — семантическое объединение: правила ракурса и
     локации из main + проверка постановки съёмки из моей ветки.
   Осиротевшие после слияния `mediaAsset.ts`, `MediaAssetActions.tsx` и их тест
   удалены — в main их заменило семейство `Frame*`.
2. **Модули P1 отсутствуют и в main.** `spend_ledger.py`, `media_qc.py`,
   `p0_control.py`, `p0_provider_dispatch.py` не найдены ни в `origin/main`, ни
   в дереве слияния: они лежат только в другом worktree/ветке. Переносить их в
   `codex/work` без решения владельца не выполнялось. `FrameTakes.tsx` и
   `CameraFramePanel.tsx` после слияния доступны.
3. **Commit SHA референсов.** `git clone` во внешний каталог заблокирован
   политикой bash, поэтому SHA не зафиксированы — в документе указаны URL и
   лицензии.
4. **Расхождение с ТЗ в имени предиката.** В примере ТЗ предикат `position`,
   в коде — `camera_position`. Расхождение задокументировано в
   `EVENT_CONTINUITY_RULES.md`.
5. **P1 без отдельного approval не начинается** — так требует ТЗ, и этот
   отчёт его соблюдает.

## 9. Что проверено, а что нет

**Проверено запуском:** тесты бэкенда (260 через pytest и 260 через unittest),
тесты фронта (47), сборка фронта (exit 0), `git diff --check` (exit 0),
красный→зелёный прогон новых тестов, отсутствие сетевых вызовов в новом коде,
живой сценарий по новым маршрутам на отдельном стенде (порт 8111, своя БД),
работа инспектора контракта в браузере: открытие, загрузка сохранённого
контракта, «Проверить», «Сохранить контракт» с ростом ревизии.

**Не проверено:** поведение на ветке, слитой с `main`; платные вызовы (не
запускались по условию); работа сценариев вне сценария «контракт сохранён»
(конфликт ревизии в интерфейсе пока не воспроизводился — на уровне API он
проверен).
