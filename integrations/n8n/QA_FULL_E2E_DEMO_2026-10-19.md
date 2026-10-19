# GremoVOD — полный сквозной QA-тест от входа до ручного gate
Дата: 19.10.2026

## Реально созданная и запущенная система

n8n project: `jG7gkyrK2hH0rEBj`
Workflow: `2DllTVkrO6imk2IR`
Editor: https://gremovod.app.n8n.cloud/workflow/2DllTVkrO6imk2IR
Status: **manual draft, not published, not scheduled**.

**Один полный исполняемый путь из 8 узлов:**

1. Manual Trigger (ручной запуск).
2. `01 · Входное задание` — синтетический тестовый brief в Code-узле.
3. `02 · A1 создаёт тестовый текст` — **реальный** Gemini 3 Flash Preview через n8n Gateway credits.
4. `03 · Фиксация текста и задания` — проверка формата, замораживание единого текста, подготовка отдельных role packets.
5. `A6 Requirements reviewer — Gateway test` — **реальный** независимый Gemini reviewer R1/R2/R3.
6. `A7 Canon reviewer — Gateway test` — **реальный** независимый Gemini reviewer C1.
7. `Сбор результатов — без автоапрува` — индивидуальные цитаты проверяются в замороженном тексте с привязкой к сцене/кадру, проверяются суммы verdict, проверяется наличие движения в аэропорт во втором кадре.
8. `04 · Только ручная приёмка` — всегда `final_release_approved=false`, `production_write_permitted=false`.

3 визуальные группы: вход/сценарист, независимые критики, проверка/приёмка. A8 выключен.

**Важно:** это настоящая единая исполняемая QA **демонстрация на синтетическом входе**, а НЕ полная продукционная интеграция local FastAPI → n8n → local FastAPI. Текст поступает из входного демо-Code-узла, **не** из утверждённых документов Studio. Настоящие сохранённые черновые n8n Agents A1/A6/A7 не вызываются: их роли выполняют изолированные Gemini prompt nodes. Нельзя считать тестовые канон и модельный PASS утверждёнными.

## Последний полный платный запуск: execution #33

Status: **success**. 3 реальные Gemini Gateway модели, без других API/платных инструментов.

**Задание (демо):** Грэм едет в аэропорт на ВАЗ-2106, скрывая удлинение до последнего кадра. Отдельный синтетический цветовой lock — баклажановый.

**Фактически созданный A1 текст:**

> Кадр 1: Крупный план Грэма, сосредоточенно смотрящего на дорогу сквозь лобовое стекло классического ВАЗ-2106. Кадр 2: Вид из салона через плечо водителя; Грэм проезжает под массивным дорожным указателем с надписью «АЭРОПОРТ», кузов автомобиля в кадре обрезан передними дверями. Кадр 3 (финал): Камера резко отлетает назад, демонстрируя невероятно длинный лимузин на базе ВАЗ-2106 баклажанового цвета, который плавно сворачивает к терминалу.

A6: R1/R2/R3 **PASS** с отдельными дословными quote receipts, подтверждающими отложенное раскрытие, направление к аэропорту и финальный reveal.

A7: C1 **PASS** на синтетическом цветовом правиле, цитата `баклажанового цвета`.

A6 вернул в `source_scope` эхо полного точного сценария вместо строки `TEXT`. Валидатор допускает **только** этот особый случай эха текущего замороженного текста (иначе BLOCKED), фиксирует предупреждение `MODEL_ECHOED_TEXT_IN_SCOPE_FIELD_NORMALIZED_TO_TRUSTED_TEXT` и выводит доверенный sandbox scope=TEXT. Любое заявление IMAGE/VIDEO/AUDIO остаётся недостоверным.

Aggregate:
- `review_status=SANDBOX_REVIEW_PASSED_NEEDS_OWNER`
- `synthetic_reviewers_pass=true`
- `qa_transport_smoke_passed=true`
- `final_release_approved=false`
- `production_text_precheck_passed=false`
- `source_is_approved=false`
- `backend_evidence_verified=false`
- `quality_claim=false`
- `auto_publish=false`.

n8n execution token metadata: 1398 input + 768 output = **2166** tokens; это НЕ точная стоимость $ (Gateway billing нужно посмотреть в UI).

## Дополнительные реальные и бесплатные тесты

- Execution **#27** — первый полный платный прогон: 8 узлов успешно. Но A6 неверно пропустил неявный маршрут во втором кадре, что обнаружено при ручном разборе.
- Execution **#28**, *pinned only*, **$0**: даже при подставленном model PASS детерминированный guard установил `CHANGES_REQUESTED_TEST` на кадре 2.
- Execution **#29**, *paid*: генерация с явным дорожным указателем. LLM ответил массивом JSON и неточной цитатой, safety validator установил `BLOCKED_UNVERIFIED`.
- Execution **#30**, *pinned only*, **$0**: все R1/R2/R3/C1 с точными quote receipts; `SANDBOX_REVIEW_PASSED_NEEDS_OWNER`.
- Execution **#31**, *paid*: A6 вернул неправильный tag `source_scope` (эхо всей сцены), валидатор закрыл `BLOCKED_UNVERIFIED`.
- Execution **#32**, *replay pinned of #31*, **$0**: разрешён только безопасный нормализатор эха замороженного текста; `SANDBOX_REVIEW_PASSED_NEEDS_OWNER`, текст и receipts совпадают.
- Execution **#33**, *paid*: end-to-end в ОДНОМ запуске успешно прошёл все этапы; manual owner release остаётся заблокирован.

## Осталось до продукционного старта / задачи Codex

1. Подключить изоляцию источников **с настоящими утверждёнными версиями** Studio. Текущий demo Code Node имитирует ввод; источник non-trusted. Применять `backend/qa_text_precheck.py` из ветки `feature/qa-text-audit-fixes-20261019` (PR #8) и регрессионные тесты.
2. Установить защищённый исходящий local Windows → n8n диспетчер, nonce/подписи, idempotency, callback, серверную проверку цитат, hash/snapshot и hard-budget. Без экспонирования локального FastAPI в интернет.
3. Разделить provider adapter: `n8n_gateway` (доступный сейчас) и будущий `kie_api`. Секреты Kie никогда не хранить в GitHub. Проверить актуальные модели, endpoint и реальный usage.
4. Сохранённые A1/A6/A7 и A8 в n8n пока не связаны с этим runnable test workflow. A8 (Sonnet) выключен.
5. Перед production нужен тест реального approved brief / canon, сравнение актуальных source revisions, защита от prompt injection, независимая проверка VIDEO/IMAGE/AUDIO со своими реальными evidence, согласие владельца.
6. Не изменять канон персонажей/авто, не публиковать workflow, не включать платный A8, не делать merge в main без явного разрешения.

**Точный остаток $5 промокредитов n8n из MCP execution API неизвестен; сверять в n8n Gateway Credits dashboard.**
