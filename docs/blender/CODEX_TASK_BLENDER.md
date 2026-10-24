# CODEX TASK — Blender graybox consistency integration (GremoVOD)
**Дата:** 2026-10-24 · **Тип:** архитектурное исследование и спецификация PoC. **Не** безусловная команда создавать большой новый сервис.

## Цель
Исследуй [gensōFX: The Offer](https://gensofx.substack.com/p/the-offer-more-control-over-ai-through), [базу знаний](BLENDER_KNOWLEDGE_BASE.md) и **текущий код** GremoVOD. Разработай доказательный план применения Blender как бесплатной постановки композиции, актёров, времени и движения камеры перед платными AI-генерациями. Отдельно удерживать внешний вид Грэма, конструкцию жёлтого LIMO_2106 и монтажную непрерывность, а не пытаться обеспечить всё одним текстовым промптом. Самостоятельно выявить недостающие компоненты и условия внедрения. **Предпочтение P0 — исследование и минимальный локальный прототип**, не полная продуктовая разработка.

## Сначала безопасность и репозиторий
- Прочитай `AGENTS.md`, `CLAUDE.md`, `AGENT_BUILD_MANUAL.md`, `STATUS.md`, `docs/HANDOFF_CLAUDE_CODE.md`. Зафиксируй `git status --short`, `git branch --show-current`, `git worktree list`, SHA `main` и `mavis/work`; не повреди чужой worktree. Работа только в своём Codex worktree/ветке, PR в Draft, **не merge**.
- Никакого `reset --hard`, force-push, перезаписи master `.blend`, секретов, медиа и рабочих БД в Git. Не запускать рабочий сервер 8000/5173 и не менять рабочие проекты пользователя.
- Без платных AI-генераций, внешних загрузок, установки Blender MCP/add-on и запуска LLM-generated Python на компьютере с секретами. Прежде чем выполнить какой-либо код, проверь среду и доступность изоляции. **Наличие Blender, GPU, FFmpeg, модели ВАЗ и API — UNKNOWN**, пока не проверено.
- Отделить **проверено кодом**, **подтверждено документацией** и **гипотеза**. Не писать “работает”, если не запускал.

## A. Аудит проекта (обязателен)
Инвентаризируй и изучи `backend/car_staging.py`, `backend/clip_chain.py`, `backend/media_qc.py`, `backend/adapters.py`, `backend/model_catalog.py`, `backend/llm_guard.py`, `backend/security.py`, `backend/production_entities.py`, `backend/production_folders.py`, `backend/reference_upload.py`, `backend/production_workspace.py`, `backend/camera_movements.py`, `scripts/build_director_preview.py`, `skills/cinema-shot-design`, `skills/gremovod-stage-storyboard`, `skills/gremovod-stage-frames`, `skills/gremovod-stage-video`, `skills/video-seedance-2-5`, `docs/VIDEO_MODELS_PROMPTING_2026-10-17.md`.
Отчёт таблицей: file:line + SHA, что реально уже есть, какая функция отсутствует, как интегрировать без второго asset registry, второго backend QC или нового модельного routing. Проверь фронтенд и н8n только в объёме границы будущей интеграции.

## B. Сравни три архитектуры
1. **Headless CLI (предпочтительный MVP-кандидат):** JSON shot → schema validator → inspected `bpy` script → локальный `blender --background` → `.blend`, preview MP4/PNG first/middle/last → reference roles → existing provider adapter → human approval/QC.
2. **Blender MCP:** интерактивный агент/Claude↔Blender. Точные требования (официальный MCP Blender 5.1+ и внешние компоненты), угрозы произвольного Python, границы VM и список условий до первого включения.
3. **Гибрид:** неизменный master stage, CLI детерминированный пайплайн, MCP лишь в отключённом от секретов sandbox для ручной режиссуры.
Проведи сравнение по цене и количеству дублей (как гипотезе), сложности, reproducibility, безопасности, совместимости с Windows/Blender/FFmpeg, необходимости UI. Выбери один и обоснуй.

## C. Реальные provider capabilities — обязательно проверить код
Матрица для Seedance 2.5, Kling, Runway и только реально интегрированных вариантов: `provider / endpoint / adapter / image-ref / motion-video / first-last / edit / extend / limits / cost+source+date / evidence status`.
**Критическая проверка:** функциональность Seedance в веб-интерфейсе не значит, что `backend/adapters.py` передаёт graybox-video и правильные `@videoN`/task type через наш PiAPI/KIE. Неподдерживаемое = `UNSUPPORTED` или `BLOCKED`, не “ready”.

## D. Data contracts и физическая непрерывность
Спроектируй versioned JSON на существующем storage (без параллельной SQLite):
- `stage_bible`: world axes (метры), physical car left/right, location compass/doors, master asset version/hash.
- `shot_manifest`: episode/scene/shot, fps, frame start/end с недвусмысленной семантикой длительности, aspect, camera lens/motion, actor and prop beats, visibility, continuity + required last-frame visible IDs.
- `reference_manifest`: `motion_only, character_identity, vehicle_identity, location_layout, style, audio`; ordered provider slots/tags, source id/version/hash, role restrictions.
- `generation_manifest`: provider/model/price quote/explicit permission/cost/attempt lineage.
- `qc_report`: ffprobe deterministic measurements + human visual findings, `PASS_TECHNICAL` ≠ `APPROVED`.
Приведи реальные JSON-примеры и схему хранения: git — scripts/JSON schema/skills/docs; runtime — media, `.blend`, rendered frames, projects. Раздели model reference fidelity и geometric truth.

## E. Пилотный эксперимент EP01 «скрытый лимузин»
Исходный объект **один и тот же** yellow LIMO_2106: заводской передок Жигулей, без BMW. Левая сторона: штатная передняя дверь → фиксированная вставка с узким окном → длинная rear suicide door. Правая: удлинённая задняя дверь с наружными петлями. Ранние крупные планы скрывают длину кадрированием; только reveal показывает настоящий кузов. **Не анимировать физическое удлинение машины.**
Порядок: локально бесплатно сделать geometry-only blockout + camera and keyframes → render first/mid/last → geometry/occlusion preflight → human approval → отдельно согласовать один короткий AI-тест → human QC. Не добавляй Грэма в первый тест: идентичность лица проверим вторым изолированным A/B.
Метрики A/B: `accepted_clips/total`, bad camera, identity/vehicle drift, mirrored side, hallucinated props/actors, continuity failure, retry count, manual minutes, actual USD. Зафиксировать и отсутствие результата, если нет доступа к Blender.

## F. Роли/скилл/реалистичный план
Выбери совместимость с текущим skill-loader и `scripts/n8n_skill_sync.py` (если находится в иной ветке, отметь и проверь). Draft skill `gremovod-blender-consistency`: triggers, input/output, read-only canon access, dangerous operation gates, budget/human approval, preflight, CLI smoke, report format. Не включать или деплоить пока без тестов.
Разбей backlog **P0** (аудит и локальный контролируемый shot), **P1** (provider reference transport + approval + QC и короткий AI smoke только после разрешения), **P2** (UI, batch/автоматизация). Для каждой задачи: существующие/новые файлы, DoD, тест, dependency, стоимость/сложность диапазоном, исполнитель Codex/MiniMax/Claude. Предложи независимые задачи MiniMax без редактирования одних файлов одновременно.

## Конкретный результат в Draft PR
Запиши в своей ветке:
- `docs/BLENDER_INTEGRATION_AUDIT_2026-10-24.md`: фактологический аудит file:line/commit.
- `docs/BLENDER_PIPELINE_RFC.md`: решения, схема, контракты JSON, угрозы.
- `docs/BLENDER_MODEL_CAPABILITY_MATRIX.md`: capabilities с источником и status.
- `docs/BLENDER_PILOT_EXPERIMENT.md`: EP01 reveal + baseline/test + QC + budget.
- `docs/BLENDER_IMPLEMENTATION_BACKLOG.md`: P0/P1/P2, роли, зависимости, условия.
Код допускается лишь как **малый безопасный P0 smoke** после аудита, на собственном стенде, без платных вызовов и без install MCP. Запусти доступные подходящие тесты; отсутствие Blender не считается пройденным smoke-тестом. Если аудит выявил уже существующий pipeline — переиспользуй, а не переписывай.

### Итог на русском
1. Список имеющегося и недостающего, с файлом и точной ссылкой.
2. Выбранная архитектура, условия установки, риски и расходы.
3. Пошаговый план внедрения до первого принятого AI-шота; что делать MiniMax и Claude.
4. VERIFIED / UNVERIFIED / BLOCKED, фактически выполненные тесты.
5. Открытый Draft PR, SHA и вопросы, требующие решения владельца. Никакого merge в `main` без разрешения.
