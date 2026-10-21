"""Offline security/regression tests for the local dispatcher. No gh/mcode/codex/network calls."""
import contextlib
import importlib.util
import io
import json
import subprocess
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


def pr(branch=BRANCH, sha=HEAD_SHA, base="mavis/work",
       repo="gremoled77-droid/gremovod", merged=False):
    return {"head": {"ref": branch, "sha": sha, "repo": {"full_name": repo}},
            "base": {"ref": base}, "merged": merged,
            "html_url": "https://github.com/x/y/pull/1"}


def summary(sha=HEAD_SHA, status="completed", any_findings=True, unresolved=True):
    payload = {"code_review": {"commit_sha": sha, "status": status,
                               "has_any_findings": any_findings,
                               "has_unresolved_findings": unresolved}}
    return {"user": {"login": d.CODEX}, "updated_at": "2026-10-21T01:00:00Z",
            "body": "<!-- codex-review-state:v1 " + json.dumps(payload) + " -->"}


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
                return FakeProc(stdout="refs/heads/" + branch + "\n" if attached else "")
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
        patch_state = mock.patch.object(d, "local_state_dir", return_value=self.state_dir)
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
        with mock.patch.object(d, "fetch_pr", return_value=payload), \
             mock.patch.object(d, "pages", return_value=discussion):
            return d.evaluate(1, self.worktree, opts, self.state_dir / "codex-wt")

    def node_calls(self):
        return [argv for argv in self.runner.argvs() if is_node(argv)]

    # --- CLI contract ------------------------------------------------------

    def test_permission_policy_is_a_supported_cli_value(self):
        self.assertEqual(d.PERMISSION_POLICY, "smart")
        self.assertIn(d.PERMISSION_POLICY, ("ask", "smart", "full", "off"))
        self.assertNotEqual(d.PERMISSION_POLICY, "auto")

    def test_minimax_command_uses_node_cli_and_supported_flags(self):
        with mock.patch.object(d, "node_executable", return_value="node"), \
             mock.patch.object(d, "mcode_cli_js", return_value=Path("cli.js")):
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
        self.assertEqual(argv[1], "exec")
        self.assertEqual(argv[argv.index("-C") + 1], "wt")
        self.assertEqual(argv[argv.index("-s") + 1], "read-only")
        self.assertIn("review", argv)
        self.assertEqual(argv[argv.index("--base") + 1], "mavis/work")
        self.assertEqual(argv[argv.index("-o") + 1], "report.md")
        self.assertIn("--json", argv)
        self.assertNotIn("-a", argv)

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
        self.assertEqual(d.review_signal(pr(sha="b" * 40), [summary(sha="a" * 40)]),
                         "WAITING_FOR_CODEX")
        self.assertEqual(d.review_signal(pr(), [summary(status="running")]),
                         "WAITING_FOR_CODEX")

    def test_current_review_findings_and_clear(self):
        self.assertEqual(d.review_signal(pr(), [summary()]), "CHANGES_REQUESTED")
        self.assertEqual(d.review_signal(pr(), [summary(any_findings=False, unresolved=False)]),
                         "REVIEW_CLEAR")
        self.assertEqual(d.review_signal(pr(), [summary(any_findings=True, unresolved=None)]),
                         "WAITING_FOR_CODEX")

    def test_feedback_no_commands_and_bounded_content(self):
        rendered = d.build_feedback(pr(), "GA-01", [], [], [
            {"user": {"login": d.CODEX}, "body": "malicious text"},
            {"user": {"login": "attacker"}, "body": "hide this"}])
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
        self.assertEqual(self.state()["tasks"]["GA-01"]["accepted"]["merge_sha"], "c" * 40)
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

    # --- model round lifecycle --------------------------------------------

    def test_stale_sha_does_not_launch_the_model(self):
        self.install_git()
        result = self.run_round(opts=d.Options(execute=True),
                                comments=[summary(sha="c" * 40)])
        self.assertEqual(result, "WAITING_FOR_CODEX")
        self.assertEqual(self.node_calls(), [])

    def test_repeated_launch_runs_the_model_once(self):
        self.install_git()
        opts = d.Options(execute=True)
        self.run_round(opts=opts)
        self.run_round(opts=opts)
        self.assertEqual(len(self.node_calls()), 1)

    def test_timeout_records_failure_and_blocks_retry(self):
        self.install_git()

        def explode(argv):
            raise subprocess.TimeoutExpired(cmd=argv, timeout=1)

        self.wrap_git(is_node, explode)
        opts = d.Options(execute=True)
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_round(opts=opts)
        key = f"1:{HEAD_SHA}:CHANGES_REQUESTED"
        self.assertEqual(self.state()["runs"][key]["status"], "TIMEOUT")
        # The next pass must not submit the same SHA again.
        self.run_round(opts=opts)
        self.assertEqual(len(self.node_calls()), 1)

    def test_nonzero_exit_records_failure_and_blocks_retry(self):
        self.install_git()

        def fail(argv):
            return FakeProc(returncode=2, stderr="mcode exec failed: --permission must be one of ...")

        self.wrap_git(is_node, fail)
        opts = d.Options(execute=True)
        with self.assertRaises(RuntimeError):
            self.run_round(opts=opts)
        key = f"1:{HEAD_SHA}:CHANGES_REQUESTED"
        self.assertEqual(self.state()["runs"][key]["status"], "FAILED")
        # The next pass must not submit the same SHA again.
        self.run_round(opts=opts)
        self.assertEqual(len(self.node_calls()), 1)

    def test_cycle_limit_blocks_the_fourth_round(self):
        self.install_git()
        opts = d.Options(execute=True, max_cycles=3)
        for index in range(4):
            self.run_round(sha=chr(97 + index) * 40, opts=opts)
        self.assertEqual(self.state()["tasks"]["GA-01"]["rounds"], 3)
        self.assertEqual(len(self.node_calls()), 3)

    def test_dry_run_runs_no_model_and_no_commit(self):
        self.install_git(dirty=" M backend/main.py\0")
        self.run_round(opts=d.Options(execute=True, dry_run=True))
        self.assertEqual(self.node_calls(), [])
        self.assertEqual(self.runner.calls_for("commit"), [])
        self.assertEqual(self.state().get("runs", {}), {})

    # --- publishing --------------------------------------------------------

    def test_no_commit_without_explicit_optin(self):
        self.install_git(dirty=" M backend/main.py\0")
        self.run_round(opts=d.Options(execute=True))
        self.assertEqual(self.runner.calls_for("add"), [])
        self.assertEqual(self.runner.calls_for("commit"), [])
        self.assertEqual(self.runner.calls_for("push"), [])

    def test_commit_stages_only_allowed_paths_and_never_adds_everything(self):
        self.install_git(dirty=" M backend/main.py\0?? docs/note.md\0",
                         staged="backend/main.py\ndocs/note.md\n")
        self.run_round(opts=d.Options(execute=True, allow_commit=True))
        adds = self.runner.calls_for("add")
        self.assertEqual(len(adds), 2)
        for argv in adds:
            self.assertEqual(argv[-2], "--")
            self.assertNotIn("-A", argv)
        self.assertEqual([argv[-1] for argv in adds], ["backend/main.py", "docs/note.md"])
        self.assertEqual(len(self.runner.calls_for("commit")), 1)

    def test_refuses_paths_outside_the_allowlist(self):
        self.install_git(dirty="?? .env\0?? secret/keys.txt\0 M backend/main.py\0",
                         staged="backend/main.py\n")
        self.run_round(opts=d.Options(execute=True, allow_commit=True))
        adds = self.runner.calls_for("add")
        self.assertEqual([argv[-1] for argv in adds], ["backend/main.py"])

    def test_path_problem_rejects_unsafe_paths(self):
        root = self.worktree
        self.assertEqual(d.path_problem(root, ".env"), "secret-like file")
        self.assertEqual(d.path_problem(root, "backend/../secrets/x"), "path traversal")
        self.assertEqual(d.path_problem(root, "/etc/passwd"), "absolute path")
        self.assertEqual(d.path_problem(root, ".git/config"), "git internals")
        self.assertEqual(d.path_problem(root, "backend/main.py"), "")

    def test_push_requires_its_own_optin(self):
        self.install_git(dirty=" M backend/main.py\0", staged="backend/main.py\n")
        self.run_round(opts=d.Options(execute=True, allow_commit=True))
        self.assertEqual(self.runner.calls_for("push"), [])
        self.assertEqual(len(self.runner.calls_for("commit")), 1)

    def test_push_requests_a_codex_review_for_the_new_sha(self):
        self.install_git(dirty=" M backend/main.py\0", staged="backend/main.py\n", head=NEW_SHA)
        self.run_round(opts=d.Options(execute=True, allow_commit=True, allow_push=True))
        gh_calls = [argv for argv in self.runner.argvs() if argv and argv[0] == "gh"]
        self.assertEqual(len(gh_calls), 1)
        self.assertIn("@codex review", gh_calls[0])
        self.assertIn(NEW_SHA, self.state()["tasks"]["GA-01"]["reviewed_shas"])

    def test_duplicate_review_for_the_same_sha_is_skipped(self):
        self.install_git(dirty=" M backend/main.py\0", staged="backend/main.py\n", head=NEW_SHA)
        seeded = {"version": 2, "runs": {},
                  "tasks": {"GA-01": {"rounds": 0, "reviewed_shas": [NEW_SHA], "accepted": None}}}
        (self.state_dir / "state.json").write_text(json.dumps(seeded), encoding="utf-8")
        self.run_round(opts=d.Options(execute=True, allow_commit=True, allow_push=True))
        gh_calls = [argv for argv in self.runner.argvs() if argv and argv[0] == "gh"]
        self.assertEqual(gh_calls, [])

    # --- local codex review ------------------------------------------------

    def test_codex_worktree_must_be_detached(self):
        codex_wt = self.state_dir / "codex-wt"
        codex_wt.mkdir()
        self.install_git(attached=True)
        with self.assertRaises(RuntimeError):
            d.assert_codex_worktree(codex_wt, pr())

    def test_codex_worktree_must_match_the_pr_head(self):
        codex_wt = self.state_dir / "codex-wt"
        codex_wt.mkdir()
        self.install_git(head="c" * 40)
        with self.assertRaises(RuntimeError):
            d.assert_codex_worktree(codex_wt, pr())

    def test_codex_review_flag_runs_an_independent_review(self):
        codex_wt = self.state_dir / "codex-wt"
        codex_wt.mkdir()
        self.install_git()
        with mock.patch.object(d, "codex_executable", return_value=Path("codex.exe")):
            self.run_round(opts=d.Options(codex_review=True))
        codex_calls = [argv for argv in self.runner.argvs() if argv and argv[0] == "codex.exe"]
        self.assertEqual(len(codex_calls), 1)
        self.assertIn("review", codex_calls[0])


