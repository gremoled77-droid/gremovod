# Проверки — 21.10.2026

**Итог: IMPLEMENTED_DRAFT / LIVE_BLOCKED. Не READY_FOR_OWNER_APPROVAL и не production-ready.**

Этап A выполнен в доступной области. n8n отвечает; инструменты create/update/validate/test/publish/unpublish и Data Table доступны. Версия сервера не раскрылась. GitHub и Telegram credentials в n8n: 0. Подходящего workflow среди 24 GremoVOD workflows и отдельного поиска GitHub не найдено. Существующий Dev Observability вызывает модели по другому назначению, переиспользовать его как monitor не стали.
B–D реализованы в draft; проверка HMAC на живом входе и атомарность sender остаются gates. E: mock PASS, live BLOCKED. F: инструкция готова, credential/получатель/отправка BLOCKED. G: отдельная worktree/ветка и этот проверяемый пакет.

## GitHub snapshot

Read-only connector запросил текущие PR, не меняя их. Все **open / draft=true / merged=false**:

| PR | Base | Head SHA |
|---|---|---|
| [54](https://github.com/gremoled77-droid/gremovod/pull/54) | mavis/work | 78a80b79531084bb014813bab18ec59bd5560378 |
| [56](https://github.com/gremoled77-droid/gremovod/pull/56) | mavis/work | 2ff006a4e09f7427b4eefba3df7f6a2427150f3e |
| [57](https://github.com/gremoled77-droid/gremovod/pull/57) | experiment/minimax-codex-handoff-vscode-20261021 | ff05bdc44a5075cf6ceb854ae4c26845690b814a |
| [58](https://github.com/gremoled77-droid/gremovod/pull/58) | mavis/work | 9b6a610a6b1afcb4e24b869649a387b7b6d5e8bf |
| [59](https://github.com/gremoled77-droid/gremovod/pull/59) | experiment/codex-minimax-local-dispatcher-20261021 | ba078cb2a48a56b3d6af8d5963373c62d05cad8b |

База `mavis/work@57cac59ca790d380d8e68f2f6db82674ca142e92` подтверждена и соответствует текущему направлению разработки. origin/main является её предком; дополнительное merge не требовалось. Git fetch прошёл с command-local OpenSSL после ошибки Windows Schannel. Новая worktree: `C:/Users/BLOWKA/aider-test/gremovod-github-live-monitor`.

## Проверяемые executions

- [72 — 36 исходных mock contracts](https://gremovod.app.n8n.cloud/workflow/iV4GGl3jWmnjh3Sd/executions/72): success.
- [73 — GitHub/Snapshot pinned, реальный журнал n8n и gate](https://gremovod.app.n8n.cloud/workflow/iV4GGl3jWmnjh3Sd/executions/73): success. В Verify/Normalize/Filter/Prepare/Insert/Get/Plan по одному выходу; Owner Approval Gate выдал 0. Telegram не исполнялся.
- [74 — карантин первоначальной фикстуры](https://gremovod.app.n8n.cloud/workflow/iV4GGl3jWmnjh3Sd/executions/74): success. Только собственная тестовая строка переведена в TEST_ONLY; insert-конфигурация журнала восстановлена и повторно проверена.
- [75 — расширенные 38 mock contracts](https://gremovod.app.n8n.cloud/workflow/iV4GGl3jWmnjh3Sd/executions/75): success, 38 PASS / 0 FAIL. Финальные executions приведены в `cloud-test-results.json`.
- [76 — финальная ревизия, 38 PASS](https://gremovod.app.n8n.cloud/workflow/iV4GGl3jWmnjh3Sd/executions/76): success, 38 выходных результатов.
- [77 — финальная цепочка с реальной записью TEST_ONLY](https://gremovod.app.n8n.cloud/workflow/iV4GGl3jWmnjh3Sd/executions/77): success, planner выдал 0, fixture не попала в очередь отправки.
- [78 — чужой repository](https://gremovod.app.n8n.cloud/workflow/iV4GGl3jWmnjh3Sd/executions/78): Verify выдал 0 normal / 1 error, Error Handler записал минимальный FAILED; Snapshot/Normalize/Telegram не исполнялись. Status success означает обработанный отказ, не принятие чужого события.

Локально `node .../tests.cjs`: 38 PASS / 0 FAIL, поимённый UTF-8 результат в `local-test-results.json`. Генератор завершился с asserts. SDK validate: valid=true, 20 nodes, без warnings. Первоначальная ошибка группы и предупреждения sample-output устранены до создания; конечные update без warnings. Временный quarantine update получил предупреждение о числе вместо string в фильтре; фактическое обновление прошло, временная конфигурация удалена, статус TEST_ONLY прочитан обратно.

## Матрица задания

PASS ниже относится к mock-контрактам; он не означает реального Telegram сообщения.

| Проверка | Mock / cloud evidence | Live |
|---|---|---|
| Новый PR: один план уведомления | PASS, contract + 73 | BLOCKED credentials/approval |
| Повтор webhook: нет второго плана | PASS delivery/semantic в batch и после SENT | BLOCKED concurrent sender |
| Новый commit: SHA | PASS, включая поздний старый event | BLOCKED webhook |
| Старый Codex review | PASS STALE | BLOCKED webhook |
| Текущий review completed | PASS; одинаковый SHA/status повторно подавлен | BLOCKED bot/current review smoke |
| P1 finding | PASS immediate, прямой URL на finding | BLOCKED receiver |
| CI failed | PASS P1/immediate | BLOCKED webhook |
| CI passed | PASS конкретный check/status | BLOCKED webhook |
| PR merged | PASS, closed без merged не считается merge | BLOCKED webhook |
| Неверная/отсутствующая подпись | BLOCKED: native boundary не вызывается mock pins | BLOCKED version/credential/test listener |
| Чужой repository | PASS rejected | BLOCKED live negative delivery |
| Telegram API error | PASS: timeout→UNKNOWN, definite 429/4xx→FAILED, без авто retry | BLOCKED actual rejection/reconciliation |
| GitHub unavailable | PASS UNKNOWN, не completed | BLOCKED network fault injection |
| Одновременные события | PASS только дедуп batch; нет атомарной гарантии | BLOCKED до сериализации |
| edited комментарий | PASS inline+commit; issue comment без commit→UNKNOWN | BLOCKED actual bot edited event |
| Секреты/HTML | PASS: сырой текст исключён, HTML escaped, ошибки фиксированными кодами | BLOCKED внешний privacy review |

Дополнительно проверены spoofed bot, отсутствие delivery, review_requested≠started, посторонний check≠Codex, GA marker≠приёмка, группировка через пять минут, urgent раньше INFO, SENDING/UNKNOWN не повторяются.

## Проверка Data Table

Два независимых вызова insert с одинаковыми event_id/delivery_id/semantic_key были отправлены параллельно. Оба вернули insertedCount=1. Read-back: **две строки**, id=2 и id=3, статус TEST_ONLY. Это доказывает отсутствие автоматической уникальности insert на выбранных колонках, а не безопасность конкурентного sender. Временная последовательность коммитов этих двух запросов не контролировалась.
Сам read→plan→mark→send межзапусковой lock не имеет. Он **не** прошёл concurrent delivery acceptance. Не включать SERIAL_SENDER_CONFIRMED без внешнего проверенного ограничения/атомарного outbox. Платформенное поведение update/upsert не объявляется exactly-once.

Все три начальные fixture-строки прочитаны обратно как TEST_ONLY. Новые ручные события тоже TEST_ONLY. Рабочих событий/отправок не было.

## Что осталось владельцу

Через защищённые формы n8n настроить два credentials, проверить версию/HMAC, обеспечить последовательный sender, подтвердить owner chat ID и отдельно разрешить одно тестовое сообщение. Затем пройти live матрицу и только после PASS рассматривать READY_FOR_OWNER_APPROVAL. Сейчас production activation и Telegram send не запрашиваются: предварительные условия не выполнены.
