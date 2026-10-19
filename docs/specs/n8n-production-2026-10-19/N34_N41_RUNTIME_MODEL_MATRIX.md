# GremoVOD — runtime routing N34–N41 (Astra v1.2)

**Дата:** 2026-10-19. **Статус:** СПЕЦИФИЦИРОВАНО, не испытано на реальном MP4; никакие модели не активированы. Документ дополняет `ASTRA_FIXES_V1_1.md`, не заменяет OWNER gate. Никаких заявлений, что видео «просмотрено», до реального media evidence.

## 1. Два раздельных бюджета: разработка и исполнение

**Coding & Architecture (Codex):**
- Старшие reasoning модели — только для анализа гонок, транзакций, fail-closed схем, миграций и аудита. Опубликованный текст LLM **никогда не является** подтверждением работы транзакций: pytest/SQLite/CI обязателен.
- Экономичный coding класс (Haiku/Flash/mini) — шаблонные адаптеры, сериализация и рефакторинг по фиксированной схеме, **с обязательными тестами**.
- Python/JS и инструменты — вычисление хэшей, строгая валидация схемы, idempotency, бюджет/квоты, ffprobe/ffmpeg. Никаких флагманских моделей для арифметики/детерминированных правил.

**Runtime n8n:**
- Творчество A1/A2 — качественная модель Sonnet-class (или другой старший GPT), только по утверждённому бюджету. A0 — лишь содержательные противоречия/возврат; технические ошибки идут через code Switch.
- A3/форматы/краткие отчёты — Flash/Haiku/mini или строгий код, если формат полностью определён.
- Медиа A6/A7/A8 — только подтверждённые **комбинации конкретного provider/model/API operation/capability**; разные модельные семейства приветствуются, но не подменяют доступ к нужной модальности или независимые сессии.

Это **предлагаемые классы**, не фиксированные SKU, их текущая доступность/цены/лимиты в Kie и n8n **не проверены**. Реальный model ID выбирается после preflight; Opus не включать автоматически.

## 2. Точная матрица N34–N41