class RealCliContractTest(unittest.TestCase):
    """The dispatcher's argv must match the CLI that is actually installed.

    Only `--help` is executed: no model is invoked, no quota is spent and no
    repository is touched. The test is skipped when a CLI is not installed.
    """

    def mcode_help(self):
        try:
            node, cli = d.node_executable(), d.mcode_cli_js()
        except RuntimeError as exc:
            self.skipTest(f"MiniMax Code CLI is not installed: {exc}")
        proc = subprocess.run([node, str(cli), "exec", "--help"], check=False, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr[:400])
        return proc.stdout

    def codex_help(self, *args):
        try:
            exe = d.codex_executable()
        except RuntimeError as exc:
            self.skipTest(f"Codex CLI is not installed: {exc}")
        proc = subprocess.run([str(exe), "exec", *args, "--help"], check=False, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr[:400])
        return proc.stdout

    def test_minimax_flags_exist_in_the_installed_cli(self):
        help_text = self.mcode_help()
        for flag in ("--cwd", "--permission", "--prompt-mode", "--output-format", "--timeout", "--max-steps"):
            self.assertIn(flag, help_text, f"{flag} is not offered by the installed mcode CLI")
        self.assertIn("-o", help_text, "mcode exec must accept -o for the result file")

    def test_permission_policy_is_documented_by_the_installed_cli(self):
        help_text = self.mcode_help()
        line = next(line for line in help_text.splitlines() if "--permission" in line)
        self.assertIn(d.PERMISSION_POLICY, line, "the configured permission policy must be a documented one")
        self.assertNotIn("auto", line, "the installed CLI does not accept the internal 'auto' spelling")

    def test_codex_flags_exist_in_the_installed_cli(self):
        exec_help = self.codex_help()
        for flag in ("-C", "-s", "--approve-for-me", "--json", "-o"):
            self.assertIn(flag, exec_help, f"{flag} is not offered by codex exec")
        review_help = self.codex_help("review")
        for flag in ("--base", "-o", "--json"):
            self.assertIn(flag, review_help, f"{flag} is not offered by codex exec review")
        self.assertIn("review", exec_help, "codex exec must expose the review subcommand")


