# Аудит Blender / GremoVOD — 2026-10-24

Результат: локальный детерминированный Blender CLI — минимальный кандидат для первого шота. В проекте уже есть storyboard, asset ownership/versioning, provider router, budget approval и технический QC. Их нужно расширять; отдельные registry, QC backend и orchestration service не нужны. Blender-постановки, физической камеры и проверки геометрической консистентности сейчас нет.

## Область и достоверность

Проверен Draft [PR #102](https://github.com/gremoled77-droid/gremovod/pull/102): base `mavis/work`, head `docs/blender-consistency-research-20261024`, SHA `9a84a0b89af4c2b3fc0b5929602fd12d73b99239`. Два файла прочитаны полностью: `docs/blender/CODEX_TASK_BLENDER.md`, `docs/blender/BLENDER_KNOWLEDGE_BASE.md`. Прочитаны `AGENTS.md`, `CLAUDE.md`, `STATUS.md`, `AGENT_BUILD_MANUAL.md`, review packet и относящаяся к работе часть handoff. STATUS датирован 19 октября и сам по себе не доказывает текущую работоспособность.

Исходная [статья gensōFX](https://gensofx.substack.com/p/the-offer-more-control-over-ai-through) не получена: веб-доступ завершался ошибками, запрос PowerShell — ошибкой TLS. Изложение эксперимента Claude → Blender → Seedance, 14 шотов / четыре генерации, взято **только из базы знаний PR**. Полное прочтение и независимая проверка этих результатов — UNVERIFIED. Успех чужого ролика не доказывает сохранение геометрии нашего автомобиля или экономию дублей.

Статусы: VERIFIED_CODE — прочитана исполняемая ветка; VERIFIED_TEST — выполнен конкретный тест; DOCUMENTED — первичная документация; PROPOSED — проект решения; BLOCKED — отсутствует необходимое условие. `verified_at` в каталоге — запись репозитория, а не проведённый в этой сессии live-тест.

## Безопасность checkout

| Проверка | Факт |
|---|---|
| Исходный checkout | `C:\AI_Workflow_Studio`, `fix/astra-aider-20261020`, HEAD `be9382ccc32c63aa230d6b34a1efd79462f66b47` |
| Чужие изменения | Root содержит untracked-файлы; `.worktrees/codex` содержит изменения handoff и untracked-материалы. Сохранены |
| Изолированная работа | `.worktrees/codex-blender-research`, `codex/blender-previz-research-20261024`, база SHA `9a84a0b...` |
| `main` / `origin/main` | `2f8f6554cc9ccc50e22c21bd992ddaff1a2fb9ac` |
| local / remote `mavis/work` | `57cac59ca790d380d8e68f2f6db82674ca142e92` / `ea05f2cd31991c2a8533720864d539759febef83`; локальная ветка отстаёт |
| Данные / серверы | Рабочие проекты и БД не открывались для изменения; 8000/5173 не запускались. Для unittest использован отдельный `%TEMP%\gremovod-blender-audit-20261024` через `STUDIO_DATA_DIR` |

Эта ветка расходится с `origin/main`; слияние main ради документов привнесло бы посторонние изменения. Новый Draft PR должен быть **stacked поверх ветки PR #102**. Его diff — только пять отчётов; он не переносит весь `mavis/work` в main. После изменения базы PR #102 потребуется проверка базы дочернего PR.

## Инвентаризация

Все ссылки ниже закреплены на исследованном SHA `9a84a0b89af4c2b3fc0b5929602fd12d73b99239`.

| Код / строки | Что реализовано | Пробел и точка расширения |
|---|---|---|
| [camera_movements.py:9](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/camera_movements.py#L9), 9–72 | 19 пресетов, схематические x/y/scale/rotation, prompt context, API presets | Нет world-space траектории, sensor/lens, столкновений. Пресет остаётся режиссёрским намерением; shot manifest задаёт физическую камеру отдельно |
| [car_staging.py:7](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/car_staging.py#L7), 7–81 | Текстовые правила водитель/пассажир, запрет зеркальности | Нет измеряемой геометрии дверей и обоих бортов; добавить stage bible, не заменять prompt rules |
| [storyboard.py:89](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/storyboard.py#L89), 89–272 | 2D asset, cast/location ownership, scene/frame nodes, порядок, выбор кадров, script import/preview | Нет previz artifact/version и timeline. Связывать через существующие nodes/files/links |
| [production_entities.py:10](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/production_entities.py#L10), 10–137+ | State/version, revision hash, cast/location refs, keyframe и AI take | Потребуются manifest attachments и связь stage revision → shot → take; не вторая таблица ассетов |
| [production_folders.py:84](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/production_folders.py#L84), 84–119, 258–367+ | Production/node/files/links, владение, library copy, sidecar/sync | Проверить и расширить allowlist kind/MIME/import для `.blend`, JSON, preview; нынешний import не считать готовым для них |
| [production_workspace.py:17](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/production_workspace.py#L17), 17–137 | Защищённая maintenance promotion и sync документов workspace | Для previz использовать документные связи; promotion/move рабочих проектов не запускать |
| [reference_upload.py:78](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/reference_upload.py#L78), 78–99 | Проверяемая загрузка изображения, временный внешний URL | Video upload/TTL/удаление/роль motion_only не подтверждены. Внешний upload только после разрешения |
| [adapters.py:118](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/adapters.py#L118), 118–236, 336–345 | Seedance image/video/audio payload, edit/extend, оценка, wire_body | Нет гарантий следования graybox. Launch gate остаётся выключенным; подробности в матрице |
| [main.py:435](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/main.py#L435), 435–568 | Единый request, HTTPS refs, preview, approval quote, reserve и отправка | Роли референсов надо компилировать до этого пути; нельзя обходить его отдельным Blender submitter |
| [security.py:27](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/security.py#L27), 27–42, 123–135 | Quote привязан к проекту/payload/стоимости, TTL 600 s, лимиты бюджета | В approval включить точные хеши/длительности загружаемых refs и конкретную попытку |
| [llm_guard.py:157](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/llm_guard.py#L157), 157–175, 229–232, 265–277 | Бюджеты LLM, передача выбранных skill instructions | Это не video budget и не автоматический loader Blender skill |
| [clip_chain.py:21](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/clip_chain.py#L21), 21–67 | FFmpeg last-frame → PNG, hash/source в library и production | Полезно для continuity; не полноценный монтаж или crossfade. Финальный монтаж остаётся в CapCut |
| [media_qc.py:179](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/media_qc.py#L179), 179–240, 433–455; `qa_reviews.py:23,66` | ffprobe, codec/fps/размер/длительность, `PASS_TECHNICAL`, review-факты | Нет проверки лица, дверей, силуэта и физики камеры. Добавить человеческие findings в существующий review |
| [build_director_preview.py:1](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/scripts/build_director_preview.py#L1) | HTML-превью каталога кадров/камер | Не Blender render engine. Можно переиспользовать представление PNG/MP4 |
| `frontend/src/GenerationReview.tsx:28–32,114–163`; `ProductionStoryboard.tsx`; `sendToBoard.ts:58`; `OutlineDialog.tsx:78` | Review цены/refs, storyboard/outline flow | Добавить роли, версию previz и отдельное локальное утверждение в существующий экран |

Строки — точки входа, а не доказательство выполнения всей системы. Точные frontend-пути: `frontend/src/GenerationReview.tsx`, `frontend/src/ProductionStoryboard.tsx`, `frontend/src/sendToBoard.ts`, `frontend/src/OutlineDialog.tsx`.

## Скиллы и граница n8n

`skills/cinema-shot-design/SKILL.md:10–48` уже описывает функцию плана, оптику, композицию и continuity. `skills/gremovod-stage-storyboard/SKILL.md:16–32` — камера A/B, ось, occlusion/reveal; `gremovod-stage-frames:14–30` — approved composition/geography; `gremovod-stage-video:14–22` — маршрут камеры до сложного движения. `skills/video-seedance-2-5/SKILL.md:19–31,42–60` описывает @video1 / @imageN, но текст skill не доказывает live transport.

`integrations/n8n/STAGE_SKILL_MAP.md:16–37` и `agent-manifest.json:199–220,273–304` задают существующие роли; n8n-копии не синхронизируются автоматически. Семь WF_00…06 сохраняются, shell в cloud n8n не добавляется. `scripts/n8n_skill_sync.py` **отсутствует в исследованном HEAD**; найден в другой истории, commit `cbecc4acb205da503ca74566f72bd1d5cb48d52e` / `codex/n8n-api-contract`. Там plan-only sync (pinned SHA/hash, bind/noop/update_draft/blocked), а не действующая публикация. Перенос не выполнен.

## Проверенная среда и проверки

- Windows; CPU Intel i7-6700K, 8 logical; GTX 950, 2048 MiB по nvidia-smi. Объём RAM UNKNOWN: системный запрос недоступен. Требуемые графические расширения и совместимость драйвера не проверены.
- Blender не найден в PATH и проверенных стандартных каталогах 4.0–4.5. Это не исчерпывающий поиск всех portable-дисков. Доступного исполняемого Blender для smoke нет — BLOCKED.
- FFmpeg/ffprobe 9.0.2 найдены. Модель ВАЗ, права на неё, утверждённый master `.blend`, утверждённые image sheets — UNKNOWN; рабочие проекты ради поиска не трогались.
- VERIFIED_TEST: `python -m unittest backend.test_seedance_adapter -v` в собственном checkout с отдельным `STUDIO_DATA_DIR`: **13 tests OK**, 0.004 s. Проверены offline payload/limits/billing/gates; никаких запросов к провайдеру. Тест, временно снимающий gate внутри fixture, не включает модель в продукте.
- Проверка документов stdlib Python: ровно пять отчётов, шесть JSON-блоков RFC успешно разобраны, внутренние `$ref` разрешаются, присутствуют пять типов examples, локальные Markdown-ссылки существуют. Полная валидация Draft 2020-12 **не выполнена**: готовый JSON Schema validator в проверенных runtime отсутствует; зависимости не устанавливались. Эта проверка синтаксиса не доказывает семантику контрактов.
- Не выполнялись Blender render, live API, upload, визуальная приёмка, полные suites/builds. Платный расход этой работы: **$0**; это не утверждение о балансе чужих jobs.

## Решение

Сначала один неизменный автомобиль и локальный reveal без человека; затем отдельно утверждённый Seedance A/B. Код интеграции и включение моделей в этом PR не создаются. Следующие документы: [RFC](BLENDER_PIPELINE_RFC.md), [матрица](BLENDER_MODEL_CAPABILITY_MATRIX.md), [пилот](BLENDER_PILOT_EXPERIMENT.md), [backlog](BLENDER_IMPLEMENTATION_BACKLOG.md).
