"""Offline regression tests for the Claude Code PreToolUse guards.

Every guard is exercised twice: once with an operation that must be allowed and
once with an operation that must be denied. The end-to-end cases run the hook
script as a subprocess with a real Claude Code hook payload on stdin, so the
JSON contract is covered as well as the decision logic.

Nothing here touches the network, a provider or the real studio database. The
Git cases run against a throwaway repository in a temporary directory.
"""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude" / "hooks"


def load_hook(name):
    """Import a hook script by path; '.claude' is not an importable package."""
    path = HOOKS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"claude_hook_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard_git = load_hook("guard_git")
guard_files = load_hook("guard_files")
guard_paid = load_hook("guard_paid")


def run_hook(script, payload):
    """Run a hook script with a payload on stdin and return the parsed answer."""
    result = subprocess.run(
        [sys.executable, str(HOOKS / script)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True, timeout=60, check=False,
    )
    return result.returncode, result.stdout.decode("utf-8", "replace")


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)


class TempRepo:
    """A throwaway repository with one commit and a selectable branch."""

    def __init__(self, branch):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name)
        git(self.path, "init", "-q", "-b", "main")
        git(self.path, "-c", "user.email=t@example.invalid", "-c", "user.name=t",
            "commit", "-q", "--allow-empty", "-m", "init")
        git(self.path, "symbolic-ref", "HEAD", f"refs/heads/{branch}")

    @property
    def cwd(self):
        return str(self.path)

    def close(self):
        self._tmp.cleanup()