class FakeRepo:
    """Small stateful git model for the end-to-end dispatcher run."""

    def __init__(self, branch=BRANCH, head=HEAD_SHA):
        self.branch = branch
        self.head = head
        self.next_head = head
        self.staged = []
        self.added = []
        self.committed = []
        self.pushed = []
        self.dirty = []

    def handler(self, argv):
        if not argv:
            return None
        if argv[0] == "gh":
            return FakeProc(stdout="{}")
        if is_node(argv):
            return FakeProc(stdout="{}")
        if argv[0] != "git":
            return None
        key = argv[3] if len(argv) > 3 else ""
        if key == "status":
            mode = argv[4] if len(argv) > 4 else ""
            if mode == "--porcelain=v1":
                return FakeProc(stdout="".join(" M " + path + "\0" for path in self.dirty))
            return FakeProc(stdout="")
        if key == "branch":
            return FakeProc(stdout=self.branch + "\n")
        if key == "rev-parse":
            return FakeProc(stdout=self.head + "\n")
        if key == "diff":
            return FakeProc(stdout="".join(path + "\n" for path in self.staged))
        if key == "add":
            self.added.append(argv[-1])
            self.staged.append(argv[-1])
            return FakeProc()
        if key == "commit":
            self.committed.append(argv[-1])
            self.head = self.next_head
            self.staged = []
            return FakeProc()
        if key == "push":
            self.pushed.append(argv[-1])
            return FakeProc()
        if key == "symbolic-ref":
            return FakeProc(stdout="")
        return FakeProc()


