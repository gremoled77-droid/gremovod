"""Fail-closed check for three-agent handoff and seven scrubbed n8n MOCK exports.

Stdlib-only. Does not connect to n8n, GitHub, paid providers, Studio, or user's
local data. JSON validity and structure do NOT prove workflow runtime safety.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / "workflows"
NAMES = [
    "WF_00_Core_Infra",
    "WF_01_Writers_Room",
    "WF_02_Canon_And_Images",
    "WF_03_Audio_Factory",
    "WF_04_Video_And_LipSync",
    "WF_05_Assembly_And_Critics",
    "WF_06_Repair_Router",
]
ALLOWED_TYPES = {
    "n8n-nodes-base.manualTrigger",
    "n8n-nodes-base.executeWorkflowTrigger",
    "n8n-nodes-base.executeWorkflow",
    "n8n-nodes-base.code",
}


class CoordinationContractTests(unittest.TestCase):
    def load(self, name):
        with (WORKFLOWS / (name + ".json")).open(encoding="utf8") as fh:
            return json.load(fh)

    def test_seven_and_only_seven_source_exports(self):
        actual = {p.name for p in WORKFLOWS.glob("WF_*.json")}
        expected = {n + ".json" for n in NAMES}
        self.assertEqual(actual, expected)

    def test_exports_are_inactive_and_mock_only(self):
        for name in NAMES:
            with self.subTest(workflow=name):
                w = self.load(name)
                self.assertIs(w["active"], False)
                self.assertEqual(w["settings"]["executionOrder"], "v1")
                self.assertEqual(w.get("pinData"), {})
                self.assertTrue(w["nodes"])
                self.assertIn("MOCK", w["name"])
                for n in w["nodes"]:
                    self.assertIn(n["type"], ALLOWED_TYPES)
                    self.assertNotIn("credentials", n)
                    self.assertNotIn("webhookId", n)
                serialized = json.dumps(w, ensure_ascii=False)
                for forbidden in ('"apiKey"', '"authorization"', '"clientSecret"',
                                  '"accessToken"', '"password"', '"credentialId"'):
                    self.assertNotIn(forbidden, serialized)

    def test_child_modules_contain_no_paid_nodes(self):
        for name in NAMES[1:]:
            w = self.load(name)
            self.assertEqual(len(w["nodes"]), 2)
            types = {node["type"] for node in w["nodes"]}
            self.assertEqual(types, {"n8n-nodes-base.executeWorkflowTrigger", "n8n-nodes-base.code"})

    def test_parent_references_six_placeholders_not_live_instance_ids(self):
        w = self.load(NAMES[0])
        children = [n for n in w["nodes"] if n["type"] == "n8n-nodes-base.executeWorkflow"]
        self.assertEqual(len(children), 6)
        targets = [n["parameters"]["workflowId"]["value"] for n in children]
        self.assertEqual(targets, [
            f"REPLACE_WITH_IMPORTED_WF_0{i}_ID" for i in range(1, 7)])
        self.assertEqual(len(w["nodes"]), 9)

    def test_all_connections_point_to_named_nodes(self):
        for name in NAMES:
            w = self.load(name)
            names = {x["name"] for x in w["nodes"]}
            self.assertEqual(len(names), len(w["nodes"]))
            self.assertLessEqual(set(w["connections"]), names)
            for edges in w["connections"].values():
                for entries in edges.values():
                    for channel in entries:
                        for edge in channel or []:
                            self.assertIn(edge["node"], names)

    def test_handoff_and_ownership_docs(self):
        for path in (
            "AGENT_BUILD_MANUAL.md", "STATUS.md", "docs/AGENT_ROLE_MATRIX.md",
            "docs/CODEX_REVIEW_PACKET.md", "docs/agent_handoffs/README.md",
            "docs/agent_handoffs/coordination-bootstrap.md",
            "prompts/README.md", "workflows/README.md",
        ):
            self.assertTrue((ROOT / path).is_file(), path)
        manual = (ROOT / "AGENT_BUILD_MANUAL.md").read_text(encoding="utf8")
        for role in ("Codex", "Claude Code", "Argon", "main", "STATUS.md"):
            self.assertIn(role, manual)

    def test_existing_root_agent_policy_references_handoff(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf8")
        self.assertIn("CLAUDE.md", agents)
        self.assertIn("AGENT_BUILD_MANUAL.md", agents)
        self.assertIn("STATUS.md", agents)

    def test_no_automerge_or_approval_claims(self):
        status = (ROOT / "STATUS.md").read_text(encoding="utf8")
        self.assertIn("READY_FOR_CODEX_REVIEW", status)
        self.assertIn("BLOCKED_NO_USER_MP4", status)
        self.assertIn("BLOCKED_NO_TRUSTED_REQUEST_APPROVAL", status)


if __name__ == "__main__":
    unittest.main()
