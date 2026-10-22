"""Offline regression tests for the Claude Code PreToolUse guards.

Every guard is exercised twice: once with an operation that must be allowed and
once with an operation that must be denied. The end-to-end cases run the hook
script as a subprocess with a real Claude Code hook payload on stdin, so the
JSON contract is covered as well as the decision logic.

Nothing here touches the network, a provider or the real studio database. The
Git cases run against throwaway repositories in temporary directories.
"""
import importlib.util
import json
import os
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

    def __init__(self, branch="feature/work", branches=(), remote=None, keep_main=True):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name)
        git(self.path, "init", "-q", "-b", "main")
        git(self.path, "-c", "user.email=t@example.invalid", "-c", "user.name=t",
            "commit", "-q", "--allow-empty", "-m", "init")
        if branch != "main":
            git(self.path, "branch", branch)
        for name in branches:
            git(self.path, "branch", name)
        if remote:
            git(self.path, "remote", "add", "origin", remote)
        git(self.path, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
        if not keep_main:
            git(self.path, "branch", "-D", "main")

    @property
    def cwd(self):
        return str(self.path)

    def close(self):
        self._tmp.cleanup()


class GitGuardTests(unittest.TestCase):
    def setUp(self):
        self.repo = TempRepo("feature/work")
        self.addCleanup(self.repo.close)

    def assertDenied(self, command, needle=None, cwd=None):
        allowed, reason = guard_git.check(command, cwd or self.repo.cwd)
        self.assertFalse(allowed, f"expected denial for: {command}")
        if needle:
            self.assertIn(needle, reason.lower())

    def assertAllowed(self, command, cwd=None):
        allowed, reason = guard_git.check(command, cwd or self.repo.cwd)
        self.assertTrue(allowed, f"expected allowance for: {command} ({reason})")

    # -- source versus target -------------------------------------------------

    def test_sync_merge_from_protected_source_is_allowed(self):
        # The task branch pulls the integration branch. The source is protected,
        # the branch being written is not.
        self.assertAllowed("git merge origin/mavis/work")

    def test_sync_merge_from_main_is_allowed(self):
        self.assertAllowed("git merge origin/main")

    def test_sync_rebase_onto_protected_source_is_allowed(self):
        self.assertAllowed("git rebase origin/mavis/work")

    def test_cherry_pick_from_protected_source_is_allowed(self):
        self.assertAllowed("git cherry-pick origin/mavis/work")

    def test_merge_into_protected_current_branch_is_denied(self):
        repo = TempRepo("mavis/work")
        self.addCleanup(repo.close)
        allowed, _ = guard_git.check("git merge feature/x", repo.cwd)
        self.assertFalse(allowed, "merging INTO a protected branch must be denied")

    def test_rebase_on_protected_current_branch_is_denied(self):
        repo = TempRepo("main")
        self.addCleanup(repo.close)
        allowed, _ = guard_git.check("git rebase origin/mavis/work", repo.cwd)
        self.assertFalse(allowed, "rebasing a protected branch must be denied")

    def test_reset_hard_on_protected_current_branch_is_denied(self):
        repo = TempRepo("main")
        self.addCleanup(repo.close)
        allowed, _ = guard_git.check("git reset --hard origin/mavis/work", repo.cwd)
        self.assertFalse(allowed, "resetting a protected branch must be denied")

    # -- push -----------------------------------------------------------------

    def test_push_to_main_is_denied(self):
        self.assertDenied("git push origin main", "protected")

    def test_push_refspec_into_main_is_denied(self):
        self.assertDenied("git push origin HEAD:main", "protected")

    def test_push_delete_of_main_is_denied(self):
        self.assertDenied("git push origin --delete main", "protected")

    def test_push_to_current_protected_branch_is_denied(self):
        repo = TempRepo("main")
        self.addCleanup(repo.close)
        allowed, _ = guard_git.check("git push", repo.cwd)
        self.assertFalse(allowed, "a bare push from a protected branch must be denied")

    def test_push_to_protected_upstream_is_denied(self):
        repo = TempRepo("feature/work")
        self.addCleanup(repo.close)
        git(repo.path, "branch", "--set-upstream-to=main", "feature/work")
        allowed, _ = guard_git.check("git push", repo.cwd)
        self.assertFalse(allowed, "pushing to a protected upstream must be denied")

    def test_mass_push_with_one_protected_ref_is_denied(self):
        self.assertDenied("git push origin feature/work main", "protected")

    def test_mass_push_to_task_branches_is_allowed(self):
        self.assertAllowed("git push origin feature/work feature/other")

    def test_push_all_is_denied_when_a_protected_branch_exists(self):
        repo = TempRepo("feature/work")
        self.addCleanup(repo.close)
        allowed, _ = guard_git.check("git push --all origin", repo.cwd)
        self.assertFalse(allowed, "push --all must not carry a protected branch")

    def test_push_all_without_protected_branch_is_allowed(self):
        repo = TempRepo("feature/work", keep_main=False)
        self.addCleanup(repo.close)
        allowed, _ = guard_git.check("git push --all origin", repo.cwd)
        self.assertTrue(allowed, "push --all without a protected branch is allowed")

    def test_push_mirror_is_denied(self):
        self.assertDenied("git push --mirror origin", "mirror")

    def test_push_tags_is_allowed(self):
        self.assertAllowed("git push origin --tags")

    def test_force_push_is_denied(self):
        self.assertDenied("git push --force origin feature/work", "force")

    def test_force_push_short_flag_is_denied(self):
        self.assertDenied("git push -f origin feature/work", "force")

    def test_force_push_clustered_flags_is_denied(self):
        self.assertDenied("git push -fu origin feature/work", "force")

    def test_force_with_lease_is_denied(self):
        self.assertDenied("git push --force-with-lease origin feature/work", "force")

    def test_push_task_branch_is_allowed(self):
        self.assertAllowed("git push -u origin feature/work")

    def test_push_feature_slash_main_is_allowed(self):
        self.assertAllowed("git push origin feature/main")

    # -- alternative working directory ---------------------------------------

    def test_git_with_alternative_directory_is_checked(self):
        other = TempRepo("main")
        self.addCleanup(other.close)
        allowed, _ = guard_git.check(f"git -C {other.cwd} push origin main", self.repo.cwd)
        self.assertFalse(allowed, "-C must switch the repository the guard inspects")

    def test_git_with_alternative_directory_on_task_branch_is_allowed(self):
        other = TempRepo("feature/other")
        self.addCleanup(other.close)
        allowed, _ = guard_git.check(f"git -C {other.cwd} push origin feature/other", self.repo.cwd)
        self.assertTrue(allowed, "a task branch in another directory is allowed")

    # -- branch and worktree deletion ----------------------------------------

    def test_delete_protected_branch_is_denied(self):
        self.assertDenied("git branch -D main", "protected")

    def test_delete_current_branch_is_denied(self):
        self.assertDenied("git branch -D feature/work", "branch")

    def test_delete_branch_used_by_another_worktree_is_denied(self):
        git(self.repo.path, "branch", "feature/shared")
        with tempfile.TemporaryDirectory() as holder:
            worktree_path = Path(holder) / "wt"
            git(self.repo.path, "worktree", "add", "-q", str(worktree_path), "feature/shared")
            self.assertDenied("git branch -D feature/shared", "worktree")

    def test_remove_other_worktree_is_denied(self):
        self.assertDenied("git worktree remove ../somebody-else", "worktree")

    def test_remove_current_worktree_is_denied(self):
        self.assertDenied(f"git worktree remove {self.repo.cwd}", "worktree")

    # -- destructive local operations -----------------------------------------

    def test_clean_force_is_denied(self):
        self.assertDenied("git clean -fdx", "clean")

    def test_checkout_main_is_denied(self):
        self.assertDenied("git checkout main", "protected")

    def test_switch_to_main_is_denied(self):
        self.assertDenied("git switch main", "protected")

    def test_checkout_new_branch_is_allowed(self):
        self.assertAllowed("git checkout -b feature/new")

    def test_bulk_discard_of_changes_is_denied(self):
        self.assertDenied("git checkout -- .", "discard")
        self.assertDenied("git restore .", "discard")

    def test_checkout_dot_is_denied(self):
        self.assertDenied("git checkout .", "discard")

    def test_checkout_tree_path_is_denied(self):
        (self.repo.path / "tree").mkdir()
        self.assertDenied("git checkout tree", "discard")

    def test_checkout_head_with_dot_is_denied(self):
        self.assertDenied("git checkout HEAD -- .", "discard")

    def test_restore_tree_path_is_denied(self):
        (self.repo.path / "tree").mkdir()
        self.assertDenied("git restore tree", "discard")

    def test_restore_worktree_with_dot_is_denied(self):
        self.assertDenied("git restore --worktree .", "discard")

    def test_restore_without_a_path_is_denied(self):
        self.assertDenied("git restore", "discard")

    def test_restore_staged_dot_is_allowed(self):
        # Index only: the change is not lost, just unstaged.
        self.assertAllowed("git restore --staged .")

    def test_checkout_single_file_is_allowed(self):
        self.assertAllowed("git checkout -- notes.txt")

    def test_stash_clear_is_denied(self):
        self.assertDenied("git stash clear", "stash")

    def test_reset_hard_with_uncommitted_changes_is_denied(self):
        repo = TempRepo("feature/work")
        self.addCleanup(repo.close)
        (repo.path / "scratch.txt").write_text("wip", encoding="utf-8")
        allowed, _ = guard_git.check("git reset --hard HEAD~1", repo.cwd)
        self.assertFalse(allowed, "reset --hard must not discard uncommitted work")

    def test_reset_hard_on_clean_tree_is_allowed(self):
        self.assertAllowed("git reset --hard HEAD")

    # -- harmless operations --------------------------------------------------

    def test_read_only_git_commands_are_allowed(self):
        self.assertAllowed("git status --short")
        self.assertAllowed("git log --oneline -5")
        self.assertAllowed("git diff origin/mavis/work...HEAD")

    def test_non_git_command_is_allowed(self):
        self.assertAllowed("npm test")

    def test_chained_command_containing_push_is_caught(self):
        self.assertDenied("git status && git push origin main", "protected")

    def test_chained_sync_merge_is_allowed(self):
        self.assertAllowed("git fetch origin && git merge origin/mavis/work")

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

    # -- canonicalisation -----------------------------------------------------

    def test_path_with_parent_segments_is_canonicalised(self):
        self.assertDenied(str(ROOT / "backend" / ".." / "backend" / "studio.sqlite3"))

    def test_relative_path_is_resolved_against_the_project(self):
        self.assertDenied("backend/studio.sqlite3")
        self.assertDenied("runtime/worker-token.txt")

    def test_write_outside_the_worktree_is_denied(self):
        # Outside the worktree and outside every designated temporary root.
        outside = Path(tempfile.gettempdir()).parent / "gremovod_outside_probe" / "notes.txt"
        self.assertDenied(str(outside), "outside")

    def test_symlink_escaping_the_worktree_is_denied(self):
        outside = Path(tempfile.gettempdir()).parent / "gremovod_symlink_target.txt"
        link = ROOT / "_tmp_link_probe.txt"
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks are not available in this environment")
        try:
            self.assertDenied(str(link), "outside")
        finally:
            link.unlink()

    def test_symlink_into_a_temporary_root_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target.sqlite3"
            link = ROOT / "_tmp_link_probe.sqlite3"
            try:
                os.symlink(target, link)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are not available in this environment")
            try:
                self.assertAllowed(str(link))
            finally:
                link.unlink()

    # -- temporary test data --------------------------------------------------

    def test_temporary_database_in_the_os_temp_dir_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertAllowed(str(Path(tmp) / "test.sqlite3"))
            self.assertAllowed(str(Path(tmp) / "frame.png"))

    def test_temporary_data_in_the_repo_tmp_folder_is_allowed(self):
        self.assertAllowed(str(ROOT / "tmp" / "test.sqlite3"))

    def test_secret_shaped_file_in_a_temporary_folder_is_still_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertDenied(str(Path(tmp) / "PIAPI_API_KEY.txt"))

    def test_real_database_at_the_repository_root_is_denied(self):
        self.assertDenied(str(ROOT / "studio.sqlite3"))


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

    def test_two_dry_runs_are_allowed(self):
        self.assertAllowed(
            "python scripts/live_piapi_test.py --dry-run && "
            "python scripts/live_piapi_test.py --dry-run")

    def test_dry_run_followed_by_a_real_run_is_denied(self):
        # The dry-run exception belongs to one invocation, not to the whole line.
        self.assertDenied(
            "python scripts/live_piapi_test.py --dry-run && "
            "python scripts/live_piapi_test.py",
            "money")

    def test_dry_run_and_real_run_split_by_semicolon_is_denied(self):
        self.assertDenied(
            "python scripts/live_piapi_test.py --dry-run; "
            "python scripts/live_piapi_test.py",
            "money")

    def test_dry_run_and_real_run_split_by_a_pipe_are_denied(self):
        self.assertDenied(
            "python scripts/live_piapi_test.py --dry-run | "
            "python scripts/live_piapi_test.py",
            "money")

    def test_dry_run_and_real_run_split_by_or_are_denied(self):
        self.assertDenied(
            "python scripts/live_piapi_test.py --dry-run || "
            "python scripts/live_piapi_test.py",
            "money")

    def test_gated_script_followed_by_a_direct_call_is_denied(self):
        self.assertDenied(
            "python scripts/watch_hunyuan_test.py && "
            "python scripts/live_piapi_test.py",
            "money")

    def test_live_piapi_confirmed_run_is_denied(self):
        self.assertDenied("python scripts/live_piapi_test.py --yes", "money")

    def test_hunyuan_watch_is_denied_by_default(self):
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

    # -- the opt-in is not an authorisation -----------------------------------

    def test_opt_in_does_not_open_direct_provider_calls(self):
        previous = os.environ.get("GREMOVOD_ALLOW_GATED_PAID")
        os.environ["GREMOVOD_ALLOW_GATED_PAID"] = "1"
        try:
            allowed, _ = guard_paid.check("curl https://api.piapi.ai/v1/task")
            self.assertFalse(allowed, "a direct provider call must stay denied")
            allowed, _ = guard_paid.check("python scripts/live_piapi_test.py")
            self.assertFalse(allowed, "a direct provider call must stay denied")
        finally:
            if previous is None:
                os.environ.pop("GREMOVOD_ALLOW_GATED_PAID", None)
            else:
                os.environ["GREMOVOD_ALLOW_GATED_PAID"] = previous

    def test_opt_in_allows_the_gated_studio_path(self):
        previous = os.environ.get("GREMOVOD_ALLOW_GATED_PAID")
        os.environ["GREMOVOD_ALLOW_GATED_PAID"] = "1"
        try:
            allowed, reason = guard_paid.check("python scripts/watch_hunyuan_test.py")
            self.assertTrue(allowed, f"the gated studio path must be allowed: {reason}")
            self.assertIn("studio", reason.lower())
        finally:
            if previous is None:
                os.environ.pop("GREMOVOD_ALLOW_GATED_PAID", None)
            else:
                os.environ["GREMOVOD_ALLOW_GATED_PAID"] = previous

    def test_old_opt_in_name_is_not_honoured(self):
        previous = os.environ.get("GREMOVOD_ALLOW_PAID")
        os.environ["GREMOVOD_ALLOW_PAID"] = "1"
        try:
            allowed, _ = guard_paid.check("curl https://api.piapi.ai/v1/task")
            self.assertFalse(allowed, "the old variable must not authorise anything")
        finally:
            if previous is None:
                os.environ.pop("GREMOVOD_ALLOW_PAID", None)
            else:
                os.environ["GREMOVOD_ALLOW_PAID"] = previous

    # -- compound and indirect calls ------------------------------------------

    def test_paid_host_inside_a_nested_shell_is_denied(self):
        self.assertDenied('bash -c "curl https://api.piapi.ai/v1/task"')

    def test_paid_host_inside_cmd_is_denied(self):
        self.assertDenied('cmd /c "curl https://api.piapi.ai/v1/task"')

    def test_paid_host_after_a_chained_command_is_denied(self):
        self.assertDenied("git status && curl https://api.openai.com/v1/images")

    def test_paid_host_in_a_piped_segment_is_denied(self):
        self.assertDenied("echo x | curl https://api.minimax.io/v1/chat")

    def test_paid_host_in_an_environment_assignment_is_denied(self):
        self.assertDenied("set PIAPI_API_KEY=abc && curl https://api.kie.ai/v1/task")


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

    def test_sync_merge_answers_with_continue(self):
        code, out = run_hook("guard_git.py", {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "cwd": self.repo.cwd,
            "tool_input": {"command": "git merge origin/mavis/work"},
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

    def test_malformed_git_payload_fails_closed(self):
        """A payload that cannot be read cannot be verified, so it is refused."""
        result = subprocess.run(
            [sys.executable, str(HOOKS / "guard_git.py")],
            input=b"not json at all",
            capture_output=True, timeout=60, check=False,
        )
        self.assertEqual(result.returncode, 0)
        answer = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_empty_payload_does_not_crash(self):
        result = subprocess.run(
            [sys.executable, str(HOOKS / "guard_paid.py")],
            input=b"",
            capture_output=True, timeout=60, check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout.decode("utf-8")), {"continue": True})

    def test_malformed_file_payload_is_denied(self):
        """A write whose payload cannot be parsed must fail closed."""
        result = subprocess.run(
            [sys.executable, str(HOOKS / "guard_files.py")],
            input=b"not json at all",
            capture_output=True, timeout=60, check=False,
        )
        self.assertEqual(result.returncode, 0)
        answer = json.loads(result.stdout.decode("utf-8"))
        self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_write_without_a_path_is_denied(self):
        code, out = run_hook("guard_files.py", {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "cwd": str(ROOT),
            "tool_input": {},
        })
        self.assertEqual(code, 0)
        answer = json.loads(out)
        self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "deny")


if __name__ == "__main__":
    unittest.main()
