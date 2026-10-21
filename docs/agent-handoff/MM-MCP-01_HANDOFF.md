# MM-MCP-01 — MiniMax MCP Bridge, independent review handoff

Reviewer: MM-MCP-01 pass over PR #72. Scope: compatibility with the installed
`mcode exec` interface, isolation, diagnostics, and offline testing with a mock
subprocess. **No live model call was made**, PR #72 was not modified, nothing was
merged, force-pushed or activated.

## 1. BASE SHA and HEAD SHA

| Item | Value |
| --- | --- |
| PR #72 head (`feature/minimax-mcp-bridge`) | `4d709112855280ee7f77cdfe6e201698ca1dd64e` |
| BASE / merge-base with `feature/codex-minimax-relay` | `fcac8fda1ed4932be9e77a9d4d29e86d0971e111` (= PR #69 head) |
| Review branch | `review/mm-mcp-01-minimax-mcp-bridge`, branched from the exact PR #72 head |
| Review branch head | see the branch tip; the only parent is the PR #72 head above |

The review branch is a descendant of the PR #72 head and contains only the changes
listed in section 4.

## 2. What was checked

Environment: Windows 10 x64, Python 3.13.14, Node 24.16.0,
**MiniMax Code CLI 0.6.12** (`@minimax-ai/code`, installed under
`%USERPROFILE%\.minimax-code\releases\0.6.12`). The CLI bundle was read directly to
establish the real contract; the offline probes below were run against the installed
binary.

### Task 1 — CLI compatibility

* `mcode exec --help` confirms every flag the bridge relies on: `--cwd`, `--config`,
  `--mode standard|lightweight`, `--prompt-mode tui|coding|work`,
  `--permission smart|full|off` (`ask` is refused in a non-interactive host),
  `--timeout`, `--max-steps`, `--output-format text|json|stream-json`,
  `--diagnostics-dir`, `--output-last-message`, `--input -`, `--input-format text|json`.
* `--output-format json` writes **exactly one JSON object** (the `ExecResult`,
  `type: "exec.result"`) plus a newline. `stream-json` is the JSONL variant and needs
  an event projector. The bridge's `json.loads(record["stdout"])` is therefore correct.
* ExecResult `status` is one of `succeeded | failed | timeout | cancelled | limit_exceeded`.
  There is no `aborted` status.
* Exit codes: `success 0, invocation 2, config 3, runtime 4, timeout 6, limit 7,
  internal 70, cancelled 130, brokenPipe 141`. **Every non-succeeded status yields a
  non-zero exit code.**
* `--mode lightweight` replaces the system prompt and sets **`tools: []`**. The model
  receives no tool at all: the "proposal-only, no model tools or file edits" claim is
  enforced by the CLI, not by the prompt text.
* `--permission smart` maps to the internal `auto` mode. An interaction request in a
  headless host becomes `awaiting-user-continuation`, which the CLI converts to status
  `failed` with `INTERACTION_NOT_AVAILABLE` and a non-zero exit code, so the bridge
  fails closed.
* `--mode lightweight` requires a new session. The bridge passes neither `--session` nor
  `--continue`, so it is compliant.
* `--input -` reads the prompt from stdin. Verified on Windows through a real pipe,
  the same mechanism `bridge.capture()` uses, with a cwd that contains spaces.
  (A PowerShell pipeline is not a reliable stdin source for this CLI — a shell quirk,
  not a CLI defect.)
* `MINIMAX_DATA_DIR` / `MAVIS_DATA_DIR` take priority over the default data dir, so
  the profile redirect works.
* The CLI resolves the credential region from the credential-state file inside the data
  dir, so a copied `auth` subtree is self-describing.
* `provider list --json` shape matches the bridge's expectations exactly:
  `{minimaxModelSource, providers[{providerId, name, kind, active, enabled, readOnly,
  hasApiKey, models}]}`.
* `subprocess.Popen(argv, shell=False)` with a list: no quoting problem on Windows for
  paths with spaces, and the bridge passes absolute paths only.

### Task 2 — isolation

* The child environment is rebuilt from scratch: only `SystemRoot`, `WINDIR` and
  `COMSPEC` are inherited, plus `HOME`/`USERPROFILE`/`APPDATA`/`LOCALAPPDATA`/
  `XDG_*` redirected to the request root and `MINIMAX_DATA_DIR`/`MAVIS_DATA_DIR`
  pointed at the profile. **No secret of the main profile is reachable through the
  environment** — this was verified with a mock worker that asserts the absence of
  `OPENAI_API_KEY`, `MINIMAX_API_KEY`, `NODE_OPTIONS`, `PYTHONPATH`, `CODEX_HOME`,
  `HTTPS_PROXY`.
* The main profile of this machine contains `mcp.json`, `mcp-runtime-names.json`,
  `config.yaml` with `custom_provider` API keys, `permission.json: bypassPermissions`,
  `credentials/`, `integrations/`, `plugins/` and `skills/`. None of it can be
  inherited once the CLI is pointed at a bridge-created runtime profile.
* `--mode lightweight` exposes no tools, so the model cannot reach the filesystem, the
  worktree or any worktree at all. The isolation of the *model* surface is structural.
* `smart` is **not** an OS sandbox: the child is an ordinary process with the user's
  rights. The real containment comes from the empty tool set, the redirected
  environment and the login-only data dir — not from the permission mode.
* The bridge cannot perform a real call without the owner grant: the grant is bound to
  the exact request digest, the exact head SHA and the PR number, is single use, and
  the call budget is 1.
* The data dir the CLI is given is populated by the CLI itself — see P1-1. This is the
  core isolation defect of the reviewed revision.

### Task 3 — diagnostics

Stored per request: request id, exact head SHA, PR number, status, error code, exit
code, bounded stdout/stderr, start/finish timestamps and the exact input SHA
(`result_sha`). `events.jsonl` keeps only id/SHA/status/error/exit code; `state.json`
keeps the bounded redacted output. Secrets are stripped with a regex before
persistence, and the journal never receives prompts, file contents or provider output.
Unbounded output is capped at 16 KB per stream. Timeout, cancellation and output
overflow each produce a distinct error code. Confirmed by the test suite and by
`test_mm_mcp_01.py`.

### Task 4 — offline testing

All new tests drive the shipped `mock_worker.py` subprocess. No model, no network, no
paid API. Covered: successful JSON answer, launch failure, non-zero exit code,
timeout, cancellation, repeated request, corrupted JSON, authorization refusal and a
Windows path containing spaces.

## 3. Findings

### P1-1 — the live path is unreachable: `PROFILE_NOT_LOGIN_ONLY` can never pass

`live_preflight()` requires the CLI data dir to contain nothing except
`auth/**/auth.json`. But the CLI writes its own bootstrap trees into whatever data dir
it is given. Measured with an empty `MINIMAX_DATA_DIR` and a single
`mcode provider list --json`:

```
config.yaml, .builtin-skills/ (hundreds of files), agents/.builtin/, auth/auth.lock,
auth/<env>/<region>/mcode-public/auth.lock, bin/, cache/models-dev-catalog.json (6 MB),
integrations/, plugins/, run/, v2/sqlite/runtime-state.sqlite (1.1 MB), ...
```

A profile produced by a real `mcode login` additionally contains
`auth/prod/<region>/mcode-public/auth-state.json` and `auth/auth.lock`, both of which
the old scan rejects as well. `live_preflight()` is called twice — the provider probe
runs *between* the two calls, and the probe is exactly what populates the directory —
so the second call can never pass either.

Net effect: **every live request fails before any model is launched.** The failure is
fail-closed, so this is a functional blocker rather than a security hole. The existing
test `test_live_command_contract_with_mocked_transport` does not catch it because it
mocks `capture()`, so the data dir is never touched.

Fix in this branch: the owner profile is never handed to the CLI. The bridge seeds a
**fresh per-request runtime profile** containing only the `auth` subtree and verifies
*that* directory is login-only. Foreign state is now excluded by construction instead
of by inspection.

### P1-2 — the subscription check is vacuous

`provider list --json` returns an **identical** `minimax_oauth` entry for a signed-in
profile and for a completely empty one:

```json
{"providerId": "minimax_oauth", "name": "MiniMax OAuth", "kind": "minimax-oauth",
 "active": true, "enabled": true, "readOnly": true, "hasApiKey": false, "models": []}
```

`minimaxModelSource` is `"token_plan"` in both cases, and the human-readable table is
identical too (`active  managed login`). The bridge's gate

```python
status.get("minimaxModelSource") != "token_plan" or not any(
    p.get("providerId") == "minimax_oauth" and p.get("active") for p in status["providers"]
)
```

therefore proves only that the CLI started. The advertised `subscription_only`
guarantee was not evidenced.

Fix in this branch: the credential-state file
`auth/<env>/<region>/mcode-public/auth-state.json` is the only local evidence of a
subscription login. The bridge now requires it and requires `status == "authenticated"`.

### P2-1 — incomplete denied-status set (latent fail-open)

The bridge rejected `status in {"failed", "aborted", "cancelled"}`. The CLI can also
return `timeout` and `limit_exceeded`, and never returns `aborted`. Not exploitable
today, because the exit-code check fires first (`timeout` → 6, `limit_exceeded` → 7,
`failed` → 3/4/70, all non-zero), but the deny-list is a fail-open shape that would
become exploitable if the exit-code check were ever removed.

Fix in this branch: only `succeeded` may be recorded as a result (live mode); the mock
fixture, which emits no status, keeps its own branch.

### P2-2 — the runtime data dir grows without bound

Each CLI run writes roughly 7 MB into the data dir (6 MB model catalogue, 1.1 MB
sqlite). A per-request runtime profile is created per request and never pruned, and
the 16 KB `OUTPUT_LIMIT` does not apply to the data dir. The state dir therefore grows
with every call. The bridge limits calls to 3 per policy, but a restart resets the
directory policy and not the disk.

### P2-3 — `PATH` is not passed to the child

`isolated_environment()` inherits only `SystemRoot`, `WINDIR` and `COMSPEC`. The CLI
starts and answers `provider list --json` with exit 0 without `PATH`, so this does not
break today; but any CLI feature that resolves an external binary by name (`git`,
`sh`) degrades silently instead of failing loudly.

### Verified as correct — no defect found

* `--output-format json` emits a single JSON object, so the parse is right.
* Every non-succeeded ExecResult status has a non-zero exit code.
* `--mode lightweight` sets `tools: []`: the model has no tools, so the proposal-only
  property is structural.
* `smart` refuses nothing silently: an interaction request becomes a failed run with a
  non-zero exit code.
* The child environment leaks no main-profile secret.
* The journal keeps no prompt, no file content and no unbounded log.

## 4. Changed files and diff --stat

```
 scripts/minimax-mcp/bridge.py         | 101 ++++++++--
 scripts/minimax-mcp/test_bridge.py    |  32 ++-
 scripts/minimax-mcp/test_mm_mcp_01.py | 370 ++++++++++++++++++++++++++++++++++
 3 files changed, 487 insertions(+), 16 deletions(-)
```

* `scripts/minimax-mcp/bridge.py`
  * `AUTH_FILES = ("auth.json", "auth-state.json")`.
  * New `seed_profile(source, target)`: copies only the `auth` subtree into a fresh
    per-request runtime profile, rejects unknown files, and requires a credential
    state with `status == "authenticated"`.
  * `live_preflight(request_digest, head_sha)` →
    `live_preflight(request_id, request_digest, head_sha)`; the grant check moved to
    `live_grant(request_digest, head_sha)`.
  * `execute()` / `run()`: the full profile check runs once before any launch; the
    post-probe call re-checks the grant only, because the CLI owns the runtime
    directory by then.
  * Result validation now accepts only a `succeeded` ExecResult.
* `scripts/minimax-mcp/test_bridge.py`: the profile fixture now provides a credential
  state; the foreign-profile test asserts the new invariant (foreign owner state is
  not copied) instead of the unreachable deny-list; the mocked live transport returns
  a realistic `succeeded` ExecResult.
* `scripts/minimax-mcp/test_mm_mcp_01.py` (new): 22 offline tests — 9 mock-subprocess
  scenarios, runtime-profile isolation, and diagnostics.

## 5. Exact test commands and exit codes

All commands were run from the repository root with a worktree-local virtualenv
(`.venv`, gitignored) holding `mcp==1.28.0`, `jsonschema` and `ruff`.

```
python -X utf8 -m unittest discover -s scripts/minimax-mcp -p test_bridge.py -q
    -> Ran 33 tests, OK, exit 0        (baseline on the untouched PR #72 head)

python -X utf8 -m unittest discover -s scripts/minimax-mcp -p 'test_*.py' -q
    -> Ran 53 tests, OK, exit 0        (this branch)

python -m ruff check scripts/minimax-mcp/
    -> All checks passed!, exit 0

python -m ruff format --check scripts/minimax-mcp/
    -> 8 files already formatted, exit 0
```

Red/green proof for the two P1 findings, using the PR #72 head of `bridge.py` and the
patched file side by side against the same fixtures (no model call):

```
realistic `mcode login` profile (auth + bootstrap trees)
  HEAD    -> RESULT: DENIED  -> PROFILE_NOT_LOGIN_ONLY        (live path unreachable)
  patched -> RESULT: ALLOWED -> runtime profile holds auth/ only

minimal profile, auth.json only, no credential state
  HEAD    -> RESULT: ALLOWED                                    (vacuous subscription check)
  patched -> RESULT: DENIED  -> SUBSCRIPTION_AUTH_UNVERIFIED
```

## 6. PASS / FAIL

| Item | Result |
| --- | --- |
| CLI interface compatibility (Task 1) | PASS — with the two P1 findings above |
| Isolation (Task 2) | PASS after the fix; **FAIL** on the PR #72 head (P1-1, P1-2) |
| Diagnostics (Task 3) | PASS |
| Offline test coverage (Task 4) | PASS — 53 tests, exit 0 |
| Ruff lint and format | PASS — exit 0 |
| Live end-to-end behaviour | **NOT VERIFIED** — no live model call was permitted |

## 7. Unverified risks

* The live path was never executed end to end. The provider probe, the ExecResult
  shape, the exit-code table and the region resolution were established from the
  installed 0.6.12 bundle and from local offline probes, not from a live run.
* A real `mcode login` into the isolated profile was not performed in this review. The
  fixtures use a synthetic `auth.json` (`{}`) and a synthetic credential state.
* `verify_codex.py` and the Codex CLI 0.160.0 integration proof were not re-run; the
  evidence file `minimax-mcp-codex-offline.json` still describes head `b9d5720`.
* The backend suite (`python -X utf8 -m unittest discover -s backend -p "test_*.py"`)
  and the frontend suite were not run: this change touches only `scripts/minimax-mcp`,
  and the review venv holds only the MCP SDK. Codex should run the full repo checks.
* Requiring `status == "authenticated"` rejects a credential that merely needs a
  refresh, even though the CLI could refresh it. Codex may prefer to accept the
  refreshable states.
* If an `auth` subtree holds two regions, the CLI's own resolution requires exactly
  one matching region and otherwise falls back to `cn`. Not exercised.
* The per-request runtime profile is ~7 MB and is not pruned (P2-2).
* Windows Job Object containment and descendant termination were exercised on this host
  only.
* The pre-fix behaviour was compared statically and with probes; the pre-fix live flow
  was never executed with a model.

## 8. What Codex should check independently

1. Whether seeding a **per-request runtime profile** is the intended design, or
   whether the owner profile was meant to be handed to the CLI directly with a
   scan-based allowlist of CLI bootstrap trees. This changes the operator workflow:
   the owner must keep a login-only profile in `<state_dir>/minimax-profile`, and the
   bridge copies the credential into a throwaway directory.
2. Whether `status == "authenticated"` is the right bar for a subscription login, and
   whether a refreshable `expired` state should also be accepted.
3. Whether "only `succeeded` may be recorded" is acceptable for the live path, and
   whether the mock fixture should be changed to emit a real ExecResult instead of
   keeping the status-free branch.
4. Whether the ~7 MB per-request data-dir growth needs pruning or a size cap.
5. Whether a minimal `PATH` should be passed to the child.
6. Whether `auth-state.json` must be copied, given it is credential state rather than
   the credential itself, and whether copying it into a derived directory is
   acceptable under the project's credential-handling rules.
7. The full repository checks (backend and frontend), which this review did not run.
8. The P1 findings against the current PR #72 head, in case #72 has changed since
   `4d709112855280ee7f77cdfe6e201698ca1dd64e`.
