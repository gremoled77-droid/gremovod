# Внедрение Blender: P0 / P1 / P2

Дата: 2026-10-24. База исследования `9a84a0b89af4c2b3fc0b5929602fd12d73b99239`. Это план, а не выполненные продуктовые изменения. Единица оценки — человеко-день (6–8 часов); диапазоны предполагают доступ к канону и исполнителю, знакомому с Blender. LLM не заменяет визуальную приёмку владельцем или работу 3D-специалиста со сложной моделью.

## P0 — первый локальный принятый шот

| ID / задача | Создать / изменить | Зависимости и риск | Оценка / исполнитель | Проверка / DoD |
|---|---|---|---|---|
| P0.0 Аудит и договорённости | Пять `docs/BLENDER_*.md` этого PR | Доступ к статье ограничен; код и docs могут расходиться | Выполнено исследование; Codex | Привязка к SHA, статусы evidence, docs-only diff, Draft PR без merge |
| P0.1 Стенд и portable Blender | Отдельный no-secrets Windows account/VM, portable LTS вне рабочих проектов; runtime environment manifest | Явное решение владельца об установке; RAM/драйвер UNKNOWN, GTX950 2GB у минимума; флаги CLI не sandbox | 0.25–0.75 дня; Claude Code, Codex проверяет boundary | Version/checksum, один trusted diagnostic render, FFmpeg/ffprobe, замер RAM/VRAM/time; никакого MCP |
| P0.2 Канон и master proxy | Runtime `master/*.blend`, stage bible; утверждённые front/left/right/top sheets | Владелец даёт refs, размеры и права. Риск ошибочной двери/передка; готовая модель UNKNOWN | 0.5–2 дня для простого proxy; Claude Code + владелец/3D-исполнитель | Обе стороны совпадают с каноном, stable IDs, positive scale, immutable mesh; human approval. Точная реалистичная модель может занять больше |
| P0.3 Контракты и validator | Новые `schemas/blender/previz-v1.schema.json`, `scripts/blender/validate_manifests.py`, узкие fixtures/tests | RFC review, существующие entity/file IDs. Не создавать второй registry | 0.5–1 день; Codex контракты, MiniMax well-scoped implementation | Valid fixtures проходят; wrong hash/path/aspect/interval/ownership/slot/approval отвергаются. Проверка negative cases, не только JSON syntax |
| P0.4 CLI renderer | Новые `scripts/blender/render_shot.py`, runner/preflight; runtime attempt dirs | P0.1–3; code review до исполнения. Риски arbitrary Python, clipping, Bezier overshoot | 0.75–1.5 дня; Claude Code; Codex security review | Trusted script, no shell interpolation, timeout/nonzero exit, master hash неизменен, first/mid/last +192 frames; no-secrets sandbox |
| P0.5 Reveal и локальный QC | Runtime два shot manifests, PNG/MP4, preflight/QC report | P0.2–4; низкая скорость GPU, ошибочное вертикальное кадрирование | 0.5–1 день + render time; Claude Code, принимает владелец | Оба аспекта, same master hash, 8s/24fps, вся траектория без коллизий; geometry canon и reveal human APPROVED |

Порядок P0.1 → P0.2 → P0.3/4 → P0.5. Начать с одного diagnostic frame; не строить HTTP job queue до локального принятия. Ориентир **2.5–6 рабочих дней** после получения исходников/стенда, без ожиданий согласования и без полноценного моделирования фотореалистичного ВАЗ. Это инженерная оценка, не обещанный срок.

## P1 — один принятый AI-шот через существующие механизмы

