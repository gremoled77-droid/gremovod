# CODEX NEXT ACTIONS — после бесплатного пилота GremoVOD
Дата проверки: 2026-10-19. Источник правды для очередности: мастер-ТЗ пользователя (6 этапов), `docs/CODEX_DECISIONS.md`, фактический результат n8n execution #39 и GitHub Actions.

## Базовое состояние, не завышать статус
- PR #17 `feature/n8n-astra-contract-hardening-20261019` — open DRAFT.
- PR #18 `feature/p0-studio-foundation-20261019` — open DRAFT, основан на ветке PR #17, не main.
- CI на ветке PR #18: run `39220285632` SUCCESS; P0 и FFmpeg тесты проводились на временных данных.
- n8n `WF_00` `j8Xqv8GQHjfJ5fVI`, execution #39 success: семь цепочечных workflow, MOCK only, zero provider calls, no real media.
- Реальная SQLite Studio не менялась; интеграция аутентификации и provider adapters не выполнена; A6/A7/A8 пока не просмотрели пользовательский MP4.
- `mock://` ссылки n8n — не настоящие downloadable assets. Real FFmpeg test runs inside GitHub runner; browser/n8n cloud cannot directly use it.

## P0 — ПЕРВЫЙ и блокирующий пакет для Codex

### TASK-01 — Согласовать код P0 с существующим backend (самый высокий приоритет)
1. Разобрать существующие таблицы и API `backend/main.py`, `backend/automation.py` и сторонние `pilot_state_sqlite.py` / `p0_control.py`; удалить функциональные дубли без удаления пользовательских данных.
2. Выбрать единственный официальный State Manager S01, SQLite connection lifecycle, WAL, per-transaction updates. Не создавать дополнительный production SQLite.
3. Переработать `db/schema.sql` / `scripts/p0_migrate.py` как безопасную миграцию по версии (backup + dry-run + rollback plan). Проверить на копии живой схемы с фиктивными данными; никаких автоматических изменений существующей БД.
4. Тесты в двух параллельных соединениях: два Resume, stale state, дубль callback, истёкшая lease, незавершённый job.
**ACCEPTANCE:** 0 потерянных legacy records, один успешный lease, restart process resumes only safe states, CI + интеграционный test.

### TASK-02 — Защищённая авторизация решений и расходов S04/S09
1. Реальные authenticated Studio sessions/project ACL/CSRF+nonce для владельца; не читать `trusted_studio_owner`, `provider_evidence_verified` или `owner_session_verified` из входного тела HTTP/n8n.
2. Два уровня: пакетный BudgetGrant и отдельный immutable request approval на каждый платный submit; валидировать frozen request hash/model/profile/stage/cap и expiry.
3. Создать недорогие API для read-only статуса и защищённых `approve/reject`; никаких автоматических UI/Telegram-approval без проверенной identity.
4. Отрицательные тесты: чужой владелец, n8n service token, replay, подмена prompt/профиля, исчерпание budget, повторный submit.
**ACCEPTANCE:** невозможно потратить денежный лимит или поставить READY через неподтверждённый запрос.

### TASK-03 — Защита от повторного списания S05
1. Durable PREPARED/INTENT, state SUBMITTING before provider POST, status UNKNOWN on lost acknowledgement.
2. Никаких автоматических повторов UNKNOWN. Реальное доказательство reconciliation `provider_job_id/client_key` для выбранного провайдера перед recovery; резерв денег не освобождать без доказательства.
3. Проверить duplicate callbacks/HTTP 200 with error body/cancel late completion.
**ACCEPTANCE:** mock-fault injection after provider POST makes submit_count=1, reserve stays, no double charge.

## P1 — РЕАЛЬНЫЙ ТРАНСПОРТ И МЕДИА (не платный)

### TASK-04 — Локальный media worker и безопасный канал к n8n Cloud
1. Найти установленный FFmpeg/ffprobe на Windows; запускать на доверенном локальном worker; n8n Cloud не выполняет shell-команды и не видит Windows localhost.
2. Организовать outbound-only dispatcher + защищённые upload/download с content_sha256, длиной, ограничением доступа и expiring grants. No public FastAPI ports.
3. Доставить один настоящий синтетический MP4 из local worker в n8n и обратно; измерить, что checksum совпадает. `mock://` ссылки заменить проверяемыми asset IDs.
4. Проверить interruption, retry data transfer, old file hash, expired URL, non-authorized fetch.
**ACCEPTANCE:** n8n реально получает и проверяет файл, а не просто JSON-запись. Никаких оплачиваемых моделей.

