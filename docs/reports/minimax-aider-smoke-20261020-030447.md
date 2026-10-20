# MiniMax Code + Aider smoke test — GremoVOD

- **Date/time and timezone:** 2026-10-20, 03:04–03:12 MSK (UTC+3)
- **Repository root:** `C:\AI_Workflow_Studio` (remote `https://github.com/gremoled77-droid/gremovod.git`)
- **Test worktree:** `C:\AI_Workflow_Studio\.worktrees\minimax-aider-smoke-20261020-030447`
- **Branch:** `test/minimax-aider-smoke-20261020-030447`
- **Git base commit SHA:** `40ca333796a686acab4f0261381924eaf6a82276` (HEAD of `experiment/minimax-aider`, branched off as a separate worktree — the main working tree has foreign uncommitted changes and was not touched)
- **MiniMax Code version:** CLI `mcode` is not present in `PATH`; this test was executed by the running MiniMax Code agent (MCode, model `MiniMax-M3.1-Flash`)
- **Aider version:** `aider 0.86.2` (pre-installed via `uv tool install aider-chat`; not reinstalled)
- **Python version used for tests:** `Python 3.13.14` (system interpreter, `python -B`)
- **Model requested by Aider:** `openai/MiniMax-M3.1-Flash` (weak model identical)
- **API endpoint domain:** `api.minimax.io` (base URL `https://api.minimax.io/v1`, OpenAI-compatible)
- **Authentication present:** yes — key read from the local DPAPI-encrypted store and injected into the Aider process as `OPENAI_API_KEY`; the value was never printed, never passed as a CLI argument, never written to the repository or to logs
- **Baseline tests:** 5 total / **3 failed** (`test_twenty_percent`, `test_ten_percent`, `test_floor_partial_cent`); process exit code **1**
- **Aider invoked:** yes; exit code **0**; duration **20.9 s**
- **calc.py SHA256 before/after:** `FACD8F17A6CD` → `1B58D7E071BC` (changed)
- **Final tests:** 5 total / **5 passed**; process exit code **0**
- **Unintended file changes:** none in project code. Two non-code side effects, both excluded from the commit:
  - `.aider.tags.cache.v4/` — Aider's tag cache directory created in the worktree root (untracked, not committed). `HEAD` of this branch does not contain the `.aider*` ignore rule.
  - Aider chat history and input history were redirected outside the repository to `%TEMP%\gremovod-aider-20261020-030447-*` and are not part of Git.
  - `tools/` is matched by `.gitignore` in this repo, so the three test files are invisible to plain `git status`; they were added with `git add -f`.
- **Git commit SHA:** recorded in the handoff message and in the follow-up metadata commit of this branch
- **GitHub push:** see the follow-up metadata commit of this branch (result reported in the handoff message)
- **PR URL:** see the follow-up metadata commit of this branch (draft PR, reported in the handoff message)
- **Token usage / money:** Aider measured **4.7k tokens sent / 586 received** and reported **$0.0011** for the message, computed from the official MiniMax pay-as-you-go rate for `MiniMax-M3.1-Flash` ($0.15/M input, $0.60/M output). The MiniMax Code side of this test was not measured. Whether the M Plan subscription quota or a pay-as-you-go balance absorbs this amount was **not** independently verified.
- **Problems and remediation:**
  1. `--no-gitignore` in Aider 0.86.2 means *"do not add `.aider*` to `.gitignore`"*, **not** *"ignore `.gitignore` when selecting files"*. Because `tools/` is listed in `.gitignore` (line 30), Aider skipped the target file with `Skipping ... that matches gitignore spec`. **Remediation:** the run used `--add-gitignore-files` in addition to the prescribed `--no-gitignore`. This is the only deviation from the prescribed command line, and it is required for the target file to be editable at all.
  2. The prescribed command passes `--yes`. With `--yes`, Aider auto-confirms *"Add file to the chat?"*, so `.gitignore` (mentioned in the task text) was added to the chat. It was **not** modified — SHA-256 `F6045706440F` before and after the run. `--yes` was used only for this single bounded test and was not propagated into any shared configuration.
  3. `tools/` being gitignored means the smoke-test files need `git add -f` to be committed. No `.gitignore` rule was modified — the task forbids touching `.gitignore`, and it was left byte-identical.
  4. `git commit` in this repository prints a benign background-maintenance error `task 'geometric-repack' failed: Permission denied` (Git cannot rename a pack file while it is open). The commit itself succeeds; it is a local maintenance warning, not a data problem.
- **Verdict:** **PASS**
- **Recommended next step:** keep Aider as a *point executor* for isolated, well-specified single-file patches with a machine-verifiable acceptance test (exactly this scenario). Do not route open-ended product work through it: the model's context is dominated by a 2048-token repository map, and it answers with a `SEARCH/REPLACE` block even for read-only questions, which makes interactive supervision mandatory. Before any wider rollout, add `--add-gitignore-files` awareness to the launch configuration and keep the DPAPI key store as the only key source.

