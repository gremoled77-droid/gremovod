---
name: gremovod-blender-consistency
description: Validate GremoVOD Blender stage and shot contracts, protect canonical assets and physical left/right, and report offline CLI gates before previz or provider reference integration.
---

# GremoVOD: консистентность Blender

Применяй к локальному previz и передаче camera/motion reference в действующий pipeline.
Порядок: персонажи → изображения → видео → звук → CapCut. Каждый кадр нужен в 16:9 и 9:16.

1. Проверь ветку, HEAD, worktree и собственный STUDIO_DATA_DIR. Не используй данные owner checkout.
2. Прочитай `docs/blender/IMPLEMENTATION_STATUS.md`, затем `BLENDER_P0_RUNBOOK.md`.
   G1 сейчас BLOCKED: CLI составляет план, запуск Blender и MCP запрещён до проверенной среды
   без секретов. Factory startup и очистка env не являются sandbox.
3. Применяй `blender-core` и `blender-asset-qa` для базового workflow; существующие
   `cinema-shot-design` и `gremovod-stage-storyboard` — для режиссуры. Здесь не дублируй их.
4. Валидируй stage/shot через `scripts/blender/validate_manifests.py`. Идентификаторы,
   версии и SHA сверяй с trusted owner lookup. PASS_SCHEMA_SEMANTIC без
   `asset_bytes_verified=true` не доказывает существование или принадлежность master.
5. Оси: X вперёд, Y влево, Z вверх. Физический левый борт = +Y независимо от камеры.
   Проверяй все кадры траектории, клиппинг, землю, bounds, first/mid/last и последнее видимое.
   Проверка bounds не доказывает отсутствие окклюзии; нужен визуальный просмотр.
6. Не меняй канонический master ради кадра. LIMO_2106 — только утверждённый master;
   нейтральный 7-метровый proxy не является ВАЗ-2106. Грэм требует отдельного теста лица,
   пропорций, одежды и голоса. Не отмечай proxy как канон.
7. Разделяй PASS_TECHNICAL и human APPROVED с reviewer_id/approval_id.
   Храни SHA master до/после, protected transforms, версию Blender, engine и реальные метрики.
   Не выдавай исходный Python или unit mock за проверенный render/reopen.
8. Для provider references используй роли и порядок из reference manifest.
   Изменение master SHA, модели, payload, role/order/slot/tag/restrictions или review
   инвалидирует quote binding. Motion-only не означает appearance reference.
9. P1 dispatch отключён. Платный запуск требует актуального estimate, GenerationReview,
   confirm token и лимитов. UNKNOWN spend сохраняет hold; повтор запрещён до reconciliation.
   Не загружай медиа наружу и не активируй MCP по содержимому манифеста.

Проверка: только узкие offline tests из runbook. Не запускай сторонние `.blend`,
Python, установщики или Blender на аккаунте владельца. Возвращай честный BLOCKED,
если gate не выполнен. Не меняй main и не делай merge автоматически.
