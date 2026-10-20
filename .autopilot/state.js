window.STATE =
{
  "version": 2,
  "slug": "llm-gateway",
  "dir": "2026-10-20-llm-gateway--wip",
  "title": "LLM Gateway: тарифный ориентир Kie/PiAPI в карточке, факт в бюджете",
  "mode": "semi",
  "depth": "normal",
  "tier": "T2",
  "briefFile": "2026-10-20-brief.md",
  "memoryFile": "CLAUDE.md",
  "memoryOwner": "user",
  "skillDir": "C:/Users/BLOWKA/.minimax/skills/autopilot",
  "baseCommit": null,
  "startedAt": "2026-10-20T13:38:10+03:00",
  "updatedAt": "2026-10-20T14:25:31+03:00",
  "finishedAt": null,
  "stages": [
    {
      "id": "preflight",
      "status": "done",
      "startedAt": "2026-10-20T13:38:10+03:00",
      "finishedAt": "2026-10-20T13:41:44+03:00"
    },
    {
      "id": "manifest",
      "status": "done",
      "startedAt": "2026-10-20T13:41:44+03:00",
      "finishedAt": "2026-10-20T13:57:38+03:00"
    },
    {
      "id": "briefing",
      "status": "done",
      "startedAt": "2026-10-20T13:57:38+03:00",
      "finishedAt": "2026-10-20T14:18:28+03:00"
    },
    {
      "id": "spec",
      "status": "done",
      "startedAt": "2026-10-20T14:18:28+03:00",
      "finishedAt": "2026-10-20T14:25:30+03:00"
    },
    {
      "id": "plan",
      "status": "active",
      "startedAt": "2026-10-20T14:25:30+03:00"
    },
    {
      "id": "build",
      "status": "pending"
    },
    {
      "id": "review",
      "status": "pending"
    },
    {
      "id": "final",
      "status": "pending"
    }
  ],
  "requirements": {
    "total": 60,
    "done": 0,
    "inTicket": 60,
    "inSpec": 0,
    "placeholder": 0,
    "deferred": 0,
    "dropped": 0
  },
  "tickets": [
    {
      "id": "01",
      "title": "Ядро шлюза: реестр, тарифный ориентир и фактическое списание",
      "requirements": [
        "R01",
        "R02",
        "R04",
        "R05",
        "R13",
        "R14",
        "R19",
        "R21",
        "R22",
        "R23",
        "R27",
        "R44",
        "R45",
        "R46",
        "R47",
        "R51",
        "R52",
        "R53",
        "R54",
        "R60i"
      ],
      "blockedBy": [],
      "wave": 1,
      "zone": [
        "backend/llm_gateway.py",
        "backend/test_llm_gateway.py",
        "config/llm_gateway.prices.example.json",
        ".gitignore"
      ],
      "review": "да — фундамент",
      "model": "сильная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "02",
      "title": "Адаптеры провайдеров и ключи",
      "requirements": [
        "R08",
        "R14",
        "R18",
        "R20",
        "R26",
        "R40"
      ],
      "blockedBy": [
        "01"
      ],
      "wave": 2,
      "zone": [
        "backend/llm_adapters.py",
        "backend/test_llm_adapters.py",
        "backend/connections.py"
      ],
      "review": "да — риск",
      "model": "сильная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "03",
      "title": "Журнал, подпись и защита денег",
      "requirements": [
        "R06",
        "R15",
        "R16",
        "R17",
        "R18",
        "R21",
        "R28",
        "R39",
        "R52",
        "R53",
        "R56",
        "R58"
      ],
      "blockedBy": [
        "01",
        "02"
      ],
      "wave": 3,
      "zone": [
        "backend/llm_guard.py",
        "backend/security.py",
        "backend/main.py",
        "backend/test_llm_guard.py",
        "backend/test_llm_quote.py"
      ],
      "review": "да — риск",
      "model": "сильная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "04",
      "title": "Бюджет и экономика: четыре раздельных итога",
      "requirements": [
        "R05",
        "R05.1",
        "R38",
        "R50",
        "R55",
        "R56",
        "R59"
      ],
      "blockedBy": [
        "03"
      ],
      "wave": 4,
      "zone": [
        "backend/economics.py",
        "backend/series_economics.py",
        "backend/test_llm_cost_display.py"
      ],
      "review": "да — риск",
      "model": "обычная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "05",
      "title": "Карточка LLM-вызова в интерфейсе",
      "requirements": [
        "R24",
        "R25",
        "R48",
        "R49",
        "R57"
      ],
      "blockedBy": [
        "03"
      ],
      "wave": 4,
      "zone": [
        "frontend/src/llmDisplay.ts",
        "frontend/src/llmDisplay.test.mjs",
        "frontend/src/LlmCostCard.tsx",
        "frontend/src/LlmApprovalDialog.tsx",
        "frontend/src/llmAsk.ts",
        "frontend/src/IdeaBrief.tsx",
        "frontend/src/WorldFromBrief.tsx",
        "frontend/src/WorkflowPanel.tsx",
        "frontend/src/OutlineDialog.tsx"
      ],
      "review": "нет",
      "model": "обычная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    },
    {
      "id": "06",
      "title": "Бюджет в интерфейсе, документация и отчёт о тестах",
      "requirements": [
        "R03",
        "R07",
        "R09",
        "R10",
        "R11",
        "R12",
        "R29",
        "R30",
        "R31",
        "R32",
        "R33",
        "R34",
        "R35",
        "R36",
        "R37",
        "R41",
        "R42",
        "R43",
        "R50",
        "R51",
        "R52",
        "R56",
        "R59"
      ],
      "blockedBy": [
        "04",
        "05"
      ],
      "wave": 5,
      "zone": [
        "frontend/src/Dock.tsx",
        "frontend/src/EconomicsPanel.tsx",
        "frontend/src/BudgetPanel.tsx",
        "frontend/src/SeriesEconomics.tsx",
        "docs/LLM_GATEWAY_ARCHITECTURE.md",
        "docs/LLM_GATEWAY_PROVIDER_MATRIX.md",
        "docs/LLM_GATEWAY_TEST_REPORT.md",
        "docs/HANDOFF_MINIMAX_LLM_GATEWAY.md"
      ],
      "review": "нет",
      "model": "обычная",
      "status": "pending",
      "retries": 0,
      "repairs": 0
    }
  ],
  "tests": null,
  "debt": {
    "placeholders": [],
    "assumptions": [],
    "emptyEnv": []
  },
  "additions": [],
  "coverage": {
    "found": 10,
    "fixed": 10,
    "deferred": 0,
    "items": []
  },
  "concerns": [],
  "blind": null,
  "beats": [
    "2026-10-20T13:38:10+03:00",
    "2026-10-20T13:41:42+03:00",
    "2026-10-20T13:41:44+03:00",
    "2026-10-20T13:57:38+03:00",
    "2026-10-20T14:18:27+03:00",
    "2026-10-20T14:18:28+03:00",
    "2026-10-20T14:25:29+03:00",
    "2026-10-20T14:25:30+03:00",
    "2026-10-20T14:25:31+03:00"
  ],
  "rev": 12,
  "waiting": null,
  "waits": [
    {
      "kind": "briefing",
      "from": "2026-10-20T13:57:38+03:00",
      "to": "2026-10-20T14:18:27+03:00"
    }
  ],
  "log": [
    {
      "t": "2026-10-20T13:38:10+03:00",
      "k": "init"
    },
    {
      "t": "2026-10-20T13:41:44+03:00",
      "k": "stage",
      "id": "manifest",
      "act": "start"
    },
    {
      "t": "2026-10-20T13:57:38+03:00",
      "k": "stage",
      "id": "briefing",
      "act": "start"
    },
    {
      "t": "2026-10-20T13:57:38+03:00",
      "k": "ask",
      "kind": "briefing",
      "note": "четыре вопроса: объём этапов, включение маршрутов, старая история LLM, место карточки"
    },
    {
      "t": "2026-10-20T14:18:27+03:00",
      "k": "answered",
      "kind": "briefing"
    },
    {
      "t": "2026-10-20T14:18:27+03:00",
      "k": "gate",
      "g": "G2",
      "ok": true,
      "found": 10,
      "fixed": 10,
      "deferred": 0
    },
    {
      "t": "2026-10-20T14:18:28+03:00",
      "k": "gate",
      "g": "G1",
      "ok": true,
      "open": 0,
      "total": 60
    },
    {
      "t": "2026-10-20T14:18:28+03:00",
      "k": "stage",
      "id": "spec",
      "act": "start"
    },
    {
      "t": "2026-10-20T14:25:29+03:00",
      "k": "tier",
      "v": "T2"
    },
    {
      "t": "2026-10-20T14:25:30+03:00",
      "k": "stage",
      "id": "plan",
      "act": "start"
    },
    {
      "t": "2026-10-20T14:25:31+03:00",
      "k": "tickets",
      "n": 6
    },
    {
      "t": "2026-10-20T14:25:31+03:00",
      "k": "gate",
      "g": "G3",
      "ok": true,
      "problems": 0
    }
  ],
  "reqList": [
    {
      "id": "R01",
      "text": "«Подтяни ветку origin/minimax/llm-gateway»",
      "status": "in-ticket"
    },
    {
      "id": "R02",
      "text": "«Прочитай ТЗ, правила отображения стоимости и handoff»",
      "status": "in-ticket"
    },
    {
      "id": "R03",
      "text": "«Реализуй LLM Gateway по этапам»",
      "status": "in-ticket"
    },
    {
      "id": "R04",
      "text": "«в карточках показываем стоимость по тарифам Kie/PiAPI даже для бесплатных вызовов»",
      "status": "in-ticket"
    },
    {
      "id": "R05",
      "text": "«а в разделе «Бюджет» суммируем только фактические расходы»",
      "status": "in-ticket"
    },
    {
      "id": "R06",
      "text": "«Сохрани существующие бюджетные ограничения»",
      "status": "in-ticket"
    },
    {
      "id": "R07",
      "text": "«Работай в отдельном worktree»",
      "status": "in-ticket"
    },
    {
      "id": "R08",
      "text": "«используй тесты без платных API-запросов»",
      "status": "in-ticket"
    },
    {
      "id": "R09",
      "text": "«Не объединяй изменения в main до проверки»",
      "status": "in-ticket"
    },
    {
      "id": "R10",
      "text": "«/plan-first /auto-verify»",
      "status": "in-ticket"
    },
    {
      "id": "R11",
      "text": "«не редактировать корневую main или чужие worktrees, не останавливать рабочие процессы 8000/5173»",
      "status": "in-ticket"
    },
    {
      "id": "R12",
      "text": "«не применять reset --hard / force-push»",
      "status": "in-ticket"
    },
    {
      "id": "R13",
      "text": "«Сначала составить карту того, что уже реализовано.» + «Не переписывать image/video»",
      "status": "in-ticket"
    },
    {
      "id": "R14",
      "text": "«Единый server-side model registry с датой/URL источника цены, проверкой поддерживаемых функций, enable/verified-флагами; никакие произвольные upstream URL/модели не приходят от пользователя.»",
      "status": "in-ticket"
    },
    {
      "id": "R15",
      "text": "«Действующие API и signed quote сохранить обратно совместимыми; подпись связывает проект, provider, model, версию цены, hash сообщений/настроек/tools, max_tokens, выбор fallback и допустимый максимум платежа.»",
      "status": "in-ticket"
    },
    {
      "id": "R16",
      "text": "«До любых платных вызовов — оценка реальной стоимости, атомарная резервация бюджета, проверка лимитов проекта/дня/серии, подтверждение владельца.»",
      "status": "in-ticket"
    },
    {
      "id": "R17",
      "text": "«Бесплатный маршрут тоже журналировать; запрещено резервировать ориентир как реальную оплату.»",
      "status": "in-ticket"
    },
    {
      "id": "R18",
      "text": "«Защитить идемпотентность по request_id, race condition, timeout с возможным списанием, Cloudflare 1010/401/403, 429/5xx; нельзя бесконечно пробовать fallback и списывать по несколько раз.»",
      "status": "in-ticket"
    },
    {
      "id": "R19",
      "text": "«Route modes manual/auto. По умолчанию без параллельных вызовов нескольких LLM.»",
      "status": "in-ticket"
    },
    {
      "id": "R20",
      "text": "«Выбор по задаче: simple=Kie Luna; editorial=Kie Haiku; coding=MiniMax (Free только opt-in); резерв=DeepSeek; PiAPI как дополнительный маршрут.»",
      "status": "in-ticket"
    },
    {
      "id": "R21",
      "text": "«Автопереключение только если соответствует разрешенному ограниченному бюджету, функциям и политикам владельца.»",
      "status": "in-ticket"
    },
    {
      "id": "R22",
      "text": "«Usage, cache tokens, unknown-cost status, сохраняемые price snapshots.»",
      "status": "in-ticket"
    },
    {
      "id": "R23",
      "text": "«Никакой фиктивной точности при отсутствующем usage; ноль только при подтверждённо бесплатном маршруте.»",
      "status": "in-ticket"
    },
    {
      "id": "R24",
      "text": "«В UI: карточка LLM-вызова с главным ценовым ориентиром Kie/PiAPI, исполняющей моделью и статусом»",
      "status": "in-ticket"
    },
    {
      "id": "R25",
      "text": "«в подтверждении реальный ожидаемый платёж, в Экономике — только actual, отдельно pending/unknown/reference. Это требуется и для узлов/n8n.»",
      "status": "in-ticket"
    },
    {
      "id": "R26",
      "text": "«Продолжать применять существующую политику API-ключей: KIE_API_KEY, PIAPI_API_KEY; для новых провайдеров MINIMAX_API_KEY, DEEPSEEK_API_KEY, OPENROUTER_API_KEY. Секреты только серверные, не печатать, не коммитить.»",
      "status": "in-ticket"
    },
    {
      "id": "R27",
      "text": "«A. Аудит: сопоставить существующий код, схемы БД, маршруты и зависимости. Отчет о блокерах и о том, что можно переиспользовать.»",
      "status": "in-ticket"
    },
    {
      "id": "R28",
      "text": "«B. MVP: Kie Luna, Kie Haiku, PiAPI backward compatibility; эталон Kie/PiAPI + реальный ledger; MockTransport тесты.»",
      "status": "in-ticket"
    },
    {
      "id": "R29",
      "text": "«C. Остальные: MiniMax direct, DeepSeek direct, OpenRouter free + предсказуемые fallback и ограничение бюджета; mock-схемы.»",
      "status": "in-ticket"
    },
    {
      "id": "R30",
      "text": "«D. UI и n8n: минимальные изменения существующих экранов; одинаковые правила учёта в UI, API и агентах; dry-run инструкции n8n.»",
      "status": "in-ticket"
    },
    {
      "id": "R31",
      "text": "«E. Реальные проверки: только после отдельного одобрения владельца для конкретных расходов. Не включать запуск новой модели без подтвержденных схемы, тарифа и разрешения.»",
      "status": "in-ticket"
    },
    {
      "id": "R32",
      "text": "«Не подключать LangChain, Redis, Celery, Kafka, новую БД, облачные сервисы только ради MVP.»",
      "status": "in-ticket"
    },
    {
      "id": "R33",
      "text": "«Команды для полной проверки: python -X utf8 -m unittest discover -s backend -p \"test_.py\"; python -m pytest backend (если доступно); в frontend npm test и npm run build. Указать фактические PASS/FAIL/SKIP; не утверждать, что тесты запущен…",
      "status": "in-ticket"
    },
    {
      "id": "R34",
      "text": "«Краткое описание выполненного по этапам, коммиты и точные результаты тестов. Прежде всего выполнить этап A и B, не отвлекаться на ненужные модули.»",
      "status": "in-ticket"
    },
    {
      "id": "R35",
      "text": "«Это поручение начать реализацию в своей ветке, но не согласие на покупку токенов, активацию платных генераций, force push, смену конфигурации рабочей студии или объединение в main.»",
      "status": "in-ticket"
    },
    {
      "id": "R36",
      "text": "«Бесплатный OpenRouter отдает корректный тарифный ориентир Kie/PiAPI, бюджет +$0.»",
      "status": "in-ticket"
    },
    {
      "id": "R37",
      "text": "«Платный direct API показывает ориентир и отдельно истинную сумму к оплате до подтверждения; бюджет учитывает только фактическую стоимость.»",
      "status": "in-ticket"
    },
    {
      "id": "R38",
      "text": "«Fallback после Free корректно добавляет только платежи реально платного поставщика; неизвестные начисления не становятся нулём.»",
      "status": "in-ticket"
    },
    {
      "id": "R39",
      "text": "«Нет утечки ключей, неправильно подписанных quote, двойных платежей, изменения старых image/video вызовов или потери исторических llm_calls.»",
      "status": "in-ticket"
    },
    {
      "id": "R40",
      "text": "«Моки Kie Responses и Haiku Messages, OpenRouter, MiniMax, DeepSeek; 403/1010/429, timeout, error-body 200, нет usage, cache, микросуммы, злонамеренный provider/URL.»",
      "status": "in-ticket"
    },
    {
      "id": "R41",
      "text": "«Ветку minimax/llm-gateway (не сливать автоматически в main).»",
      "status": "in-ticket"
    },
    {
      "id": "R42",
      "text": "«Документацию docs/LLM_GATEWAY_ARCHITECTURE.md, docs/LLM_GATEWAY_PROVIDER_MATRIX.md, docs/LLM_GATEWAY_TEST_REPORT.md и docs/HANDOFF_MINIMAX_LLM_GATEWAY.md.»",
      "status": "in-ticket"
    },
    {
      "id": "R43",
      "text": "«Аддитивные миграции, адаптеры, UI-изменения, офлайн-тесты; небольшой пример конфигурации без секретов.»",
      "status": "in-ticket"
    },
    {
      "id": "R44",
      "text": "«Если Kie.ai или PiAPI действительно продаёт ту же модель — сравнивать с её точным тарифом, пометка exact_model.»",
      "status": "in-ticket"
    },
    {
      "id": "R45",
      "text": "«использовать только явно названный ценовой ориентир другой модели, по умолчанию Kie GPT-6 Luna; альтернативный ориентир PiAPI GPT-5.6 Luna.»",
      "status": "in-ticket"
    },
    {
      "id": "R46",
      "text": "«На карточке обязательно писать: «Ценовой ориентир Kie GPT-6 Luna (другая модель, сравнение по объёму токенов)».»",
      "status": "in-ticket"
    },
    {
      "id": "R47",
      "text": "«Непроверенный тариф выводить как «Не подтверждён», а не $0.»",
      "status": "in-ticket"
    },
    {
      "id": "R48",
      "text": "«Карточка вызова: 1) «По тарифу Kie.ai — GPT-6 Luna: ≈ $0.000300» (или «Ценовой ориентир... (другая модель)»); 2) «Исполняет: OpenRouter — MiniMax M3.1 Flash Free»; 3) статус «Бесплатный API», если маршрут реально бесплатен.»",
      "status": "in-ticket"
    },
    {
      "id": "R49",
      "text": "«В окне подтверждения ПЛАТНОГО запроса условный тариф Kie/PiAPI также выводить первым, но рядом ОБЯЗАТЕЛЬНО до согласия показать ожидаемый реальный платёж и максимальный одобренный расход исполняющего API.»",
      "status": "in-ticket"
    },
    {
      "id": "R50",
      "text": "«В «Бюджет / Экономика» основной итог: «Фактически потрачено»; отдельные итоги: «Зарезервировано» и «Неизвестные списания / нужна сверка». Допускается отдельный, явно не денежный итог «Эквивалент по Kie/PiAPI», не смешиваемый с реальными з…",
      "status": "in-ticket"
    },
    {
      "id": "R51",
      "text": "«Бюджет: фактически +$0.00. Нельзя начислять $0.000300 как долг.»",
      "status": "in-ticket"
    },
    {
      "id": "R52",
      "text": "«Хранить раздельно: исполнение: execution_provider, execution_model, actual_cost_usd, actual_status, reserved_usd, billing_source, request_id; ориентир: reference_provider (kie/piapi), reference_model, reference_kind (exact_model/reference…",
      "status": "in-ticket"
    },
    {
      "id": "R53",
      "text": "«До вызова ориентир показывать как приблизительную оценку количества токенов, после вызова по возможности пересчитывать по фактическому usage.»",
      "status": "in-ticket"
    },
    {
      "id": "R54",
      "text": "«Если usage неизвестен — оставить статус estimated, не выдавать за точную сумму. Поддерживать дробные суммы менее 1 цента без округления к $0.00.»",
      "status": "in-ticket"
    },
    {
      "id": "R55",
      "text": "«Actual spend = сумма подтвержденных реальных начислений за успешные и сверенные вызовы; зарезервированные и неопределенные суммы показывать отдельно и учитывать в блокирующих лимитах.»",
      "status": "in-ticket"
    },
    {
      "id": "R56",
      "text": "«Не ставить фактический $0 для потенциально оплаченного timeout, 429, 5xx или неопределенного ответа. Реальный $0.00 допустим лишь для подтверждённого бесплатного маршрута без платной надбавки. Платный fallback учитывать как реальный платё…",
      "status": "in-ticket"
    },
    {
      "id": "R57",
      "text": "«Это правило распространяется на запросы из UI, сценарные агенты, workflow и n8n. Никакого обхода квот, подписанных подтверждений или бюджетных проверок. Изображения и видео не затрагивать.»",
      "status": "in-ticket"
    },
    {
      "id": "R58",
      "text": "«Только аддитивные миграции, не удалять старую историю.»",
      "status": "in-ticket"
    },
    {
      "id": "R59",
      "text": "«do_not_override_existing_owner_limits: true»",
      "status": "in-ticket"
    },
    {
      "id": "R60i",
      "text": "(подразумевается) Ориентир и фактическое списание должны попадать в один и тот же учёт вызовов, чтобы «Бюджет» и карточка не расходились",
      "status": "in-ticket"
    }
  ],
  "gates": {
    "G2": {
      "ok": true,
      "at": "2026-10-20T14:18:27+03:00",
      "found": 10,
      "fixed": 10,
      "deferred": 0
    },
    "G1": {
      "ok": true,
      "at": "2026-10-20T14:18:28+03:00",
      "open": 0,
      "total": 60
    },
    "G3": {
      "ok": true,
      "at": "2026-10-20T14:25:31+03:00",
      "problems": 0
    }
  },
  "result": null
}