### TASK-05 — Довести семь WF до физической работы на реальных бесплатных файлах
1. `WF_00` — state/budget/owner gate в FastAPI; `WF_01` — реальные skills из git snapshot и данные approved brief; `WF_02` — два unapproved test canon fixtures; `WF_03` — независимые voice/sfx/music; `WF_04` — mock image→video + lipsync separate operation; `WF_05` — манифест, реальный FFmpeg master, N34 technical QC, N35 evidence; `WF_06` — repair shot_02 only.
2. Не переключать в paid mode; шаблон `external_tts` (native disabled), длительность речи измеряется, а не задаётся фантазией модели.
3. Прогон в n8n с действительными asset hashes и локальными FFmpeg результатами.
**ACCEPTANCE:** от концепта до master_scene.mp4 на mock файлах за один воспроизводимый запуск, после repair два незатронутых файла имеют прежний SHA.

### TASK-06 — Media QA: считать VERIFIED только проверенные возможности
1. N34 technical = FFprobe/FFmpeg 0 LLM. N35 media packets с audio and frame ranges; STT word timestamps только когда доступен локальный движок или отдельное budget approval.
2. N36–38 model capability evaluation на заранее известном баге. Проверка идентичности/тембра/motion/lip sync не подтверждается одним текстом, транскриптом или 1fps нарезкой.
3. N39 проверяет 3 verdict on same current immutable snapshot, N40 owner session, N41 READY only owner+verified evidence.
**ACCEPTANCE:** ошибки типа silent audio / wrong master / stale canon / wrong role / missing A8/expiring URL => BLOCKED. Пока нет настоящего пользовательского MP4 — реальная художественная оценка BLOCKED_AWAITING_MP4.

## P2 — ПОДКЛЮЧЕНИЕ ПО ОДНОМУ, ПОТОМ ПИЛОТ

### TASK-07 — Проверенные API-адаптеры без случайных списаний
1. Provider discovery and actual pricing Kie/TTS/image/video/lipsync by connector contract; no credentials in git. Проверить поддерживаемый endpoint, idempotency, cancellation and callback authenticity.
2. Включать feature flags строго последовательно: (1) TTS → (2) reference-based image → (3) short video 3–5 s → (4) lip-sync as separate job. Везде request-bound Spend Gate, cost ledger.
3. Проверять реальный остаток провайдера, не считать n8n promotional credit валютой Kie.
**ACCEPTANCE:** разрешённые вызовы прослеживаются до owner grant, нет скрытого второго submit. Пока без проверенного approval — все адаптеры OFF.

### TASK-08 — Контентное качество и первый короткий реальный пилот
1. Подключить approved series bible / characters / stable voices / skills. `generate-fresh-ideas`, `grem` и др. не считать установленными без файлов/источника.
2. В реальном brief owner выбирает концепт; A1/A2 пишут сценарий и план; затем TTS→image→video→separate lip-sync→full manifest→master→3 independent critics→human acceptance.
3. Подтвердить targeted repair and re-review of entire new master snapshot; не переписывать канон автоматически.
**ACCEPTANCE:** реальная 3–5 шотов сцена проходит owner decision и проверку бюджета. Пользовательского видео пока нет, что блокирует real QA; mock fixture не подменяет acceptance.

### TASK-09 — Только после настоящего пилота: Studio UI и масштабирование
Разработка React UI только по проверенным реальным действиям (owner grants, jobs/status, asset gallery, Canon Vault, review evidence, budget ledger). SQLite→PostgreSQL только при подтверждённой необходимости и безопасной миграции. Не создавать новые функции интерфейса для мок-API, выдаваемые за production.

## Правила работы Codex
- Владелец разрешил **двигаться между задачами разработки без повторного запроса подтверждения**, но платный submit, изменение единственной рабочей БД, публикация и утверждение канона остаются gated на доверенном runtime.
- Критические решения и блокеры: запись `docs/CODEX_DECISIONS.md` и безопасная реализация, не bypass.
- В main PR #17 / #18 не сливать без code review и сопоставления зависимостей.
- При любом пункте честно разделять `MOCK_PASS`, `TECHNICAL_PASS`, `PROVIDER_TESTED`, `READY_FOR_PRODUCTION`.
