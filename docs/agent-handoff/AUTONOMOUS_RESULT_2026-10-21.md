# Owner report: smoke failed, autonomous execution stopped

**HALTED / MINIMAX_FAILED. No ACCEPT. Production task execution was not enabled.**
The owner authorized smoke and conditional continuation; its required success condition did not occur.
No second smoke or new model call was made after the failure.

## What Codex did

Inspected current PRs, existing process/task metadata and worktrees without stopping or switching
unrelated processes. MiniMax session metadata and background-task metadata showed no active GremoVOD
job at the final observation. The existing original MiniMax worktree remained clean at `5c47ace...`;
the published GA-01 branch was already `c634c0c...`. It was not reset or updated in place.

Re-ran the unchanged safe-behavior contracts from PR #65 through disposable Git archives, with temporary
SQLite and an outbound socket audit hook, against the exact current commits:

| PR / SHA | Existing tests | Independent safe contracts |
| --- | --- | --- |
| #58 GA-01 `c634c0c915a1afbf3d75df5bc897f75ef5b723ea` | 98 passed | 8 cases: 3 pass, 2 failures, 3 errors |
| #62 GA-04 `6898e4e6930ed8ec92bbdc67b429d54d706995dc` | Not repeated in this run | 4 cases: 2 pass, 3 failure records including subtests |
| #63 GA-05 `7524c677551c7ba3f34b8ce40a1a655895a88ff5` | Not repeated in this run | 5 cases: 7 failure records including subtests |
| #64 GA-03 `f10a22bf9e3e0d0c90fdb13ffa52acfa87bed3f0` | Runtime not executed | Architectural decisions remain owner-controlled |

Audit source: #65 `1bb406e8bf277d9c4ebef20896b86c208b2f32de`.
The existing-suite green result does not override the new red contracts.

GA-01 now passes the contradictory-zero-usage, normal upgrade/reopen and interrupted-backfill contracts.
Do not assign those fixes again. Remaining observations:

* Negative legacy spend still remains `-0.14` and can lower the budget.
* Malformed legacy tokens still raise a startup TypeError.
* Reconcile reports `confirmed_usd=0.000014` against total `usd=0.001014`.
* Nonfinite pricing raises TypeError instead of returning an unknown settlement.
* The task-prepare `task_identity` NameError remains an out-of-scope GA-02 boundary observation;
  no GA-02 implementation was assigned.

GA-04 has changed its workflow to materialize trusted base code. Its old direct-head-script injection
contract needs adaptation before using that result as a verdict on the new entry point. The bootstrap
path still executes head code when the trusted base has no compatible guard. Heavy CI still omits
workflow/checker changes from its trigger patterns. These require review, not an automatic ACCEPT.
GA-05's deployed proxy/throttle, intermediate-hop and IPv6 contracts remain red on its unchanged SHA.

## What the live smoke actually proved

Task Scheduler launched the existing dispatcher in a separate task, using a shared persistent state,
`IgnoreNew`, Interactive/Limited, a five-minute trigger and a two-hour repetition window.
The old disabled smoke task and all unrelated tasks/processes were left alone.

On Draft #70, exact HEAD `a2b999df0196539361a22bc93a39ce594389ed45`:

1. Codex CLI produced schema-valid P2 findings for `tests/agent_handoff_smoke/value.py`, tied to that SHA.
   Its report explicitly says local shell/test execution was blocked and code was read through GitHub.
   This is not claimed as successful local diff/test execution inside the Codex sandbox.
2. Dispatcher independently reproduced `AssertionError: -4 != 0` with the frozen test.
3. MiniMax edited only the smoke `value.py` to clamp negative values.
4. MiniMax returned nonzero without a final result file. Its runtime session/turn is `aborted`.
5. Dispatcher recorded HALTED, published an owner report, and wrote STOP. No commit/push or second
   Codex review occurred. The scheduled task was then disabled.

After the stop, a read-only diagnostic reran the two tests on the dirty local file: both pass.
That does **not** make the smoke successful: the CLI failed and the changed bytes have no new reviewed
commit. The patch remains uncommitted in the smoke worktree and is preserved as an evidence attachment.
Remote #70 HEAD is unchanged; GA-01/04/05/03 branches were not modified by this run.

## Diagnosed safety break and hardening

The runtime tool configuration was insufficient isolation. The initial preparation incorrectly relied
on it to exclude the main profile's capabilities. The observed MiniMax session could still use `skill`,
`task_query` and n8n MCP tools, and made unrelated `search_workflows`, `list_credentials`, `search_nodes`
read calls after editing the fixture. No workflow activation or media-generation tool appears in this
run's observed tool journal. Credential response contents and private transcripts are not published.

The journal contains nine assistant entries, all ending in tool use and no final answer, with CLI
`--max-steps 8` supplied. The exact abort reason cannot be proven: the first version discarded nonzero
CLI stderr. Step exhaustion is a plausible explanation, not a verified error code.

Future MiniMax execution now requires a dedicated `<state>/minimax-profile`, normal subscription login
there, no profile MCP/plugins/integrations, and explicit process-local data-directory overrides.
The ordinary shared profile is no longer used. Existing credentials are not copied or exported.
A missing login or unexpected capability config blocks before a model launch. Bounded redacted stderr
is retained locally on future nonzero CLI exits. This profile change has **mock proof only**;
capability isolation and successful execution still need a newly authorized live smoke.

New controls also enforce six total reserved CLI launches across jobs, one active PR, subscription-only
authentication checks, a fixed MiniMax account model, terminal GitHub reporting and STOP. A competing
dispatcher lock is a no-op and never stops an already-running job. Final checks: **42 relay tests and
15 compatibility tests pass**, Ruff and diff checks pass. No further live model was used to test these fixes.

## Counts and evidence

| Metric | Actual |
| --- | --- |
| Codex CLI launches | 1 |
| MiniMax CLI launches | 1 |
| Total / session ceiling | 2 / 6 |
| Correcting iterations | 1 attempted |
| Production task model launches | 0 |
| Fix commits / pushes | 0 / 0 |
| Independent review of a new fix SHA | Not performed |
| Scheduler / STOP | Disabled / present |

Launches mean CLI processes, not provider-internal model turns. Token spend or monetary charge is not
inferred from this count. Local checks selected ChatGPT auth and MiniMax token_plan; API/custom providers
were inactive. Billing statements were not inspected.

* [Automatic owner report on #70](https://github.com/gremoled77-droid/gremovod/pull/70#issuecomment-6325326360)
* [Structured live result](evidence/autonomous-smoke-stopped.json)
* [Phase journal](evidence/autonomous-smoke-events.jsonl)
* [Exact-HEAD Codex findings](evidence/autonomous-smoke-codex-review.json)
* [Uncommitted MiniMax patch](evidence/smoke-minimax-uncommitted.patch)

## What awaits the owner

Review this failed smoke and the isolated-profile preparation. A fresh normal login into that profile
and a new explicitly authorized smoke are required before autonomous GA work can resume. Do not clear
STOP, overwrite approvals, reset state/budgets or retry the same PR/SHA automatically. GA-01 remains
CHANGES_REQUESTED. GA-02 and GA-03 runtime remain blocked; no merge/integration is authorized.

Emergency stop (already applied):

```powershell
& 'C:\Users\BLOWKA\aider-test\gremovod-agent-relay\scripts\agent-handoff\Manage-RelayTask.ps1' -Action Stop -StateDirectory 'C:\Users\BLOWKA\aider-test\outputs\autonomous-relay-20261021\state'
```