| Узел / стоимость | Исполнитель | Обязательный вход | Выход и решение | Условие BLOCKED |
|---|---|---|---|---|
| **N34 Technical Master QC — 0 LLM** | **локальный Windows media worker** с ffprobe + FFmpeg; Code нода валидирует подписанный ответ worker | `master_asset_id`, `expected_media_manifest`, `master_sha256`, `output_spec`, `producer_profile_revision` | `TechnicalQCResult`: streams, duration_ms, fps, width/height, audio streams, codec, bitrate, format, decode, optional ebur128/LUFS, silence/blackframe/blackdetect observations; `PASS_TECHNICAL/FAIL/BLOCKED` | Неизвестный/недоступный файл, несходящийся checksum, ffprobe/ffmpeg недоступен, отсутствующая обязательная дорожка. LUFS/тишина/чёрные кадры — **измерения и сигналы**, не художественный PASS. |
| **N35 Freeze + evidence — code, optional STT** | FastAPI trusted backend + media worker, затем STT (локальный Whisper, если есть вычисления; либо оплачиваемая услуга по grant) | Подтверждённый N34, actual master, approved canon/brief/bar/policy, model/skill profiles, `required_modalities`, hash всего manifest | `ReviewSnapshot`, `MediaEvidenceManifest`, три **раздельных** reviewer packet IDs на **один** round/hash. Не включать историю автора или чужие отзывы. | Нет полного обязательного coverage, audio/video доступен только по неподтверждённому URL, отсутствует право на обработку контента, expired URL без re-sign, STT ошибочно принимается за доказательство тембра/эмоции. |
| **N36 A6 requirements — bounded LLM** | **video-capable Gemini-class** на исходном медиа + trusted measurements; дешевая модель допустима только если пройдёт capability benchmark | Замороженный `review_round_id/snapshot_hash/master_checksum`, требования по ID, полное видео+аудио либо coverage evidence, технические факты + цитаты/таймкоды | `CriticVerdict` A6: per-requirement PASS/FAIL/BLOCKED, цитаты/интервалы, один главный дефект; не более **1 initial call**, retry только после preflight/approval | Нет фактического наблюдения требуемого действия/реплик/синхронизации. Вход только TEXT ⇒ BLOCKED для media criteria. |
| **N37 A7 continuity — independent multimodal LLM** | video-capable Gemini-class или верифицированная визуальная модель с нарезками; отдельная сессия; Sonnet-class **не утверждает непрерывное движение/звук** по одним кадрам | Тот же hash/round, релевантные **approved** версии Vault, кадры+видео/аудио coverage; без A6/A8 мнений | `CriticVerdict` A7: идентичность, костюм, цвет/география, связность, таймкоды/эталоны | Canon revision stale; внешность без reference evidence; звук/движение без фактической поддержки; reviewer видит чужой отчёт. |
| **N38 A8 craft — optional expensive model, required final role** | отдельный **native audiovisual evaluator с проверенной способностью слушать и наблюдать timeline**; Sonnet-class допустим для композиции по кадрам, но не как единственный источник оценки lip-sync/audio | Тот же master/round/hash, `craft_bar`, camera/acting/cuts/pace/audio windows, waveform/STT alignment, подтверждённая пользовательская оплата | `CriticVerdict` A8 по наблюдаемым критериям, локализованные проблемы; **сейчас DISABLED и BLOCKED**, не SKIPPED для финала | Недоступно видео/звук или не доказано lip-sync/движение, нет request authorization, опытная модель не протестирована. |
| **N39 Aggregate — 0 LLM** | trusted FastAPI/SQLite code | **ровно 3** current role responses A6/A7/A8, неизменные snapshot/round/master hash, coverage provenance, budgets spent/unknown | PASS всех → `AWAITING_OWNER_APPROVAL`; любой FAIL → `CHANGES_REQUESTED`; BLOCKED/dup/stale/mismatch/UNKNOWN → `BLOCKED`; no majority vote | Неполный/дублированный review set; одна модель проверяла иной файл; отсутствуют временные окна; неверная подпись media evidence. |
| **N40 Owner decision — 0 LLM** | authenticated Studio user session (не роль n8n) | Trusted same-snapshot verdicts + сам воспроизводимый MP4/аудио, owner identity, revision, decision nonce | `OwnerDecision` READY/RETURN_FOR_FIX с exact snapshot+master hash; никакого silent approval | Нет подтверждённой сессии человека, пользователь не увидел актуальный файл, hash сменился, роль service/AI. |
| **N41 READY — 0 LLM** | transactionally locked FastAPI + storage | `OwnerDecision`, актуальные master+snapshot, release manifest, idempotency key, сохранённая verified round | Idempotent immutable `READY` asset/manfiest; отдельные публикации в соцсети НЕ запускаются | Нет верной QA round, owner grant, файл подменён, новый canon/requirements/bar, повтор под другим ключом. |

**Значение PASS:** N34 — лишь технический экспорт; N36–N38 — фактически наблюдаемое содержание; N39 — структурная достоверность verdicts; N40 — решение человека. Ни один уровень не подменяет другой.

## 3. Проверяемость по модальностям

| Критерий | Что допустимо считать доказательством | Что недостаточно |
|---|---|---|
| Длительность, FPS, потоки, формат, checksum | доверенный ffprobe + decode/hash локального файла | LLM слова, filename/URL |
| Интегральная громкость/пики LUFS | FFmpeg ebur128/loudnorm измерение с аудиопотоком | один текстовый отчёт A1 |
| Паузы/чёрные интервалы/повторы | ffmpeg silencedetect/blackdetect/freezedetect как индикаторы, с таймкодами; пороги из output_spec | нулевой порог по умолчанию, отсутствие сигнала не доказывает «красивый монтаж» |
| Слова | STT word timestamps + spot-check по аудио, сверка с текстом; word timestamps не гарантируют покадровую точность | только исходный сценарий/субтитры |
| Тембр/интонация/эмоция/синхрон губ | реальное прослушивание и видеокадры на нужных временных окнах, профиль способностей модели, при сомнении человек | STT или редкая нарезка кадров |
| Монтажные стыки/осевая логика | оригинальный клип и temporal coverage, при нужде увеличенная частота кадров | 1fps sampling для быстрых стыков |
| Канон | verified approved Vault references соответствующей ревизии и media evidence | «так сказал» генератор, любой кандидат |

**Важное ограничение Gemini:** многие режимы по умолчанию семплируют видео примерно 1 кадр/сек, что **не гарантирует** обнаружение коротких стыков и точного lip-sync; нужен отдельный временной анализ, либо `BLOCKED`. Вендорская поддержка аудиовизуального файла ≠ доказанная способность проверять каждый критерий. Документация https://ai.google.dev/gemini-api/docs/video-understanding.

