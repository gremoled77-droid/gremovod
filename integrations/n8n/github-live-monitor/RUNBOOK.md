# Подключение, публикация и отключение

## GitHub

1. Открыть существующий draft workflow. Не нажимать Publish/Activate.
2. В n8n Credentials создать GitHub credential. Значение токена вводить только в защищённую форму n8n; не в чат и не в Git. Доступ ограничить `gremoled77-droid/gremovod`: read repository metadata, contents, pull requests, checks/statuses; управление repository webhooks нужно нативному Trigger. Конкретные возможности fine-grained token/GitHub App сверить в выбранном credential.
3. Выбрать credential в `GitHub Trigger` и `Current GitHub Snapshot`. Наличие admin у подключённого GitHub-коннектора не передаёт credential в n8n. На диагностике GitHub connector сообщил admin/pull/push, но n8n GitHub credential отсутствовал.
4. Проверить версию n8n через About/Settings. По [release notes](https://docs.n8n.io/release-notes/) signature verification появилась в линейке 2.5, но поведения конкретной версии и legacy hook это не доказывает. Проверить реализацию/обновление и новый secret-managed hook. Флаг `SIGNATURE_BOUNDARY_CONFIRMED` пока false.
5. После отдельного разрешения на live smoke зарегистрировать **тестовый**, не production webhook через GitHub Trigger test listener. Это внешняя запись webhook; не создавать её без разрешения. Native Trigger управляет URL и secret: не дублировать его ручным hook с пустым secret.
6. В GitHub Settings → Webhooks проверить HTTPS URL n8n, SSL verification включена; events: push, pull_request, pull_request_review, pull_request_review_comment, issue_comment, check_run, check_suite, status. Не подписываться на лишние события.
7. Выполнить GitHub ping/redelivery безопасного события и сохранить delivery/result/execution ID. Некорректная и отсутствующая подпись должны дать 401 до выполнения workflow. Неверный repository должен быть отклонён приложением. Нативный ping сам по себе может не создавать execution — проверить HTTP delivery response.
8. Удалить тестовую подписку штатным завершением listener и проверить отсутствие лишних hooks. Production hook создаётся при последующей одобренной активации.

Сейчас реальные hooks и их доставка не подтверждены. Read-only получение пяти PR через connector — отдельный smoke доступа, не webhook E2E.

## Telegram

1. В официальном Telegram открыть проверенного `@BotFather`, выполнить `/newbot`, выбрать имя и username. Сохранить выданный token в n8n Telegram credential. Не присылать token в этот чат, не сохранять в репозитории.
2. Открыть личный диалог с созданным ботом, нажать Start. Подтвердить, что получатель — владелец. Не подключать неизвестные группы/каналы.
3. Получить chat ID из `getUpdates` через защищённый credential-aware инструмент/UI n8n, не помещая token в URL командной строки, browser history или Git. Альтернатива — отдельный Telegram Trigger в тестовом listener после согласования; один бот имеет один webhook, существующую подписку нельзя молча перезаписывать. Проверить owner chat по входящему сообщению.
4. Выбрать credential в `Telegram Notification`. Chat ID в рабочем draft задаётся только после подтверждения владельца; репозиторный экспорт сохраняет пустое значение.
5. Отдельно получить разрешение на **одно** сообщение в этот chat ID. До этого gate остаётся закрытым. Отправить безопасный фиксированный текст и сохранить message_id и execution ID. Mock PASS не заменяет этот шаг.

## Сериализация и повторы

Data Table get → plan → update не имеет доказанной атомарной уникальности. Для первой версии нужен подтверждённый предел **один production execution этого sender одновременно**, распространяющийся на webhook и schedule пути. Нельзя считать медленное расписание таким пределом. Запретить параллельные ручные запуски production sender.
Если текущий Cloud plan не предоставляет подходящий контроль concurrency, **не включать sender**. Подготовить отдельно атомарный outbox/unique semantic key в поддерживаемом хранилище, затем параллельный E2E-тест. В этом пакете новая БД/сервер не создаются.

Не ставить Telegram retryOnFail=true. При SENDING без завершения, UNKNOWN или timeout сначала проверить диалог и execution. Если сообщение есть — вручную отметить SENT/message_id. Если достоверно не отправлено — разрешённое владельцем возвращение выбранной строки в PENDING. При 429 дождаться retry_after, затем сверить отсутствие сообщения и повторить только одну выбранную запись. При 400/401/403 исправить параметры/credential перед повтором. При недоказанном исходе оставить UNKNOWN: риск пропуска предпочтён автоматическому дублю. Повтор не должен массово сбрасывать SENT или UNKNOWN.

## Приёмка и включение

Выполнить live tests из TEST_REPORT, проверить credentials и receiver, HMAC, сериализацию, ошибки, дубликаты, edited и stale review. Проверить фактический Codex bot/app slug. Уточнить authoritative GA/dispatcher signal; до этого их UNKNOWN не заменять догадками.
Проверить таблицу: тестовые записи имеют TEST_ONLY и не должны становиться PENDING. Архив/retention журнала проектируются отдельно; сейчас читается вся таблица, поэтому для большого потока перед масштабированием нужен ограниченный outbox и сохранение dedupe-истории.
Проверить доступ к execution logs и retention сырых GitHub payloads. Секреты credential не экспортировать; staticData с webhookSecret не включать в Git.

Только когда live проверки PASS: поставить статус READY_FOR_OWNER_APPROVAL и показать отчёт владельцу.
После **отдельного явного подтверждения** владельца открыть gate: OWNER_APPROVED, SIGNATURE_BOUNDARY_CONFIRMED, SERIAL_SENDER_CONFIRMED и подтверждённый CHAT_ID; затем Publish. Эти действия текущим заданием не разрешены автоматически.
После одобренного включения проверить доставку GitHub, одно сообщение, message_id, SENT и отсутствие повторения при redelivery. Не просить модель/диспетчер создавать события для smoke, не запускать Codex/MiniMax.

## Отключение и восстановление

Unpublish/Deactivate конкретный monitor в n8n. Проверить остановку schedule и удаление/отключение принадлежащего ему GitHub hook. Другие workflows/hooks не трогать. Закрыть OWNER_APPROVED. Журнал сохранить для reconciliation и дедупликации; не удалять/не обнулять статусы доставки.
При восстановлении загрузить credential-free экспорт как draft, связать нужную **существующую** таблицу и credentials через UI. Не создавать второго production sender. Повторить live gates; новый экземпляр GitHub Trigger должен получить собственный проверенный secret.
