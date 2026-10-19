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