## 4. Контракты JSON между узлами

Путь: `N34 TechnicalQCResult` → `N35 FrozenReviewPacket` → `N36/37/38 CriticVerdict` → `N39 DecisionEnvelope` → `N40 OwnerDecision` → `N41 ReadyManifest`. Точный schema v1.2: `contracts/final-runtime-v1_2.schema.json`.

Поля N34: `media_uri_ref` (ID, не file path), `master_checksum`, `probe_status`, `duration_ms`, `video_stream_count`, `audio_stream_count`, `width`, `height`, `fps_num/fps_den`, `measured_lufs` (nullable), `black_intervals`, `silence_intervals`, `worker_identity`, `worker_signature_ref`, `extractor_version`, `measurement_coverage`.
Поля N35: `review_round_id`, `snapshot_hash`, `master_checksum`, `approved_brief_revision`, `canon_revision`, `review_bar_revision`, `model_profile_hashes`, `skills_hashes`, `media_manifest_hash`, `required_modalities`, `media_evidence_uris`, `reviewers[A6,A7,A8]`.
Поля reviewer: `review_round_id,role,snapshot_hash,master_checksum,provider,model,model_version,request_id,role_prompt_hash,session_id,capabilities,verdict,checks[{criterion_id,result,evidence_refs,largest_gap}],input_tokens,output_tokens,cost_usd,status`. Не включать сами приватные media в долгоживущие application logs.
N39 не доверяет user-supplied verdict, пересчитывает `hash(es)`, проверяет роль, round, уникальность, временной coverage и evidence refs.
N40/41 проверяют точные owner session/nonce/decision hash и актуальность текущего canonical source.

## 5. Стоимость и запуск

- `N34`: 0 токенов LLM; локальные CPU и storage **не бесплатны**, ffprobe не доказывает художественный результат.
- `N35`: ffprobe/FFmpeg/local STT = 0 **LLM** tokens (но время CPU); облачный STT требует отдельного budget grant; фиксировать фактический счёт и не обещать цену.
- `N36–38`: заранее согласовать per-role max requests/expected input video seconds, tokens, actual provider price, reserved cents и total cap. Начальная политика **не более одного запрос на роль и одного исправления по отдельному разрешению**. По ошибке UNKNOWN не повторять submit.
- `N39–41`: 0 LLM tokens. A0 не вызывается при технических инцидентах, его включение возможно при содержательном конфликте и только по отдельному платному approval.
- **n8n Cloud Execute Command отсутствует:** ffprobe/ffmpeg делать в локальном media worker, передать только trusted signed measurements через FastAPI и outbound integration. Code node n8n не имеет shell. https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executecommand/
- n8n Gateway credits на нашем экземпляре **проверены только** для Google Gemini text/message и Google Gemini image/generate; video/analyze и audio/analyze могут существовать как узлы, но не подтверждены как оплачиваемые из промокредитов. Нужен проверенный другой credential/profile, иначе BLOCKED.
- Существующий `n8n Execute Sub-workflow` mock у нас прошёл execution #36 (родитель вызвал A6 child, результат BLOCKED), а не saved Agent call.

## 6. Pre-live checklist

1. `N34` заполнен реальным достоверным ffprobe/FFmpeg worker output; есть право на файл.
2. `N35` три packets frozen отдельно; не содержат чужого verdict; media доступно каждому consumer; reviewer capability profile validated.
3. `N36–38`: video+audio tests на известных ошибках с конкретным backend-verified media; A8 включить только когда модель и spend approval проверены.
4. `N39` отбрасывает старые, чужие, неполные и дублированные verdict.
5. `N40` только user-session; `N41` только idempotent verified READY.
6. Если любого обязательного media/evidence нет, итог `BLOCKED_NO_REAL_MEDIA`, независимо от зелёного выполнения workflow.

## Источники для проверки окружения (не утверждают реальный успешный запуск)

- n8n Execute Command cloud restriction: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executecommand/
- n8n Gateway Credits: https://docs.n8n.io/deploy/use-n8n-cloud/gateway-credits/
- Gemini video understanding: https://ai.google.dev/gemini-api/docs/video-understanding
- FFprobe: https://ffmpeg.org/ffprobe.html
- FFmpeg filters (blackdetect/silencedetect/ebur128): https://ffmpeg.org/ffmpeg-filters.html
