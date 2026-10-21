"""Real local Git + real independent tests; models and GitHub are mocked, never invoked."""

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

spec = importlib.util.spec_from_file_location(
    "relay_dispatcher", Path(__file__).with_name("dispatcher.py")
)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

REL = "tests/agent_handoff_smoke/value.py"
TEST = "tests/agent_handoff_smoke/test_value.py"
BAD = "def nonnegative(value):\n    return value\n"
GOOD = "def nonnegative(value):\n    return max(0, value)\n"


class RelayTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.wt, self.reviewer, self.origin = (
            self.root / n for n in ("developer", "reviewer", "origin.git")
        )
        self.state_dir = self.root / "state"
        self.wt.mkdir()
        self.git("init", cwd=self.wt)
        self.git("config", "user.name", "Relay Offline Test")
        self.git("config", "user.email", "relay-test@local.invalid")
        self.git("checkout", "-b", "feature/codex-minimax-relay")
        (self.wt / "README.md").write_text(
            "isolated offline fixture\n", encoding="utf-8"
        )
        self.git("add", "README.md")
        self.git("commit", "-m", "base")
        self.base = self.git("rev-parse", "HEAD")
        self.branch = "minimax/relay-smoke-offline"
        self.git("checkout", "-b", self.branch)
        (self.wt / REL).parent.mkdir(parents=True)
        (self.wt / REL).write_text(BAD, encoding="utf-8")
        (self.wt / TEST).write_text(
            "import unittest\nfrom value import nonnegative\n"
            "class Regression(unittest.TestCase):\n"
            "    def test_negative(self): self.assertEqual(nonnegative(-4), 0)\n"
            "    def test_positive(self): self.assertEqual(nonnegative(7), 7)\n",
            encoding="utf-8",
        )
        self.git("add", "--", REL, TEST)
        self.git("commit", "-m", "failing regression")
        self.initial = self.git("rev-parse", "HEAD")
        self.git("init", "--bare", str(self.origin))
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-u", "origin", self.branch)
        self.git("worktree", "add", "--detach", str(self.reviewer), self.initial)
        self.job = {
            "version": 1,
            "repo": d.REPO,
            "pr_number": 7001,
            "task_id": "SMOKE-OFFLINE",
            "branch": self.branch,
            "base": "feature/codex-minimax-relay",
            "worktree": str(self.wt),
            "review_worktree": str(self.reviewer),
            "review_source": "local-codex",
            "allowed_paths": [REL],
            "verification_paths": [TEST],
            "tests": [
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "tests/agent_handoff_smoke",
                    "-p",
                    "test_*.py",
                ]
            ],
            "max_cycles": 3,
            "expected_failure": "AssertionError: -4 != 0",
            "max_minimax_calls": 3,
            "max_codex_calls": 4,
            "minimax_timeout_seconds": 30,
            "codex_timeout_seconds": 30,
            "test_timeout_seconds": 10,
            "max_steps": 4,
        }
        self.path = self.root / "job.json"
        self.write_policy()
        self.model_calls = {"codex": 0, "minimax": 0, "github_request": 0}
        self.fixed_contents = GOOD
        self.always_findings = False
        self.patches = [
            mock.patch.object(d, "fetch_pr", side_effect=self.fetch_pr),
            mock.patch.object(d, "run_codex_review", side_effect=self.codex),
            mock.patch.object(d, "run_minimax", side_effect=self.minimax),
            mock.patch.object(
                d, "request_codex_review", side_effect=self.github_request
            ),
            mock.patch.object(d, "pages", side_effect=self.github_pages),
            mock.patch.object(d, "assert_remote"),
            mock.patch.object(d, "subscription_preflight"),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def git(self, *args, cwd=None):
        p = subprocess.run(
            ["git", *args],
            cwd=str(cwd or self.wt),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        return p.stdout.strip()

    def write_policy(self):
        self.path.write_text(json.dumps(self.job), encoding="utf-8")
        self.job = d.load_job(self.path)

    def fetch_pr(self, number):
        return {
            "number": number,
            "state": "open",
            "merged": False,
            "head": {
                "ref": self.branch,
                "sha": self.remote_sha(),
                "repo": {"full_name": d.REPO},
            },
            "base": {"ref": self.job["base"], "sha": self.base},
        }

    def remote_sha(self):
        return self.git("--git-dir", str(self.origin), "rev-parse", self.branch)

    def review(self, sha=None, verdict=None):
        bad = self.always_findings or (self.wt / REL).read_text(encoding="utf-8") == BAD
        verdict = verdict or ("changes_requested" if bad else "clear")
        return {
            "version": 1,
            "pr_number": self.job["pr_number"],
            "head_sha": sha or self.remote_sha(),
            "verdict": verdict,
            "findings": [
                {
                    "priority": "P1",
                    "path": REL,
                    "line": 2,
                    "title": "Negative value is returned unchanged",
                    "description": "Negative input must clamp to zero",
                    "reproduction": "The approved Regression.test_negative fails: -4 != 0",
                    "test_argv": self.job["tests"][0],
                }
            ]
            if verdict == "changes_requested"
            else [],
        }

    def codex(self, root, base, output, timeout, prompt, runner):
        self.model_calls["codex"] += 1
        output.write_text(
            json.dumps(self.review(self.git("rev-parse", "HEAD", cwd=root))),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess([], 0, "", "")

    def minimax(self, root, prompt, result_path, timeout, max_steps, runner):
        self.model_calls["minimax"] += 1
        (root / REL).write_text(self.fixed_contents, encoding="utf-8")
        return subprocess.CompletedProcess([], 0, "", "")

    def github_request(self, number):
        self.model_calls["github_request"] += 1

    def github_pages(self, endpoint):
        sha = self.remote_sha()
        review = self.review(sha)
        if "/issues/" in endpoint:
            payload = {
                "code_review": {
                    "commit_sha": sha,
                    "status": "completed",
                    "has_any_findings": bool(review["findings"]),
                    "has_unresolved_findings": bool(review["findings"]),
                }
            }
            return [
                {
                    "id": 1,
                    "user": {"login": d.CODEX},
                    "updated_at": "2026-10-21T00:00:00Z",
                    "body": "<!-- codex-review-state:v1 "
                    + json.dumps(payload)
                    + " -->",
                }
            ]
        return (
            [
                {
                    "id": 2,
                    "user": {"login": d.CODEX},
                    "commit_id": sha,
                    "path": REL,
                    "line": 2,
                    "body": "[P1] nonnegative(-4) returns -4; run the approved regression test.",
                }
            ]
            if review["findings"]
            else []
        )

    def arm(self):
        with d.dispatcher_lock(self.state_dir):
            return d.arm_job(self.job, self.state_dir)

    def tick(self):
        with d.dispatcher_lock(self.state_dir):
            return d.evaluate_job(self.job, self.state_dir)

    def state(self):
        return d.load_state(self.state_dir / "state.json")

    def record(self):
        return self.state()["jobs"][d.digest(self.job)]

    def test_local_full_review_fix_real_test_commit_push_review(self):
        before = hashlib.sha256((self.wt / TEST).read_bytes()).hexdigest()
        self.arm()
        self.assertEqual(self.tick(), "AWAITING_REVIEW")
        changed = self.remote_sha()
        self.assertNotEqual(changed, self.initial)
        self.assertEqual(self.tick(), "CLEAR_WAITING_OWNER")
        self.assertEqual(self.tick(), "CLEAR_WAITING_OWNER")
        self.assertEqual(
            self.model_calls, {"codex": 2, "minimax": 1, "github_request": 0}
        )
        self.assertEqual(
            self.git("rev-list", "--count", f"{self.initial}..{changed}"), "1"
        )
        self.assertEqual(
            before, hashlib.sha256((self.wt / TEST).read_bytes()).hexdigest()
        )
        phases = [
            json.loads(line)["status"]
            for line in (self.state_dir / "events.jsonl").read_text().splitlines()
        ]
        for phase in (
            "REVIEW_RUNNING",
            "REVIEW_READY",
            "REPRODUCED",
            "FIX_RUNNING",
            "TESTS_PASSED",
            "COMMITTED",
            "PUSHED",
            "CLEAR_WAITING_OWNER",
        ):
            self.assertIn(phase, phases)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_github_full_cycle_uses_separate_contract(self):
        self.job["review_source"] = "github-codex"
        self.write_policy()
        self.arm()
        self.assertEqual(self.tick(), "AWAITING_REVIEW")
        self.assertEqual(self.tick(), "CLEAR_WAITING_OWNER")
        self.assertEqual(
            self.model_calls, {"codex": 0, "minimax": 1, "github_request": 1}
        )

    def test_ide_publication_drives_fix_without_github_marker(self):
        self.arm()
        d.publish_review(
            self.job,
            self.fetch_pr(7001),
            self.state_dir,
            self.review(),
            "owner-attested-ide",
        )
        self.tick()
        self.assertEqual(self.model_calls["codex"], 0)
        self.assertEqual(self.model_calls["minimax"], 1)

    def test_no_approval_means_zero_models(self):
        with self.assertRaisesRegex(RuntimeError, "AWAITING_OWNER_APPROVAL"):
            self.tick()
        self.assertEqual(sum(self.model_calls.values()), 0)

    def test_foreign_or_stale_local_result_is_rejected(self):
        self.arm()
        for patch in ({"head_sha": "a" * 40}, {"pr_number": 2}):
            with self.assertRaisesRegex(RuntimeError, "REVIEW_INVALID"):
                d.publish_review(
                    self.job,
                    self.fetch_pr(7001),
                    self.state_dir,
                    {**self.review(), **patch},
                    "owner-attested-ide",
                )
        self.assertEqual(sum(self.model_calls.values()), 0)

    def test_invalid_producer_and_cross_source_are_rejected(self):
        self.arm()
        for producer in ("random-process", "github-codex"):
            with self.assertRaises(RuntimeError):
                d.publish_review(
                    self.job,
                    self.fetch_pr(7001),
                    self.state_dir,
                    self.review(),
                    producer,
                )

    def test_tampered_signature_halts_before_models(self):
        self.arm()
        d.publish_review(
            self.job,
            self.fetch_pr(7001),
            self.state_dir,
            self.review(),
            "owner-attested-ide",
        )
        path = d.review_path(self.job, self.state_dir, self.initial)
        value = json.loads(path.read_text())
        value["data"]["review"]["verdict"] = "clear"
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(RuntimeError, "UNTRUSTED_RESULT"):
            self.tick()
        self.assertEqual(self.record()["phase"], "HALTED")
        self.assertEqual(sum(self.model_calls.values()), 0)

    def test_bad_regression_stops_without_commit_or_retry(self):
        self.arm()
        self.fixed_contents = "def nonnegative(value):\n    return -99\n"
        with self.assertRaisesRegex(RuntimeError, "TESTS_FAILED"):
            self.tick()
        self.assertEqual(self.remote_sha(), self.initial)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.initial)
        self.assertEqual(self.tick(), "HALTED")
        self.assertEqual(self.model_calls["minimax"], 1)

    def test_protected_tests_modified_by_model_halt(self):
        self.arm()

        def tamper(*args):
            result = self.minimax(*args)
            (self.wt / TEST).write_text("# fake pass\n")
            return result

        with (
            mock.patch.object(d, "run_minimax", side_effect=tamper),
            self.assertRaisesRegex(RuntimeError, "VERIFICATION_CHANGED"),
        ):
            self.tick()
        self.assertEqual(self.remote_sha(), self.initial)

    def test_other_files_modified_by_model_halt(self):
        self.arm()

        def outside(*args):
            result = self.minimax(*args)
            (self.wt / "README.md").write_text("unapproved edit")
            return result

        with (
            mock.patch.object(d, "run_minimax", side_effect=outside),
            self.assertRaisesRegex(RuntimeError, "FILE_SCOPE_CONFLICT"),
        ):
            self.tick()
        self.assertEqual(self.remote_sha(), self.initial)

    def test_dirty_worktree_before_launch_halts(self):
        self.arm()
        (self.wt / REL).write_text("dirty")
        with self.assertRaisesRegex(RuntimeError, "DIRTY_WORKTREE"):
            self.tick()
        self.assertEqual(sum(self.model_calls.values()), 0)

    def test_codex_timeout_is_terminal_not_retryable(self):
        self.arm()
        with (
            mock.patch.object(
                d, "run_codex_review", side_effect=subprocess.TimeoutExpired("codex", 1)
            ),
            self.assertRaises(subprocess.TimeoutExpired),
        ):
            self.tick()
        self.assertEqual(self.record()["codex_calls"], 1)
        self.assertEqual(self.record()["reason"], "TIMEOUT")
        self.assertEqual(self.tick(), "HALTED")

    def test_failed_minimax_is_terminal(self):
        self.arm()
        with (
            mock.patch.object(
                d,
                "run_minimax",
                return_value=subprocess.CompletedProcess([], 1, "", "secret output"),
            ),
            self.assertRaisesRegex(RuntimeError, "MINIMAX_FAILED"),
        ):
            self.tick()
        self.assertEqual(self.remote_sha(), self.initial)
        self.assertNotIn("secret output", (self.state_dir / "state.json").read_text())

    def test_interrupted_launch_is_unknown_and_never_resubmitted(self):
        approval = self.arm()
        state = {
            "version": 3,
            "runs": {},
            "tasks": {},
            "jobs": {
                d.digest(self.job): {
                    "phase": "FIX_RUNNING",
                    "sha": approval["head_sha"],
                    "minimax_calls": 1,
                    "codex_calls": 1,
                }
            },
        }
        d.save_state(self.state_dir / "state.json", state)
        with self.assertRaisesRegex(RuntimeError, "UNKNOWN_AFTER_RESTART"):
            self.tick()
        self.assertEqual(sum(self.model_calls.values()), 0)

    def test_budget_limit_stops_second_fix_even_after_new_sha(self):
        self.job["max_cycles"] = self.job["max_minimax_calls"] = 1
        self.write_policy()
        self.arm()
        self.always_findings = True
        self.tick()
        with self.assertRaisesRegex(RuntimeError, "CYCLE_LIMIT"):
            self.tick()
        self.assertEqual(self.model_calls["minimax"], 1)

    def test_corrupt_state_never_resets_budget(self):
        self.arm()
        (self.state_dir / "state.json").write_text("{broken")
        with self.assertRaisesRegex(RuntimeError, "STATE_INVALID"):
            self.tick()
        self.assertEqual(sum(self.model_calls.values()), 0)
        self.assertEqual((self.state_dir / "state.json").read_text(), "{broken")

    def test_changed_policy_has_no_approval(self):
        self.arm()
        self.job["max_steps"] += 1
        with self.assertRaisesRegex(RuntimeError, "AWAITING_OWNER_APPROVAL"):
            self.tick()

    def test_changed_verification_cannot_be_approved_implicitly(self):
        self.arm()
        (self.wt / TEST).write_text("changed")
        with self.assertRaisesRegex(RuntimeError, "VERIFICATION_CHANGED"):
            self.tick()
        self.assertEqual(sum(self.model_calls.values()), 0)

    def test_expired_approval_does_not_run_models(self):
        approval = self.arm()
        approval["expires_at"] = "2020-01-01T00:00:00+00:00"
        d.atomic_json(
            self.state_dir / "approvals" / (d.digest(self.job) + ".json"),
            d.sign_record(self.state_dir, approval),
        )
        with self.assertRaisesRegex(RuntimeError, "APPROVAL_EXPIRED"):
            self.tick()
        self.assertEqual(sum(self.model_calls.values()), 0)

    def test_duplicate_publication_is_idempotent(self):
        self.arm()
        a = d.publish_review(
            self.job,
            self.fetch_pr(7001),
            self.state_dir,
            self.review(),
            "owner-attested-ide",
        )
        b = d.publish_review(
            self.job,
            self.fetch_pr(7001),
            self.state_dir,
            self.review(),
            "owner-attested-ide",
        )
        self.assertEqual(a["review_id"], b["review_id"])

    def test_source_cannot_inject_a_test_command(self):
        review = self.review()
        review["findings"][0]["test_argv"] = ["powershell.exe", "-Command", "evil"]
        with self.assertRaisesRegex(RuntimeError, "REVIEW_INVALID"):
            d.validate_review(review, self.job, self.initial)

    def test_local_publication_redacts_credentials_before_signing(self):
        self.arm()
        review = self.review()
        review["findings"][0]["description"] = (
            'api_key="do-not-store" Bearer secretvalue ghp_testtesttest'
        )
        packet = d.publish_review(
            self.job, self.fetch_pr(7001), self.state_dir, review, "owner-attested-ide"
        )
        stored = d.review_path(self.job, self.state_dir, self.initial).read_text()
        for secret in ("do-not-store", "secretvalue", "ghp_testtesttest"):
            self.assertNotIn(secret, stored)
        self.assertIn("REDACTED", packet["review"]["findings"][0]["description"])

    def test_remote_head_change_during_review_prevents_fix(self):
        self.arm()
        original = self.fetch_pr

        def changed(number):
            value = original(number)
            if self.model_calls["codex"]:
                value["head"]["sha"] = "d" * 40
            return value

        with (
            mock.patch.object(d, "fetch_pr", side_effect=changed),
            self.assertRaisesRegex(RuntimeError, "HEAD_CHANGED"),
        ):
            self.tick()
        self.assertEqual(self.model_calls["minimax"], 0)
        self.assertEqual(self.remote_sha(), self.initial)

    def test_changed_contents_during_tests_prevent_commit(self):
        self.arm()
        real = d.run_process

        def concurrent_edit(argv, cwd, timeout, directory):
            result = real(argv, cwd, timeout, directory)
            if argv == self.job["tests"][0] and (self.wt / REL).read_text() == GOOD:
                (self.wt / REL).write_text(GOOD + "# unrelated writer changed bytes\n")
            return result

        with (
            mock.patch.object(d, "run_process", side_effect=concurrent_edit),
            self.assertRaisesRegex(RuntimeError, "FILE_CONFLICT"),
        ):
            self.tick()
        self.assertEqual(self.remote_sha(), self.initial)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.initial)

    def test_same_sha_global_run_key_never_retries_a_fix(self):
        self.arm()
        key = f"{self.job['pr_number']}:{self.initial}:CHANGES_REQUESTED"
        d.save_state(
            self.state_dir / "state.json",
            {"version": 3, "runs": {key: {"status": "TIMEOUT"}}, "tasks": {}},
        )
        with self.assertRaisesRegex(RuntimeError, "ALREADY_LAUNCHED"):
            self.tick()
        self.assertEqual(self.model_calls["minimax"], 0)

    def test_forged_github_bot_marker_cannot_launch_fix(self):
        self.job["review_source"] = "github-codex"
        self.write_policy()
        self.arm()
        real = self.github_pages

        def forged(endpoint):
            data = real(endpoint)
            for item in data:
                item["user"]["login"] = "someone-else"
            return data

        with mock.patch.object(d, "pages", side_effect=forged):
            self.assertEqual(self.tick(), "WAITING_GITHUB")
        self.assertEqual(sum(self.model_calls.values()), 0)

    def test_github_trigger_uses_json_rest_response(self):
        # Exercise the real helper rather than its E2E model-subscription mock.
        self.patches[3].stop()
        with mock.patch.object(d, "gh", return_value={"id": 42}) as api:
            d.request_codex_review(7001)
        self.assertEqual(api.call_args.args[:3], ("api", "--method", "POST"))
        self.assertIn("body=@codex review", api.call_args.args)

    def test_reproducing_green_regression_stops_before_minimax(self):
        (self.wt / REL).write_text(GOOD)
        self.git("add", "--", REL)
        self.git("commit", "-m", "already fixed")
        self.git("push", "origin", self.branch)
        self.arm()
        self.always_findings = True
        with self.assertRaisesRegex(RuntimeError, "NOT_REPRODUCED"):
            self.tick()
        self.assertEqual(self.model_calls["minimax"], 0)

    def test_policy_scope_and_three_cycle_limits(self):
        for name, value in (
            ("base", "main"),
            ("branch", "main"),
            ("max_cycles", 4),
            ("max_steps", 41),
            ("pr_number", True),
            ("allowed_paths", ["backend/main.py"]),
        ):
            bad = {**self.job, name: value}
            self.path.write_text(json.dumps(bad))
            with self.assertRaises((ValueError, TypeError)):
                d.load_job(self.path)

    def test_setup_error_is_not_a_reproduced_bug(self):
        (self.wt / TEST).write_text("import missing_relay_test_dependency\n")
        self.git("add", "--", TEST)
        self.git("commit", "-m", "broken test environment")
        self.git("push", "origin", self.branch)
        self.arm()
        with self.assertRaisesRegex(RuntimeError, "NOT_REPRODUCED"):
            self.tick()
        self.assertEqual(self.model_calls["minimax"], 0)

    def test_push_remote_must_be_the_approved_repository(self):
        self.patches[5].stop()
        with self.assertRaisesRegex(RuntimeError, "REMOTE_CHANGED"):
            self.arm()
        self.git(
            "remote", "set-url", "--push", "origin", f"https://github.com/{d.REPO}.git"
        )
        d.assert_remote(self.job)

    def test_fetch_pr_refreshes_cached_base_sha_from_branch_ref(self):
        self.patches[0].stop()
        pr = self.fetch_pr(7001)
        with mock.patch.object(
            d, "gh", side_effect=[pr, {"object": {"sha": "b" * 40}}]
        ) as api:
            current = d.fetch_pr(7001)
        self.assertEqual(current["base"]["sha"], "b" * 40)
        self.assertIn(
            "git/ref/heads/feature/codex-minimax-relay", api.call_args.args[1]
        )

    def test_lock_blocks_another_writer(self):
        with (
            d.dispatcher_lock(self.state_dir),
            self.assertRaisesRegex(RuntimeError, "ALREADY_RUNNING"),
            d.dispatcher_lock(self.state_dir),
        ):
            self.fail("second writer acquired state lock")

    def test_six_launch_budget_is_shared_between_jobs(self):
        self.arm()
        d.save_state(
            self.state_dir / "state.json",
            {
                "runs": {},
                "tasks": {},
                "jobs": {
                    "earlier": {
                        "codex_calls": 4,
                        "minimax_calls": 2,
                        "phase": "CLEAR_WAITING_OWNER",
                        "pr_number": 70,
                    }
                },
            },
        )
        with self.assertRaisesRegex(RuntimeError, "SESSION_MODEL_LIMIT"):
            self.tick()
        self.assertEqual(sum(self.model_calls.values()), 0)

    def test_an_unfinished_different_pr_blocks_launch(self):
        self.arm()
        d.save_state(
            self.state_dir / "state.json",
            {
                "runs": {},
                "tasks": {},
                "jobs": {
                    "other": {
                        "codex_calls": 1,
                        "minimax_calls": 0,
                        "phase": "AWAITING_REVIEW",
                        "pr_number": 999,
                    }
                },
            },
        )
        with self.assertRaisesRegex(RuntimeError, "OTHER_PR_ACTIVE"):
            self.tick()
        self.assertEqual(sum(self.model_calls.values()), 0)

    def test_owner_report_stops_and_is_not_submitted_twice(self):
        self.arm()
        self.tick()
        self.tick()
        with mock.patch.object(d, "gh", return_value={"id": 123}) as api:
            d.finish_job(self.job, self.state_dir, "CLEAR_WAITING_OWNER")
            d.finish_job(self.job, self.state_dir, "CLEAR_WAITING_OWNER")
        self.assertEqual(api.call_count, 1)
        self.assertTrue((self.state_dir / "STOP").exists())

    def test_a_busy_dispatcher_is_never_stopped_by_another_tick(self):
        with (
            d.dispatcher_lock(self.state_dir),
            mock.patch.object(
                sys,
                "argv",
                [
                    "dispatcher.py",
                    "--job",
                    str(self.path),
                    "--state-dir",
                    str(self.state_dir),
                    "--run",
                ],
            ),
        ):
            self.assertEqual(d.main(), 0)
        self.assertFalse((self.state_dir / "STOP").exists())
        self.assertEqual(sum(self.model_calls.values()), 0)

    def test_subscription_preflight_rejects_api_and_accepts_account_only(self):
        self.patches[6].stop()
        with (
            mock.patch.object(
                d,
                "read_json",
                return_value={"auth_mode": "apikey", "OPENAI_API_KEY": "synthetic"},
            ),
            self.assertRaisesRegex(RuntimeError, "SUBSCRIPTION_REQUIRED"),
        ):
            d.subscription_preflight("Codex")
        with mock.patch.object(
            d,
            "read_json",
            return_value={"auth_mode": "chatgpt", "tokens": {"synthetic": True}},
        ):
            d.subscription_preflight("Codex")
        for source, accepted in (("api_key", False), ("token_plan", True)):
            result = subprocess.CompletedProcess(
                [],
                0,
                json.dumps(
                    {
                        "minimaxModelSource": source,
                        "providers": [{"providerId": "minimax_oauth", "active": True}],
                    }
                ),
                "",
            )
            with mock.patch.object(d.subprocess, "run", return_value=result):
                if accepted:
                    d.subscription_preflight("MiniMax")
                else:
                    with self.assertRaisesRegex(RuntimeError, "SUBSCRIPTION_REQUIRED"):
                        d.subscription_preflight("MiniMax")

    def test_stop_before_tick_spends_nothing(self):
        self.arm()
        (self.state_dir / "STOP").write_text("owner stop")
        with self.assertRaisesRegex(d.RelayStopped, "STOPPED"):
            self.tick()
        self.assertEqual(sum(self.model_calls.values()), 0)

    def test_stop_kills_only_the_owned_child_tree(self):
        self.state_dir.mkdir()
        timer = threading.Timer(
            0.4, lambda: (self.state_dir / "STOP").write_text("stop")
        )
        timer.start()
        started = time.monotonic()
        try:
            with self.assertRaises(d.RelayStopped):
                d.run_process(
                    [sys.executable, "-c", "import time; time.sleep(15)"],
                    self.wt,
                    10,
                    self.state_dir,
                )
        finally:
            timer.join()
        self.assertLess(time.monotonic() - started, 5)

    def test_real_process_timeout_is_bounded(self):
        self.state_dir.mkdir()
        with self.assertRaises(subprocess.TimeoutExpired):
            d.run_process(
                [sys.executable, "-c", "import time; time.sleep(15)"],
                self.wt,
                0.2,
                self.state_dir,
            )


if __name__ == "__main__":
    unittest.main()
