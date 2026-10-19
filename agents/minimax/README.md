# MiniMax temporary coder — GremoVOD

**Window:** 2026-10-20 through 2026-10-24. On 2026-10-25 hand tasks back to Codex when access returns; Codex is not removed or replaced.
**Status:** Experimental handoff document; does not install, run, or connect the MiniMax agent. Confirm the installed MiniMax version/model locally (official coding release is M3.1 Flash).
**Main repository:** `gremoled77-droid/gremovod`. `main` remains protected by convention; no direct bot pushes.

## Roles

- **MiniMax Code / M3.1 Flash (coder):** Reads and edits source, runs free local tests in its own Git worktree/feature branch; prepares a Draft PR.
- **Argon via existing local review tool (reviewer):** Reads explicit commit/PR diffs and short requirements only; no write credentials, no shell execution. Trigger manually with review of payload and credits. No paid auto-retry.
- **GPT-6 Sol via existing Aider / KIE Proxy v2 (backup):** Preserve tested localhost port 8767 and routes. Do not change `proxy.py` for this experiment. GPT-6.1 Sol remains separate until tested.
- **Codex (returns October 25):** Resumes from open PR, tests, handoff; do not delete GitHub issues or existing Codex configuration.
- **Human approval:** Selects tasks, reviews diff, authorizes external data transfer/API costs, merges PRs.

## Shared state (GitHub rather than implicit agent memory)

- Issues: one task per change, with acceptance criteria.
- Branches/PRs: MiniMax work remains in a feature branch and Draft PR; status and changes are visible under Files changed, Conversation, Checks.
- For each task, add a short PR comment or Markdown handoff with: objective, files changed, tests + outcomes, known limitations, Argon review status, estimated/actual credit consumption if verified, and next action for Codex.
- No external agent assumes access to another agent's private chat or local session. Do not sync secrets or private character assets through a public repository.

## Allowed first five-day scope

1. Audit installation, Git remote and project tests. Prefer `mcode --version` and `/model`; if different product than MiniMax Code, identify it before applying commands.
2. Set up one *separate* worktree; do not switch or clean the dirty working tree at `C:\AI_Workflow_Studio`.
3. Start with one small reversible task (one module + tests), not a broad refactor.
4. Run local offline tests and inspect `git diff --check`, `git status`, and changed files before committing.
5. Request one manual Argon review of a vetted bounded diff. Provider error/HTTP 429 is INCONCLUSIVE, not a code failure.
6. On 2026-10-24 produce handoff for Codex: open branches/PRs, completed tasks, blockers, tests and next priorities.

## Safety and MCP boundaries

- Git CLI already reads and writes local worktrees; GitHub MCP optional, **not** required for source changes.
- Never grant Argon write access to Git/files. MiniMax MCP permissions should start read-only for external services and minimal filesystem scope.
- MCP connection does NOT transfer chat history or cause agents to know one another's state; use Issues/PR comments/hand-off docs.
- Do not put API keys, `.env`, logins, local private media, generated previews or private character references in `.mcp.json` or GitHub. Project MCP endpoints/headers must be confirmed against the actual installed MiniMax Code version; do not invent server URLs.
- No Aider `--auto-test` that calls paid Argon; no unlimited loops, force push, reset/clean or automatic merge.
- Offline review before any provider call; cap payload size, inspect and hash diff, one user-authorized request, no automatic retry.

## Codex return checklist — 2026-10-25

- [ ] Inspect latest accepted PR and open Draft PR.
- [ ] Read MiniMax handoff and accepted requirements.
- [ ] Run local project tests, compare against MiniMax's results.
- [ ] Decide which tasks Codex resumes; do not silently modify another agent's branch.
- [ ] Keep Argon as independent reviewer, with manual explicit API permission.

**Initial GitHub meta task:** see the temporary MiniMax onboarding issue/PR linked in the discussion. This README is documentation only; nothing runs until the user starts MiniMax on their Windows machine.

## Проверено локально на ПК владельца (19.10.2026)

Заменяет догадки в разделе Status выше проверенными фактами.

