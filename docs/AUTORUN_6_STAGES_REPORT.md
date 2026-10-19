# GremoVOD — автоматический прогон этапов 1–6, отчёт для Codex

Дата: 19.10.2026. Владелец разрешил **продолжать все этапы без промежуточного подтверждения**, критические решения документировать и откладывать на ревью Codex. Это не даёт возможности обходить реальные provider billings, session ACL или отсутствие видео.

## Проверенные результаты

- **7 физических n8n workflow**, вход WF_00 вызывает все WF_01–WF_06 через Execute Sub-workflow. Execution **#39** `success`, `all_seven_modules_ran=true`, 3 mock-шота, 3 mock-дорожки (voice/sfx/music), ремонт только `shot_02`, остальные два закэшированы, `paid_calls=0`, `final_release_approved=false`. Workspace GremoVOD; все 7 `active=false` — только draft.
- Регистратор IDs: `integrations/n8n/WF_00_WF_06_MANIFEST.json`.
- **Пять дополнительных SQLite-таблиц**: `db/schema.sql`. Existing `backend/main.py` использует `studio.sqlite3` и прежнюю таблицу `jobs`, поэтому добавлены `p0_*` без перезаписи. Никаких изменений на настоящем диске пользователя.
- **Контрольная модель** `backend/p0_control.py`: две защиты от повторного запуска, замороженный запрос, атомарный бюджет в целых центах, UNKNOWN сохраняет резерв и никогда не re-submit, сверка подтверждённой оплаты по event ID, неполный scene manifest блокирует монтаж.
- **Безопасная миграция** `scripts/p0_migrate.py`: dry-run по умолчанию, явный `--apply` делает отдельный SQLite online backup и затем добавляет таблицы. Тестовый вариант проверен на temporary DB в CI.
- **FFmpeg mock factory** `tools/mock_media_pilot.py`: генерирует 3 синтетических 3-секундных видео со звуком + PNG + WAV, делает MP4 master, N34 ffprobe/ffmpeg decode/FPS/streams/checksum, меняет только `shot_02` и собирает master снова, сравнивает checksum двух нетронутых шотов.
- **N35 evidence** `tools/mock_evidence.py`: на реально созданном synthetic MP4 извлекает mono 16 kHz audio и 3 кадра по таймкодам, связывает версию сценария и master в SHA-256 snapshot. STT, lip sync, монтажные стыки и мультимодальная художественная оценка честно `BLOCKED`.
- **Канон**: `canon/characters/TEST_CHARACTER_A.json`, `TEST_CHARACTER_B.json`, `canon/locations/TEST_LOCATION.json`, `canon/voices/TEST_VOICE.json`. **Все явно noncanonical/unapproved**, нет voice cloning.
- **Реальные provider adapters**: `backend/p0_provider_dispatch.py` по умолчанию закрыты для TTS/image/video/lip-sync. Mock допустим, real submit нет; защищает от расхода без биллинга/доступа.
- **Спецификация и схемы**: `SPECIFICATION.md`, `NODES.md`, `nodes.json`, `VALIDATION.json` содержат семь WF и внешний TTS-first (native audio disabled). В `docs/CODEX_DECISIONS.md` — 12 pending critical decisions.
- **GitHub Actions**: `.github/workflows/n8n-astra-pilot.yml` запускает SQLite unittest + Node аварийные тесты + реальную FFmpeg mock сборку/N35. Успешный базовый прогон **39219461036**: 63 Python теста и 7 Node тестов (включая ffmpeg) + проверка каталога 52 IDs. Дополнительно добавлены тесты миграции и N35; смотреть current branch latest CI для нового общего итога.

## Статусы по этапам

| Этап | Результат без платных API | Что ещё реально НЕ готово |
|---|---|---|
| 1. Память, деньги, восстановление | **REFERENCE CODE TESTED IN CI**: 5 SQLite tables, backup, locks, budget, UNKNOWN | Подключение к **реальной** FastAPI owner-session и текущей DB требует ревью |
| 2. Приёмная комиссия | **TECHNICAL MOCK**: ffprobe, FFmpeg, audio+frame pack | Пользовательский MP4, Whisper word timestamps, motion/cuts/lip-sync, A8 media capability |
| 3. Сценарная комната | **ROUTED MOCK**: WF_01 и существующие skills registry, no paid prompts | Approved brief/voice/canon и реальный A1/A2 call |
| 4. Библия и free pipeline | **EXECUTED MOCK**: 7 connected n8n workflows, 3 slots+3 tracks and isolated repair | Реальные мультимедийные файлы доступны лишь локальному runner, **не** n8n cloud worker |
| 5. Боевые генераторы | **DISABLED ADAPTERS**: безопасные mock профили | Verified TTS/Kie credentials, цена, оплатный лимит, outbound worker |
| 6. Настоящий пилот | **MOCK E2E only**, release blocked | Настоящее утверждённое видео/голоса/канон, мультимодальный QA и решение человека |

## Критические решения в очереди Codex

Источник: `docs/CODEX_DECISIONS.md` (D-001–D-012). **Не считать их решёнными по факту зеленого mock.**
- D-001–D-003: migration path; владельческая session/ACL, schema mapping к существующим сущностям.
- D-004: provider UNKNOWN reconciliation, доказательства оплаты и запрет повторного submit.
- D-005–D-006: TTS/voice rights, затем отдельный lip-sync job после аудио и видео.
- D-007–D-008: семь физических WF и защищённый outbound worker с FFmpeg реальным доступом.
- D-009–D-010: skills и независимые multimodal critics.
- D-011–D-012: реальные MP4, бюджет, отказ от ложной готовности.

## Важная граница

Зелёный n8n execution **не** означает production. Здесь все сценарии `MOCK_MODE=true` с заглушками, оба provider submission paths закрыты, сценарий не утверждён владельцем, реальные A6/A7/A8 не работали с user MP4, и `READY=false`.

**Следующий технический PR Codex**: интеграция безопасных P0 маршрутов FastAPI к session + существующему `studio.sqlite3`; отдельные end-to-end тесты на копии БД и mock FFmpeg в окружении Windows; проверенная доставка meda-blob в n8n; только потом реальный user MP4 и provider authorizations.
