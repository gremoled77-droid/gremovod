# Temporary autonomous authorization: 2026-10-21

**Outcome: smoke failed; autonomous GA work was not enabled.** See [owner report](AUTONOMOUS_RESULT_2026-10-21.md).
The intended tool restriction below did not exclude shared-profile MCP/skills in the live run.
Future MiniMax runs are blocked until an independently authenticated isolated profile is prepared and verified.

Owner authorized the existing dispatcher to run the isolated smoke and continue only if it succeeds.
This run uses one shared durable state directory, at most six total model launches including smoke,
one active PR, at most three correcting iterations per PR, and a two-hour schedule window.
No GA-02 transition before owner acceptance/integration of GA-01; no GA-03 runtime.

## Synchronization before models

| PR | Current head | Read-only PR65 regression retest |
| --- | --- | --- |
| #58 GA-01 | c634c0c915a1afbf3d75df5bc897f75ef5b723ea | 8 contracts: 3 pass, 2 assertion failures, 3 runtime errors |
| #62 GA-04 | 6898e4e6930ed8ec92bbdc67b429d54d706995dc | 4 contracts: 2 pass, 3 failure records including subtests |
| #63 GA-05 | 7524c677551c7ba3f34b8ce40a1a655895a88ff5 | 5 contracts, 7 failure records including subtests |
| #64 GA-03 | f10a22bf9e3e0d0c90fdb13ffa52acfa87bed3f0 | Plan only; runtime execution prohibited |
| #65 audit | 1bb406e8bf277d9c4ebef20896b86c208b2f32de | Unchanged test materials used through disposable Git archives |

GA-01's contradictory zero-usage and interrupted-backfill contracts now pass: do not assign them again.
Remaining failures: negative legacy spend, full confirmed reconcile amount, malformed legacy tokens,
nonfinite pricing and the existing task_identity NameError. The last is a GA-02 boundary observation,
not authorization to implement GA-02. GA-04's new workflow attempts trusted-base execution, so the
old direct-head-checker adversarial test alone is not evidence that the new workflow can be bypassed;
the actual bootstrap path and missing heavy-CI trigger coverage need separate review.

Existing interactive MiniMax processes were observed, not stopped or switched. No new work is assigned
to their worktrees. Current contracts use temporary archives and temporary SQLite, without Studio servers.

## Subscription and process controls

Read-only local checks found Codex auth_mode=chatgpt, no OpenAI API key; MiniMax source=token_plan,
active minimax_oauth, API/custom providers inactive. Every model start repeats the relevant auth check.
Codex ignores user configuration, pins gpt-6.1-sol and ChatGPT auth, and uses read-only detached worktrees.
MiniMax pins minimax/MiniMax-M3.1-Flash, always smart, with explicit runtime tools limited to
read/write/edit/grep/glob. No shell, delegation, browser, web search or external skill tool is requested.
No provider connection test, API-key fallback or media generation is part of this run.

All model reservations count before submission, including an uncertain launch. Shared state sums
Codex and MiniMax reservations across jobs; the seventh is blocked. Never erase state to reset limits.
On completion/error the dispatcher saves a local owner report, attempts one GitHub report and writes STOP.
An uncertain GitHub POST is not automatically repeated. An already-held dispatcher lock is a no-op;
another tick must not stop an existing process. Model process trees are stopped only by their own deadlines
or the explicit STOP marker. Existing unrelated processes are never killed.

The new scheduled task repeats every five minutes for two hours, Interactive/Limited, IgnoreNew plus
OS lock. Its controller and shared state remain outside model worktrees. A restart at an ambiguous model
phase halts for reconciliation instead of silently retrying. Terminal state and STOP block all model calls.

## Concrete run files

Controller: `C:\Users\BLOWKA\aider-test\gremovod-agent-relay\scripts\agent-handoff\dispatcher.py`.
Policies/evidence: `C:\Users\BLOWKA\aider-test\outputs\autonomous-relay-20261021`.
Shared state: that directory's `state` subdirectory. Smoke is Draft #70; implementation is Draft #69.

Emergency stop:

```powershell
& 'C:\Users\BLOWKA\aider-test\gremovod-agent-relay\scripts\agent-handoff\Manage-RelayTask.ps1' -Action Stop -StateDirectory 'C:\Users\BLOWKA\aider-test\outputs\autonomous-relay-20261021\state'
```

Live outcome and actual counts are recorded after execution; this preparation is not ACCEPT or live proof.
Exact tokens cannot be capped by these CLIs; the bound is model invocations, steps and wall time.
The CLI tool set/permission policy is not a same-user OS sandbox. No merge, main/mavis/work changes,
production SQLite, deployment, paid media, n8n activation or canon changes are authorized.
