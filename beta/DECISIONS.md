# BETA — журнал решений и ограничений

## B-001 · Независимая песочница
**Решение:** ветка `experiment/beta-gateway-first-20261019` (от `main`); папка n8n `BETA Lab — experiments` в том же проекте. Новый репозиторий и новая SQLite **не создаются**. Основные WF_00–WF_06 не меняются.

## B-002 · Использовать внутренние n8n Gateway credits, а не API ключ Anthropic
**Подтверждено:** workflow [BETA-001](https://gremovod.app.n8n.cloud/workflow/cDmIlNKvFunUqNEm) использует нативную node `@n8n/n8n-nodes-langchain.googleGemini` и при создании автоматически получил **credential `Gateway credits`, source=`aiGateway`**. Существующие сохранённые Agents A6/A7 используют **`Anthropic account`, managed=false** и расходуют потенциально внешний аккаунт. Для внутреннего теста их не вызываем.

## B-003 · Резерв $1 и видимость баланса
**Граница:** сумма $5 является сообщением владельца, **не подтверждена live balance API**. Наш MCP connector умеет узнать eligibility Gateway, но не баланс. Авторитетное отображение: n8n Cloud Admin → Gateway credits (Balance/Spend). Остаток общий для инстанса. Поскольку нет trusted balance endpoint, **никакого автоматического снижения до $1** и auto-switch на Kie. Требуем вручную подтверждённый свежий остаток (до 10 мин) в workflow; preflight рекомендует запуск только при `balance >= $1.35` (1 reserve+0.10 text target + 0.25 buffer). Стоимость одного реального запроса по факту сверяем в Cloud и заносим в журнал. Это не абсолютный серверный лимит и не может защитить от других одновременно работающих workflows. Если для будущей беты нужен строгий стоп, Codex должен найти/проверить достоверный balance endpoint или сделать внешнюю ручную approval-per-request.

## B-004 · Сначала одиночный реальный A1-текст, потом медиа
**Модель:** `models/gemini-3-flash-preview`, максимум 256 output tokens, thinkingBudget=0, без встроенных поисковых инструментов. Workflow содержит одну Gemini Gateway node, ручной триггер, без авто-повтора и публикации. Ответ: два кандидатных логлайна, статус `CANDIDATES_NEED_HUMAN_REVIEW`. Канон и main не меняем.
Порядок проверки: text → image (после цены) → TTS (после цены и прав) → video 3–5 сек (после цены). Никаких больших дорогих петель A8 и эскалации.

## B-005 · Первый технический запуск
**n8n execution #46:** входовая защитная Code-нода **корректно заблокировала** реальный вызов с `BETA_PRE_FLIGHT_BLOCKED`; Gemini node НЕ выполнялась. `gateway_spent_in_execution=0` (отсутствовал вызов модели), текущий глобальный Gateway баланс **неизвестен**. Это тест безопасности, а не полученная AI-генерация.

## Передача Codex/Claude
Когда эксперимент KEEP, записать `prompt_revision`, `model/provider`, фактический результат и измеренную стоимость в `EXPERIMENT_LOG.md`. Лишь затем Codex решает перенос в production contracts, Claude внедряет код; экспериментальный workflow нельзя напрямую merge/activate в рабочем WF_00.