class GitGuardTests(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo("feature/work")
        self.addCleanup(self.repo.close)

    def assertDenied(self, command, needle=None):
        allowed, reason = guard_git.check(command, self.repo.cwd)
        self.assertFalse(allowed, f"expected denial for: {command}")
        if needle:
            self.assertIn(needle, reason.lower())

    def assertAllowed(self, command):
        allowed, reason = guard_git.check(command, self.repo.cwd)
        self.assertTrue(allowed, f"expected allowance for: {command} ({reason})")

    def test_push_to_main_is_denied(self):
        self.assertDenied("git push origin main", "protected")

    def test_push_to_current_protected_branch_is_denied(self):
        repo = TempRepo("main")
        self.addCleanup(repo.close)
        allowed, _ = guard_git.check("git push", repo.cwd)
        self.assertFalse(allowed, "a bare push from a protected branch must be denied")

    def test_merge_of_main_is_denied(self):
        self.assertDenied("git merge origin/main", "protected")

    def test_merge_while_on_protected_branch_is_denied(self):
        repo = TempRepo("mavis/work")
        self.addCleanup(repo.close)
        allowed, _ = guard_git.check("git merge feature/x", repo.cwd)
        self.assertFalse(allowed, "merging while on a protected branch must be denied")

    def test_checkout_main_is_denied(self):
        self.assertDenied("git checkout main", "protected")

    def test_switch_to_main_is_denied(self):
        self.assertDenied("git switch main", "protected")

    def test_force_push_is_denied(self):
        self.assertDenied("git push --force origin feature/work", "force")

    def test_clean_force_is_denied(self):
        self.assertDenied("git clean -fdx", "clean")

    def test_delete_protected_branch_is_denied(self):
        self.assertDenied("git branch -D main", "protected")

    def test_remove_other_worktree_is_denied(self):
        self.assertDenied("git worktree remove ../somebody-else", "worktree")

    def test_push_task_branch_is_allowed(self):
        self.assertAllowed("git push -u origin feature/work")

    def test_push_feature_slash_main_is_allowed(self):
        self.assertAllowed("git push origin feature/main")

    def test_read_only_git_commands_are_allowed(self):
        self.assertAllowed("git status --short")
        self.assertAllowed("git log --oneline -5")
        self.assertAllowed("git diff origin/mavis/work...HEAD")

    def test_non_git_command_is_allowed(self):
        self.assertAllowed("npm test")

    def test_chained_command_containing_push_is_caught(self):
        self.assertDenied("git status && git push origin main", "protected")

    def test_outside_a_repository_a_plain_command_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            allowed, _ = guard_git.check("git status --short", tmp)
            self.assertTrue(allowed, "outside a repository the guard must not block")

    def test_outside_a_repository_an_explicit_protected_target_is_still_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            allowed, _ = guard_git.check("git push origin main", tmp)
            self.assertFalse(allowed, "an explicit protected target is denied everywhere")

    def test_empty_command_is_allowed(self):
        self.assertAllowed("")


class FileGuardTests(unittest.TestCase):
    def assertDenied(self, path, needle=None):
        allowed, reason = guard_files.check(path, str(ROOT))
        self.assertFalse(allowed, f"expected denial for: {path}")
        if needle:
            self.assertIn(needle, reason.lower())

    def assertAllowed(self, path):
        allowed, reason = guard_files.check(path, str(ROOT))
        self.assertTrue(allowed, f"expected allowance for: {path} ({reason})")

    def test_sqlite_database_is_denied(self):
        self.assertDenied(str(ROOT / "backend" / "studio.sqlite3"))

    def test_api_key_file_is_denied(self):
        self.assertDenied(str(ROOT / "PIAPI_API_KEY.txt"))

    def test_env_file_is_denied(self):
        self.assertDenied(str(ROOT / ".env"))

    def test_env_example_is_allowed(self):
        self.assertAllowed(str(ROOT / ".env.example"))

    def test_media_folder_is_denied(self):
        self.assertDenied(str(ROOT / "backend" / "media" / "frame.png"))

    def test_library_folder_is_denied(self):
        self.assertDenied(str(ROOT / "backend" / "library" / "ref.jpg"))

    def test_runtime_folder_is_denied(self):
        self.assertDenied(str(ROOT / "runtime" / "prompt-chat" / "worker-token.txt"))

    def test_local_settings_are_denied(self):
        self.assertDenied(str(ROOT / ".claude" / "settings.local.json"))

    def test_tracked_claude_config_is_allowed(self):
        self.assertAllowed(str(ROOT / ".claude" / "rules" / "backend.md"))
        self.assertAllowed(str(ROOT / ".claude" / "skills" / "gremovod-verify" / "SKILL.md"))
        self.assertAllowed(str(ROOT / ".claude" / "hooks" / "guard_git.py"))
        self.assertAllowed(str(ROOT / ".claude" / "settings.json"))

    def test_source_file_is_allowed(self):
        self.assertAllowed(str(ROOT / "backend" / "main.py"))

    def test_pem_key_is_denied(self):
        self.assertDenied(str(ROOT / "certs" / "server.pem"))


class PaidGuardTests(unittest.TestCase):
    def assertDenied(self, command, needle=None):
        allowed, reason = guard_paid.check(command)
        self.assertFalse(allowed, f"expected denial for: {command}")
        if needle:
            self.assertIn(needle, reason.lower())

    def assertAllowed(self, command):
        allowed, reason = guard_paid.check(command)
        self.assertTrue(allowed, f"expected allowance for: {command} ({reason})")

    def test_live_piapi_script_is_denied(self):
        self.assertDenied("python scripts/live_piapi_test.py", "money")

    def test_live_piapi_dry_run_is_allowed(self):
        self.assertAllowed("python scripts/live_piapi_test.py --dry-run")

    def test_hunyuan_watch_is_denied(self):
        self.assertDenied("python scripts/watch_hunyuan_test.py")

    def test_paid_host_call_is_denied(self):
        self.assertDenied("curl https://api.piapi.ai/v1/task")

    def test_spend_flag_is_denied(self):
        self.assertDenied("python scripts/generate.py --paid")

    def test_read_only_audit_is_allowed(self):
        self.assertAllowed("python scripts/p0_paid_dispatch_audit.py --markdown")

    def test_documentation_fetch_is_allowed(self):
        self.assertAllowed("curl https://developers.openai.com/api/docs/guides/x.md")

    def test_ordinary_command_is_allowed(self):
        self.assertAllowed("python -m unittest tests.test_claude_hooks -v")

    def test_opt_in_environment_variable_allows(self):
        import os
        previous = os.environ.get("GREMOVOD_ALLOW_PAID")
        os.environ["GREMOVOD_ALLOW_PAID"] = "1"
        try:
            allowed, _ = guard_paid.check("python scripts/live_piapi_test.py")
            self.assertTrue(allowed, "the explicit opt-in must open the guard")
        finally:
            if previous is None:
                os.environ.pop("GREMOVOD_ALLOW_PAID", None)
            else:
                os.environ["GREMOVOD_ALLOW_PAID"] = previous


class HookContractTests(unittest.TestCase):
    """The hook scripts must answer with the JSON Claude Code expects."""

    def setUp(self):
        self.repo = TempRepo("feature/work")
        self.addCleanup(self.repo.close)

    def test_denied_push_answers_with_deny_decision(self):
        code, out = run_hook("guard_git.py", {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "cwd": self.repo.cwd,
            "tool_input": {"command": "git push origin main"},
        })
        self.assertEqual(code, 0)
        answer = json.loads(out)
        decision = answer["hookSpecificOutput"]
        self.assertEqual(decision["hookEventName"], "PreToolUse")
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertTrue(decision["permissionDecisionReason"])

    def test_allowed_command_answers_with_continue(self):
        code, out = run_hook("guard_git.py", {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "cwd": self.repo.cwd,
            "tool_input": {"command": "git status --short"},
        })
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"continue": True})

    def test_denied_write_answers_with_deny_decision(self):
        code, out = run_hook("guard_files.py", {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "cwd": str(ROOT),
            "tool_input": {"file_path": str(ROOT / "backend" / "studio.sqlite3")},
        })
        self.assertEqual(code, 0)
        answer = json.loads(out)
        self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_denied_paid_command_answers_with_deny_decision(self):
        code, out = run_hook("guard_paid.py", {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "cwd": str(ROOT),
            "tool_input": {"command": "python scripts/live_piapi_test.py"},
        })
        self.assertEqual(code, 0)
        answer = json.loads(out)
        self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_malformed_payload_does_not_crash(self):
        result = subprocess.run(
            [sys.executable, str(HOOKS / "guard_git.py")],
            input=b"not json at all",
            capture_output=True, timeout=60, check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout.decode("utf-8")), {"continue": True})

    def test_empty_payload_does_not_crash(self):
        result = subprocess.run(
            [sys.executable, str(HOOKS / "guard_paid.py")],
            input=b"",
            capture_output=True, timeout=60, check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout.decode("utf-8")), {"continue": True})


if __name__ == "__main__":
    unittest.main()
