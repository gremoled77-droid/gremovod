# Codex ↔ MiniMax: bounded automatic relay

Status: prepared for an explicitly approved smoke; live model execution is not yet proven.
The existing `scripts/agent-handoff/dispatcher.py` owns the loop. No service, new orchestrator,
queue database, Python dependency or model SDK is introduced. Changes are stacked on PR #60,
not integrated into production Studio. The test PR targets this relay branch.

## Diagnosed breaks

| Existing component | Why it did not advance | Change |
| --- | --- | --- |
| PR #56 GitHub handoff | Workflow exports notifications/feedback; it never starts MiniMax. Draft/unmerged workflow is not an installed scheduler. | Keep GitHub as one explicit review source; install the existing dispatcher as a Windows task. |
| PR #57 Dispatcher v1 | Only the official GitHub bot marker on exact HEAD is an actionable review signal. Finishing an IDE conversation creates no such marker. | Add explicit local publication and signed source-specific receipts. No reading hidden VS Code chat storage. |
| PR #59 Dispatcher v2 | Local review writes Markdown but `evaluate` still waits for GitHub. A foreground hourly watch ends with its process. | Bounded job mode consumes local JSON independently; Task Scheduler runs a tick every minute. |
| v2 fixes | Model success/text is not independent test evidence; post-push review worktree is not updated. | Reproduce a frozen regression before the fix; independently test after it; detach reviewer at the new owned SHA. |
| v2 CLI/lifecycle | `gh pr comment` returns a URL but the helper JSON-decodes every result; detached `symbolic-ref` has exit 1; corrupt state resets counters. | Review trigger uses JSON REST; strict worktree checks; corrupt state blocks. |
| PR #60 monitor | It reads legacy snapshots/reports; no dispatcher phase journal exists. | Emit `events.jsonl`; read it through the existing validated AgentEvent parser and watcher, with STOP warning. |

Inspected heads on 2026-10-21: #56 `2ff006a4e09f7427b4eefba3df7f6a2427150f3e`,
#57 `ff05bdc44a5075cf6ceb854ae4c26845690b814a`,
#59 `70324c1ff9929e81d6eecacfc01dec4fc2212174`,
#60 `38b318713a150945b6dd8692e2ee1e28acc9e4f5`.
#59's newer additions are documentation/tests; its dispatcher runtime matches the version inherited by #60.

## Two review contracts

`review.schema.json` requires `version`, numeric `pr_number`, exact 40-character `head_sha`,
`verdict` (`clear` or `changes_requested`) and `findings`. Each finding requires P0/P1/P2,
exact allowed `path`, positive `line`, `title`, `description`, `reproduction`, `test_argv`.
The test argv must already exist in the owner policy; findings cannot inject executable commands.

* `local-codex`: ordinary `codex -a never exec -s read-only --output-schema …`, in a separate
  clean detached worktree. CLI output is validated and atomically published with a local HMAC receipt,
  job digest, base SHA and producer `codex-cli`. A completed IDE review can instead publish JSON
  through `--publish-review result.json --attest-local`; this is explicitly **owner-attested-ide**,
  not proof that an arbitrary JSON came from Codex. The active scheduler discovers the receipt on its next tick.
* `github-codex`: only the official `chatgpt-codex-connector[bot]` exact-HEAD completed marker
  is accepted. Structured findings are normalized from that bot's exact-SHA inline comments with
  P0/P1/P2, file and line. The adapter associates the first owner-approved regression argv and
  independently reproduces it; the bot does not supply a trusted executable test command.
  Missing inline details block. After push a bounded `@codex review` request is recorded before submission;
  an uncertain response never causes an automatic second request. Initial review must already be requested.

Sources never silently substitute for each other. Duplicate identical receipts are idempotent;
conflicting results for the same source/SHA block. Structured publication alone grants no model budget.
An already approved job may consume newly published local findings without opening any chat.

## Owner policy and authorization

Copy `relay-job.example.json` outside model worktrees. Set the actual numeric PR, branches,
separate absolute developer/reviewer worktrees, exact editable files and immutable regression files.
Use the absolute Python interpreter running dispatcher in every `tests` argv. Tests are argv arrays,
without a shell. `expected_failure` must identify the actual regression assertion, not generic exit 1.
Smoke policy is constrained to `tests/agent_handoff_smoke/`; canonical GA branches retain their own contract.

The controller must live outside both model worktrees. State, signing key and approval must also live
outside them. Keep state durable between runs: deleting/recreating it discards local dedupe history.
Restrict the state directory to the owner using Windows directory permissions; HMAC and `smart` do not
create an OS security boundary against another process running as the same user.

Before `--arm`, show the owner the actual PR, diff, job JSON and expense bounds, and obtain explicit consent.
`--arm` binds policy, controller/schema hashes, initial HEAD, base SHA, immutable test hashes, and expires
in two hours. Changing these requires owner review. Do not automatically re-arm or erase budgets.
Legacy `--execute` / `--codex-review` paid modes now reject execution; migrate their callers to job mode.
VS Code tasks deliberately contain no automatic arm action.

```powershell
$python = 'C:\AI_Workflow_Studio\.venv\Scripts\python.exe'
$controller = 'C:\path\to\relay-controller\scripts\agent-handoff\dispatcher.py'
$job = 'C:\path\outside-models\job.json'
$state = 'C:\path\outside-models\state'
& $python $controller --job $job --validate-only # local validation; no network/model/state
& $python $controller --job $job --state-dir $state # GitHub plan, no models
# ONLY after explicit owner consent to the concrete budget:
& $python $controller --job $job --state-dir $state --arm
# Optional manual tick; same action as Scheduler:
& $python $controller --job $job --state-dir $state --run
```