| ID / задача | Создать / изменить | Зависимости и риск | Оценка / исполнитель | Проверка / DoD |
|---|---|---|---|---|
| P1.1 Регистрация previz assets | `backend/production_folders.py`, `production_entities.py`, минимально `storyboard.py`; существующие files/links/sidecar | P0 approved. Allowlist `.blend`/JSON/video, ownership, path traversal; не выполнять `.blend` при import | 0.5–1.5 дня; Claude Code | Import в изолированную production, чужой project/path отказ, hash/version lineage, исходники не перемещаются |
| P1.2 Reference role compiler | Новый небольшой `backend/previz_references.py` либо helper в существующем module; `adapters.py`, узкие tests | Согласованный reference_manifest. Риск перестановки slots/role leakage | 0.5–1 день; Codex дизайн, MiniMax реализация по контракту | Exact Seedance wire JSON; negative wrong media/role/tag/duration; first/last не изобретается |
| P1.3 Video transport | Расширить `reference_upload.py`, существующий asset storage/config; без секретов в manifests | Разрешённые upload destination/TTL/удаление/права. SSRF/redirect, size/duration и сетевые ошибки | 0.75–1.5 дня; Claude Code, Codex review | Локальные fake transport tests без upload; approved live upload отдельно; URL доступен provider и удаляется по политике. Отказ не вызывает paid submit |
| P1.4 Review и cost lineage | `frontend/src/**/GenerationReview.tsx`, `main.py`, `security.py`, существующий budget/activity | P1.1–3; не ослабить signed quote. Смена refs/длительности инвалидирует approval | 0.75–1.5 дня; Claude Code | Роли/preview/version/цена видны; stale quote/changed ref отказ; UNKNOWN удерживает reserve и запрещает retry |
| P1.5 Контролируемая live-верификация Seedance | `model_catalog.py`, existing verification script/path, `adapters.py` только при найденном расхождении | **Отдельное разрешение** exact upload/call/cap; не глобальный toggle ради теста | 0.5–1 день + ожидание provider; Claude Code, Codex независимый audit | Первая согласованная B может быть verification call; job/result/billing reconciled, verified_at только после факта. Не добавлять скрытый пятый вызов к A/B |
| P1.6 Human consistency QC | `media_qc.py` переиспользовать, `qa_reviews.py`, `clip_chain.py`; review rubric/attachments | P1.5 и owner preview. ffprobe не проверяет идентичность | 0.5–1 день; Codex рубрика, MiniMax fixtures, Claude интеграция | PASS_TECHNICAL и human APPROVED раздельны; reject BMW/mirror/extra wheels/graybox leakage; last frame lineage |
| P1.7 A/B и решение | Runtime manifests/review facts, краткий обезличенный отчёт в docs | P0/P1 gates, новая цена и отдельное разрешение; 1 pair — слабая статистика | 0.25–0.75 дня human work + неизвестная latency; Claude запускает, владелец принимает, Codex оценивает | До 4 согласованных calls, $6 planning estimate, no retries; accepted/total, errors, minutes и actual USD либо UNKNOWN зафиксированы |

Ориентир P1 **4–8 дней** с учётом интеграционных исправлений, без ожидания разрешений/доступности провайдера. Части P1.2 и transport fixtures можно вести параллельно в разных файлах. Paid verification и budget review последовательны. Сначала одна горизонтальная пара за плановые $3, затем вертикальная пара после анализа — разумный способ сократить риск, но решение владельца должно задавать конкретный scope.

## P2 — только после принятого шота

| ID / задача | Файлы / область | Зависимости / риски | Оценка / исполнитель | Проверка |
|---|---|---|---|---|
| P2.1 Local jobs UI | `activity.py`, существующие production/storyboard UI, новый небольшой local worker adapter | P0 runner/P1 import; ports 8001/5174 и отдельный data dir; queue/cleanup на слабом GPU | 2–4 дня; Claude Code | Cancel/timeout/restart не меняют master, нет orphan jobs, bounded disk; никаких root 8000/5173 restarts |
| P2.2 Character и multi-shot continuity | Runtime approved sheets, stage variants; existing frame/video skills, `clip_chain`, `qa_reviews` | Отдельно принятый автомобильный shot и новые расходы. Лицо/одежда/рост не доказаны первым тестом | 1–3 дня + утверждённые генерации; Codex эксперимент, Claude исполнение | Изолированный GREM A/B, accepted last→first continuity, canon refs без подсмены |
| P2.3 Kling Omni / Runway | `adapters.py`, `model_catalog.py`, transport/review tests, docs | Необходимость доказать на Seedance failure case; отдельные цены/live OK | 2–4 дня на provider; Codex contract audit, Claude adapter | Документированные поля не равны Seedance, failure/billing tests, отдельный approved live; UNKNOWN запрещает запуск |
| P2.4 Skill/n8n binding | Новый `skills/gremovod-blender-consistency/SKILL.md`, stage map/manifest; оценить перенос plan-only sync из другой ветки | Нужен verified local path, нет auto loader; не новый восьмой workflow | 0.5–1.5 дня; MiniMax draft, Codex review, Claude binding | Простые name/description, pinned SHA/hash, dry-run plan; deployment отдельное разрешение |
| P2.5 MCP / hybrid | Изолированная VM, официальный add-on/server/client config; экспорт stage в CLI | **Отдельное разрешение на установку**, Blender5.1+, no-secrets VM, measured benefit | 1–3 дня эксперимента; Claude Code, Codex threat review | Нет доступа к host credentials; после interactive session CLI воспроизводит экспорт. Если выгоды нет — не внедрять |

