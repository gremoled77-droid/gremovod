"""Offline regression tests for new-branch ownership guard."""
import json
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


if __name__ == "__main__":
    unittest.main()