class DispatcherEndToEndTest(unittest.TestCase):
    """MiniMax → Codex → MiniMax loop with every external call mocked.

    No model is invoked: the CLI processes are replaced by recorded fakes and the git
    calls are answered by a small stateful repository model.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_dir = Path(self.tmp.name)
        patch_state = mock.patch.object(d, "local_state_dir", return_value=self.state_dir)
        patch_state.start()
        self.addCleanup(patch_state.stop)
        self.worktree = self.state_dir / "wt"
        self.worktree.mkdir()
        self.codex_wt = self.state_dir / "codex-wt"
        self.codex_wt.mkdir()
        self.repo = FakeRepo()
        self.runner = FakeRunner()
        self.runner.handler = self.repo.handler
        patch_run = mock.patch.object(d.subprocess, "run", self.runner)
        patch_run.start()
        self.addCleanup(patch_run.stop)
        self.summary = summary()

    def state(self):
        path = self.state_dir / "state.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def pages_for(self, endpoint):
        if "issues" in endpoint:
            return [self.summary]
        return []

    def round(self, sha, findings=True, opts=None, next_head=None):
        """Run one dispatcher round for a PR head SHA.

        `next_head` is the SHA the model round is expected to publish; the commit
        of the round moves the repository to it.
        """
        self.repo.head = sha
        self.repo.next_head = next_head or sha
        self.summary = summary(sha=sha, any_findings=findings, unresolved=findings)
        opts = opts or d.Options(execute=True, allow_commit=True, allow_push=True, codex_review=True)
        with mock.patch.object(d, "fetch_pr", return_value=pr(sha=sha)), \
             mock.patch.object(d, "pages", side_effect=self.pages_for), \
             mock.patch.object(d, "codex_executable", return_value=Path("codex.exe")):
            return d.evaluate(1, self.worktree, opts, self.codex_wt)

    def model_calls(self):
        return [argv for argv in self.runner.argvs() if is_node(argv)]

    def codex_calls(self):
        return [argv for argv in self.runner.argvs() if argv and argv[0] == "codex.exe"]

    def test_full_loop_minimax_codex_minimax_without_calling_a_model(self):
        """Two rounds of findings, then a clear review: the loop stops on its own."""
        self.repo.dirty = ["backend/main.py"]
        third = "c" * 40
        self.assertEqual(self.round(HEAD_SHA, next_head=NEW_SHA), "CHANGES_REQUESTED")
        self.assertEqual(self.round(NEW_SHA, next_head=third), "CHANGES_REQUESTED")
        self.assertEqual(self.round(third, findings=False), "REVIEW_CLEAR")
        # One MiniMax round per round with findings, none for the clear review.
        self.assertEqual(len(self.model_calls()), 2)
        self.assertEqual(len(self.codex_calls()), 3)
        # Every round published its own commit and push.
        self.assertEqual(len(self.repo.committed), 2)
        self.assertEqual(len(self.repo.pushed), 2)
        # The staged set is exactly the allowed path; `git add -A` is never used.
        self.assertEqual(self.repo.added, ["backend/main.py", "backend/main.py"])
        self.assertFalse(any("add" in argv and "-A" in argv for argv in self.runner.argvs()))
        state = self.state()
        self.assertEqual(state["tasks"]["GA-01"]["rounds"], 2)
        # Every SHA that reached a Codex review is recorded: the two published heads
        # and the head whose review came back clear.
        self.assertEqual(state["tasks"]["GA-01"]["reviewed_shas"], [HEAD_SHA, NEW_SHA, third])
        self.assertEqual(sorted(state["runs"]), sorted(["1:" + HEAD_SHA + ":CHANGES_REQUESTED",
                                                        "1:" + NEW_SHA + ":CHANGES_REQUESTED"]))
        # A Codex review was requested for each published SHA.
        gh_calls = [argv for argv in self.runner.argvs() if argv and argv[0] == "gh"]
        self.assertEqual(len(gh_calls), 2)
        for argv in gh_calls:
            self.assertIn("@codex review", argv)

    def test_loop_stops_at_three_rounds(self):
        """The fourth round with findings is refused: the budget is three cycles."""
        self.repo.dirty = ["backend/main.py"]
        heads = (HEAD_SHA, NEW_SHA, "c" * 40)
        for index, sha in enumerate(heads):
            self.round(sha, next_head="d" * 40 if index == 2 else sha)
        self.assertEqual(len(self.model_calls()), 3)
        self.assertEqual(self.state()["tasks"]["GA-01"]["rounds"], 3)
        # A fourth round must not reach the model.
        self.round("d" * 40, next_head="e" * 40)
        self.assertEqual(len(self.model_calls()), 3, "the cycle limit must stop the fourth round")
        self.assertEqual(self.state()["tasks"]["GA-01"]["rounds"], 3)

    def test_the_same_sha_is_never_reviewed_twice(self):
        """A repeated head SHA must not start a second model round for the same review."""
        self.repo.dirty = ["backend/main.py"]
        self.round(HEAD_SHA, next_head=NEW_SHA)
        self.assertEqual(len(self.model_calls()), 1)
        self.round(HEAD_SHA, next_head=NEW_SHA)
        self.assertEqual(len(self.model_calls()), 1, "the same SHA must not launch the model again")
        self.assertEqual(self.state()["tasks"]["GA-01"]["rounds"], 1)

    def test_state_survives_a_crash_and_blocks_a_second_launch(self):
        """A crash between the launch record and the result must not re-trigger the model."""
        self.repo.dirty = ["backend/main.py"]
        crash = OSError("the dispatcher process was killed")
        self.runner.handler = lambda argv: crash if (argv and is_node(argv)) else self.repo.handler(argv)
        with self.assertRaises(OSError):
            self.round(HEAD_SHA)
        state = self.state()
        key = "1:" + HEAD_SHA + ":CHANGES_REQUESTED"
        self.assertIn(key, state["runs"], "the launch record must survive the crash")
        self.assertEqual(state["runs"][key]["status"], "LAUNCHED")
        self.assertEqual(state["tasks"]["GA-01"]["rounds"], 1)
        # A second attempt with the same SHA must not call the model again.
        calls_before = len(self.model_calls())
        self.runner.handler = self.repo.handler
        self.round(HEAD_SHA)
        self.assertEqual(len(self.model_calls()), calls_before, "a crashed launch must not be repeated")
        self.assertEqual(self.state()["tasks"]["GA-01"]["rounds"], 1)


if __name__ == "__main__":
    unittest.main()
