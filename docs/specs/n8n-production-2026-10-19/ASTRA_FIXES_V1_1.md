# Astra review closure v1.1 — исполнимые правила пилота

**Дата:** 2026-10-19. **Источник:** обзор Astra `codex/n8n-full-production-spec-20261019`. **Статус:** контракт и проверяемая офлайн-логика; не production и не подтверждённая media QA.

**Принцип очередности:** сейчас исправляем P0/P1/P2, используем mock/negative tests и регистрируем решения. Реальный MP4, генерация, ролевая video/audio экспертиза, публикация и Studio UI **отложены** до получения файла и отдельного разрешения. Документы не утверждают никаких артефактов/канона. Рабочие n8n демо и backend из иных веток не объединять без проверки.

## Решение по P0-01: S01/S08/S09 — одно состояние и доверенные решения

Для **локального пилота** единственный источник истины — **существующий FastAPI + SQLite Studio** (после безопасного чтения текущей схемы и миграции в отдельной тестовой базе; без дополнительной production SQLite). Отдельную writable БД n8n не создавать; n8n только исполнитель. Cloud не получает прямой доступ к SQLite/Windows loopback. Облачная очередь — outbound dispatcher из Windows либо строго контролируемый HTTPS proxy после threat review; **пока не соединён**.

- `run_id, operation_id, attempt_id, project_id, artifact_revision, input_snapshot_hash, state_revision, lease_owner, lease_until, updated_at` хранятся долговременно. Каждый переход — транзакция с `BEGIN IMMEDIATE` / сравнение `state_revision`; при необходимости lease захватывается атомарно `UPDATE ... WHERE state_revision=? AND (lease_owner IS NULL OR lease_until<?)`. Одновременные resume не исполняют один и тот же operation.
- n8n execution ID — лишь корреляция, **не** ключ первичного состояния. Outbox/Inbox фиксируют отправку и доставку; повтор webhook/callback идемпотентен по `(run_id,event_id)`, несовпадающий payload под тем же ID => 409.
- Все события содержат `actor_type, actor_id, operation_id, expected_state_revision, snapshot_hash, recorded_at` и result/evidence refs без сырого секретного payload в логах.
- Владелец принимает выбор концепции, канон, бюджетный пакет, конкретный запрос и READY **только через существующую аутентифицированную сессию Studio**; проверяются project ownership, тип решения, ревизия объекта и подпись/CSRF согласно существующему session gate. **n8n service token не может делать owner approval**. Для временной ручной процедуры используется точно зафиксированное подтверждение с идентифицированной сессией Studio, но не кнопка n8n, не чат с моделью и не `approved:true` из JSON.
- Одна попытка/статус для одной логической операции; различать `created`, `authorized`, `submitted`, `delivered`, `verified`, `accepted`.

**Тестовые инварианты:** два resume → только один lease; stale revision → 409; повтор одинакового event → тот же результат; изменённый event → 409; service role пытается APPROVE → 403. Приложение не объявляется подключённым, пока не пройдёт реальный API sandbox.

## P0-02: S04/S05/N17/N43 — ambiguous paid submit

До каждого внешнего запроса создать долговременную операцию с `operation_id, provider, profile_revision, request_hash, provider_idempotency_key, budget_reservation_id, attempt=1, submit_state=PREPARED`.

Порядок: freeze inputs → package approval → specific request hash + профиль/ценовой ceiling → **атомарный резерв** → immutable PREPARED запись → отправка. После записи намерения `SUBMITTING` любое падение/timeout прежде получения provider job ID означает `UNKNOWN`; **не делать новый submit**. Сохранять резерв и `possible_charge=true`. Автоматическая сверка допустима **только** при доказанной provider-side идемпотентности или search by client key, зафиксированной для конкретного адаптера с живым тестом; иначе ручная финансовая сверка. Запрещено освобождать резерв по таймеру при UNKNOWN. После доказанного no-charge можно явно отпустить резерв; при доказанном charge учесть фактический расход. Отмена не возвращает уже потраченный бюджет и не гарантирует остановку provider job.

**Тесты:** timeout после submit → UNKNOWN, число submits=1; recover без provider ID не звонит provider повторно; callback после cancel не оживляет операцию; body-level error при HTTP 200 = ошибка; дубль callback не увеличивает счёт.

## P0-03: двойной бюджетный контракт

`BudgetGrant` — разрешение ВЛАДЕЛЬЦА на конкретную область: `project_id, run_id, stage_set, provider_allowlist, model_allowlist, total_cap, currency, maximum_calls, expires_at, owner_session_decision_id`, текущий `reserved+spent <= cap`.

