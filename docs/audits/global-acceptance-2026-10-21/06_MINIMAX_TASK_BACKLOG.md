# Минимальная очередь MiniMax — задания подготовлены, не назначены

База каждого будущего PR: новый зафиксированный SHA от `mavis/work@57cac59` с уже принятыми зависимостями. Не переписывать старые MM-ветки и не переносить весь llm_guard из старой базы.

Общий запрет всех задач: без production SQLite/media/credentials, платных API, канона, существующих AGENTS/CLAUDE/SKILL, сервера 8000/5173, merge/main/force-push. Не включать чужие незакоммиченные файлы. Публикация будущих PR/исполнение этих задач не авторизованы этим бэклогом.

## GA-01 · Достоверный settlement всех LLM · P0

**Доказательство:** P0-01 в 03: 3 mock calls без usage → $0; отрицательные токены → -$0.14; conditional task timeout → failed/$0. Существующий MM-001 `f9f810f` содержит полезный validator, но основан на старой версии.

**Существующие файлы/функции:** [backend/llm_guard.py:296](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/llm_guard.py#L296) minimax_actual_cost, execute_minimax_task, guarded_chat, settle_call; [backend/main.py:792](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L792) run_agents; test_money_boundary.py, test_llm_guard.py. Найти все callers расчёта/settlement, включая compose/Producer/Story Plan, до правки. Реестр моделей остаётся существующим.

**Изменить:** переиспользовать один валидатор usage/стоимости внутри llm_guard; принимать только целые неотрицательные токены, не bool; не принимать NaN/Inf и отрицательную итоговую цену. Отсутствующий/повреждённый usage удерживает резерв и объясняет неопределённость. При частично оплаченном multi-role run учитывать подтверждённую часть и сохранять неопределённую, без ложного $0. Task transport timeout/parser failure не освобождает деньги без достоверного no-charge evidence. Записывать реальный overrun, без min(estimate).

**Запрещено:** менять тарифы, UI, схемы проектов/канона, маршруты TTS, n8n workflow, придумывать второй ledger/реестр или повторять paid submit.

**Зависимости:** нет для guarded_chat/agents; task lifecycle нужно принять совместно с GA-02 до его включения. Баги SQL нельзя исправить так, чтобы открылась unsafe task-ветка до денежного retest.

**Тесты/негативные случаи:** обычный usage; missing one/both counters; отрицательные/bool/string/слишком большие значения; nonfinite сумма; 4xx до исполнения vs timeout после отправки; 200 с неразбираемым content; 3 роли, у второй отсутствует usage; реальный cost выше оценки; дубликат request_id, перезапуск/сверка без повторного submit; счётчик media/LLM в обоих порядках.

**DoD:** ни один невалидный usage не уменьшает занятый бюджет; UNKNOWN удерживается; подтверждённый факт виден один раз; все прежние money/unified-budget/P0 тесты зелёные.

**Риск:** высокие связи со статусами и расчётами серии. **Проверка Codex:** повторить четыре синтетические пробы из 03, проверить строки ledger и число mock submit, затем затронутые suites. **Ветка:** `minimax/ga-01-llm-settlement`. **Минимальный PR:** только эти две runtime-функциональные области и их regression tests, без механического форматирования всего main.

## GA-02 · Восстановить prepare/permit/execute · P1

**Доказательство:** P1-01: отсутствующие task_identity/task_request_id; reserve INSERT 10 значений в 11-column llm_calls. [backend/llm_guard.py:327](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/llm_guard.py#L327), [backend/llm_guard.py:438](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/llm_guard.py#L438).

**Существующие файлы/функции:** llm_guard.py::prepare_task, task_status, permit_task, reserve_minimax_task, execute_minimax_task; test_llm_guard.py. В локальном незакоммиченном root есть helpers; сначала прочитать/сопоставить, не импортировать весь dirty файл.

**Изменить:** минимально восстановить существующий контракт identity/request_id; использовать явные columns при INSERT; добавить реальный endpoint lifecycle test с startup note-column и повторным открытием временной базы.

**Запрещено:** новый API-протокол, новый ledger, фронтенд-редизайн, отключение проверок revision/permit/approval или удаление note ради старого INSERT.

**Зависимости:** GA-01 обязателен до включения paid execution; D2 решает, нужен ли этот путь первой бете. При исключении из беты сервер должен явно отказывать, а UI это показывать; не просто скрыть кнопку.

**Тесты:** prepare same request→same task; request ID с другим spec→409; permit expiration/изменённая revision; double execute/параллельный execute; missing key; normal result JSON/text; no provider call до правильного reserve; timeout/parse error по GA-01; stored result replay.

**DoD:** настоящий lifecycle без monkeypatch внутренних helpers, корректный id на всех ответах; провайдер вызван ровно один раз; no-charge/UNKNOWN не смешиваются.

**Риск:** средний, совместимость request_id и сохранённых task rows. **Codex:** повторить неизменённый первоначальный prepare-repro, lifecycle и reopened DB. **Ветка:** `minimax/ga-02-text-task-lifecycle`. **PR:** llm_guard + один lifecycle test file/существующий test module.

## GA-03 · Связать импорт master с приёмкой выпуска · P1

**Доказательство:** `persist_release_artifact` безусловно ставит `ready`; ReleaseSummary показывает «финальных MP4», QC/QA APIs независимы. [backend/release_artifacts.py:140](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/release_artifacts.py#L140), [frontend/src/StageSummary.tsx:158](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/frontend/src/StageSummary.tsx#L158). Это статически подтверждённый продуктовый пробел, не утверждение о публикации файла наружу.

**Существующие файлы/функции:** release_artifacts.py::persist_release_artifact, listing, artifact_record; media_qc.py::_qc_record/_artifact_path; qa_reviews.py::freeze_media/review_status; StageSummary.tsx::ReleaseSummary; tests media_qc/n35/smoke.

**Изменить:** после D3 сформировать минимальный server-owned read model: импортирован / technical-pass / решение владельца по тому же master hash. При отсутствии/ошибке/устаревшем QC не показывать «проверенный выпуск». Переиспользовать existing QC records и project revision; не строить второй QA engine.

**Запрещено:** автоматически утверждать канон/художественное качество, запускать три paid critics, доверять client boolean вместо зафиксированного решения, менять исходный master или удалять старые imports.

**Зависимости:** D3 (ручная owner-приёмка для пилота или обязательный critic contract). GA-01 нужен для любых будущих платных critics, но локальный N34 не зависит от него.

**Тесты:** импорт без QC; FAIL/BLOCKED; PASS другой hash/revision; изменённый/пропавший файл; отсутствие approval; правильный hash+technical+owner; повторное открытие и старые артефакты. Негативные сценарии на синтетическом MP4.

**DoD:** один импортированный MP4 не может стать «проверенным выпуском» только по факту upload. Тот же hash проходит обязательные выбранные проверки и явное owner-решение.

**Риск:** средний, прежнее значение ready и UI wording; старые записи сохраняются. **Codex:** route-negative tests + вручную browser путь на временном стенде, сверить hash/ответ API. **Ветка:** `minimax/ga-03-release-acceptance-state`. **PR:** минимальный status/read-model/API+UI+tests, без нового монтажа.

## GA-04 · Сделать CI кандидата проверяемым · P1

**Доказательство:** .github в кандидатном SHA содержит узкий n8n pilot и coordination/scope checks; predicate scope-guard не включает minimax/*, mavis/*; для candidate SHA check-runs пуст. Branch settings отдельно UNKNOWN по auth-доступу.

**Существующие файлы:** [.github/workflows/agent-scope-guard.yml:15](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/.github/workflows/agent-scope-guard.yml#L15), [.github/workflows/n8n-astra-pilot.yml:1](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/.github/workflows/n8n-astra-pilot.yml#L1), tools/check_agent_scope.py, frontend/package.json, backend/requirements.lock.txt.

**Изменить:** малый workflow с backend offline unit tests на временной DB, frontend tests+tsc/build; для новых task-веток MiniMax применять явный allowlist/проверку scoped paths без ломки исторических PR. Не запускать live scripts. Проверить корректные path filters для main/llm_guard/character_voice/spend_ledger/frontend.

**Запрещено:** менять repository settings, required checks или permissions без отдельного решения владельца; secrets в CI; автоматический merge или provider smoke.

**Зависимости:** нет для workflow; GA-01/02 должны иметь свои tests, чтобы CI их реально запускал. D7 — отдельно о включении обязательности checks.

**Тесты:** fork/PR без credentials; deliberate failing assertion→красный check; смена main.py запускает suite; смена чужого пути в task-ветке→scope fail; docs-only PR не создаёт ложный статус полной Studio-приёмки.

**DoD:** фиксированный candidate SHA получает воспроизводимые offline checks; UI и критический backend покрыты. «Workflow существует» и «branch protection требует его» отчётливо различаются.

**Риск:** средний, false skip и неполные dependencies. **Codex:** diff workflow permissions/commands, реальные Actions jobs и logs, negative path filter fixture. **Ветка:** `minimax/ga-04-studio-offline-ci`. **PR:** CI + scope-test/allowlist, без runtime-кода.

## GA-05 · Доверенные proxy для login throttle · P1 перед remote

**Доказательство:** семь неверных паролей с разными XFF→семь 401; [backend/remote_access.py:89](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/remote_access.py#L89), [backend/remote_access.py:145](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/remote_access.py#L145).

**Существующие файлы/функции:** remote_access.py::client_ip/login/is_loopback; test_remote_access.py; чтение Caddyfile/Dockerfile/topology.

**Изменить:** по умолчанию peer address; forwarded headers учитывать только от явно доверенного proxy и по определённому правилу цепочки. Для локального пилота достаточно loopback без remote. Не менять общий auth/session механизм.

**Запрещено:** публично открывать сервер, ослаблять Host/Origin/cookie gates, читать production пароль, добавлять обходные логины.

**Зависимости:** нет для default peer-address защиты; реальный proxy trust contract проверяется до удалённого запуска.

**Тесты:** прямой peer с меняющимися XFF всё равно получает 429; доверенный proxy; forged chain/пустой/некорректный XFF; IPv4/IPv6; spoof loopback Host; secure cookie и foreign Origin.

**DoD:** без trusted proxy произвольный заголовок не меняет rate-limit identity; действующий login flow остаётся.

**Риск:** средний, несколько клиентов за proxy могут делить лимит при неверной настройке. **Codex:** повторить probe + remote_access suite; проверить настройки только на временном стенде. **Ветка:** `minimax/ga-05-trusted-proxy-throttle`. **PR:** remote_access + targeted tests; deployment-настройки отдельно по решению владельца.

## После исправлений — приёмка, не новая волна разработки

Следовать 08: один offline E2E, browser, CapCut, выбранный master, restore/hash и owner decision. P2-01/P2-02 сначала решаются сверкой существующей документации/skill-catalog; не поручать повторную реализацию общего бюджета или ещё один writers-room. Художественные предложения #50–53 не входят автоматически в эти пять PR.
