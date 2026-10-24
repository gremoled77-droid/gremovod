# GremoVOD Studio — project rules
Owner grem: reply in Russian; UI text Russian. Context: docs/HANDOFF_CLAUDE_CODE.md, TODO.md.

## Scope
- Pipeline: characters → images → video → sound → CapCut (editing outside studio).
- Every frame: 16:9 + 9:16. Do not revive frozen systems (outside pipeline).

## Map
- backend/: FastAPI+SQLite :8000; main.py + modules register(app, studio)
- model_catalog.py, adapters.py: PiAPI catalog, price, confirm token, budget
- activity.py jobs; temp_cleanup.py trash; storyboard.py, production_*.py
- frontend/src/: React18+TS+Vite :5173; App.tsx shell
- GenerationReview.tsx paid confirm; WorkflowPanel.tsx+workflowPlan.ts nodes
- skills/ prompt rules; docs/ decisions, live tests

## Checks (narrow first)
- Run: .\.venv\Scripts\python.exe scripts\start_studio.py
- Health: http://127.0.0.1:8000/api/health
- Backend: .\.venv\Scripts\python.exe -m pytest backend -k <name>
- frontend/: npx tsc --noEmit; npm test; npm run build
- Format: npx prettier --write <files>
- UI: verify in browser at 127.0.0.1:5173

## Git & ports
- Root = main + owner data: no dev there.
- Claude: .worktrees/claude (claude/work); Codex: .worktrees/codex.
- Start: git fetch origin; git merge origin/main.
- git add exact paths; push own branch only; no force-push.
- 8000/5173: only Claude Code restarts studio from root.
- Codex: 8001/5174 + own STUDIO_DATA_DIR.
- Never commit keys, DBs, media, projects/.

## Money & safety
- Never print/commit keys (*_API_KEY.txt, .env*).
- Paid run = estimate + GenerationReview + confirm token + limits.
- Test spend: fresh owner OK each session, small cap.
- Unknown spend stays UNKNOWN: keep holds; no paid retry
  without reconciliation.
- Enable model only after live verified call (verified_at).
- Delete = soft trash + cleanup_journal; keep used files.
