# GremoVOD — Blender graybox / consistency: source-of-truth and implementation knowledge
**Дата:** 2026-10-24 · **Статус:** RESEARCH, не внедрено, не проверено в локальном Blender.

## Первичный кейс
[gensōFX: *The Offer: more control over AI through gray boxes* (04.10.2026)](https://gensofx.substack.com/p/the-offer-more-control-over-ai-through): 60-секундный фильм, 14 планов, 4 × 15-секундные AI-генерации. Claude через Blender создал простую цветовую 3D-постановку, затем отдельные character ID sheets и location views были соединены с motion guide для Seedance. Автор наблюдал последовательность и плавные стыки, но также лишнюю массовку, внезапно появившуюся обувь и ошибочную зеркальную локацию. Один успешный кейс не доказывает гарантии или проценты экономии.

**Основной принцип:** Blender фиксирует **КОГО, ГДЕ, КОГДА и КАК снимаем**; approved identity/location/vehicle sheets — **КТО и КАК ВЫГЛЯДИТ**; видеомодель заполняет материалы, освещение, анимационную детализацию. Визуальный ручной QC остаётся обязательным.

## Опорные правила (не упускать при создании скилла)
1. Сначала `shot_id`, сценарные beats, fps/длительность/раскадровка — и только потом камера или платная генерация.
2. Постоянные `asset_id`, approved version/hash, физические оси и масштабы. Левый/правый **борт машины** не путать с left/right кадра.
3. В Blender единый master stage, коллекции `SET/ACTORS/VEHICLE/PROPS/CAMERAS`, уникальные цвета proxy→ID; референсы не смешивают персонажей.
4. Отдельный beat/keyframe для каждого физического действия и появления/исчезновения реквизита. Нельзя писать действие в промпте, если оно отсутствует в блок-ауте.
5. Сохранять ориентацию стен, дверей, окон, направление движения и линии взгляда; делать direction sheet для локаций, иначе видеомодель может зеркалить помещение.
6. Для `extend` проверять реальную поддержку режима на конкретном backend/provider. Каждый персонаж, необходимый в следующем сегменте, должен быть виден в последнем кадре текущего достаточно отчётливо.
7. `reference_manifest`: `motion_only` / `character_identity` / `vehicle_identity` / `location_layout` / `style` / `audio`; порядок, тег, разрешённый endpoint, версии и hash.
8. Блок-аут не должен превращаться в серых людей/кирпичи в финале; явно запретить copying of proxy appearance.
9. `ffprobe`/local validation для fps, кадров, длины, декодируемости, ассетов и денег; identity, geometry and story continuity — отдельный визуальный QC, human approval.
10. Сравнивать одинаковые A/B генерации `prompt + sheets` против `prompt + sheets + blockout`; метрики `accepted/renders`, drift, retakes, USD, время. До замера не обещать экономию.

## GremoVOD canon
**GREM:** коренастый минский водитель, красная вельветовая кепка, чёрная футболка, борода/усы. Утверждённые референсы — истина о лице. Глаза смотрят нормально прямо, без случайного косоглазия. Повторно генерировать облик без approval запрещено.

**LIMO_2106:** жёлтый VIP ВАЗ-2106, классические жигулёвские передние фары/решётка, НЕ BMW; увеличенная длина, широкий кузов, BBS-mesh. **Левый борт:** передняя дверь штатная, за ней короткая неподвижная вставка с узким отдельным окном, затем удлинённая задняя дверь с открыванием против движения и петлями у задней стойки. **Правый борт:** удлинённая задняя дверь, накладные петли, дополнительная стойка и узкое центральное окно. Сохранять ручки, форточки, интерьеры (коричневая ромб-кожа, деревянные панели, чёрный руль, красная «розочка», VIP-задний ряд). Master geometry не реконструировать под ракурс.

**Утверждённый hook пилота:** сначала обычные детали передка ВАЗ‑2106, *никакого намёка* на удлинение, затем резкий reveal полного лимузина. Длина скрывается **рамкой камеры**, а не изменением машины.

## Производственный SOP (13 шагов)
0. Проверить наличие Blender, FFmpeg, версии, OS/GPU, права к 3D-ассетам, API и изоляцию.
1. Загрузить утверждённый канон GREM, LIMO_2106, location, сохранить версии и hashes.
2. Создать `shot_manifest` с fps, frame range, beats, lenses, camera and actor transforms.
3. Зафиксировать географию/систему координат и `stage_bible` (оси, единицы, двери, обе стороны автомобиля).
4. Собрать proxy 3D scene, не разрабатывать полную модель ради первого теста.
5. Поставить keyframes актёров, камеры и реквизита; геометрически обеспечить occlusion.
6. Отрендерить **дешёвое** локальное превью с first/middle/last кадрами.
7. Подготовить identity/vehicle/location sheets; необходимые ракурсы без зеркальных подмен.
8. Сформировать machine-readable reference contract с ролью каждого входа.
9. Подготовить model-specific prompt, role mapping, exclusions, real capability flags.
10. Отдельный `approval` для внешних загрузок/платной генерации и бюджета.
11. Генерировать только разрешённый вариант, логировать actual cost, сравнить с blockout.
12. Local technical QC + human visual QC; различать `PASS_TECHNICAL` и `APPROVED`.
13. Iteration and archiving: править неверное движение в Blender, идентичность — в sheets; version everything.

## Integration map на ветке mavis/work, 24.10.2026
- `backend/car_staging.py`: физическая постановка и ракурсы салона.
- `backend/clip_chain.py`: FFmpeg extraction of last frame (это **не** доказательство server-side extend).
- `backend/media_qc.py`: N34 измерения без LLM; визуальный verdict отдельно.
- `backend/adapters.py`, `backend/model_catalog.py`, `backend/llm_guard.py`: provider routing and budget approval.
- `backend/production_entities.py`, `backend/production_folders.py`, `backend/reference_upload.py`: жизненный цикл/ссылки на ассеты.
- `skills/cinema-shot-design`, `skills/gremovod-stage-storyboard`, `skills/gremovod-stage-frames`, `skills/gremovod-stage-video`, `skills/video-seedance-2-5`: требования постановки и видеомодели. **Не дублировать.**
- `docs/VIDEO_MODELS_PROMPTING_2026-10-17.md`: ранее зафиксировано различие между возможностями платформы и **фактической передачей видео-референсов адаптером**. Перепроверить live code.
- Пакет скилла `gremovod-blender-consistency` пока DRAFT и не установлен.

## Рекомендуемый порядок реализации
**P0:** read-only audit + mock manifest + capability matrix; безопасный `blender --background --python` для детерминированного scene build/export **в отдельной среде**. Если Blender нет, завершить `BLOCKED`, не придумывать success.

**P1:** один 4–8-секундный локальный test secret limo reveal (без персонажа), human approve blockout, затем только согласованный 1 AI-вызов и QC. Тест Грэма и межклипового стыка — отдельно.

**P2:** skill packaging, UI/оркестрация, batch shot generation, интеграция в n8n только если обоснована. Не делать второй реестр моделей/asset storage или QC.

## Безопасность Blender
Официальный [Blender MCP Server](https://www.blender.org/lab/mcp-server/) предупреждает, что выполняет LLM-generated Python **без защиты данных** и рекомендует VM/машину без важных данных. В документации обозначены Blender 5.1+, add-on, MCP server и клиент; наличие у пользователя не подтверждено. Для MVP предпочтителен reviewed Python + Blender CLI, а не автоматическая установка MCP. Ни `main`, ни рабочие проекты/секреты не менять.

[Полное задание Codex](CODEX_TASK_BLENDER.md). Читайте также исходную статью и официальную документацию Blender, а не принимайте предыдущие заметки за исчерпывающий факт.
