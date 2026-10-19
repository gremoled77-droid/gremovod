# GremoVOD — полный план пилота n8n Cloud → GitHub Actions → Aider/GPT → Git → Argon

**Дата:** 2026-10-19  
**Статус:** SPEC / NOT IMPLEMENTED / NO LIVE RUN  
**Приоритет:** P0 для испытания контура разработки, независимо от медиапроизводства GremoVOD.  
**Владелец решений и платных запусков:** пользователь.  
**Базовый репозиторий:** https://github.com/gremoled77-droid/gremovod  
**Связанные материалы:** [Issue #21](https://github.com/gremoled77-droid/gremovod/issues/21), [ручной Draft PR #22](https://github.com/gremoled77-droid/gremovod/pull/22), [PR #19 — разделение ролей](https://github.com/gremoled77-droid/gremovod/pull/19).

> Это план, не активный workflow и не отчёт об успешном LIVE-прогоне. Ни один API-вызов, платный тест, merge, настройка secrets или запуск Actions этим документом не производится. Не считать прохождение MOCK тестированием реального API.

## 0. Цель и определение успеха

За один изолированный пилот провести малую проверяемую задачу: **владелец задаёт задачу → n8n регистрирует → GitHub запускает изолированный job → Aider выполняет ограниченное изменение → бесплатные тесты → коммит в отдельной ветке → Argon оценивает строго выбранный diff → результат в Draft PR → владелец принимает решение**.

На первом этапе операции идут вручную и офлайн; только затем после отдельных подтверждений допускаются одиночные платные запросы. Успех = прозрачный воспроизводимый протокол, измеренные расходы, доказанная блокировка аварийных случаев, отсутствие влияния на main и производственные workflows. Не оценивать успех по одному слову PASS от LLM.

**Не входит:** генерация медиа, правка персонажей/канона, работа с локальной боевой SQLite/медиафайлами, облачное развёртывание GremoVOD, автоматический merge, бесконечные циклы исправлений, активация существующих n8n MOCK.

## 1. Подтверждённая база и обязательные ограничения

1. В Draft PR #22 уже предложены docs/ai-review/PLAN_RU.md, TASK_FOR_ARGON_RU.md, tools/ai_review/argon_review.py и tests/test_argon_review.py. Использовать их после чтения и code review; **не переписывать и не копировать без причины**. PR #22 пока не равен содержимому main.
2. Ручной скрипт Argon по умолчанию OFFLINE, LIVE требует подтверждения. Не превращать его интерактивное подтверждение в слепое --yes-always на CI. Для удалённого запуска понадобится отдельный авторизационный протокол; пока его нет — LIVE Argon только вручную.
3. Известный маршрут Argon: https://api.kie.ai/gemini-4-argon-openai/v1/chat/completions (через KIE, chat-only). Модель, формат ответа, единицы кредитов и фактическое списание отдельно проверить одиночным запросом.
4. Рабочая локальная связка GPT-6 Sol + KIE Proxy v2 + localhost:8767 на Windows НЕ переносится автоматически в GitHub-hosted runner: localhost там другой компьютер. Нельзя публиковать порт 8767. Для облачного Aider требуется **отдельно подтверждённый доступный из runner API** и утверждённый способ хранения ключа; если такого доступа нет — cloud LIVE остаётся BLOCKED, тестируем MOCK или вручную на локальном компьютере.
5. В n8n Cloud нет Execute Command. Команды выполняет GitHub Actions runner, n8n только вызывает ограниченные API и отображает статусы.
6. Для repository_dispatch файл слушающего GitHub Actions workflow должен существовать в default branch. Сначала безопасный bootstrap через Draft PR с ручным approval/merge, затем внешнее событие. Наличие workflow только в экспериментальной ветке не подтверждает работоспособность dispatch.
7. Репозиторий публичный. Ни токены, ни конфиденциальный diff, ни сырые headers/ответы платных API, ни файлы из локального Character Vault не попадают в GitHub, Actions artifacts, PR, логи, n8n executions.
8. Соблюдать существующие AGENTS.md/CLAUDE.md и зоны ownership; не менять работающие ветки Codex/Claude/Argon, не делать git reset --hard / git clean / git add -A в рабочем Windows каталоге.

## 2. Принципиальная схема и распределение ролей

| Участник | Делает | Запрещено |
|---|---|---|
| Владелец | Даёт task ID, допускает LIVE и бюджет на конкретный SHA, решает merge | Автопринятие без проверки |
| n8n Cloud (новый Dev Orchestrator) | Принимает task_id из allowlist, ведёт state, готовит dispatch, опрашивает GitHub, выводит отчёт | Терминальные команды, хранение API-ключей в нодах/логе, пересоздание job по сетевой ошибке |
| GitHub Actions | Изолированно запускает проверенные скрипты и тесты, собирает метрики и артефакты | Прямое исполнение webhook-поля как shell-команды, запись в main |
| Aider/GPT | При разрешении предлагает изменения в sandbox-ветке в рамках allowlist | Неконтролируемая правка произвольных путей, автономные платные ретраи |
| Офлайн CI | Линтер, unit tests, проверка области файлов, secrets, diff, SHA | Любые внешние платные запросы |
| Argon/KIE | Только текстовый read-only аудит diff + задачи + итогов тестов | Git push, правка файлов, прямое approve/merge, повторные платные попытки |
| GitHub Draft PR | Хранит изменения кода, проверочные статусы и санитизированный отчёт | Публикация ключей, секретных данных, автоматический merge |

**Последовательность:** MANUAL_INPUT → VALIDATED → OFFLINE_READY → [OWNER_AUTHORIZE_CODER] → CODER_RUNNING → CI → DIFF_FROZEN → [OWNER_AUTHORIZE_REVIEWER] → ARGON_REVIEW → OWNER_DECISION. Ответ Argon исправление не инициирует; максимум одна новая редакция после отдельного подтверждения. Неизвестная сеть/платёж = HALTED_UNKNOWN, а не FAIL_CODE.

## 3. Релизные ворота (никого не обходить)

- **G0 — Документы:** согласованы контракт задачи, диапазон файлов, модель/route, схема затрат; только планы, ноль API.
- **G1 — Офлайн:** все негативные тесты и MOCK end-to-end зелёные, без секретов и сети.
- **G2 — Ручной LIVE reviewer:** один текстовый вызов Argon на зафиксированный diff после согласия, сравнение usage/credits.
- **G3 — Ручной LIVE coder:** одна ограниченная задача Aider с подтверждённым маршрутом модели и отдельным согласием; без n8n автозапуска.
- **G4 — GitHub Actions:** изолированный ручной workflow_dispatch (после попадания bootstrap-файла в main), репорт/PR без автослияния.
- **G5 — n8n Cloud:** отдельный неактивный workflow проходит MOCK с GitHub API; затем после approval dispatch включается для строго определённых task_id.
- **G6 — Controlled E2E:** один полный LIVE маршрут, не больше двух API-операций (coder + reviewer) на первой попытке. Любой повтор требует нового согласия; финальная рекомендация GO / CONDITIONAL / NO-GO.

G2 и G3 допускают перестановку после G1, но до G4/G5 нельзя заявлять, что интеграция полностью готова.

## 4. Пошаговые работы для Codex и участников

### P0-A. Снять слепок состояния без изменений
- [ ] Получить реальные SHA и статусы main, PR #22, issue #21, родственных PR #19/#17 и Actions; определить на какой базе PR #22 собран, нет ли конфликтов.
- [ ] На Windows: git remote -v, git status --short, git branch -vv, наличие незакоммиченных/untracked; ничего не чистить, не переписывать.
- [ ] Проверить tools/ai_review/argon_review.py, 5 тестов и запуск из изолированной временной копии; не утверждать LIVE по офлайн-результату.
- [ ] Проверить фактические доступные GitHub Actions права/лимиты, branch protection и действующие org policies. Не предполагать, что бесплатные минуты бесконечны.
- [ ] Выяснить, какой внешний API у GPT реально доступен из hosted runner. Отдельно проверить имя модели, edit format, поддержку caching, metering. **До подтверждения LIVE CODER = BLOCKED.**
- **Выход:** STATUS_BASELINE.md с SHA, окружением, несовпадениями и список BLOCKED вопросов.

### P0-B. Микрозадача для теста
- [ ] Создать отдельную ветку pilot/dev-001-<run_id> исключительно из зафиксированной base SHA, не переиспользовать общие ветки.
- [ ] **Task DEV-PILOT-001:** новый независимый Python-модуль pilot/budget_guard.py с функцией can_authorize(spent, estimate, cap), использующей Decimal и fail-closed входы; unit tests в tests/pilot/test_budget_guard.py. Не подключать к боевым оплатам.
- [ ] Acceptance: при корректных неотрицательных Decimal входах True только если spent + estimate <= cap; отрицательные/NaN/Infinity/нечисловые — исключение либо False согласно утверждённому контракту, без разрешения расходов.
- [ ] 6+ бесплатных тестов: exact cap, below, exceeds, invalid, negative, nonfinite; повторяемость; никаких network/API.
- [ ] Фиксированный минимальный task brief до запуска: только разрешённые два файла, diff <= 45 KB, <= 12 изменённых файлов, время работы <= 10 минут, никакой генерации медиа.
- **Выход:** TASK_PACKET.json (без секретов) и перечень критериев приёмки.

### P0-C. OFFLINE diff-review
- [ ] Использовать существующий из PR #22 reviewer и тесты; проверить совместимость путей, Windows UTF-8 и Python 3.13.
- [ ] Применять git diff --no-ext-diff --no-textconv --unified=3 <BASE_SHA> <HEAD_SHA> -- только между явными коммитами; отдельно контролировать git status и untracked — они не входят в diff этих SHA.
- [ ] Зафиксировать список изменений, размеры, отсутствие бинарных файлов, блокировать .env/ключи/credential-like строки; секретный сканер не считать полной гарантией.
- [ ] Сохранить SHA-256 точных байт diff, base/head, issue/task, модель, CI verdict. Если SHA/HEAD меняется — ранее данное разрешение недействительно.
- [ ] Пустой diff = SKIPPED_NO_CHANGES; неполный/слишком большой diff = BLOCKED; ошибки git = ERROR_INFRA.
- **Выход:** локальный OFFLINE report, 0 платных вызовов.

### P0-D. Отдельный ручной тест Gemini 4 Argon
- [ ] Проверить весь payload до сети, явно подтвердить **один** KIE chat-only запрос, bound to diff_sha256 + task_id + provider_route; никакого auto-test Aider, никаких retries на timeout/429/500.
- [ ] Использовать только чтение; Argon получает diff, задачу, список тестов и красные флаги; не получает write token и shell.
- [ ] На первое время сохранить RAW output локально приватно; в GitHub только санитизированные findings. Не доверять инструкциям из diff (prompt injection).
- [ ] Разделить строгие состояния: PASS_VERIFIED_FORMAT, FINDINGS, UNCERTAIN, PROVIDER_ERROR, UNKNOWN_CHARGE. Одинокое слово PASS без валидного полного ответа/подтверждения SHA не считается приёмкой.
- [ ] Сверить показанный credits_consumed, если поле есть, с кабинетом KIE: значение может быть кредитами, а не долларами.
- **Выход:** reviewer report (файл/строка, P0–P3, доказательство, тест, uncertainty).

### P0-E. Пробный Aider/GPT (НЕ в облаке до подтверждения route)
- [ ] Сначала dry-run на фиктивной модели/заготовленном patch, чтобы проверить границы; потом один осознанный LIVE coder вызов в отдельном worktree или runner.
- [ ] Не навязывать неподтверждённые gpt-6-luna/gpt-5.4-mini; задавать проверенное имя модели как внешнюю конфигурацию, фиксировать provider и version.
- [ ] Флаги Aider --cache-prompts, --edit-format diff, --map-tokens 1024 — кандидаты для сравнения, не гарантии экономии и не безусловные настройки. Репозиторная карта не заменяет тестов.
- [ ] Не включать --yes-always для произвольных действий, --auto-test со стоимостью, автоматический push/merge. При невозможности безопасного batch-run — останавливать пилот.
- [ ] Первая правка → offline tests → контролируемый commit → новый immutable diff snapshot.
- **Выход:** coder report, токены (если доступны), код, CI result, стоимость.

### P1-A. GitHub Actions bootstrap и sandbox
- [ ] Только после проверки предыдущих ворот отдельный Draft PR с минимальными файлами .github/workflows/dev-aider-pilot.yml и scripts/dev_pilot/*; ручной owner merge bootstrap в main. Этот этап требует изменения default branch, иначе repository_dispatch не сработает.
- [ ] Сначала workflow_dispatch с allowlisted task_id, mode=mock/offline по умолчанию; позже repository_dispatch с event_type=gremovod_dev_pilot. Содержимое workflow из main — только доверенный зафиксированный код; task payload — недоверенные данные.
- [ ] Jobs: validate → sandbox_prepare → optional_coder (secrets scoped) → offline_tests (без секретов, новый job/runner) → diff_snapshot → optional_review (read-only API) → sanitized_report → draft_PR.
- [ ] Настроить timeout-minutes, concurrency group task_id, cancel/duplicate handling; не позволять ручной rerun платных jobs без fresh approval.
- [ ] GitHub token с минимальными permissions (contents:write только job, реально создающему ветку/PR; pull-requests:write только при необходимости); секреты никогда не печатать.
- [ ] Для PR из untrusted code не применять pull_request_target с опасным checkout. Запускаемые тесты рассматривать как недоверенный код; отделять их от секретов/токенов.
- [ ] Проверять изменённые файлы по allowlist до commit/push; создавать PR только в экспериментальную базу, никогда не писать напрямую в main и не включать auto-merge.
- **Выход:** вручную запускаемый зелёный MOCK workflow, run URL, artifacts sanitized.

### P1-B. Новый n8n Dev Orchestrator (не существующие медиаворкфлоу)
- [ ] Создать отдельный workflow **GremoVOD Dev Pilot — OFFLINE FIRST**, **active=false** при создании; не менять 18 существующих workflows.
- [ ] Узлы: Manual Trigger / защищённый Webhook → Validate task_id / owner grant → Deduplicate run_id → preflight limits → GitHub HTTP dispatch → poll/check run → map statuses → sanitized notification / PR link. Никакой Execute Command.
- [ ] Ключ GitHub fine-grained минимальной области доступов хранить только в n8n Credentials; секреты провайдеров в n8n не нужны, если запросы выполняет Actions (или наоборот, закрепить один безопасный секретный контур, не дублировать ключи).
- [ ] По умолчанию имитировать responses без KIE/GPT. Внешние webhooks с auth, защищённые от повторов; без свободного текста, способного попасть в shell; не писать raw tokens/diff в execution data.
- [ ] Связывать n8n и GitHub по task_id, run_id, source commit SHA и immutable attempt_id; polling с ограниченным числом запросов и тайм-аутом; коллизии и двойной клик не создают второй coder/reviewer вызов.
- [ ] Никогда не маппить HTTP 429/timeout в «AI нашёл ошибку в коде». При неизвестном исходе платежа status=HALTED_UNKNOWN до ручной сверки.
- **Выход:** один завершённый бесплатный MOCK E2E с ссылками n8n execution ↔ Actions run ↔ PR.

### P1-C. Контролируемый live end-to-end
- [ ] Только если G0–G5 PASS, владелец подтверждает уникальный run_id, task, provider routes и стоимость **каждого** одиночного запроса.
- [ ] Ровно одна задача DEV-PILOT-001, одна попытка Aider и один Argon; без repair loop, без media API.
- [ ] Если Argon даёт FINDINGS, создать Issue/comment и остановиться. Исправление — новая вручную санкционированная попытка с новой SHA и новой оценкой стоимости (лимит дополнительно не более одной попытки).
- [ ] Результат отдавать в Draft PR: PASS/FAIL по CI отдельно от REVIEW, список файлов, тесты, стоимость и отметка owner decision.
- [ ] Merge в main только вручную после независимой проверки; для пилота достаточно закрытого/оставленного Draft PR — вливание тестового кода не требуется.
- **Выход:** журнал фактического LIVE запуска или явный BLOCKED_REASON без выдуманных результатов.

## 5. Структура минимальных контрактов

**Task packet (только пример формы, не текущий активный API):**

~~~json
{
  "schema_version": "dev-pilot/1",
  "task_id": "DEV-PILOT-001",
  "run_id": "immutable-unique-id",
  "mode": "offline",
  "base_sha": "<full git commit sha>",
  "allowed_paths": ["pilot/budget_guard.py", "tests/pilot/test_budget_guard.py"],
  "max_changed_files": 12,
  "max_diff_bytes": 45000,
  "max_coder_attempts": 1,
  "max_reviewer_attempts": 1,
  "estimated_max_usd": "1.00",
  "expires_at": "<UTC timestamp>",
  "owner_authorization_id": null
}
~~~

Запрещены произвольные shell, произвольные workflow names, автоматическое поднятие mode от offline к live через webhook, необработанный текст модели и изменения модели после подписи. Task packet хранится как immutable hash.

**Reviewer decision (обязательный нормализованный JSON после валидации; сырой KIE ответ сам по себе не удовлетворяет схеме):**

~~~json
{
  "schema_version": "dev-review/1",
  "task_id": "DEV-PILOT-001",
  "run_id": "<run id>",
  "base_sha": "<base sha>",
  "head_sha": "<head sha>",
  "diff_sha256": "<sha256>",
  "status": "PASS | FINDINGS | UNCERTAIN | PROVIDER_ERROR | UNKNOWN_CHARGE",
  "findings": [],
  "tests_status": "PASS | FAIL | NOT_RUN",
  "human_approved": false,
  "provider_reported_usage": null
}
~~~

Проверить schema_version/enum строго; LLM verdict не переписывает tests_status и human_approved. PASS не означает автоматического merge.

## 6. Протокол ограничений и бухгалтерия

**Начальный экспериментальный потолок:** целевой общий бюджет до **$1**, но $1 не является автоматическим жёстким лимитом расходов у провайдера. При отсутствии provider-side hard cap и достоверной предварительной оценки — запрещать live до ручного решения. Отдельно учитывать расходы KIE кредитами и приблизительный USD только при подтверждённом курсе. Не путать подписку ChatGPT, API, KIE, GitHub Actions и тариф n8n.

- До каждого платного запроса: approved_task, exact model/endpoint, amount_reserved, remaining_budget, unique authorization, immutable SHA, TTL, max input/output tokens, current ledger. Если цена неизвестна — блокировать.
- После: success + usage/token breakdown/credits + wall time; при ошибке после отправки POST не повторять, фиксировать UNKNOWN_CHARGE до сверки биллинга.
- Снять метрики: input/output/reasoning если показаны, cached tokens/read/write если доступны, retries, changed lines, CI time, review finding count, ручное время, фактический provider charge.
- Prompt caching считать только по provider usage, не по предположениям; с KIE-прокси экономия не подтверждена.
- Авто-ремонт в первой LIVE сессии выключен. В расширенном эксперименте максимум 1 дополнительная исправляющая итерация **после нового согласия**. Не использовать сетевой retry/continue как обход лимита.

**Таблица cost comparison:**
1. Aider через проверенный API route: provider billed cost + GitHub minutes + время и результат.
2. Codex по подписке на идентичной независимой задаче/зафиксированной base SHA: фиксировать фактические ограничения, время, правки и качество; не присваивать фиктивную цену токенов подписке.
3. Ручное инженерное решение: качество/стоимость/скорость/воспроизводимость/риски. «В 5–10 раз дешевле» — гипотеза, принимаем только измеренный результат.

## 7. Контрольные и негативные тесты (все бесплатно до G2/G3)

| ID | Испытание | Ожидаемый итог |
|---|---|---|
| T01 | valid task_id в offline mode | MOCK PASS; 0 KIE calls |
| T02 | неразрешённый task_id | BLOCKED до dispatch |
| T03 | повтор того же run_id | одно выполнение, нет доп. счёта |
| T04 | две параллельные заявки того же task_id | lock/idempotency, без второго coder |
| T05 | пустой git diff | SKIPPED_NO_CHANGES, reviewer не вызывается |
| T06 | изменённый head после разрешения | STALE_APPROVAL |
| T07 | перепутаны base/head, некорректная ссылка | ERROR_INFRA |
| T08 | untracked файл существует | не прятать, проверка status и явный отказ |
| T09 | .env/private key/API token в diff | BLOCKED_SECRET; не отправлять модели |
| T10 | бинарный PDF/PNG/SQLite или diff > 45 KB | BLOCKED_DIFF |
| T11 | выход за allowed_paths | BLOCKED_SCOPE, без push |
| T12 | prompt injection внутри diff/task | трактовать как данные, без команд |
| T13 | KIE 429 / 5xx / timeout | PROVIDER_ERROR либо UNKNOWN_CHARGE, без retry |
| T14 | KIE вернул неверный JSON/пустой content | UNCERTAIN, не PASS |
| T15 | reviewer вернул PASS, CI красный | общий результат FAIL |
| T16 | CI зелёный, reviewer нашёл P0 | BLOCKED_REVIEW |
| T17 | превышен зарезервированный бюджет/нет цены | BLOCKED_BUDGET |
| T18 | GitHub workflow не на default branch | ожидаемый bootstrap BLOCKED, не заявлять E2E |
| T19 | runner не видит localhost:8767 | BLOCKED_ROUTE, не открывать порт наружу |
| T20 | нет owner grant/истёк grant | STOP; нельзя запустить LIVE |
| T21 | нет прав push или pull-requests | ERROR_PERMISSIONS, без эскалации |
| T22 | n8n потерял ответ после dispatch | найти job по run_id; не повторять слепо |
| T23 | PR обновился после review SHA | STALE_REVIEW, блокировать merge |
| T24 | raw log пытается включить ключ/личные данные | redaction + fail/удалить артефакт до публикации |
| T25 | сравнение с Codex на той же задаче | фиксировать diff/tests/time; не считать разные задачи сравнимыми |

Проверки T01–T25 должны иметь зафиксированный список исполненных тестов и timestamps; не помечать как PASS, если тест только описан.

## 8. Отчёт и наблюдаемость

Каждое завершение даёт следующие артефакты (без секретов):
- **run-summary.md:** кто инициировал, task_id, mode, ссылка на n8n execution / Actions run / Draft PR, итог G0–G6.
- **code-change.md:** base/head SHA, changed files/lines, SHA-256 diff, allowed_paths, commit URL.
- **tests.json:** имена тестов, количества PASS/FAIL/SKIP, environment + Python/Node version, elapsed time.
- **review-summary.md:** provider, формат ответа, доказательные findings P0–P3, uncertainty, hash audited.
- **cost-ledger.json:** модель/тариф на дату, provider credits, usage, estimated/actual spend, unknown liabilities.
- **decision.md:** GO/CONDITIONAL/NO-GO и решение владельца; никакая модель не выставляет owner approval.

Ссылки собираются в одном Draft PR. n8n показывает метаданные и переходы состояний, а не все приватные payload.

## 9. Что поручить Codex, Argon и n8n (без пересечения правок)

**Codex — ответственный интегратор:** проверить существующий PR #22, стандартизировать task schema/state/budget & SHA gating, подготовить бесплатные тесты, отдельные bootstrap Actions и минимальный адаптер для n8n; не менять основной runtime или канон; все коммиты только в его новой экспериментальной ветке. До G1 никакого LIVE.

**Argon — независимый ревьюер:** сначала на единичном frozen diff после user approval, без Git credentials, без автоисправления; критичные находки с воспроизводимыми тестами, никакого косметического рефакторинга.

**n8n — оркестратор:** сначала отдельный inactive draft, mock dispatch + polling, idempotency и human approval; затем вручную запустить только разрешённую задачу. Не менять имеющиеся WF_00..WF_06, BETA-001 или production-пайплайны.

**Пользователь:** утверждает модель/route и бюджет; отдельно подтверждает каждый LIVE вызов и любое исправление; принимает решение об итоговом PR. Автоматические платные исправления, merge и публикация недопустимы.

## 10. Приёмка и стоп-условия

**GO:** G0–G6 действительно пройдены, T01–T24 закрыты (или явно документированы как ещё не пройденные с решением не расширять rollout), никаких секретов/производственных данных, расходы подтверждены, diff и reviewer согласованы по SHA, owner вручную принял результат. GO разрешает **следующий контролируемый пилот**, а не production auto-coding.

**CONDITIONAL:** офлайн интеграция доказана, но hosted GPT route недоступен или Argon LIVE не проверен. Оставить режим manual/mock, указать следующий конкретный тест.

**NO-GO:** есть утечка, необъяснимый платный повтор, обход grant, запись в main, исполняемый shell из user task, AUTO merge, потеря контроля версии или некорректное сопоставление SHA. Остановить и исправить в отдельной ветке, независимо от того, что показал Argon.

**Немедленно остановить при:** неожиданных списаниях, росте расходов без телеметрии, 429 после send, недоступном provider route, обнаруженном токене в output, изменении diff между approval и dispatch, попытке запуска из незнакомого webhook, красных CI tests или переходе MOCK → LIVE без отдельного решения.

## 11. Порядок внедрения (не путать план с фактом)

1. [ ] **Этап A / 0$**: audit #21/#22; слепок SHA, сравнение с main, ревью скрипта и офлайн тестов.
2. [ ] **Этап B / 0$**: 25 негативных сценариев, mock Aider patch, fake Argon responses, отчёт и ручной Draft PR.
3. [ ] **Этап C / LIVE только с согласием**: один реальный Argon review frozen diff и сверка credits.
4. [ ] **Этап D / LIVE только с согласием**: один реальный Aider GPT на безопасной задаче; при отсутствии cloud route — локально/STOP.
5. [ ] **Этап E / 0$**: создать и проверить Actions bootstrap, owner merge после ревью, затем проверенный workflow_dispatch → repository_dispatch.
6. [ ] **Этап F / 0$**: создать новый inactive n8n Dev Pilot, проверить mock dispatch/status/idempotency, не трогать текущие workflows.
7. [ ] **Этап G / LIVE только с согласием**: один E2E в изолированной ветке, Draft PR, actual costs, проверка владельцем.
8. [ ] **Этап H / 0$**: сравнить с Codex, решить: оставить manual, использовать n8n+Actions только для небольших задач или расширить.

## 12. Проверяемые справочники

- n8n Execute Command (self-hosted only): https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executecommand/
- GitHub repository_dispatch и требование default branch: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#repository_dispatch
- Aider options: https://aider.chat/docs/config/options.html
- Aider edit formats: https://aider.chat/docs/more/edit-formats.html
- OpenAI prompt caching: https://developers.openai.com/api/docs/guides/prompt-caching
- Существующий ручной прототип: https://github.com/gremoled77-droid/gremovod/pull/22

**Итоговый принцип:** сначала воспроизводимость и безопасность, потом одиночные платные проверки, потом orchestration. Никогда не платить за автоматический спор двух моделей и не выдавать MOCK за реальный успех.
