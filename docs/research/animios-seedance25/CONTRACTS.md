# Офлайн-контракты 1.0.0

Реализация: `backend/reference_production.py`, CLI: `scripts/reference_production_preflight.py`. Это минимальная библиотека подготовки и preflight, без новых серверных маршрутов, БД, регистрации модели или второго видеоконвейера. Blender RFC остаётся в Draft PR [#102](https://github.com/gremoled77-droid/gremovod/pull/102); его архитектура здесь не копируется.

| Структура | Данные и проверки |
|---|---|
| Stage Bible | `schema_version`, `scene_id`, `world_axes`, `approval_status`; опциональные `world_bounds` (три пары min/max), assets.geometry ID/hash. +Y вперёд, +X вправо, +Z вверх. Геометрия из реестра должна совпадать с master hash. |
| Shot Manifest | `video_stream.fps_num/fps_den/frame_count`, assets.character_ids/location_ids/prop_ids, shots[].shot_id/start_frame/end_frame/location_id/character_ids/prop_ids. Целочисленные полуоткрытые интервалы без дыр, перекрытий и дубликатов. |
| Reference Manifest | shot_id, reference_mapping[].asset_id/asset_version/sha256/source_role/source_type/provider_slot, prompt_template. Проверка типа, роли, последовательности слотов, тегов промпта, версии и хеша из отдельного доверенного snapshot. |
| Generation Manifest | provider/model_id, source_digest, reference_mapping, wire_payload, payload_sha256, estimated/actual_cost_usd, approval_id, hold_status, attempts. BLOCKED source не получает payload/quote. Валидный контракт получает только синтетические URL `.invalid`; execution_allowed всегда false. |
| Continuity Report | status OK/WARN/BLOCKED, issues[].code/severity/detail, input_digest, visual_acceptance=NOT_PERFORMED. Отсутствие доказательств не становится художественным одобрением. |

`registry_snapshot(db, production_id)` выполняет только SELECT над существующими `library_assets`, `production_files`, `production_nodes`, оставляя только привязанные к production assets. Соединение принадлежит вызывающему коду; используйте SQLite read-only/query_only. Модуль не открывает owner DB и не импортирует `main`.

Для проверки утверждения используется необязательный серверный `library_assets.metadata.reference_production`:

```json
{"approved":true,"version":"immutable-version-id","sha256":"64 lowercase hex digits","kind":"image","roles":["character_identity"]}
```

Для video/audio нужны также фактические `duration_seconds`, чтобы существующий адаптер проверил лимиты и рассчитал цену. Запись/утверждение этих данных данным PR **не реализованы**: существующие legacy assets останутся unverified. Нельзя передавать snapshot с клиентским самоподтверждением; это доверенный серверный экспорт, связанный с уже проверенным media hash/version. Production revision из `production_entities.state()` сохраняет контекст карточки, но не заменяет неизменную версию медиа. Права пользователя на production проверяет существующий вызывающий слой до SELECT.

Дополнительный continuity ledger внутри shots: `prop_state_start` и `prop_state_end` — mapping prop ID → JSON-состояние (holder, position, container и прочее); разрыв между соседними планами блокирует проверку, если нет `continuity_events` с соответствующим `entity_id`. Пропавшие из видимости персонажи/реквизит и смена локации без события дают WARN: монтаж не доказывает физическое исчезновение. World position за границами stage блокируется; неизвестная позиция даёт WARN. Координаты — положения в мире, не экранные стороны. Полнота и художественный смысл заявленных событий требуют ручной проверки.

Ошибочные структуры JSON возвращают BLOCKED_SCHEMA. Поля path/file_path/url/download_url/script/code/command блокируются рекурсивно; provenance `source_url` остаётся инертной строкой. Файлы/URL/код из контрактов не открываются и не исполняются. CLI читает только фиксированные исследовательские имена, ничего не скачивает.

Привязка keyframe_start/end означает роль изображения в omni_reference и его тег в промпте; это не обещание отдельного API с жёстким first/last-frame constraint. `generation_manifest()` связывает реальные записи контракта с существующим адаптером, `build_preview()` отдельно демонстрирует A/B/C на синтетических данных. Ни один результат не пригоден для платного submit. Реальная отправка должна пройти существующие GenerationReview, confirm token, бюджет и свежую сверку расходов; этот модуль их не заменяет. UNKNOWN/hold/retry не изменяются.

Пределы: preflight не сравнивает пиксели персонажей и не доказывает неизменность меша, траекторию пиццы или художественное качество. Реальная registry approval persistence, UI и разрешённая live-проверка провайдера остаются следующими этапами.
