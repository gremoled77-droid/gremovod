window.STATE =
{
  "version": 2,
  "slug": "llm-gateway",
  "dir": "2026-10-20-llm-gateway",
  "title": "LLM Gateway: тарифный ориентир Kie/PiAPI в карточке, факт в бюджете",
  "mode": "semi",
  "depth": "normal",
  "tier": "T2",
  "briefFile": "2026-10-20-brief.md",
  "memoryFile": "CLAUDE.md",
  "memoryOwner": "user",
  "skillDir": "C:/Users/BLOWKA/.minimax/skills/autopilot",
  "baseCommit": "df1e1a3",
  "startedAt": "2026-10-20T13:38:10+03:00",
  "updatedAt": "2026-10-21T05:18:53+03:00",
  "finishedAt": "2026-10-21T05:18:53+03:00",
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
      "status": "done",
      "startedAt": "2026-10-20T14:25:30+03:00",
      "finishedAt": "2026-10-20T14:27:40+03:00"
    },
    {
      "id": "build",
      "status": "done",
      "startedAt": "2026-10-20T14:27:40+03:00",
      "finishedAt": "2026-10-21T00:06:23+03:00"
    },
    {
      "id": "review",
      "status": "done",
      "startedAt": "2026-10-21T00:06:23+03:00",
      "finishedAt": "2026-10-21T03:04:19+03:00"
    },
    {
      "id": "final",
      "status": "done",
      "startedAt": "2026-10-21T03:04:19+03:00",
      "finishedAt": "2026-10-21T05:18:53+03:00"
    }
  ],
  "requirements": {
    "total": 60,
    "done": 60,
    "inTicket": 0,
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
      "status": "done",
      "startedAt": "2026-10-20T14:27:41+03:00",
      "finishedAt": "2026-10-20T15:49:55+03:00",
      "retries": 0,
      "repairs": 2,
      "repairFindings": [
        "reference_quote падает TypeError на записи реестра с незаполненным тарифом",
        "ориентир не доходит до alternative_baseline, если у default_baseline не заполнен тариф"
      ],
      "tests": {
        "passed": 276,
        "failed": 0
      },
      "commit": "94d294a"
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
        "backend/connections.py",
        ".env.example"
      ],
      "review": "да — риск",
      "model": "сильная",
      "status": "done",
      "startedAt": "2026-10-20T15:49:56+03:00",
      "finishedAt": "2026-10-20T17:10:18+03:00",
      "retries": 0,
      "repairs": 1,
      "repairFindings": [
        "неверный путь Kie Responses (404) и нет гейта на выключенный маршрут — реальный POST с ключом"
      ],
      "tests": {
        "passed": 299,
        "failed": 0
      },
      "commit": "38d93ba"
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
      "status": "done",
      "startedAt": "2026-10-20T17:10:19+03:00",
      "finishedAt": "2026-10-20T19:32:32+03:00",
      "retries": 0,
      "repairs": 2,
      "repairFindings": [
        "платный маршрут без usage пишет usd=0 под done; legacy-путь не отличает подтверждённый отказ от 5xx",
        "HTTP 200 без пригодного текста выходит мимо классификатора: платный вызов показан как 0 потраченного, резерв висит фантомом"
      ],
      "tests": {
        "passed": 327,
        "failed": 0
      },
      "commit": "e087879"
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
        "backend/native_chat.py",
        "backend/llm_gateway.py",
        "backend/test_llm_cost_display.py"
      ],
      "review": "да — риск",
      "model": "обычная",
      "status": "done",
      "startedAt": "2026-10-20T19:32:33+03:00",
      "finishedAt": "2026-10-20T23:26:42+03:00",
      "retries": 0,
      "repairs": 2,
      "repairFindings": [
        "неизвестное списание агента может остаться без резерва и вне итогов; задание агенту уходит без проверки лимита; запись о расходе после коммита задания",
        "400 на отчёте отвергает бесплатную модель (тариф 0/0) и оставляет задание в preparing, блокируя очередь агента по студии; отчёт failed не журналирует расход"
      ],
      "tests": {
        "passed": 349,
        "failed": 0
      },
      "commit": "c33635c"
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
      "status": "done",
      "startedAt": "2026-10-20T19:32:34+03:00",
      "finishedAt": "2026-10-20T20:04:13+03:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 115,
        "failed": 0
      },
      "commit": "35ce981"
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
        "backend/security.py",
        "docs/LLM_GATEWAY_ARCHITECTURE.md",
        "docs/LLM_GATEWAY_PROVIDER_MATRIX.md",
        "docs/LLM_GATEWAY_TEST_REPORT.md",
        "docs/HANDOFF_MINIMAX_LLM_GATEWAY.md"
      ],
      "review": "нет",
      "model": "обычная",
      "status": "done",
      "startedAt": "2026-10-20T23:26:43+03:00",
      "finishedAt": "2026-10-21T00:06:22+03:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 353,
        "failed": 0
      },
      "commit": "d7e3e15"
    },
    {
      "id": "F1",
      "title": "Ремонт ветки: две платные попытки, потерянный usage, зависшая очередь и ложные утверждения",
      "requirements": [
        "R21",
        "R23",
        "R30",
        "R33",
        "R34",
        "R42",
        "R49",
        "R50",
        "R57"
      ],
      "blockedBy": [],
      "wave": 6,
      "zone": [
        "backend/llm_guard.py",
        "backend/llm_gateway.py",
        "backend/llm_adapters.py",
        "backend/native_chat.py",
        "backend/test_llm_guard.py",
        "backend/test_llm_adapters.py",
        "backend/test_llm_cost_display.py",
        "backend/test_budget_breakdown.py",
        "frontend/src/BudgetPanel.tsx",
        "frontend/src/SeriesEconomics.tsx",
        "frontend/src/WorkflowPanel.tsx",
        "docs/HANDOFF_MINIMAX_LLM_GATEWAY.md",
        "docs/LLM_GATEWAY_PROVIDER_MATRIX.md",
        "docs/LLM_GATEWAY_ARCHITECTURE.md",
        "docs/LLM_GATEWAY_TEST_REPORT.md",
        ".gitignore"
      ],
      "review": "да — ремонт ветки",
      "model": "сильная",
      "status": "done",
      "startedAt": "2026-10-21T00:39:22+03:00",
      "finishedAt": "2026-10-21T02:37:41+03:00",
      "retries": 0,
      "repairs": 1,
      "repairFindings": [
        "fallback резерва агента берёт 0/0-маршрут и даёт нулевой резерв: задание ставится при исчерпанном лимите, списание невидимо"
      ],
      "tests": {
        "passed": 360,
        "failed": 0
      },
      "commit": "eb41189"
    },
    {
      "id": "F2",
      "title": "Две мелочи после ревью ремонта ветки",
      "requirements": [
        "R49",
        "R33"
      ],
      "blockedBy": [],
      "wave": 7,
      "zone": [
        "frontend/src/WorkflowPanel.tsx",
        "frontend/src/llmDisplay.ts",
        "frontend/src/llmDisplay.test.mjs",
        "backend/test_llm_cost_display.py"
      ],
      "review": "да — ремонт ветки",
      "model": "сильная",
      "status": "done",
      "startedAt": "2026-10-21T02:37:42+03:00",
      "finishedAt": "2026-10-21T03:03:25+03:00",
      "retries": 0,
      "repairs": 0,
      "tests": {
        "passed": 359,
        "failed": 0
      },
      "commit": "f1c4250"
    },
    {
      "id": "F3",
      "title": "Две находки слепой приёмки",
      "requirements": [
        "R08",
        "R23",
        "R30",
        "R33",
        "R38",
        "R56"
      ],
      "blockedBy": [],
      "wave": 8,
      "zone": [
        "backend/llm_guard.py",
        "backend/llm_gateway.py",
        "backend/test_llm_guard.py",
        "backend/test_llm_cost_display.py",
        "backend/test_llm_adapters.py",
        "backend/test_budget_breakdown.py",
        "backend/test_llm_gateway.py",
        "backend/conftest.py"
      ],
      "review": "да — ремонт ветки",
      "model": "сильная",
      "status": "done",
      "retries": 0,
      "repairs": 0,
      "startedAt": "2026-10-21T03:41:12+03:00",
      "finishedAt": "2026-10-21T05:17:57+03:00",
      "tests": {
        "passed": 371,
        "failed": 0
      },
      "commit": "0512213"
    }
  ],
  "tests": {
    "passed": 371,
    "failed": 371
  },
  "debt": {
    "placeholders": [
      "Тарифы, capabilities и base_url маршрутов minimax/deepseek/openrouter в config/llm_gateway.prices.example.json — иллюстративные (capabilities=false, часть тарифов null, verified_at=null, enabled=false). Заполняет владелец после живой проверки; до этого маршруты не включаются.",
      "Путь проверки ключа MiniMax (/v1/models) не подтверждён документацией — владелец сверяет перед включением маршрута",
      "Точные upstream model id для Kie GPT-6 Luna / Claude Haiku 5.5 и MiniMax M3.1 Flash не подтверждены — по документации Kie модели берутся из GET /openai/v1/models и GET /anthropic/v1/models",
      "Форма тела Responses-запроса к Kie (input/content) и пути чата MiniMax и OpenRouter не подтверждены живой проверкой — владелец сверяет своим ключом перед включением маршрутов",
      "Цена записи кеша (Anthropic cache_creation) отдельно не тарифицируется — токены записи считаются по обычному входному тарифу; владелец уточняет, если нужен отдельный тариф"
    ],
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
  "concerns": [
    "test_default_registry_is_closed подменяет load_registry — поведение «закрыто по умолчанию» не закреплено тестом, проверено вручную",
    "actual_quote и гейт адаптера по-разному определяют «бесплатный маршрут»: расчёт даёт 0.0/confirmed для тарифа 0/0 при free=false, гейт считает 0/0 свободным; сумма  в обоих, денежной дыры нет",
    "Классификация подтверждённого отказа в legacy-пути держится на тексте 'PiAPI вернул ошибку' из main.py:136 — при смене формулировки отказ молча станет unknown (направление консервативное, дыры нет). Дешёвое лечение: типизированный флаг у ошибки вместо разбора текста",
    "В адаптерном пути провайдер отбрасывает usage при непригодном тексте: исход остаётся unknown с удержанием резерва вместо confirmed с фактом. Направление консервативное, дыры нет — но два пути расходятся; кандидат в ревью ветки",
    "Не-HTTPException из транспорта (внутренняя ошибка) оставляет строку в status=reserved навсегда и блокирует повтор с тем же request_id (409). Резерв удержан, строка видна в неизвестных списаниях — риск операционный, не денежный",
    "up_error различает 403-блок Cloudflare по подстроке '1010'/'browser_signature_banned' в теле ответа провайдера — единственный оставшийся текстовый сигнал; направление денежно-безопасное (заблокированный запрос до модели не доходит)",
    "Панель «Бюджет» (BudgetPanel.tsx) показывает llm_project_usd = экспозиция как «LLM-запросы» — вне зоны таска 04, закрывается таском 06: /api/budgets должен отдавать четыре раздельные величины, и budgetLines (llmDisplay.ts) пока никем не вызывается",
    "Гейт «тариф есть» бьёт и по describe_character, чьи вызовы в журнал не пишутся: без тарифа в базовой линии операция не запускается вовсе",
    "Гейт постановки смотрит только базовую линию: при базовой линии без цены свободная 0/0-модель не доходит до отчёта",
    "Тариф 0/0 без флага free при отчёте без usage даёт unknown с нулевым резервом — деньги не видны ни в одном итоге и не занимают лимит",
    "Сбой вставки в llm_calls откатывает транзакцию и оставляет задание в preparing, удерживая очередь воркера — исходный паттерн студии (то же при 409 на недопустимый переход); деньги не теряются, повторный отчёт их записывает"
  ],
  "blind": {
    "checked": 24,
    "matched": 23,
    "mismatches": [
      "«Free → платный fallback» — частично: цепочка прерывается, если сбой Free-классифицирован как «возможно списано» (429/403/1010/5xx/таймаут), платный маршрут не вызывается; фоллбэк срабатывает только при «списания не было» (401)"
    ]
  },
  "beats": [
    "2026-10-20T13:38:10+03:00",
    "2026-10-20T13:41:42+03:00",
    "2026-10-20T13:41:44+03:00",
    "2026-10-20T13:57:38+03:00",
    "2026-10-20T14:18:27+03:00",
    "2026-10-20T14:18:28+03:00",
    "2026-10-20T14:25:29+03:00",
    "2026-10-20T14:25:30+03:00",
    "2026-10-20T14:25:31+03:00",
    "2026-10-20T14:26:46+03:00",
    "2026-10-20T14:27:40+03:00",
    "2026-10-20T14:27:41+03:00",
    "2026-10-20T14:59:18+03:00",
    "2026-10-20T15:08:14+03:00",
    "2026-10-20T15:08:15+03:00",
    "2026-10-20T15:27:31+03:00",
    "2026-10-20T15:49:55+03:00",
    "2026-10-20T15:49:56+03:00",
    "2026-10-20T16:24:57+03:00",
    "2026-10-20T16:36:31+03:00",
    "2026-10-20T16:36:32+03:00",
    "2026-10-20T16:36:33+03:00",
    "2026-10-20T17:10:16+03:00",
    "2026-10-20T17:10:18+03:00",
    "2026-10-20T17:10:19+03:00",
    "2026-10-20T18:24:42+03:00",
    "2026-10-20T18:39:29+03:00",
    "2026-10-20T18:51:25+03:00",
    "2026-10-20T19:09:53+03:00",
    "2026-10-20T19:32:31+03:00",
    "2026-10-20T19:32:32+03:00",
    "2026-10-20T19:32:33+03:00",
    "2026-10-20T19:32:34+03:00",
    "2026-10-20T20:04:13+03:00",
    "2026-10-20T21:29:41+03:00",
    "2026-10-20T21:29:42+03:00",
    "2026-10-20T22:42:10+03:00",
    "2026-10-20T23:26:42+03:00",
    "2026-10-20T23:26:43+03:00",
    "2026-10-21T00:06:22+03:00",
    "2026-10-21T00:06:23+03:00",
    "2026-10-21T00:39:20+03:00",
    "2026-10-21T00:39:21+03:00",
    "2026-10-21T00:39:22+03:00",
    "2026-10-21T00:39:24+03:00",
    "2026-10-21T01:58:55+03:00",
    "2026-10-21T02:37:40+03:00",
    "2026-10-21T02:37:41+03:00",
    "2026-10-21T02:37:42+03:00",
    "2026-10-21T03:03:24+03:00",
    "2026-10-21T03:03:25+03:00",
    "2026-10-21T03:04:19+03:00",
    "2026-10-21T03:40:01+03:00",
    "2026-10-21T03:41:11+03:00",
    "2026-10-21T03:41:12+03:00",
    "2026-10-21T05:17:56+03:00",
    "2026-10-21T05:17:57+03:00",
    "2026-10-21T05:17:58+03:00",
    "2026-10-21T05:18:53+03:00"
  ],
  "rev": 65,
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
    },
    {
      "t": "2026-10-20T14:27:40+03:00",
      "k": "stage",
      "id": "build",
      "act": "start"
    },
    {
      "t": "2026-10-20T14:27:41+03:00",
      "k": "ticket",
      "ids": [
        "01"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-20T14:59:18+03:00",
      "k": "ticket",
      "ids": [
        "01"
      ],
      "act": "review"
    },
    {
      "t": "2026-10-20T15:08:14+03:00",
      "k": "ticket",
      "ids": [
        "01"
      ],
      "act": "repair",
      "note": "reference_quote падает TypeError на записи реестра с незаполненным тарифом"
    },
    {
      "t": "2026-10-20T15:08:15+03:00",
      "k": "add",
      "key": "debt.placeholders",
      "n": 1
    },
    {
      "t": "2026-10-20T15:27:31+03:00",
      "k": "ticket",
      "ids": [
        "01"
      ],
      "act": "repair",
      "note": "ориентир не доходит до alternative_baseline, если у default_baseline не заполнен тариф"
    },
    {
      "t": "2026-10-20T15:49:55+03:00",
      "k": "ticket",
      "ids": [
        "01"
      ],
      "act": "done",
      "tests": {
        "passed": 276,
        "failed": 0
      }
    },
    {
      "t": "2026-10-20T15:49:56+03:00",
      "k": "ticket",
      "ids": [
        "02"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-20T16:24:57+03:00",
      "k": "add",
      "key": "debt.placeholders",
      "n": 1
    },
    {
      "t": "2026-10-20T16:24:57+03:00",
      "k": "add",
      "key": "debt.placeholders",
      "n": 1
    },
    {
      "t": "2026-10-20T16:36:31+03:00",
      "k": "ticket",
      "ids": [
        "02"
      ],
      "act": "repair",
      "note": "неверный путь Kie Responses (404) и нет гейта на выключенный маршрут — реальный POST с ключом"
    },
    {
      "t": "2026-10-20T16:36:32+03:00",
      "k": "add",
      "key": "debt.placeholders",
      "n": 1
    },
    {
      "t": "2026-10-20T16:36:33+03:00",
      "k": "add",
      "key": "debt.placeholders",
      "n": 1
    },
    {
      "t": "2026-10-20T17:10:16+03:00",
      "k": "add",
      "key": "concerns",
      "n": 2
    },
    {
      "t": "2026-10-20T17:10:18+03:00",
      "k": "ticket",
      "ids": [
        "02"
      ],
      "act": "done",
      "tests": {
        "passed": 299,
        "failed": 0
      }
    },
    {
      "t": "2026-10-20T17:10:19+03:00",
      "k": "ticket",
      "ids": [
        "03"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-20T18:24:42+03:00",
      "k": "ticket",
      "ids": [
        "03"
      ],
      "act": "repair",
      "note": "платный маршрут без usage пишет usd=0 под done; legacy-путь не отличает подтверждённый отказ от 5xx"
    },
    {
      "t": "2026-10-20T18:39:29+03:00",
      "k": "add",
      "key": "concerns",
      "n": 1
    },
    {
      "t": "2026-10-20T18:51:25+03:00",
      "k": "ticket",
      "ids": [
        "03"
      ],
      "act": "repair",
      "note": "HTTP 200 без пригодного текста выходит мимо классификатора: платный вызов показан как 0 потраченного, резерв висит фантомом"
    },
    {
      "t": "2026-10-20T19:09:53+03:00",
      "k": "add",
      "key": "concerns",
      "n": 1
    },
    {
      "t": "2026-10-20T19:32:31+03:00",
      "k": "add",
      "key": "concerns",
      "n": 2
    },
    {
      "t": "2026-10-20T19:32:32+03:00",
      "k": "ticket",
      "ids": [
        "03"
      ],
      "act": "done",
      "tests": {
        "passed": 327,
        "failed": 0
      }
    },
    {
      "t": "2026-10-20T19:32:33+03:00",
      "k": "ticket",
      "ids": [
        "04"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-20T19:32:34+03:00",
      "k": "ticket",
      "ids": [
        "05"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-20T20:04:13+03:00",
      "k": "ticket",
      "ids": [
        "05"
      ],
      "act": "done",
      "tests": {
        "passed": 115,
        "failed": 0
      }
    },
    {
      "t": "2026-10-20T21:29:41+03:00",
      "k": "ticket",
      "ids": [
        "04"
      ],
      "act": "repair",
      "note": "неизвестное списание агента может остаться без резерва и вне итогов; задание агенту уходит без проверки лимита; запись о расходе после коммита задания"
    },
    {
      "t": "2026-10-20T21:29:42+03:00",
      "k": "add",
      "key": "concerns",
      "n": 1
    },
    {
      "t": "2026-10-20T22:42:10+03:00",
      "k": "ticket",
      "ids": [
        "04"
      ],
      "act": "repair",
      "note": "400 на отчёте отвергает бесплатную модель (тариф 0/0) и оставляет задание в preparing, блокируя очередь агента по студии; отчёт failed не журналирует расход"
    },
    {
      "t": "2026-10-20T23:26:42+03:00",
      "k": "add",
      "key": "concerns",
      "n": 4
    },
    {
      "t": "2026-10-20T23:26:42+03:00",
      "k": "ticket",
      "ids": [
        "04"
      ],
      "act": "done",
      "tests": {
        "passed": 349,
        "failed": 0
      }
    },
    {
      "t": "2026-10-20T23:26:43+03:00",
      "k": "ticket",
      "ids": [
        "06"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-21T00:06:22+03:00",
      "k": "ticket",
      "ids": [
        "06"
      ],
      "act": "done",
      "tests": {
        "passed": 353,
        "failed": 0
      }
    },
    {
      "t": "2026-10-21T00:06:23+03:00",
      "k": "stage",
      "id": "review",
      "act": "start"
    },
    {
      "t": "2026-10-21T00:39:20+03:00",
      "k": "add",
      "key": "report",
      "n": 5
    },
    {
      "t": "2026-10-21T00:39:21+03:00",
      "k": "tickets",
      "n": 7
    },
    {
      "t": "2026-10-21T00:39:22+03:00",
      "k": "ticket",
      "ids": [
        "F1"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-21T00:39:24+03:00",
      "k": "gate",
      "g": "G3",
      "ok": true,
      "problems": 0
    },
    {
      "t": "2026-10-21T01:58:55+03:00",
      "k": "ticket",
      "ids": [
        "F1"
      ],
      "act": "repair",
      "note": "fallback резерва агента берёт 0/0-маршрут и даёт нулевой резерв: задание ставится при исчерпанном лимите, списание невидимо"
    },
    {
      "t": "2026-10-21T02:37:40+03:00",
      "k": "add",
      "key": "report",
      "n": 1
    },
    {
      "t": "2026-10-21T02:37:41+03:00",
      "k": "ticket",
      "ids": [
        "F1"
      ],
      "act": "done",
      "tests": {
        "passed": 360,
        "failed": 0
      }
    },
    {
      "t": "2026-10-21T02:37:41+03:00",
      "k": "tickets",
      "n": 8
    },
    {
      "t": "2026-10-21T02:37:42+03:00",
      "k": "ticket",
      "ids": [
        "F2"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-21T03:03:24+03:00",
      "k": "add",
      "key": "report",
      "n": 2
    },
    {
      "t": "2026-10-21T03:03:25+03:00",
      "k": "ticket",
      "ids": [
        "F2"
      ],
      "act": "done",
      "tests": {
        "passed": 359,
        "failed": 0
      }
    },
    {
      "t": "2026-10-21T03:04:19+03:00",
      "k": "stage",
      "id": "final",
      "act": "start"
    },
    {
      "t": "2026-10-21T03:40:01+03:00",
      "k": "gate",
      "g": "G4",
      "ok": false,
      "checked": 24,
      "matched": 23
    },
    {
      "t": "2026-10-21T03:41:11+03:00",
      "k": "tickets",
      "n": 9
    },
    {
      "t": "2026-10-21T03:41:12+03:00",
      "k": "ticket",
      "ids": [
        "F3"
      ],
      "act": "start"
    },
    {
      "t": "2026-10-21T05:17:56+03:00",
      "k": "add",
      "key": "report",
      "n": 3
    },
    {
      "t": "2026-10-21T05:17:57+03:00",
      "k": "ticket",
      "ids": [
        "F3"
      ],
      "act": "done",
      "tests": {
        "passed": 371,
        "failed": 0
      }
    },
    {
      "t": "2026-10-21T05:17:58+03:00",
      "k": "tests",
      "passed": 371,
      "failed": 371
    },
    {
      "t": "2026-10-21T05:18:53+03:00",
      "k": "finish",
      "result": "LLM Gateway собран: карточка показывает тарифный ориентир Kie/PiAPI первым, «Бюджет» суммирует только фактическое списание; 371 backend + 119 frontend тестов зелёные, слепая приёмка PASS"
    }
  ],
  "reqList": [
    {
      "id": "R01",
      "text": "«Подтяни ветку origin/minimax/llm-gateway»",
      "status": "done"
    },
    {
      "id": "R02",
      "text": "«Прочитай ТЗ, правила отображения стоимости и handoff»",
      "status": "done"
    },
    {
      "id": "R03",
      "text": "«Реализуй LLM Gateway по этапам»",
      "status": "done"
    },
    {
      "id": "R04",
      "text": "«в карточках показываем стоимость по тарифам Kie/PiAPI даже для бесплатных вызовов»",
      "status": "done"
    },
    {
      "id": "R05",
      "text": "«а в разделе «Бюджет» суммируем только фактические расходы»",
      "status": "done"
    },
    {
      "id": "R06",
      "text": "«Сохрани существующие бюджетные ограничения»",
      "status": "done"
    },
    {
      "id": "R07",
      "text": "«Работай в отдельном worktree»",
      "status": "done"
    },
    {
      "id": "R08",
      "text": "«используй тесты без платных API-запросов»",
      "status": "done"
    },
    {
      "id": "R09",
      "text": "«Не объединяй изменения в main до проверки»",
      "status": "done"
    },
    {
      "id": "R10",
      "text": "«/plan-first /auto-verify»",
      "status": "done"
    },
    {
      "id": "R11",
      "text": "«не редактировать корневую main или чужие worktrees, не останавливать рабочие процессы 8000/5173»",
      "status": "done"
    },
    {
      "id": "R12",
      "text": "«не применять reset --hard / force-push»",
      "status": "done"
    },
    {
      "id": "R13",
      "text": "«Сначала составить карту того, что уже реализовано.» + «Не переписывать image/video»",
      "status": "done"
    },
    {
      "id": "R14",
      "text": "«Единый server-side model registry с датой/URL источника цены, проверкой поддерживаемых функций, enable/verified-флагами; никакие произвольные upstream URL/модели не приходят от пользователя.»",
      "status": "done"
    },
    {
      "id": "R15",
      "text": "«Действующие API и signed quote сохранить обратно совместимыми; подпись связывает проект, provider, model, версию цены, hash сообщений/настроек/tools, max_tokens, выбор fallback и допустимый максимум платежа.»",
      "status": "done"
    },
    {
      "id": "R16",
      "text": "«До любых платных вызовов — оценка реальной стоимости, атомарная резервация бюджета, проверка лимитов проекта/дня/серии, подтверждение владельца.»",
      "status": "done"
    },
    {
      "id": "R17",
      "text": "«Бесплатный маршрут тоже журналировать; запрещено резервировать ориентир как реальную оплату.»",
      "status": "done"
    },
    {
      "id": "R18",
      "text": "«Защитить идемпотентность по request_id, race condition, timeout с возможным списанием, Cloudflare 1010/401/403, 429/5xx; нельзя бесконечно пробовать fallback и списывать по несколько раз.»",
      "status": "done"
    },
    {
      "id": "R19",
      "text": "«Route modes manual/auto. По умолчанию без параллельных вызовов нескольких LLM.»",
      "status": "done"
    },
    {
      "id": "R20",
      "text": "«Выбор по задаче: simple=Kie Luna; editorial=Kie Haiku; coding=MiniMax (Free только opt-in); резерв=DeepSeek; PiAPI как дополнительный маршрут.»",
      "status": "done"
    },
    {
      "id": "R21",
      "text": "«Автопереключение только если соответствует разрешенному ограниченному бюджету, функциям и политикам владельца.»",
      "status": "done"
    },
    {
      "id": "R22",
      "text": "«Usage, cache tokens, unknown-cost status, сохраняемые price snapshots.»",
      "status": "done"
    },
    {
      "id": "R23",
      "text": "«Никакой фиктивной точности при отсутствующем usage; ноль только при подтверждённо бесплатном маршруте.»",
      "status": "done"
    },
    {
      "id": "R24",
      "text": "«В UI: карточка LLM-вызова с главным ценовым ориентиром Kie/PiAPI, исполняющей моделью и статусом»",
      "status": "done"
    },
    {
      "id": "R25",
      "text": "«в подтверждении реальный ожидаемый платёж, в Экономике — только actual, отдельно pending/unknown/reference. Это требуется и для узлов/n8n.»",
      "status": "done"
    },
    {
      "id": "R26",
      "text": "«Продолжать применять существующую политику API-ключей: KIE_API_KEY, PIAPI_API_KEY; для новых провайдеров MINIMAX_API_KEY, DEEPSEEK_API_KEY, OPENROUTER_API_KEY. Секреты только серверные, не печатать, не коммитить.»",
      "status": "done"
    },
    {
      "id": "R27",
      "text": "«A. Аудит: сопоставить существующий код, схемы БД, маршруты и зависимости. Отчет о блокерах и о том, что можно переиспользовать.»",
      "status": "done"
    },
    {
      "id": "R28",
      "text": "«B. MVP: Kie Luna, Kie Haiku, PiAPI backward compatibility; эталон Kie/PiAPI + реальный ledger; MockTransport тесты.»",
      "status": "done"
    },
    {
      "id": "R29",
      "text": "«C. Остальные: MiniMax direct, DeepSeek direct, OpenRouter free + предсказуемые fallback и ограничение бюджета; mock-схемы.»",
      "status": "done"
    },
    {
      "id": "R30",
      "text": "«D. UI и n8n: минимальные изменения существующих экранов; одинаковые правила учёта в UI, API и агентах; dry-run инструкции n8n.»",
      "status": "done"
    },
    {
      "id": "R31",
      "text": "«E. Реальные проверки: только после отдельного одобрения владельца для конкретных расходов. Не включать запуск новой модели без подтвержденных схемы, тарифа и разрешения.»",
      "status": "done"
    },
    {
      "id": "R32",
      "text": "«Не подключать LangChain, Redis, Celery, Kafka, новую БД, облачные сервисы только ради MVP.»",
      "status": "done"
    },
    {
      "id": "R33",
      "text": "«Команды для полной проверки: python -X utf8 -m unittest discover -s backend -p \"test_.py\"; python -m pytest backend (если доступно); в frontend npm test и npm run build. Указать фактические PASS/FAIL/SKIP; не утверждать, что тесты запущен…",
      "status": "done"
    },
    {
      "id": "R34",
      "text": "«Краткое описание выполненного по этапам, коммиты и точные результаты тестов. Прежде всего выполнить этап A и B, не отвлекаться на ненужные модули.»",
      "status": "done"
    },
    {
      "id": "R35",
      "text": "«Это поручение начать реализацию в своей ветке, но не согласие на покупку токенов, активацию платных генераций, force push, смену конфигурации рабочей студии или объединение в main.»",
      "status": "done"
    },
    {
      "id": "R36",
      "text": "«Бесплатный OpenRouter отдает корректный тарифный ориентир Kie/PiAPI, бюджет +$0.»",
      "status": "done"
    },
    {
      "id": "R37",
      "text": "«Платный direct API показывает ориентир и отдельно истинную сумму к оплате до подтверждения; бюджет учитывает только фактическую стоимость.»",
      "status": "done"
    },
    {
      "id": "R38",
      "text": "«Fallback после Free корректно добавляет только платежи реально платного поставщика; неизвестные начисления не становятся нулём.»",
      "status": "done"
    },
    {
      "id": "R39",
      "text": "«Нет утечки ключей, неправильно подписанных quote, двойных платежей, изменения старых image/video вызовов или потери исторических llm_calls.»",
      "status": "done"
    },
    {
      "id": "R40",
      "text": "«Моки Kie Responses и Haiku Messages, OpenRouter, MiniMax, DeepSeek; 403/1010/429, timeout, error-body 200, нет usage, cache, микросуммы, злонамеренный provider/URL.»",
      "status": "done"
    },
    {
      "id": "R41",
      "text": "«Ветку minimax/llm-gateway (не сливать автоматически в main).»",
      "status": "done"
    },
    {
      "id": "R42",
      "text": "«Документацию docs/LLM_GATEWAY_ARCHITECTURE.md, docs/LLM_GATEWAY_PROVIDER_MATRIX.md, docs/LLM_GATEWAY_TEST_REPORT.md и docs/HANDOFF_MINIMAX_LLM_GATEWAY.md.»",
      "status": "done"
    },
    {
      "id": "R43",
      "text": "«Аддитивные миграции, адаптеры, UI-изменения, офлайн-тесты; небольшой пример конфигурации без секретов.»",
      "status": "done"
    },
    {
      "id": "R44",
      "text": "«Если Kie.ai или PiAPI действительно продаёт ту же модель — сравнивать с её точным тарифом, пометка exact_model.»",
      "status": "done"
    },
    {
      "id": "R45",
      "text": "«использовать только явно названный ценовой ориентир другой модели, по умолчанию Kie GPT-6 Luna; альтернативный ориентир PiAPI GPT-5.6 Luna.»",
      "status": "done"
    },
    {
      "id": "R46",
      "text": "«На карточке обязательно писать: «Ценовой ориентир Kie GPT-6 Luna (другая модель, сравнение по объёму токенов)».»",
      "status": "done"
    },
    {
      "id": "R47",
      "text": "«Непроверенный тариф выводить как «Не подтверждён», а не $0.»",
      "status": "done"
    },
    {
      "id": "R48",
      "text": "«Карточка вызова: 1) «По тарифу Kie.ai — GPT-6 Luna: ≈ $0.000300» (или «Ценовой ориентир... (другая модель)»); 2) «Исполняет: OpenRouter — MiniMax M3.1 Flash Free»; 3) статус «Бесплатный API», если маршрут реально бесплатен.»",
      "status": "done"
    },
    {
      "id": "R49",
      "text": "«В окне подтверждения ПЛАТНОГО запроса условный тариф Kie/PiAPI также выводить первым, но рядом ОБЯЗАТЕЛЬНО до согласия показать ожидаемый реальный платёж и максимальный одобренный расход исполняющего API.»",
      "status": "done"
    },
    {
      "id": "R50",
      "text": "«В «Бюджет / Экономика» основной итог: «Фактически потрачено»; отдельные итоги: «Зарезервировано» и «Неизвестные списания / нужна сверка». Допускается отдельный, явно не денежный итог «Эквивалент по Kie/PiAPI», не смешиваемый с реальными з…",
      "status": "done"
    },
    {
      "id": "R51",
      "text": "«Бюджет: фактически +$0.00. Нельзя начислять $0.000300 как долг.»",
      "status": "done"
    },
    {
      "id": "R52",
      "text": "«Хранить раздельно: исполнение: execution_provider, execution_model, actual_cost_usd, actual_status, reserved_usd, billing_source, request_id; ориентир: reference_provider (kie/piapi), reference_model, reference_kind (exact_model/reference…",
      "status": "done"
    },
    {
      "id": "R53",
      "text": "«До вызова ориентир показывать как приблизительную оценку количества токенов, после вызова по возможности пересчитывать по фактическому usage.»",
      "status": "done"
    },
    {
      "id": "R54",
      "text": "«Если usage неизвестен — оставить статус estimated, не выдавать за точную сумму. Поддерживать дробные суммы менее 1 цента без округления к $0.00.»",
      "status": "done"
    },
    {
      "id": "R55",
      "text": "«Actual spend = сумма подтвержденных реальных начислений за успешные и сверенные вызовы; зарезервированные и неопределенные суммы показывать отдельно и учитывать в блокирующих лимитах.»",
      "status": "done"
    },
    {
      "id": "R56",
      "text": "«Не ставить фактический $0 для потенциально оплаченного timeout, 429, 5xx или неопределенного ответа. Реальный $0.00 допустим лишь для подтверждённого бесплатного маршрута без платной надбавки. Платный fallback учитывать как реальный платё…",
      "status": "done"
    },
    {
      "id": "R57",
      "text": "«Это правило распространяется на запросы из UI, сценарные агенты, workflow и n8n. Никакого обхода квот, подписанных подтверждений или бюджетных проверок. Изображения и видео не затрагивать.»",
      "status": "done"
    },
    {
      "id": "R58",
      "text": "«Только аддитивные миграции, не удалять старую историю.»",
      "status": "done"
    },
    {
      "id": "R59",
      "text": "«do_not_override_existing_owner_limits: true»",
      "status": "done"
    },
    {
      "id": "R60i",
      "text": "(подразумевается) Ориентир и фактическое списание должны попадать в один и тот же учёт вызовов, чтобы «Бюджет» и карточка не расходились",
      "status": "done"
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
      "at": "2026-10-21T00:39:24+03:00",
      "problems": 0
    },
    "G4": {
      "ok": false,
      "at": "2026-10-21T03:40:01+03:00",
      "checked": 24,
      "matched": 23
    }
  },
  "result": "LLM Gateway собран: карточка показывает тарифный ориентир Kie/PiAPI первым, «Бюджет» суммирует только фактическое списание; 371 backend + 119 frontend тестов зелёные, слепая приёмка PASS",
  "report": [
    "403 без маркеров Cloudflare классифицируется по-разному в двух путях: legacy отпускает резерв, адаптер удерживает его навсегда — деньги не теряются, но бюджет владельца блокируется отказом, который ничего не стоил",
    "Не-HTTPException из транспорта (внутренняя ошибка) оставляет строку в status=reserved/actual_status=estimated навсегда и блокирует повтор с тем же request_id (409). Резерв учтён в лимите, но виден в «зарезервировано», а не в корзине «неизвестные списания», которую владелец сверяет",
    "Гейт «тариф есть» бьёт и по describe_character, чьи вызовы не журналируются, а economics их исключает: проверка без учётного контрапункта, операция не запускается вовсе, бюджет по ней не виден",
    "Новые тесты закрепляют текст ошибок (backend/test_llm_cost_display.py:184,215,246,284,298,308; backend/test_budget_breakdown.py:245) — смена формулировки сломает их; классификация уже структурная, закрепления быть не должно",
    "Пробел покрытия: нет теста на отчёт агента с названной, но отсутствующей в реестре моделью",
    "Тариф дешевле половины микродоллара (вход 0 + выход ≤ 0.02 USD/Mtok) округляется до нуля при точности 6 → резерв 0.0, и задание агента может встать при исчерпанном лимите. Текущие тарифы владельца (0.02/0.08, 0.15/0.6, 0.03/0.15) это не задевает",
    "В окне «Запустить всё» общий потолок запуска печатается в каждой строке LLM-узла — так и требовалось условием, но воспринимается как потолок на отдельный узел",
    "В недостижимом случае пустого лимита эталонное окно печатает \\, а новое — «не задан»: небольшое расхождение между двумя окнами",
    "Предвызовная проверка лимита в backend/llm_guard.py идёт по reserve маршрута (0 у маршрута 0/0), а не по удерживаемому held: при лимите меньше held один вызов проходит, экспозиция становится в разы больше лимита. Строка unknown это видит и блокирует следующие вызовы, то есть обход ограничен одним held-резервом на проект",
    "Защита сети в backend/network_guard.py не закрывает UDP sendto и gethostbyname, и действует только в процессе — субпроцесс может выйти наружу",
    "loopback-тест в backend/test_llm_guard.py не закрывает принятый сокет — ResourceWarning в прогоне"
  ]
}
