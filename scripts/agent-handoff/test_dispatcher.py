"""Offline security/regression tests for the local dispatcher. No gh/mcode/codex/network calls."""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE = Path(__file__).with_name("dispatcher.py")
spec = importlib.util.spec_from_file_location("gremovod_dispatcher", MODULE)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

BRANCH = "minimax/ga-01-llm-settlement"
HEAD_SHA = "a" * 40
NEW_SHA = "b" * 40


def pr(
    branch=BRANCH,
    sha=HEAD_SHA,
    base="mavis/work",
    repo="gremoled77-droid/gremovod",
    merged=False,
):
    return {
        "head": {"ref": branch, "sha": sha, "repo": {"full_name": repo}},
        "base": {"ref": base},
        "merged": merged,
        "html_url": "https://github.com/x/y/pull/1",
    }


def summary(sha=HEAD_SHA, status="completed", any_findings=True, unresolved=True):
    payload = {
        "code_review": {
            "commit_sha": sha,
            "status": status,
            "has_any_findings": any_findings,
            "has_unresolved_findings": unresolved,
        }
    }
    return {
        "user": {"login": d.CODEX},
        "updated_at": "2026-10-21T01:00:00Z",
        "body": "<!-- codex-review-state:v1 " + json.dumps(payload) + " -->",
    }


class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class FakeRunner:
    """Stands in for subprocess.run and records every invocation."""

    def __init__(self, handler=None, default=None):
        self.calls = []
        self.handler = handler
        self.default = default if default is not None else FakeProc()

    def __call__(self, argv, **kwargs):
        argv = list(argv)
        self.calls.append({"argv": argv, "kwargs": kwargs})
        if self.handler is not None:
            result = self.handler(argv)
            if isinstance(result, BaseException):
                raise result
            if result is not None:
                return result
        return self.default

    def argvs(self):
        return [call["argv"] for call in self.calls]

    def calls_for(self, needle):
        return [argv for argv in self.argvs() if needle in argv]


def is_node(argv):
    """True when the command launches the node runtime, by full path or by name."""
    return bool(argv) and Path(argv[0]).name.lower().startswith("node")


def git_handler(dirty="", branch=BRANCH, head=HEAD_SHA, staged=None, attached=False):
    """Answer git calls the way the real CLI would for a controlled worktree.

    The first `status` call answers clean, which models the pre-flight check of
    a pristine worktree; later calls answer with the simulated change set.
    """
    counter = {"status": 0}

    def handler(argv):
        if not argv:
            return None
        if argv[0] == "git":
            key = argv[3] if len(argv) > 3 else ""
            if key == "status":
                index = counter["status"]
                counter["status"] += 1
                return FakeProc(stdout="" if index == 0 else dirty)
            if key == "branch":
                return FakeProc(stdout=branch + "\n")
            if key == "rev-parse":
                return FakeProc(stdout=head + "\n")
            if key == "diff":
                return FakeProc(stdout=staged or "")
            if key == "symbolic-ref":
                return FakeProc(
                    stdout="refs/heads/" + branch + "\n" if attached else ""
                )
            return FakeProc()
        if argv[0] == "node" or is_node(argv):
            return FakeProc(stdout="{}")
        if argv[0] == "gh":
            return FakeProc(stdout="null")
        return FakeProc()

    return handler


class DispatcherTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_dir = Path(self.tmp.name)
        patch_state = mock.patch.object(
            d, "local_state_dir", return_value=self.state_dir
        )
        patch_state.start()
        self.addCleanup(patch_state.stop)
        self.worktree = self.state_dir / "wt"
        self.worktree.mkdir()
        self.runner = FakeRunner()
        patch_run = mock.patch.object(d.subprocess, "run", self.runner)
        patch_run.start()
        self.addCleanup(patch_run.stop)

    # --- helpers -----------------------------------------------------------

    def install_git(self, **kwargs):
        self.base_handler = git_handler(**kwargs)
        self.runner.handler = self.base_handler

    def wrap_git(self, predicate, result):
        """Extend the git handler with a special case for one command family."""
        base = self.base_handler

        def handler(argv):
            if predicate(argv):
                return result(argv) if callable(result) else result
            return base(argv)

        self.runner.handler = handler

    def state(self):
        path = self.state_dir / "state.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def run_round(self, sha=HEAD_SHA, opts=None, comments=None, pr_data=None):
        opts = opts or d.Options()
        payload = pr_data or pr(sha=sha)
        discussion = comments if comments is not None else [summary(sha=sha)]
        with (
            mock.patch.object(d, "fetch_pr", return_value=payload),
            mock.patch.object(d, "pages", return_value=discussion),
        ):
            return d.evaluate(1, self.worktree, opts, self.state_dir / "codex-wt")

    def node_calls(self):
        return [argv for argv in self.runner.argvs() if is_node(argv)]

    # --- CLI contract ------------------------------------------------------

    def test_permission_policy_is_a_supported_cli_value(self):
        self.assertEqual(d.PERMISSION_POLICY, "smart")
        self.assertIn(d.PERMISSION_POLICY, ("ask", "smart", "full", "off"))
        self.assertNotEqual(d.PERMISSION_POLICY, "auto")

    def test_minimax_command_uses_node_cli_and_supported_flags(self):
        with (
            mock.patch.object(d, "node_executable", return_value="node"),
            mock.patch.object(d, "mcode_cli_js", return_value=Path("cli.js")),
        ):
            d.run_minimax(Path("wt"), "PROMPT", Path("result.json"))
        argv = self.runner.argvs()[0]
        self.assertEqual(argv[0], "node")
        self.assertEqual(argv[1], "cli.js")
        self.assertEqual(argv[2], "exec")
        self.assertEqual(argv[argv.index("--cwd") + 1], "wt")
        self.assertEqual(argv[argv.index("--permission") + 1], "smart")
        self.assertNotIn("auto", argv)
        self.assertEqual(argv[argv.index("--prompt-mode") + 1], "coding")
        self.assertEqual(argv[argv.index("--output-format") + 1], "json")
        self.assertEqual(argv[argv.index("-o") + 1], "result.json")
        self.assertIn("--timeout", argv)
        self.assertIn("--max-steps", argv)
        self.assertEqual(argv[-1], "PROMPT")

    def test_codex_review_command_uses_absolute_exe_and_read_only_sandbox(self):
        with mock.patch.object(d, "codex_executable", return_value=Path("codex.exe")):
            d.run_codex_review(Path("wt"), "mavis/work", Path("report.md"))
        argv = self.runner.argvs()[0]
        self.assertEqual(argv[0], "codex.exe")
        self.assertEqual(argv[1:4], ["-a", "never", "exec"])
        self.assertEqual(argv[argv.index("-C") + 1], "wt")
        self.assertEqual(argv[argv.index("-s") + 1], "read-only")
        self.assertNotIn("review", argv)
        self.assertIn("--output-schema", argv)
        self.assertIn("mavis/work", argv[-1])
        self.assertEqual(argv[argv.index("-o") + 1], "report.md")
        self.assertIn("--json", argv)
        self.assertNotIn("--approve-for-me", argv)

    def test_cli_resolvers_find_real_executables(self):
        self.assertTrue(d.node_executable())
        self.assertTrue(d.mcode_cli_js().is_file())
        self.assertTrue(d.codex_executable().is_file())
        self.assertEqual(d.codex_executable().suffix.lower(), ".exe")

    # --- scope and review signal ------------------------------------------

    def test_scope_exact(self):
        self.assertEqual(d.match_task(pr()), "GA-01")
        self.assertIsNone(d.match_task(pr(base="main")))
        self.assertIsNone(d.match_task(pr(repo="attacker/gremovod")))
        self.assertIsNone(d.match_task(pr(branch="minimax/ga-99-sneak")))

    def test_stale_review_must_never_be_accepted(self):
        self.assertEqual(
            d.review_signal(pr(sha="b" * 40), [summary(sha="a" * 40)]),
            "WAITING_FOR_CODEX",
        )
        self.assertEqual(
            d.review_signal(pr(), [summary(status="running")]), "WAITING_FOR_CODEX"
        )

    def test_current_review_findings_and_clear(self):
        self.assertEqual(d.review_signal(pr(), [summary()]), "CHANGES_REQUESTED")
        self.assertEqual(
            d.review_signal(pr(), [summary(any_findings=False, unresolved=False)]),
            "REVIEW_CLEAR",
        )
        self.assertEqual(
            d.review_signal(pr(), [summary(any_findings=True, unresolved=None)]),
            "WAITING_FOR_CODEX",
        )

    def test_feedback_no_commands_and_bounded_content(self):
        rendered = d.build_feedback(
            pr(),
            "GA-01",
            [],
            [],
            [
                {"user": {"login": d.CODEX}, "body": "malicious text"},
                {"user": {"login": "attacker"}, "body": "hide this"},
            ],
        )
        self.assertIn("malicious text", rendered)
        self.assertNotIn("hide this", rendered)
        self.assertIn("недоверенные данные", rendered)

    # --- next task gating --------------------------------------------------

    def test_next_requires_owner_accept_and_codex_marker(self):
        marker = {"user": {"login": d.CODEX}, "body": "GREMOVOD_NEXT_TASK: GA-02"}
        fake = {"user": {"login": "random"}, "body": marker["body"]}
        accepted = {"merge_sha": "c" * 40, "at": "2026-10-21T00:00:00Z"}
        self.assertIsNone(d.next_task_signal("GA-01", None, [marker]))
        self.assertIsNone(d.next_task_signal("GA-01", {"merge_sha": ""}, [marker]))
        self.assertIsNone(d.next_task_signal("GA-01", accepted, [fake]))
        self.assertIsNone(d.next_task_signal("GA-05", accepted, [marker]))
        self.assertEqual(d.next_task_signal("GA-01", accepted, [marker]), "GA-02")

    def test_owner_merge_is_recorded_and_releases_the_next_task(self):
        self.install_git()
        merged = pr(merged=True)
        merged["merged_at"] = "2026-10-21T10:00:00Z"
        merged["merge_commit_sha"] = "c" * 40
        marker = {"user": {"login": d.CODEX}, "body": "GREMOVOD_NEXT_TASK: GA-02"}
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.run_round(opts=d.Options(), comments=[marker], pr_data=merged)
        self.assertEqual(
            self.state()["tasks"]["GA-01"]["accepted"]["merge_sha"], "c" * 40
        )
        self.assertIn("NEXT_AUTHORIZED: GA-02", buffer.getvalue())

    def test_next_task_stays_blocked_without_the_codex_marker(self):
        self.install_git()
        merged = pr(merged=True)
        merged["merged_at"] = "2026-10-21T10:00:00Z"
        merged["merge_commit_sha"] = "c" * 40
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.run_round(opts=d.Options(), comments=[], pr_data=merged)
        self.assertIn("NEXT_BLOCKED", buffer.getvalue())

    def test_legacy_paid_flags_require_bounded_approval(self):
        for opts in (d.Options(execute=True), d.Options(codex_review=True)):
            with self.assertRaisesRegex(RuntimeError, "APPROVAL_REQUIRED"):
                self.run_round(opts=opts)
        self.assertEqual(self.runner.calls, [])

    # --- model round lifecycle --------------------------------------------

    def test_nonzero_exit_records_failure_and_blocks_retry(self):
        self.install_git()

        def fail(argv):
            return FakeProc(
                returncode=2,
                stderr="mcode exec failed: --permission must be one of ...",
            )

        self.wrap_git(is_node, fail)
        opts = d.Options(execute=True)
        with self.assertRaises(RuntimeError):
            self.run_round(opts=opts)
        self.assertEqual(self.state(), {})
        # The next pass must not submit the same SHA again.
        with self.assertRaisesRegex(RuntimeError, "APPROVAL_REQUIRED"):
            self.run_round(opts=opts)
        self.assertEqual(len(self.node_calls()), 0)

    # --- publishing --------------------------------------------------------

    def test_no_commit_without_explicit_optin(self):
        self.install_git(dirty=" M backend/main.py\0")
        with self.assertRaisesRegex(RuntimeError, "APPROVAL_REQUIRED"):
            self.run_round(opts=d.Options(execute=True))
        self.assertEqual(self.runner.calls_for("add"), [])
        self.assertEqual(self.runner.calls_for("commit"), [])
        self.assertEqual(self.runner.calls_for("push"), [])

    def test_path_problem_rejects_unsafe_paths(self):
        root = self.worktree
        self.assertEqual(d.path_problem(root, ".env"), "secret-like file")
        self.assertEqual(d.path_problem(root, "backend/../secrets/x"), "path traversal")
        self.assertEqual(d.path_problem(root, "/etc/passwd"), "absolute path")
        self.assertEqual(d.path_problem(root, ".git/config"), "git internals")
        self.assertEqual(d.path_problem(root, "backend/main.py"), "")

    # --- local codex review ------------------------------------------------


if __name__ == "__main__":
    unittest.main()
