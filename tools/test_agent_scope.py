"""Offline regression tests for new-branch ownership guard."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.check_agent_scope import (
    ROOT,
    forbidden_files,
    load_manifest,
    manifest_tasks,
    role_for_branch,
    task_key_for_branch,
    validate_manifest,
)

MANIFEST_FILE = ROOT / "tools" / "minimax_task_scopes.json"

# The real control code and the real manifest are what the CI runs, so the tests
# below exercise the shipped files instead of a copy that could drift.
REAL_VALIDATOR = (ROOT / "tools" / "check_agent_scope.py").read_text(encoding="utf8")
REAL_MANIFEST = MANIFEST_FILE.read_text(encoding="utf8")

# The lowest trusted-interface version this repository knows how to drive. A base
# revision with an older validator cannot judge a pull request, and the workflow
# falls back to the bootstrap path instead of running a half-understood tool.
SCOPE_MIN_INTERFACE = 2


def repo_manifest():
    return json.loads(MANIFEST_FILE.read_text(encoding="utf8"))


class AgentScopeTests(unittest.TestCase):
    def test_new_task_branch_roles(self):
        self.assertEqual(role_for_branch("build/claude/stage-1-db"),"claude")
        self.assertEqual(role_for_branch("build/argon/stage-4-mock"),"argon")
        self.assertEqual(role_for_branch("codex/review-p0"),"codex")
        self.assertEqual(role_for_branch("codex/spec-n35"),"codex")
        self.assertEqual(role_for_branch("coordination/agent-roles-handoff-20261019"),"coordination")

    def test_legacy_worktrees_not_retroactively_blocked(self):
        for branch in ("main","claude/work","codex/work","feature/p0-studio-foundation-20261019"):
            self.assertIsNone(role_for_branch(branch))
            self.assertFalse(forbidden_files(branch, ["backend/main.py"]))

    def test_argon_cannot_change_sql_or_canon(self):
        forbidden=forbidden_files("build/argon/n8n-test",
                                  ["workflows/WF_01_Writers_Room.json",
                                   "integrations/n8n/README.md",
                                   "db/schema.sql","canon/characters/graham.json"])
        self.assertEqual(forbidden,["db/schema.sql","canon/characters/graham.json"])

    def test_claude_cannot_change_spec_or_canon(self):
        forbidden=forbidden_files("build/claude/stage-1-db",
                                  ["backend/p0_control.py", "tests/test_p0_state.js",
                                   "docs/specs/n8n-production-2026-10-19/nodes.json",
                                   "canon/characters/Graham.json"])
        self.assertEqual(len(forbidden),2)

    def test_codex_cannot_overwrite_builder_code(self):
        self.assertEqual(
            forbidden_files("codex/review-budget",[
                "docs/specs/n8n-production-2026-10-19/VALIDATION.json",
                "backend/main.py","scripts/p0_migrate.py"]),
            ["backend/main.py","scripts/p0_migrate.py"])

    def test_coordination_bootstrap_paths_are_bounded(self):
        self.assertFalse(forbidden_files("coordination/agent-roles-handoff-20261019",
                                         ["AGENT_BUILD_MANUAL.md","STATUS.md","AGENTS.md",
                                          "workflows/WF_00_Core_Infra.json",
                                          "prompts/README.md",
                                          ".github/workflows/agent-scope-guard.yml"]))
        self.assertEqual(forbidden_files("coordination/agent-roles-handoff-20261019",
                                         ["backend/main.py"]),["backend/main.py"])


class TaskScopeTests(unittest.TestCase):
    """MiniMax/owner task branches are scoped through tools/minimax_task_scopes.json."""

    def test_task_key_is_read_from_task_branches(self):
        self.assertEqual(task_key_for_branch("minimax/ga-04-studio-offline-ci"), "ga-04")
        self.assertEqual(task_key_for_branch("minimax/ga-01-llm-settlement"), "ga-01")
        self.assertEqual(task_key_for_branch("mavis/ga-02-text-task-lifecycle"), "ga-02")

    def test_integration_and_legacy_branches_have_no_task_key(self):
        for branch in ("mavis/work", "mavis/p0-merge-trial", "minimax/p0-budget-authz",
                       "minimax/llm-gateway", "minimax/money-ledger-20261020",
                       "feature/gremovod-agent-monitor-v1", "main"):
            self.assertIsNone(task_key_for_branch(branch), branch)

    def test_legacy_branches_stay_unenforced_even_with_a_manifest(self):
        manifest = repo_manifest()
        for branch in ("mavis/work", "minimax/p0-budget-authz", "feature/whatever"):
            self.assertEqual(forbidden_files(branch, ["backend/main.py"], manifest), [])

    def test_task_branch_may_touch_its_declared_files(self):
        manifest = repo_manifest()
        own = [".github/workflows/studio-offline-ci.yml",
               "tools/check_agent_scope.py",
               "tools/minimax_task_scopes.json"]
        self.assertEqual(forbidden_files("minimax/ga-04-studio-offline-ci", own, manifest), [])

    def test_task_branch_is_blocked_on_a_foreign_path(self):
        manifest = repo_manifest()
        foreign = ["frontend/src/App.tsx", "backend/main.py", "canon/characters/graham.json"]
        self.assertEqual(
            forbidden_files("minimax/ga-04-studio-offline-ci", foreign, manifest),
            foreign)

    def test_ga_01_scope_covers_its_own_llm_settlement_files(self):
        manifest = repo_manifest()
        own = ["backend/llm_guard.py", "backend/main.py", "backend/test_llm_settlement.py"]
        self.assertEqual(forbidden_files("minimax/ga-01-llm-settlement", own, manifest), [])

    def test_unknown_task_branch_fails_closed(self):
        manifest = repo_manifest()
        paths = ["backend/main.py", "docs/somewhere.md"]
        self.assertEqual(forbidden_files("minimax/ga-99-unknown-task", paths, manifest), paths)

    def test_common_allow_permits_a_task_to_write_its_documentation(self):
        manifest = repo_manifest()
        docs = ["docs/audits/ga-01-note.md", "docs/HANDOFF_CLAUDE_CODE.md"]
        self.assertEqual(forbidden_files("minimax/ga-01-llm-settlement", docs, manifest), [])

    def test_common_deny_blocks_the_protected_areas(self):
        manifest = repo_manifest()
        protected = [
            "canon/characters/graham.json",
            "skills/gremovod-screenplay/SKILL.md",
            "docs/specs/n8n-production-2026-10-19/nodes.json",
            "AGENTS.md",
            "CLAUDE.md",
            "AGENT_BUILD_MANUAL.md",
        ]
        self.assertEqual(
            forbidden_files("minimax/ga-04-studio-offline-ci", protected, manifest),
            protected)

    def test_common_deny_wins_over_a_task_scope(self):
        manifest = {
            "tasks": {"ga-01": {"allow": ["canon/characters/graham.json"]}},
            "common_allow": [],
            "common_deny": ["canon/"],
        }
        self.assertEqual(
            forbidden_files("minimax/ga-01-llm-settlement",
                            ["canon/characters/graham.json"], manifest),
            ["canon/characters/graham.json"])

    def test_ga_05_scope_covers_the_trusted_proxy_task_files(self):
        manifest = repo_manifest()
        own = ["backend/remote_access.py", "backend/test_remote_access.py",
               ".env.cloud.example", "docs/CLOUD_DEPLOY.md"]
        self.assertEqual(forbidden_files("minimax/ga-05-trusted-proxy-throttle", own, manifest), [])

    def test_missing_manifest_fails_closed(self):
        paths = ["backend/main.py"]
        self.assertEqual(forbidden_files("minimax/ga-04-studio-offline-ci", paths, None), paths)

    def test_repository_manifest_is_valid(self):
        self.assertEqual(validate_manifest(repo_manifest()), [])

    def test_repository_manifest_declares_every_backlog_task(self):
        tasks = repo_manifest()["tasks"]
        for key in ("ga-01", "ga-02", "ga-03", "ga-04", "ga-05"):
            self.assertIn(key, tasks)

    def test_repository_manifest_paths_are_plausible(self):
        """Allowed paths may be files a task has not created yet, but their directory
        must exist: that catches typos in the directory part without blocking a task
        that legitimately creates a new file."""
        for key, entry in repo_manifest()["tasks"].items():
            for path in entry["allow"]:
                target = ROOT / path
                self.assertTrue(target.exists() or target.parent.is_dir(),
                                f"{key}: {path}")

    def test_invalid_manifest_is_reported(self):
        problems = validate_manifest({"tasks": {"ga-01": {"allow": []}}})
        self.assertTrue(problems)
        self.assertTrue(validate_manifest({"tasks": {"GA_1": {"allow": ["a"]}}}))
        self.assertTrue(validate_manifest({"nope": 1}))

    def test_manifest_is_loaded_from_the_base_commit_when_present(self):
        manifest, bootstrapped, in_force = load_manifest("mavis/work")
        self.assertIsInstance(manifest, dict)
        self.assertIn("tasks", manifest)
        self.assertIsInstance(bootstrapped, bool)
        self.assertIsInstance(in_force, bool)

    def test_no_manifest_anywhere_means_scopes_are_not_in_force(self):
        """A task branch created before the manifest existed must not be failed
        closed: it would be blocked for touching its own files."""
        with tempfile.TemporaryDirectory() as tmp:
            manifest, bootstrapped, in_force = load_manifest("no-such-base-xyz", Path(tmp))
            self.assertFalse(in_force)
            self.assertEqual(manifest_tasks(manifest), {})


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          capture_output=True, text=True)


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf8")


def _make_repository(root, base_files):
    """Create a bare origin plus a working clone that holds one base revision."""
    origin = Path(root) / "origin.git"
    work = Path(root) / "work"
    subprocess.run(["git", "init", "--quiet", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "init", "--quiet", "-b", "main", str(work)], check=True)
    _git(work, "config", "user.email", "ci@example.test")
    _git(work, "config", "user.name", "CI Probe")
    _git(work, "remote", "add", "origin", str(origin))
    for path, text in base_files.items():
        _write(work / path, text)
    _git(work, "add", "-A")
    _git(work, "commit", "-m", "base revision")
    _git(work, "push", "origin", "main")
    return work


def _materialize_trusted_code(work, base_ref, dest):
    """Mirror the workflow: the control code comes from the base revision."""
    dest = Path(dest)
    (dest / "tools").mkdir(parents=True, exist_ok=True)
    for name in ("check_agent_scope.py", "minimax_task_scopes.json"):
        result = subprocess.run(["git", "-C", str(work), "show", f"{base_ref}:tools/{name}"],
                                capture_output=True)
        if result.returncode == 0:
            (dest / "tools" / name).write_bytes(result.stdout)
    return dest / "tools" / "check_agent_scope.py"


def _control_code_mode(trusted_script):
    """Mirror the workflow: trusted only when the base validator speaks the interface."""
    script = Path(trusted_script)
    if not script.is_file():
        return "bootstrap"
    result = subprocess.run([sys.executable, str(script), "--interface-version"],
                            capture_output=True, text=True)
    try:
        version = int(result.stdout.strip())
    except ValueError:
        return "bootstrap"
    return "trusted" if version >= SCOPE_MIN_INTERFACE else "bootstrap"


def _run_scope_check(work, script, branch, base):
    return subprocess.run([sys.executable, str(script), "--branch", branch, "--base", base],
                          cwd=str(work), capture_output=True, text=True)


class TrustedControlCodeTests(unittest.TestCase):
    """The guard must judge a pull request with control code the pull request cannot change.

    Every test builds a real git repository and replays the protocol of
    ``.github/workflows/agent-scope-guard.yml``: the control code is taken from the
    base revision and run against the pull request head. Only git is read, nothing
    from the pull request is executed.
    """

    BASE_FILES = {
        "tools/check_agent_scope.py": REAL_VALIDATOR,
        "tools/minimax_task_scopes.json": REAL_MANIFEST,
        "backend/main.py": "# base\n",
        "backend/remote_access.py": "# base\n",
        ".github/workflows/agent-scope-guard.yml": "# base workflow\n",
    }

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.work = _make_repository(self._tmp.name, self.BASE_FILES)
        self.trusted = Path(self._tmp.name) / "trusted"

    def _pull_request(self, branch, files):
        """Create the pull request revision on top of the base revision."""
        _git(self.work, "checkout", "-B", branch, "main")
        for path, text in files.items():
            _write(self.work / path, text)
        _git(self.work, "add", "-A")
        _git(self.work, "commit", "-m", "pull request revision")

    def _run_ci_protocol(self, branch, base="main"):
        """Replay the workflow: trusted control code, or the bootstrap fallback."""
        script = _materialize_trusted_code(self.work, f"origin/{base}", self.trusted)
        if _control_code_mode(script) == "trusted":
            return _run_scope_check(self.work, script, branch, base)
        return _run_scope_check(self.work, self.work / "tools" / "check_agent_scope.py",
                                branch, base)

    def test_forbidden_file_is_rejected(self):
        self._pull_request("minimax/ga-05-trusted-proxy-throttle",
                           {"backend/main.py": "# forbidden\n"})
        result = self._run_ci_protocol("minimax/ga-05-trusted-proxy-throttle")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("CROSS_OWNER_CHANGE: backend/main.py", result.stdout)

    def test_replacing_the_validator_does_not_help(self):
        """The pull request rewrites the checker and touches a forbidden file."""
        noop = "import sys\nprint('SCOPE: everything is fine')\nsys.exit(0)\n"
        self._pull_request("minimax/ga-04-studio-offline-ci",
                           {"backend/main.py": "# forbidden\n",
                            "tools/check_agent_scope.py": noop})
        result = self._run_ci_protocol("minimax/ga-04-studio-offline-ci")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("CROSS_OWNER_CHANGE: backend/main.py", result.stdout)

    def test_widening_the_allowlist_does_not_help(self):
        """The pull request adds the forbidden file to its own scope."""
        manifest = json.loads(REAL_MANIFEST)
        manifest["tasks"]["ga-05"]["allow"].append("backend/main.py")
        self._pull_request("minimax/ga-05-trusted-proxy-throttle",
                           {"backend/main.py": "# forbidden\n",
                            "tools/minimax_task_scopes.json": json.dumps(manifest, indent=2)})
        result = self._run_ci_protocol("minimax/ga-05-trusted-proxy-throttle")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("CROSS_OWNER_CHANGE: backend/main.py", result.stdout)

    def test_changing_the_workflow_is_reported(self):
        """A pull request that edits the guard itself is named in the check output."""
        self._pull_request("minimax/ga-04-studio-offline-ci",
                           {".github/workflows/agent-scope-guard.yml": "# neutered\n"})
        result = self._run_ci_protocol("minimax/ga-04-studio-offline-ci")
        self.assertIn("CONTROL_FILE_CHANGE: .github/workflows/agent-scope-guard.yml",
                      result.stdout)

    def test_allowed_change_passes(self):
        self._pull_request("minimax/ga-05-trusted-proxy-throttle",
                           {"backend/remote_access.py": "# allowed\n"})
        result = self._run_ci_protocol("minimax/ga-05-trusted-proxy-throttle")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_legacy_branches_keep_their_documented_behaviour(self):
        self._pull_request("build/claude/stage-1-db",
                           {"canon/characters/graham.json": "# forbidden\n"})
        result = self._run_ci_protocol("build/claude/stage-1-db")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("CROSS_OWNER_CHANGE: canon/characters/graham.json", result.stdout)
        self._pull_request("feature/whatever", {"backend/main.py": "# not enforced\n"})
        result = self._run_ci_protocol("feature/whatever")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_base_revision_without_a_guard_is_the_bootstrap_case(self):
        """A base revision that cannot judge the pull request is a separate case."""
        with tempfile.TemporaryDirectory() as tmp:
            work = _make_repository(tmp, {"backend/main.py": "# base\n"})
            script = _materialize_trusted_code(work, "origin/main", Path(tmp) / "trusted")
            self.assertEqual(_control_code_mode(script), "bootstrap")

    def test_base_revision_with_an_older_validator_is_the_bootstrap_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            legacy = Path(tmp) / "legacy"
            legacy.mkdir()
            (legacy / "check_agent_scope.py").write_text("print('legacy guard')\n",
                                                          encoding="utf8")
            self.assertEqual(_control_code_mode(legacy / "check_agent_scope.py"), "bootstrap")

    def test_trusted_control_code_answers_the_interface_version(self):
        script = _materialize_trusted_code(self.work, "origin/main", self.trusted)
        self.assertEqual(_control_code_mode(script), "trusted")

    def test_bootstrap_fallback_judges_the_pull_request_by_its_own_declaration(self):
        """Without a trusted guard the pull request's own validator runs, loudly."""
        with tempfile.TemporaryDirectory() as tmp:
            base = {"backend/main.py": "# base\n",
                    "tools/minimax_task_scopes.json": REAL_MANIFEST,
                    "backend/remote_access.py": "# base\n"}
            work = _make_repository(tmp, base)
            _git(work, "checkout", "-B", "minimax/ga-05-trusted-proxy-throttle", "main")
            _write(work / "tools" / "check_agent_scope.py", REAL_VALIDATOR)
            _write(work / "backend" / "main.py", "# forbidden\n")
            _git(work, "add", "-A")
            _git(work, "commit", "-m", "pull request revision")
            script = _materialize_trusted_code(work, "origin/main", Path(tmp) / "trusted")
            self.assertEqual(_control_code_mode(script), "bootstrap")
            result = _run_scope_check(work, work / "tools" / "check_agent_scope.py",
                                      "minimax/ga-05-trusted-proxy-throttle", "main")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("CROSS_OWNER_CHANGE: backend/main.py", result.stdout)


if __name__ == "__main__":
    unittest.main()