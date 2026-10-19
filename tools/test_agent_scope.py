"""Offline regression tests for new-branch ownership guard."""
import unittest
from tools.check_agent_scope import role_for_branch, forbidden_files


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


if __name__ == "__main__":
    unittest.main()
