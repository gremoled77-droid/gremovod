# Coordination — agent handoff bootstrap (19.10.2026)

- **Сделано:** подготовлены общий регламент, STATUS, карта зон, семь безопасных mock JSON-экспортов и Codex review packet; существующий `AGENTS.md` / `CLAUDE.md` оставлен главным источником правил Windows worktree.
- **Файлы:** `AGENT_BUILD_MANUAL.md`, `STATUS.md`, `workflows/WF_00..WF_06*.json`, `workflows/README.md`, `prompts/README.md`, `docs/CODEX_REVIEW_PACKET.md`, `docs/agent_handoffs/**`.
- **Следующий шаг:** Codex разбирает зависимые PR #17 → #18, выбирает единый SQLite контракт и выдаёт задания Claude/Argon. Экспорты WF — без credentials, родитель требует remap ID и не является production ready.
- **Проверки:** будет отдельный CI `agent-coordination.yml` для структуры файлов/JSON; облачный n8n mock ранее исполнен как #39 с $0 API.
- **Блокировки для Codex:** `CODEX_DECISION_REQUIRED` — owner auth, DB migration, real asset transport, отказ от ложного видео PASS, drift между спецификацией и облачными workflow.
