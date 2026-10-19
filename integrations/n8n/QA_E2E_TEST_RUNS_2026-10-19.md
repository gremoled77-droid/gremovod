# GremoVOD — пошаговый QA E2E тест, 19 октября 2026

## Результаты, проверенные через n8n Cloud MCP

**Основной QA Orchestrator:** `nh3ARcl4XPW6RHqs` (manual draft, 7 узлов, ноль платных запросов)

- Выполнение **#23**, pin данных только на Manual Trigger.
- Отработали входной валидатор, A6/A7 mock-шлюзы, блокировка A8 и объединение вердиктов.
- Статус: `BLOCKED_TEXT_REVIEW_NOT_CONNECTED`.
- `text_precheck_passed=false`, `all_passed=false`, `final_release_approved=false`.
- Демонстрационная модель не выдала успешное *производственное* QA заключение без доверенного backend.

**Тестовая Gateway-ветка:** `2DllTVkrO6imk2IR`, URL:
https://gremovod.app.n8n.cloud/workflow/2DllTVkrO6imk2IR

- Manual-only draft, *не опубликован*.
- Два отдельных `Google Gemini 3 Flash Preview` node через **n8n-managed Gateway credits**; не личный Anthropic.
- **Не настоящие сохранённые n8n Agents A6/A7**, а role-specific isolated prompts, воспроизводящие их задачи.
- A8 (Opus уже заменён на Sonnet в самостоятельном черновике) не вызывается.
- Нет реальной авторизации source/canon и нет интеграции с loopback Windows FastAPI.

### Раунд 1 — синтетический сценарий с ошибками

Выполнение **#24**: `success`.

- A6 (REVIEW-REQ) `FAIL`: `кадр 1 — весь удлиненный лимузин виден`; нарушение задержанного раскрытия.
- A7 (REVIEW-SYSTEM) `FAIL`: `герой подъезжает на ярко-желтой машине`; синтетический (неproduction) lock задавал баклажановый цвет.
- Токены A6: вход 105, выход 77. A7: вход 121, выход 85.
- Всего: **388** входящих+исходящих токенов по метаданным n8n.
- Сборщик: `qa_transport_smoke_passed=true`, но `quality_claim=false`, `final_release_approved=false`, `source_is_approved=false`.

### Раунд 2 — исправленный синтетический сценарий

Выполнение **#25**: `success`.

Замороженный текст демо:
> Кадр 1: Грэм подходит к гаражу, автомобиль в кадре не виден. Кадр 2: Грэм едет в аэропорт, только крупный план его лица за рулём, кузов не показан. Кадр 3 (финал): камера впервые показывает целиком удлинённый лимузин баклажанового цвета; Грэм выходит встречать гостя.

- A6 `PASS` c exact-quote доказательством: `Кадр 3 (финал): камера впервые показывает целиком удлинённый лимузин баклажанового цвета`.
- A7 `PASS` c exact-quote: `камера впервые показывает целиком удлинённый лимузин баклажанового цвета`.
- Токены A6: вход 237, выход 63. A7: вход 235, выход 56.
- Всего: **591** токен по метаданным n8n.
- Сборщик: `qa_transport_smoke_passed=true`, `synthetic_reviewers_pass=true`, `review_status=SANDBOX_REVIEW_PASSED_NEEDS_OWNER`.
- **При этом** `source_is_approved=false`, `backend_evidence_verified=false`, `text_precheck_passed=false`, `final_release_approved=false`, `auto_publish=false`.

**Токены раундов #24 + #25 = 979** (не финансовый отчёт). Долларовую сумму списаний из n8n Gateway Credits по API исполнения не удалось получить; проверить в интерфейсе Billing/Gateway credits.

### Дополнительные бесплатные проверки

- В отдельной Gateway-ветке execution **#21**: pinned корректный текстовый FAIL у обоих критиков, агрегатор подтвердил синтетический транспорт.
- Execution **#22**: pinned вымышленная цитата A6, агрегатор отклонил как недостоверную (`qa_transport_smoke_passed=false`).

## Ограничения и следующий этап для Codex

**Это полный демонстрационный цикл QA-проверки текста в двух согласованных тестовых workflow, но НЕ одна объединённая исполняемая система Studio→n8n→Studio.** Создать новый десятишаговый E2E workflow в данном запуске не удалось: его создание было заблокировано, и новый workflow не создан. Не заявлять обратного.

Необходимо:
1. Ветка `feature/qa-text-audit-fixes-20261019` + draft PR #8: source snapshot current notes + Story Plan Card; прогнано 46 оффлайн-тестов.
2. Разработать защищённый **outbound Windows→n8n dispatch** с подписанными role packets, nonce, source revision и idempotency; локальный FastAPI должен оставаться loopback.
3. A6 и A7 должны получать отдельные, server-approved источники, а не demo/static text, и их ответы надо нормализовать в QA verdict schema backend; exact quote offsets проверяет trusted server.
4. A8 остаётся неактивным до реального media evidence и отдельного разрешения расходов.
5. Подготовить provider interface `TextReviewerProvider` для переключения `n8n_gateway` → `kie_api`, с подтверждёнными endpoints/model list, хранением credential в секретах и серверными бюджетными ограничениями.
6. Ни одна тестовая проверка не даёт права переписывать канон, считать media PASS, запускать платную генерацию изображений, публикацию или merge в main.
7. **Не выполнять реальных платных тестов без явного разрешения владельца.**

По состоянию на тест n8n-модель вызывается только через управляемый `Gateway credits`, а сохранённые A6/A7 draft Agents всё ещё привязаны к отдельному Anthropic credential; их не запускали.

### Ещё один бесплатный негативный тест

- Основной оркестратор execution **#26** — вход без одобренных требований и brief.
- Все узлы выполнились технически; итог **`BLOCKED_INVALID_INPUT`**, `input_errors=[approved_requirements,approved_brief]`, `quality_claim=false`, `final_release_approved=false`.
- Paid API: **0** в этом запуске.