| Параметр | Факт |
|---|---|
| MiniMax Code | **3.1.1.171**, desktop-приложение (`%LOCALAPPDATA%\Programs\MiniMax Code`). Отдельной CLI-команды `mcode` в `PATH` нет. |
| Активная модель | **MiniMax-M3.1-Flash** (каноническое имя). `MiniMax-M3.1-Flash-Preview` официально выведен из обращения; локальный `defaultModel` в `config.yaml` всё ещё использует старый алиас — работает, но имя стоит нормализовать. |
| Endpoint в `config.yaml` | `https://agent.minimax.io/mavis/api/v1/llm/v1` — это внутренний маршрут авторизованного MiniMax Code, **не** публичный M Plan API. |
| Контекст | 512 000 токенов, выход 128 000; опционально 1 000 000 с пометкой `higher_usage`. Официально модель держит 1 000 000, клиенту рекомендуют 512K. |
| Размышление | M3.1-Flash размышляет всегда; `thinking.type=disabled` и `reasoning_effort=none` отклоняются с 400. Глубина — `output_config.effort`: `low\|medium\|high\|xhigh\|max`. |
| Aider | **0.86.2**, установлен через `uv tool`. Нужные флаги (`--reasoning-effort`, `--cache-prompts`, `--cache-keepalive-pings`, `--auto-commits`, `--auto-test`, `--yes-always`, `--edit-format`, `--model-settings-file`) присутствуют. |
| KIE Proxy v2 | Жив на `127.0.0.1:8767`, `GET /health` → `mode: live`, ключ загружен. **Каждый вызов через него тратит кредиты KIE.** |
| Прокси не умеет tool-calling | `proxy.py` отвечает 400 на `tools`/`tool_choice`. Режимы Aider `architect`/`editor` через 8767 не работают — только `ask`/`chat`. |
| Argon | Реальный LIVE-ревью уже проведён: 4 находки P1–P3, расход **4.1 кредита**, SHA-256 входа зафиксирован. Инструмент — `tools/ai_review/argon_review.py`, OFFLINE по умолчанию. |
| n8n MCP | Подключён (`https://gremovod.app.n8n.cloud/mcp-server/http`), 54 инструмента, из них **22 мутирующих** (включая `execute_workflow`, `publish_workflow`, `delete_agent`). Токен лежит открытым текстом в `%USERPROFILE%\.minimax\mcp.json`. **19.10.2026 отключён** (`enabled: false`) — по заданию «подключить позднее, сначала read-only». Включается обратно одной командой. |
| GitHub CLI | `gh` **не установлен**. Доступ к GitHub идёт через REST API. Для push/PR нужен `gh` или git credential helper. |
| M Plan CLI | `mmx` **не установлен** (`npm ls -g`: только `@evolinkai/cli`, `@genspark/cli`, `@openai/codex`, `piapi-cli`). `mmx quota` недоступен до `npm i -g mmx-cli` + `mmx auth login`. |
| Репозиторий | `origin = https://github.com/gremoled77-droid/gremovod.git`. 16 открытых PR, 14 из них Draft. `main` не защищён (проверка через `gh` не выполнена — API отдаёт 401 анонимно). |

### Найденные риски окружения

- **KIE-ключ лежит открытым текстом в истории PowerShell**
  (`%APPDATA%\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt`,
  95 строк с `KIE_API_KEY`). DPAPI-хранилище `kie-access/api-key.dpapi` **не создано** —
  ключ существует только в окружении запущенного процесса и в тексте истории.
  Требуется санация истории и перенос ключа в DPAPI-хранилище.
- **Обвязка прокси не зафиксирована.** `$env:OPENAI_API_BASE`, `$env:OPENAI_API_KEY`,
  `$env:ANTHROPIC_API_BASE` задаются вручную в сессии терминала VS Code и не
  сохраняются ни в `.env`, ни в `.aider.conf.yml`, ни в переменных User/Machine.
  Новая вкладка терминала → Aider молча уйдёт на `api.openai.com` вместо прокси.
  Ключ, который Aider шлёт прокси, для биллинга не используется: прокси берёт
  `KIE_API_KEY` из собственного окружения, поэтому воспроизводимая обвязка
  не требует хранения секрета.
- **`permissionMode: bypassPermissions` в `config.yaml` MiniMax Code** — эквивалент
  `yes-always` на уровне приложения.
- **Локальный `main` отставал от `origin/main` на 2 коммита**; рабочая ветка
  MiniMax построена от обновлённого `origin/main` (`82adb2d`).
- **Дубликаты исходников.** `pixar_study.py` и `tests/test_core.py` существуют
  в двух экземплярах с идентичным SHA-256 (в корне и в `GremoVOD_Pixar_Study_Kit/`)
  и **не входят в Git** — они untracked. Правка одной копии молча оставит вторую
  устаревшей.
- **Правило `tools/` в `.gitignore` глушило весь каталог.** Инструмент Argon был
  добавлен в индекс принудительно, и любая последующая команда `git add` по этому
  пути молча его пропускала. Заменено на `tools/*` + `!tools/ai_review/`.

### Что делать дальше

План проверки по гейтам — `agents/minimax/PLAN_CHECK.md`.
Шаблон конфигурации Aider для M Plan (без ключей) — `agents/minimax/aider-minimax.example.env`.
Передача Codex с 25 октября — `agents/minimax/HANDOFF_FOR_CODEX.md`.