Не оценивать P2 как обязательный пакет: сначала принять решение по результату P1. Полный новый сервис, замена provider router, GPU upgrade и автоматический visual judge не являются условием первого кадра.

## Независимые задания MiniMax

MiniMax здесь — исполнитель разработки, не разрешение вызывать платный MiniMax API. Работы выдаются через имеющийся авторизованный канал; отдельные внешние model calls в этой сессии не делались.

- По утверждённому RFC создать schema fixtures и негативные JSON cases в собственном тестовом файле. Codex владеет schema contract, Claude не меняет его одновременно.
- Подготовить draft body skill и визуальный QC checklist в отдельном файле. Не редактировать `AGENTS.md`, `STATUS.md`, n8n runtime или общие skills других стадий.
- После P1.2 создать pure-function compiler tests на фиксированных fixtures без сети. Claude владеет transport/main; MiniMax не правит их одновременно.

Codex эффективнее для аудита, data contracts, provider discrepancies, cost/security и независимой проверки. Claude Code — для Blender runner/backend/UI и локальной диагностики. MiniMax — для ограниченных преобразований/fixtures/текста по готовому контракту. Канон и визуальный accept остаются у владельца.

## Ресурсы и решения владельца

| Ресурс | Оценка / что измерить |
|---|---|
| Лицензии | Blender/FFmpeg — без платы за использование; лицензия найденного car asset отдельно |
| CPU/GPU/RAM | Имеющийся i7-6700K / GTX950 2 GB; RAM UNKNOWN. Не обещать Eevee compatibility или render speed без первого кадра |
| Диск | Плановый запас 2–5 GB для portable/tool/runtime плюс попытки. 384 preview PNG двух аспектов могут занять сотни MB; реальный размер зависит от сцены/codec, измерить и ограничить quota |
| Render time | UNKNOWN. Замерить 1, затем 24 кадра; экстраполировать на 384, пометив оценкой. Лимит на одну попытку согласовать по замеру |
| AI | $0 израсходовано в этой задаче; A/B planning $3/aspect, $6/both. Upload/storage/налоги UNKNOWN; любые доплаты требуют нового quote |
| Люди | P0 2.5–6 дней, P1 4–8 дней; владельцу минимум отдельная приёмка master, обоих previews и AI takes. Ожидания согласований не включены |

Требуются решения: (1) разрешить portable Blender и выбрать изолированную среду; (2) предоставить/утвердить модель, реальные размеры и reference sheets обеих сторон; (3) утвердить локальную постановку 8s и два формата после просмотра; (4) позже разрешить конкретный upload destination/TTL и exact paid A/B cap, либо ограничиться бесплатным local preview. Сейчас **не** запрашивается платное разрешение вместо отсутствующего preview.

## Фактическая поставка этого PR

Пять исследовательских отчётов; изменения executable code, установок и моделей: 0. Offline `backend.test_seedance_adapter`: 13 tests OK с отдельным TEMP data dir. Blender smoke, uploads, live API и human visual QC не выполнены. Не считать эти отчёты реализацией pipeline. Draft PR stacked над PR #102; никакого merge, main или рабочих данных.