`RequestAuthorization` — *перед КАЖДЫМ* submit: `operation_id, stage, frozen_request_hash, artifact_revision, provider/model/profile revision, projected_upper_cost, parent_grant_id`. Если любой hash, профиль, версия, цена, владелец или политика изменились — авторизация недействительна; пересчитать бюджет и запросить разрешение. Нет строгого upper bound у модели/операции → BLOCKED либо отдельный явный фиксированный envelope, не заявлять о hard stop без API провайдера. **n8n Free Credit ≠ гарантированная нулевая стоимость**; проверять реальные дебеты в биллинге.

**Тесты:** изменение промпта/референса после approval → BLOCKED; конкурентные reservations не превышают grant; call_count максимум; при UNKNOWN резерв остаётся; изменения grant без повторной авторизации конкретного запроса не допускаются.

## P0-04: реальный media-evidence и A6/A7/A8

Сейчас все IMAGE/VIDEO/AUDIO/FINAL_MEDIA gates возвращают **BLOCKED `MEDIA_NOT_YET_AVAILABLE`**. Модельный текст/JSON/транскрипт/отдельная картинка не считаются доказательством движения, голоса и монтажных стыков. Таблица capabilities должна хранить реально испытанные `frames,continuous_motion,audio_listening,dialogue_content,voice_timbre,lip_sync,edit_cut` (каждый `verified|unsupported|unverified`), `provider,model,version,method,coverage,start/end,reliability_test`. Нельзя подставить `verified=true` из ответа модели — ставит только trusted extractor.

При появлении MP4 первым тестом делаем: доступность файла из реальной среды n8n → codec/streams/duration/checksum → синхронизированное окно видео+аудио → три независимых QA-пакета на тот же snapshot → owner decision. До этого реальных трёх PASS/READY нет. `Gemini video analyze` и `audio analyze` доступны как **типы нод**, но Gateway coverage и реальный мультимодальный доступ/цену/модель надо отдельно проверить, не считать текущую текстовую демоверсию подтверждением.

## P1 — исправленные маршруты по узлам

**N20 → N22 → N26 (audio strategy):** `audio_strategy` выбирается/фиксируется **в N20**, до N22. Одновременно фиксируются `speech_strategy = external_tts | native_video | silent`, `ambient/SFX/music` независимыми обязательными дорожками. Для native реплик `dialogue_timing.estimated` плановый, не фактический; N26 использует диапазон и проверяет поместимость; после N30 фактический тайминг измеряется из клипа и передаётся в N25 до N32. `native_video` пропускает только external TTS, **не** музыку/SFX/ambient и финальный аудиопросмотр. Silent допустим лишь если сценарий не требует речи.

**N22–N25/N31/N42:** callback audio failure содержит `origin=speech_native | speech_external | music | sfx | ambience`: native speech → N27/N28 (новый видео request approval); external дорожка → N21/N22; микс/стык → N32/N33. Никаких полных видео-повторов при дефекте внешней дорожки.

**N12 → N15–N19 → N12:** отдельный subflow `IMAGE_REFERENCE_CANDIDATE` с минимальными карточками и `reference_role,identity_source_ids,output_target=reference_candidate`. N15 принимает режим `shot_image | reference_candidate`; после N19 эталон **CANDIDATE**, возвращается в N12 с обязательным owner approval. Обычный shot_image после N19 идёт к N20. В пилоте — заранее подготовленный утверждённый комплект, если такого комплекта нет: BLOCKED, не зацикливать.

**N29 → N30 → N29 → N30:** `video_generation` и `lip_sync` — *отдельные* operations с собственными ID, source asset checksum, профилем, preflight и платным разрешением. Сначала N30 сохраняет проверенный клип, затем (если запрошен) N28 снова проверяет lip-sync request, N29 отправляет только lip-sync, N30 сохраняет его производный клип. Сбой lip-sync не вызывает повторную исходную video-generation job.

**N32/33:** до монтажа `expected_media_manifest` замораживает **все** необходимые shot/voice/music/SFX/ambience/titles `{slot_id,kind,required,artifact_revision,checksum,selected_take_id,status}`. Все required слоты должны быть fulfilled на актуальных ревизиях, с валидным checksum и разрешённым источником; `SKIPPED` только по явной политике, не эквивалент PASS. Частичный batch никогда не завершает сцену.

**N35–N41:** `review_round_id` + `snapshot_hash` от: master checksum, замороженного manifest, requirements, canon, review_bar, policies, profiles+roles, skills hashes, provenance. A6/A7/A8 получают **один и тот же** snapshot и **раздельные** сессии. N39 принимает ровно один текущий ответ каждой роли и отбрасывает stale/duplicate; N41 **повторно сверяет** rev/hash/policy/доступ и owner decision для точного hash. Master без изменения байтов, но изменённый канон/бар => новый review snapshot и требование новых вердиктов.