To publish a completed IDE review, ask that review to return the schema JSON, save it, inspect it,
then use the same controller/job/state with `--publish-review result.json --attest-local`.
No paid call occurs during publication. Do not publish model-generated shell instructions.

## Windows Task Scheduler

Use an interactive, signed-in Windows user already authenticated to GitHub, Codex and MiniMax.
The scheduler does not export credentials or log in for the user. Keep the controller checkout fixed
while an approval is active. Installation does not call models and is **disabled by default**.

```powershell
$manage = 'C:\path\to\relay-controller\scripts\agent-handoff\Manage-RelayTask.ps1'
& $manage -Action Install -Job $job -Python $python -StateDirectory $state -ValidateOnly
& $manage -Action Install -Job $job -Python $python -StateDirectory $state `
  -TaskName GremoVOD-AgentRelay-Smoke-20261021
# ONLY after owner consent and successful --arm:
Enable-ScheduledTask -TaskName GremoVOD-AgentRelay-Smoke-20261021
Start-ScheduledTask -TaskName GremoVOD-AgentRelay-Smoke-20261021
& $manage -Action Status -StateDirectory $state -TaskName GremoVOD-AgentRelay-Smoke-20261021
```

The trigger repeats every minute, `MultipleInstances=IgnoreNew`, `RunLevel=Limited`, interactive logon.
A cross-process OS lock also protects the shared state. Every approved job has its own policy;
sharing the same state directory retains global PR/SHA dedupe and STOP. Existing named tasks are never overwritten.
The task time limit includes both model deadlines, before/after tests and a shutdown margin.
The model runner observes STOP every 0.2 seconds and terminates its own child process tree.
If termination cannot be confirmed, it reports `PROCESS_TERMINATION_UNCONFIRMED` for manual inspection.

**Stop all relay jobs sharing this controller/state directory with one command:**

```powershell
& $manage -Action Stop -StateDirectory $state
```

This writes persistent STOP first and disables matching relay scheduled tasks. For emergency use without
ScheduledTasks access: `& $python $controller --stop --state-dir $state` blocks further calls and stops owned children.
STOP is not automatically cleared. Do not delete state to restart: inspect the halt, local diff/commit,
remote SHA and budgets; prepare a new explicit owner decision. Other agents/tasks are not killed.

## Loop and failure behavior

One tick obtains a source-specific exact-HEAD review. For changes requested:
reproduce the expected failure → MiniMax smart → verify scope/index/HEAD/protected tests → independent
tests → check byte snapshots → stage exact paths → commit → ordinary push to the exact allowed branch.
The next tick reviews that new SHA. A clear review still requires green tests, then stops at
`CLEAR_WAITING_OWNER`; it never merges or advances to another GA task.

The maximum is three correcting iterations per task; tighter policy limits take precedence.
PR/SHA launch records and counters are saved before model submission. Timeout, nonzero exit, stale HEAD/base,
dirty worktree, unexpected index/files, protected-test change, missing reproduction, failed tests, budget
exhaustion or interrupted phase stops the job. An uncertain restart becomes `UNKNOWN_AFTER_RESTART`, not a retry.
No force-push, main modification, merge, or paid media generation command is part of this controller.
MiniMax is always `--permission smart`; `full` is never selected.

`smart` is MiniMax's permission policy, not a filesystem/network sandbox. Exact allowed-file checks protect
what dispatcher commits/pushes and detect ordinary concurrent edits; they cannot undo arbitrary side effects
of an independently compromised CLI or freeze another same-user writer. Keep smoke worktrees isolated.
Model-call/time/step limits are enforced; subscription token cost and provider-internal tool usage are not
an exact monetary cap. Logs use heuristic credential redaction, not a proof that arbitrary output has no secrets.

## Evidence and Agent Monitor

Run mocks first, without models/network:

```powershell
& $python -X utf8 -m unittest discover -s scripts/agent-handoff -p 'test_dispatcher.py' -q
& $python -X utf8 -m unittest discover -s scripts/agent-handoff -p 'test_relay.py' -q
cd extensions/agent-monitor
npm test
```

The relay suite uses real temporary Git commits, a local bare remote, independent Python tests,
and mocked models/GitHub. It covers both contracts, IDE publication, budgets/dedupe, stale SHA,
source/signature mismatch, failed/setup/green tests, dirty/conflicting files, STOP, timeout, restart and lock.
`evidence/relay-mock-summary.json` and the corresponding JSONL show a captured mock cycle.
They are **not live subscription or GitHub E2E proof**.

Build the monitor from this branch and set `gremovodAgentMonitor.dispatcherDirectory` to `$state`.
It reads validated `events.jsonl` phases (review, reproduction, fix, tests, commit, push, halt/clear) and STOP.
Its own journal remains separate. A phase is a timestamped observation, not an inferred live heartbeat.
Test reports are `PR-N-SHA-reproduction-tests.json` and `PR-N-SHA-tests.json`;
post-fix tests describe the working tree at the reviewed HEAD, followed by the controller's commit in the journal.
Signed review receipts are under `reviews/`, owner approval under `approvals/`; never publish `.publisher-key`.

Prepare one Draft smoke PR containing only the intentionally broken `nonnegative` fixture and its frozen
regression. Bound it to one MiniMax call (8 steps/120s), two Codex calls (180s each), test timeout 30s,
one correcting iteration. Obtain explicit consent **before** arming/enabling. After the permitted smoke,
record initial/fixed SHAs, model call counters, immutable test hash, green independent tests, second exact-HEAD
review and terminal phase; stop the task and attach a redacted evidence summary. Until then live proof remains pending.
