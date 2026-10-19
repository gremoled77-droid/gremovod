# Контракт для Argon — INTEGRATE-01

- Сделано: семь draft/mock JSON проверены; доказанного сквозного file transport пока нет. Контракт подготовлен; Argon не запущен, сообщение не отправлено.
- Файлы: только `workflows/**`, `integrations/n8n/**`, собственный `docs/agent_handoffs/argon-integrate01.md`. Тесты пока помещать в `integrations/n8n/test_argon_transport.py`: документированный tests/test_argon_ префикс сейчас ошибочно отвергается scope guard. Не трогать backend/, db/, scripts/, tools/, docs/specs/, canon/, STATUS/CI.
- Следующий шаг: в отдельной ветке `build/argon/mock-transport-contract` от `9287455` описать outbound transport и сделать бесплатные contract tests. Реальные облачные изменения и импорт не входят в это задание. Сдать PR с JSON examples и результатами Codex.

Сохранить семь физических WF, `active=false`, `MOCK_MODE=true`, `final_release_approved=false`, ноль provider calls. Ни loopback в публичной сети, ни credentials/подписанные URL в git. Asset reference должен включать непрозрачный ID, SHA-256, размер, тип, revision и срок; backend подтверждает project scope/доступ/фактический hash. URL и локальный путь не являются подтверждением доступа.

Контракт отдельно различает transfer retry и provider submit retry: UNKNOWN paid operation не повторять. Отрицательные тесты: неверный hash, expired grant, чужой project, отсутствующий asset, неизвестный workflow ID, stale revision, transfer interruption. Нельзя возвращать PASS за реально не доставленный файл. IDs дочерних workflows переназначать только в отдельной тестовой копии после согласования backend route.

Зависимость от Claude: реальные protected asset routes и State Manager ещё не готовы. До их готовности только offline contract tests с честным BLOCKED для фактической доставки; mock:// не выдавать за сквозной Windows/cloud тест. Windows worker/бюджет/owner API не реализовывать в n8n Code node.