**S06/N30/N35:** каждый derivative имеет `source_checksum, derivative_checksum, transform_name+version+parameters_hash, timestamps/coverage, codec/stream metadata`, доказуемый content-addressing и доступность **со стороны критика**, не только Windows. Истечение signed URL обновляет `access_grant`, но НЕ меняет контент/хэш; переподписанный доступ нельзя использовать для нового файла или иного scope.

**N34 (P2):** только технический preflight экспортированного master: file exists, codec/streams, manifest completeness, silence/clipping/black-frame indicators where extractor exists. Ремесленные A6/A7/A8 делают **единственную** содержательную критику master в N36–N38; второй художественный прогон только по отдельному approval.

**N07:** политика первой версии — **минимум 2 смыслово различных варианта**, N07 проверяет все предложения, N08 допускает выбор среди `accepted_count >= 2`; один слабый вариант не обязан блокировать хорошие, если минимальное количество выполняется. Если нужно больше — это отдельное правило пользователя, не скрытая настройка A1.

## Контракты перехода (необходимая сторона для mock и Codex)

Каждый переход между этапами передаёт:
- `task/run/operation/attempt IDs, stage, project_id, state_revision, artifact_id/revision, input_snapshot_hash, idempotency_key`.
- `artifact_manifest` с проверяемым происхождением всех required outputs; NO missing input silently.
- `role_verdicts` и `blocked_reason` как разные виды результатов; `SKIPPED` не успех, если слот обязателен.
- `budget_grant_id, request_authorization_id, reserved/spent/possible_charge` только когда планируется платное действие.

Реальные методы исполнения/вызываемый Code или HTTP Request выбирает код после проверки prereq; нода/LLM не придумывает новые ходы. Любой unsupported branch/unknown charge/stale revision становится `PAUSED`, а не SUCCESS.

## Перед запуском реального медиа (отложено)

1. У пользователя есть разрешённый реальный MP4 (без публикации), требования и применимый канон, выбранными референсами; проверить, что он вправе использовать голос/музыку/образы.
2. File transfer Windows→n8n: **действительно** доступный host-to-cloud маршрут, ограниченный конкретным blob, checksum/length, expiring access. Не выставлять local FastAPI в Интернет.
3. Фактический provider/model capability test для visual motion/audio/timbre/lip-sync/transitions, проверка отдельных модальностей известными ошибками.
4. Один конкретный `BudgetGrant` и freeze request approvals на проверку (LLM, audio transcribe и др.).
5. Контролируемые failure injections: unknown submit, double resume, stale snapshot, duplicate callbacks, expired URL; помечать `NOT_TESTED` в облаке до реальной проверки.
6. Только потом short clip → three reviewers → owner decision; затем идея→A1→A2→изображения→звук→видео→монтаж→READY.

## Доказательства и границы текущего этапа

Эта версия исправляет **схему**, а не подтверждает provider/audio/video. JSON-спецификация должна ссылаться на эти правила, но лишь статус `SPECIFIED`/ `SIMULATED` допустим без live runtime. Owner approval, бюджет и carrier state должны быть проверены в backend, а не в LLM или n8n Code.


## Вызов ролевых агентов в n8n: не смешивать продукты

Официальная документация описывает **Message an Agent v3.1**, но у конкретного MCP-инстанса были retired/несогласованные метаданные. Нельзя объявлять этот node глобально удалённым и нельзя считать доступность доказанной. Для пилота остаётся выбранный в спецификации **Execute Sub-workflow** с независимыми ролевыми workflow и одним закреплённым источником инструкций; это НЕ исполнение saved Agent IDs. Начать с mock child workflow без LLM и проверить передачу/ожидание результата. До cloud-проверки sub-workflow endpoint: статус `NOT_TESTED`. Для Message an Agent отдельная безопасная проверка версии и состояния публикации; не активировать saved Agents для обхода.

## Доверенная граница SQLite reference-кода

`integrations/n8n/pilot_state_sqlite.py` — импортируемый **офлайн reference module**, но не FastAPI router, не session validator и не provider adapter. Его `owner_authenticated`, `trusted_backend_verifier`, `owner_session_verified` сейчас передаются вызывающим тестовым кодом. В production их **никогда не передавать из HTTP body, n8n JSON или LLM**: они должны вычисляться внутри защищённого FastAPI из существующей сессии человека и серверного evidence-verifier, после проверки project ownership. В целях безопасности `owner_ready` дополнительно требует persisted final round, а незаполненные media states всегда BLOCKED. Реальный S09 нельзя считать выполненным до такого интеграционного испытания.
