# Prepared smoke: explicit quota approval still required

Historical plan. The owner subsequently authorized one attempt; [its result](AUTONOMOUS_RESULT_2026-10-21.md)
is HALTED / MINIMAX_FAILED. No automatic retry or autonomous GA execution was enabled.

Implementation: [Draft PR #69](https://github.com/gremoled77-droid/gremovod/pull/69),
stacked on #60. Test only: [Draft PR #70](https://github.com/gremoled77-droid/gremovod/pull/70),
base `feature/codex-minimax-relay`, head `minimax/relay-smoke-20261021`.
Initial smoke HEAD: `a2b999df0196539361a22bc93a39ce594389ed45`.
No live model proof is claimed. Both PRs remain Draft; no merge is authorized.

## Concrete installation

* Controller: `C:\Users\BLOWKA\aider-test\gremovod-agent-relay\scripts\agent-handoff\dispatcher.py`.
* Developer: `C:\Users\BLOWKA\aider-test\gremovod-relay-smoke`.
* Detached reviewer: `C:\Users\BLOWKA\aider-test\gremovod-relay-reviewer`.
* Owner policy: `C:\Users\BLOWKA\aider-test\outputs\relay-smoke-job.json`.
* Persistent state: `C:\Users\BLOWKA\aider-test\outputs\relay-smoke-state`.
* Registered task: `GremoVOD-AgentRelay-Smoke-20261021`, **Disabled**.
* STOP: present. Approval: absent. No CLI subscription job has been started by this preparation.

Only `tests/agent_handoff_smoke/value.py` is editable. Its frozen `test_value.py` imports no Studio code.
The baseline was run: negative test fails with `AssertionError: -4 != 0`, positive test passes.
The intended fix clamps negatives to zero. Production Studio, main and existing GA tasks are outside this job.

## Requested expense authorization

| Invocation | Maximum | Purpose |
| --- | --- | --- |
| Codex CLI, read-only | 2 calls, 180 seconds each | Initial structured review, then review of pushed fix SHA |
| MiniMax CLI, smart | 1 call, 120 seconds, 8 steps | Fix the confirmed finding in value.py |
| Independent Python tests | 30 seconds per run | Confirm baseline failure, then green tests before commit and after review |
| Git correction | 1 commit/push to the smoke branch | No force-push; no merge |

There is no automatic retry after failure, timeout, conflict or uncertain launch. This smoke's maximum is
one correcting iteration; general dispatcher maximum remains three. MiniMax's own deadline is five seconds
shorter than the external 120-second limit. The policy cannot enforce an exact number of subscription
tokens or monetary spend; these are invocation/time/step bounds. No paid media generation is requested.

After explicit confirmation: inspect fresh remote HEAD/base, clean worktrees and policy; remove this STOP;
arm the expiring policy; enable/start the installed task. Watch `state.json` and `events.jsonl` through
initial review → reproduced regression → MiniMax → independent tests → commit → push → second review.
Stop/disable the task on terminal clear or any failure. Save redacted live evidence with both SHAs,
actual call counters, frozen-test hash and test/review results. Attach it to #69 without merging.
If the provider fails or the time limit is too small, report that result; extra calls require a new decision.

## Stop immediately

```powershell
& 'C:\Users\BLOWKA\aider-test\gremovod-agent-relay\scripts\agent-handoff\Manage-RelayTask.ps1' -Action Stop -StateDirectory 'C:\Users\BLOWKA\aider-test\outputs\relay-smoke-state'
```

This exact command was checked against the installed task. It writes STOP and disables matching tasks
without killing other agents. Model process-tree shutdown was tested offline on Windows.
See [scheduler preflight](evidence/relay-scheduler-preflight.json),
[mock summary](evidence/relay-mock-summary.json), [mock phases](evidence/relay-mock-events.jsonl)
and [installation/runbook](AUTOMATIC_RELAY_2026-10-21.md).

Verified before approval: 36 relay tests, 15 compatibility tests, 25 monitor tests/TypeScript build,
Ruff, clean diff checks, real disabled task registration and STOP. Models/GitHub were mocked in the
relay E2E; local Git and independent tests were real. No new browser/VS Code UI walkthrough was run for
this journal-only monitor adapter; adapter tests verify event ingestion and STOP.
