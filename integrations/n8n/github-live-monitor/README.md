# GremoVOD — GitHub Live Monitor

Состояние: **IMPLEMENTED_DRAFT / LIVE_BLOCKED**, 21.10.2026. Production не активирован.
`READY_FOR_OWNER_APPROVAL` пока не достигнут: нужны credentials, проверка HMAC и последовательного sender, затем разрешённый владельцем Telegram smoke.

- [Workflow в существующем n8n](https://gremovod.app.n8n.cloud/workflow/iV4GGl3jWmnjh3Sd), 20 узлов, personal project GremoVOD, корень проекта.
- Таблица `GremoVOD_GitHub_Live_Monitor_Events`, ID `kwfLFihCIf0z10TW`.
- [Отчёт проверок](TEST_REPORT.md), [эксплуатация и подключение](RUNBOOK.md).
- [Экспорт без credentials](workflow.json), [SDK-описание](workflow.sdk.ts), [схема событий](event.schema.json).
- Логика: `core.cjs`; фикстуры: `fixtures.cjs`; тесты: `tests.cjs`; воспроизводимая сборка: `build.cjs`.

## Что работает в черновике

GitHub Trigger → Verify Event → Current GitHub Snapshot → Normalize Event → Event Filter → Event Journal.
Журнал → Deduplicate and Severity Router → Owner Approval Gate → Mark SENDING → Telegram → Persist Delivery Result.
Расписание каждые 30 секунд подбирает оставшуюся очередь. Обычные и критические события готовы к отправке сразу после записи; информационные ждут пять минут и группируются до 15 событий.
За один проход отправляется одна группа, критическая раньше обычной; при очереди возможна дополнительная задержка.

`Owner Approval Gate` сейчас всегда возвращает ноль элементов. Все ручные запуски записывают `TEST_ONLY`, не production `PENDING`.
Встроенный ручной триггер `Mock Tests` исполняет только контракты без сети, моделей и уведомлений.

Поддержаны push (последний SHA), opened/reopened/synchronize/ready_for_review/closed PR, Codex review и inline findings P0/P1/P2, created/edited комментариев, check_run/check_suite/status.
Новый SHA не означает исправления замечаний. `PR_READY` не означает приёмку. `PR_MERGED` требует GitHub `merged=true`.
CI success означает успех конкретного check/status, а не всех проверок PR.

## Границы достоверности

Нативный GitHub Trigger служит границей аутентификации; `Verify Event` проверяет repository и метаданные, но сам не пересчитывает HMAC.
По [актуальному исходнику Trigger](https://github.com/n8n-io/n8n/blob/master/packages/nodes-base/nodes/Github/GithubTrigger.node.ts) новый webhook получает случайный secret; [helper](https://github.com/n8n-io/n8n/blob/master/packages/nodes-base/nodes/Github/GithubTriggerHelpers.ts) проверяет raw body и X-Hub-Signature-256 через HMAC-SHA256 и timingSafeEqual.
Это доказательство реализации upstream, **не установленной версии Cloud**. Версия инстанса через доступные инструменты/публичный settings endpoint не раскрылась. До проверки версии и отрицательного smoke HMAC-флаг закрыт. Старые версии/legacy hooks могут вести себя иначе.

Codex доверяется только точному `chatgpt-codex-connector[bot]` с `type=Bot`; его фактическое присутствие в данном репозитории не подтверждено. Для review нужен `commit_id`, равный свежему SHA из GitHub API. Старый review получает `STALE`; недоступный GitHub — `UNKNOWN`.
Issue comment, включая edited, не содержит авторитетного `commit_id`: наличие SHA в тексте не повышает его до актуального review. В журнале остаётся `CODEX_COMMENT_UNCORRELATED / UNKNOWN`. Inline edited с commit_id обрабатывается.
Started распознаётся только по текущему SHA и нативному check_run приложения с точным slug `chatgpt-codex-connector`; существование такого check у репозитория ещё не доказано. Запрос review сам по себе не Started.
GA-переход и «MiniMax исправил замечания» остаются UNKNOWN до подключения авторитетного подтверждения диспетчера/приёмки. Локальный state диспетчера не читается; Draft #59 не считается внедрённым.
Owner labels `security-blocked`, `financial-blocked`, `dispatcher-stopped` принимаются только при sender `gremoled77-droid`. Сам monitor не назначает эти метки.

## Доставка и безопасность

Delivery ID и semantic key подавляют дубликаты в одном планировании и после записанного SENT/SENDING/UNKNOWN/FAILED. Семантика включает PR, SHA, вид и статус; findings/checks дополнительно различаются evidence ID. Повторный completed review того же SHA/status не создаёт новый план.
**Data Table не имеет подтверждённого unique constraint на этих полях.** Два параллельно запрошенных insert сохранили одинаковые ключи дважды. Планирование не является атомарным межпроцессным claim. Параллельные sender запрещены: до подтверждения сериализации флаг закрыт.
После MARK SENDING обрыв не даёт автоматического повторения. Timeout Telegram → UNKNOWN; definite rejection → FAILED. Все повторы ручные после сверки доставки. Exactly-once не заявляется.

В Telegram идут только фиксированный тип, severity, номер PR, SHA и каноническая GitHub-ссылка, для review/finding — прямая ссылка на запись. Сырой текст комментариев, названия PR, diff, commit message, emails, пути и токены не передаются. Так замечания доступны по ссылке без экспорта произвольного текста. HTML экранируется, previews выключены.
Журнал содержит нормализованный envelope; ошибки сохраняются кодом без raw exception. Необработанные входные данные могут оставаться в закрытых n8n execution logs: доступ и retention проверить перед live.

## Воспроизведение

Из корня отдельной worktree:

```powershell
node integrations/n8n/github-live-monitor/tests.cjs
node integrations/n8n/github-live-monitor/build.cjs
```

Без установки зависимостей. Тесты пишут UTF-8 `local-test-results.json`. Сборка генерирует SDK, credential-free JSON и схему; asserts проверяют закрытый gate, запрет автоматического retry Telegram, отсутствие модельных узлов и обязательные поля образца.
Экспорт JSON предназначен для импорта с последующим ручным выбором credentials. SDK содержит только имена незаполненных credential-запросов, никаких секретов/ID credential.

## Область изменений

Только `integrations/n8n/github-live-monitor/`, отдельная ветка `feature/gremovod-github-live-monitor` от `mavis/work@57cac59`.
main является предком базы (проверено Git). Runtime студии, SQLite, канон, чужие worktree и PR #58/#59 не менялись. Новая инсталляция n8n, платные вызовы и запуск агентов отсутствуют.