---

## What actually happened (evidence)

1. **MiniMax prepared the check.** Created the intentionally broken `calc.py`, the `unittest` suite `test_calc.py` and the task text `aider_task.txt` in `tools/agent_smoke/minimax_aider_smoke/`. Baseline run: 5 tests, 3 failures, exit code 1 — the failure is expected, not a defect.
2. **Aider really ran.** One synchronous invocation of the `aider` binary as a separate process (exit code 0, 20.9 s). Startup banner: `Aider v0.86.2`, `Model: openai/MiniMax-M3.1-Flash with diff edit format`, `Git repo: ..\..\.git\worktrees\minimax-aider-smoke-20261020-030447 with 530 files`, `Repo-map: using 2048 tokens`. Log excerpt:
   ```
   Added tools\agent_smoke\minimax_aider_smoke\calc.py to the chat.
   ...
   <<<<<<< SEARCH
       return amount_cents  # Intentionally wrong: ignores tax.
   =======
       return amount_cents + (amount_cents * tax_percent) // 100
   >>>>>>> REPLACE
   ...
   Tokens: 4.7k sent, 586 received. Cost: $0.0011 message, $0.0011 session.
   Applied edit to tools\agent_smoke\minimax_aider_smoke\calc.py
   ```
3. **MiniMax independently confirmed it.** File hashes, file contents, the absence of side-effect edits and the test suite were all re-checked after the process exited — the verdict does not rely on Aider's own claim of success.

### Exact diff of the Aider edit

```diff
--- a/calc.py
+++ b/calc.py
@@ -2,4 +2,4 @@ def total_with_tax(amount_cents: int, tax_percent: int) -> int:
     """Return integer cents with tax added; round down partial cents."""
     if amount_cents < 0 or tax_percent < 0:
         raise ValueError("Inputs must be non-negative")
-    return amount_cents  # Intentionally wrong: ignores tax.
+    return amount_cents + (amount_cents * tax_percent) // 100
```

1 file changed, 1 insertion(+), 1 deletion(-).

### Integrity checks

| File | SHA-256 before | SHA-256 after | Verdict |
| --- | --- | --- | --- |
| `tools/agent_smoke/minimax_aider_smoke/calc.py` | `FACD8F17A6CD` | `1B58D7E071BC` | changed by Aider — expected |
| `tools/agent_smoke/minimax_aider_smoke/test_calc.py` | `5F42892827A6` | `5F42892827A6` | untouched |
| `tools/agent_smoke/minimax_aider_smoke/aider_task.txt` | `FE4A86585FFD` | `FE4A86585FFD` | untouched |
| `.gitignore` | `F6045706440F` | `F6045706440F` | untouched |

---

## Why Aider at all, when MiniMax Code can edit files itself

**Where Aider adds real value**

- **An independent executor with its own acceptance criteria.** Aider runs the edit as a separate process against the repository, applies a patch, and reports the result — it does not share the coordinator's "I believe it is fixed" bias. Here it produced the patch, and the coordinator verified it independently by hash and by an independent test run.
- **A narrow, reviewable contract.** The task was handed over as one file and one instruction block. The blast radius was bounded by construction, and the diff is one line — easy to review, easy to revert.
- **A repeatable machine-checkable loop.** `calc.py` → `unittest` → Aider → `unittest` is an automatable gate that can be reused in CI, not just in a conversation.
- **Provider decoupling.** The executor talks to `api.minimax.io` through an OpenAI-compatible interface, independent of the agent runtime. The executor can be swapped, throttled or removed without touching the coordinator.

**Where Aider is redundant or harmful**

- **For ordinary editing inside MiniMax Code it is strictly worse.** Aider re-scans the repository, builds a 2048-token map, pays for an extra round trip and then answers with a `SEARCH/REPLACE` block — even for read-only questions where no code change was requested at all.
- **It has no product context.** It sees the repository map, not the task history, the project canon, the character vault or the user decisions. In GremoVOD those live in `AGENTS.md`, `CLAUDE.md` and `docs/`; Aider has to rediscover them.
- **It needs constant supervision.** Without a terminal it treats EOF as "yes" and applies edits; with `--yes` it can even create empty files from words in the prompt. Interactive confirmation is not optional.
- **It has its own failure modes.** In this very run the prescribed `--no-gitignore` flag did not mean what the author expected, and `tools/` being gitignored would have blocked the edit completely — a configuration trap that costs more time than the edit saves.

**Recommendation:** keep Aider as a *point executor* for isolated, well-specified single-file patches with a machine-verifiable acceptance test. Do not connect it automatically to general development work in GremoVOD.

---

## Scope statement

This is a single bounded probe of the toolchain on an artificial 5-line module. It is **not** evidence that Aider produces good quality on large GremoVOD features, and it is not evidence about the quality of AI-assisted development in general.
