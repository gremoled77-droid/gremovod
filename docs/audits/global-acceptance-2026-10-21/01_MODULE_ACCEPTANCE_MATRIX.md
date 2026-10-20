# Матрица приёмки модулей

**PARTIAL.** Статус оценивает весь производственный маршрут, а не наличие экрана. `VERIFIED_WORKING` ниже допустим только для явно ограниченного офлайн-компонента, проверенного в текущем аудите. Тесты с mock не подтверждают реальное качество/цену провайдера.

Обозначения доказательств: B — текущие backend-тесты на временных данных; F — 120 frontend unit-тестов; T — tsc/build. Браузерного E2E нет. Полные результаты — [08](08_ACCEPTANCE_AND_RETEST_PLAN.md).

## Девять основных стадий

| Стадия | Статус всего маршрута | Реализация / UI | Связь и сохранение | Проверено сейчас / блокировка |
|---|---|---|---|---|
| Идея | PARTIAL | Producer [backend/producer_stage.py:399](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/producer_stage.py#L399), [frontend/src/ProducerPanel.tsx:27](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/frontend/src/ProducerPanel.tsx#L27) | выбирает project/cast/refs; callback сохраняет scenario в project [frontend/src/App.tsx:2077](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/frontend/src/App.tsx#L2077) | B: mock contract, selected refs, quote denial; F/T. Художественная ценность и paid result NOT_RUN |
| Мир и персонажи | PARTIAL | [backend/production_folders.py:276](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/production_folders.py#L276), [frontend/src/App.tsx:1893](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/frontend/src/App.tsx#L1893) | character library, категории reference/approved/rejected, shared owner refs | B: roundtrip, categories, project isolation, версии. Визуальное соответствие реальным героям NOT_RUN |
| Сценарий | PARTIAL | [backend/story_plan.py:133](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/story_plan.py#L133), [frontend/src/StoryPlanBoard.tsx:67](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/frontend/src/StoryPlanBoard.tsx#L67) | отдельные plan revision/board revision; preview/apply сохраняет сцены и не переписывает старый текст | B: stale revision, foreign links, rollback. Автоматический Producer→Story Plan не подтверждён; ручная сборка полного эпизода NOT_RUN |
| Раскадровка | PARTIAL | [backend/main.py:971](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L971), ProductionStoryboard / production_entities | hierarchy, selected image/video, cast/location, shooting data | B: board order, entity navigation, stale sources; F/T. Полный UI путь и утверждённый эпизод NOT_RUN |
| Изображения | PARTIAL | [backend/main.py:538](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L538), CreateScreen / GenerationReview | estimate→confirm→job→delivery→library; external generation — отдельный ручной маршрут | B: mock submit, rejection, idempotency, downloads, reopen. Платные refs/edit и провайдерские outputs NOT_RUN |
| Видео | PARTIAL | VideoScreen, adapters, [backend/main.py:568](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L568) | jobs и library; clip_chain/последний кадр | B: synthetic MP4 delivery/reopen и last-frame; тесты временно включают launch flags моделей, что не является их активацией |
| Звук | PARTIAL | [backend/character_voice.py:129](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/character_voice.py#L129), [backend/sound.py:1](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/sound.py#L1), SoundScreen | voices, cues, файлы на кадрах, CSV/длительность | B: WAV import/analyze/cut, mock TTS и бюджет. Настоящие голоса, музыка, эмоциональный тайминг NOT_RUN |
| Монтаж | PARTIAL | [backend/edit_list.py:160](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/edit_list.py#L160), [frontend/src/EditListPanel.tsx:30](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/frontend/src/EditListPanel.tsx#L30), motion, clip_chain | JSON/CSV списка файлов, cuts/warnings; ручной CapCut | B: synthetic durations, order, CSV, safe failure; motion transport mocked. Реальный CapCut import/render NOT_RUN |
| Выпуск | PARTIAL | [backend/release_artifacts.py:181](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/release_artifacts.py#L181), [frontend/src/StageSummary.tsx:121](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/frontend/src/StageSummary.tsx#L121) | project revision + prompt version + local master/library; N34/N35 отдельно | B: upload/QC/freeze на synthetic MP4. P1-03: ready не доказывает QC/owner approval; реальный финальный файл NOT_RUN |

Навигация содержит 9 UI-этапов, но сценарий объединён с «Идеей», а персонажи выделены отдельно: [frontend/src/StageNav.tsx:31](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/frontend/src/StageNav.tsx#L31). Это UI-группировка, не отсутствие Story Plan.

## Сквозные подсистемы

| Модуль / граница | Статус | Текущие доказательства и предел |
|---|---|---|
| Project/production persistence на временной базе | VERIFIED_WORKING | B: smoke project roundtrip, production tree, workspace promote/rollback; рабочая БД не проверялась |
| Producer MOCK | MOCK_ONLY | test_producer_stage: deterministic structure, 0 provider calls, schema/refs checks. Код paid-ветки существует, но её реальное исполнение не проверялось |
| Writers' Room как полный самостоятельный runtime | IMPLEMENTED_UNVERIFIED | main AGENT_ROLES + draft n8n manifests; 3-role prototype не эквивалентен рабочей writers-room серии |
| Character Vault storage/selection | VERIFIED_WORKING | B: category exclusions, selected references, shared refs; качество личности и канон утверждает владелец |
| Style Library / визуальные правила | PARTIAL | state.style + visual_plan + prompt rules; Библия мира не равна автономному каталогу утверждённых style assets |
| Continuity | PARTIAL | prompt-role [backend/main.py:717](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L717), cast/location/car validators; не найдена отдельная исполняемая модель before/after continuity всего эпизода |
| Prompt Adapter / per-model profiles | PARTIAL | system_rules, adapters/catalog, quote payload, revisions; B/F. Действительность live contract каждого provider/model NOT_RUN |
| LLM prepare/permit/execute | BROKEN | текущая отрицательная проба NameError; после in-memory helper stub INSERT 11/10; P1-01 |
| Общий бюджетный счётчик | VERIFIED_WORKING | B: media+LLM+P0+n8n, ограничения и overrun. **Не распространять этот статус на корректность всех settlement**, P0-01 остаётся |
| N34 technical master QC | VERIFIED_WORKING | B: настоящий локальный FFmpeg/full-decode синтетического MP4, signature/hash/tamper tests. Это technical, не художественный PASS |
| N35 freeze/evidence | VERIFIED_WORKING | B: separate role packets, общий frozen hash, права/required modalities, missing QC blocks. Входы синтетические |
| FINAL_MEDIA critics в live n8n | IMPLEMENTED_UNVERIFIED | snapshots/runbooks не подтверждают текущую активность Cloud, доступ моделей к видео и счёт |
| Audio Lab | PARTIAL | библиотека/профили/cues/upload есть; музыка и постановочный финальный микс вручную |
| Seven WF_00–WF_06 source exports | MOCK_ONLY | active=false/mock exports и тестовые routing contracts; deployed IDs/credentials/worker не проверялись |
| Release approval gate | PARTIAL | отдельные QC/QA APIs есть, общего обязательного server-gate импорт→approved release не найдено |
| CI / ownership | PARTIAL | несколько узких workflow; broad Studio/frontend checks не найдены в кандидатном дереве; см. P1-04 |

## Что тесты не доказывают

Вызов AsyncMock не подтверждает оплату, настоящие reference capabilities или качество image/video/audio. Файл синтетического генератора подтверждает транспорт/декодирование, но не production media. Tsc/build подтверждают сборку, но не доступность и понятность интерфейса. Статусы не повышены на основании прошлых handoff.
