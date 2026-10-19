# Короткий запрос к MiniMax — подключение Argon через KIE, экономный режим

Прочитай методичку: docs/experiments/MINIMAX_ARGON_KIE_BRIDGE_METHOD_RU.md (текущая ветка experiment/minimax-kie-argon-bridge-20261019).
Она уточняет существующие PR #22 / #23, Issue #27 и ожидающий Argon PR #29.

**Задача:** собрать OFFLINE-прототип безопасного моста MiniMax -> frozen Git diff + краткая выжимка -> один вызов KIE Argon -> GitHub Draft PR report, но **не выполнять LIVE запросы**.

До первой записи: проверь Git/dirty/untracked, AGENTS.md, CLAUDE.md, existing argon_review.py. Покажи список затрагиваемых файлов. Не изменяй main, C:\AI_Workflow_Studio, Proxy v2, SQLite, медиа или канон.

Реализация: ограничение 6KiB payload; 1 KIE review на PR/head по отдельному согласию, 2 в день, 5 в неделю, ноль ретраев, атомарный ledger; Git evidence реальные hunks, не одно summary; недоверенные поля и запрет секретов; владельцу только sanitized report и ссылки. Протестируй MOCK/OFFLINE, сделай Draft PR. Временно не подключай облачный n8n и API оплаты.

Верни:
1. what exists vs implemented vs blocked;
2. files and SHA / Draft PR URL;
3. exact tests and results;
4. mocked example request and response;
5. current risks and next owner approvals;
6. handoff для Codex на 25 октября.

Не отправляй никаких ключей. Не создавай KIE платежей без последующего отдельного разрешения владельца.
