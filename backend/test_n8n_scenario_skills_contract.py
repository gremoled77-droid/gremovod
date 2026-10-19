"""N01–N11 scenario module contracts only; no real model or owner approval."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/specs/n8n-production-2026-10-19"
R = json.loads((BASE / "contracts/scenario-skills-routing-v1.json").read_text(encoding="utf-8"))
S = json.loads((BASE / "contracts/scenario-preprod-v1.schema.json").read_text(encoding="utf-8"))


class ScenarioSkillsContract(unittest.TestCase):
    def test_eleven_ordered_stages(self):
        stages = R["stages"]
        self.assertEqual([s["id"] for s in stages], [f"N{i:02d}" for i in range(1, 12)])
        self.assertEqual(len(set(s["produces"] for s in stages)), len(stages))

    def test_existing_skills_are_real_files(self):
        self.assertGreaterEqual(len(R["skills"]), 6)
        for item in R["skills"]:
            self.assertEqual(item["kind"], "repo_existing")
            self.assertTrue((ROOT / item["repository_path"]).is_file(), item["id"])
            self.assertTrue(item["used_by"])
            self.assertTrue(set(item["used_by"]).issubset(
                {f"N{i:02d}" for i in range(1, 12)} | {"N42"}))

    def test_proposed_skill_names_not_pretended_installed(self):
        options = {x["external_skill_name"]:x for x in R["optional_proposed_techniques"]}
        self.assertEqual(set(options), {
            "generate-fresh-ideas", "get-more-perspectives", "grem", "match-my-writing-style"})
        self.assertTrue(all(x["status"] == "NOT_FOUND_AS_INSTALLED_SKILL" for x in options.values()))

    def test_owner_approval_fences_real_work(self):
        self.assertFalse(R["allow_real_source_without_trusted_backend"])
        self.assertEqual(R["stages"][4]["engine"], "CODE_AND_OWNER")
        self.assertEqual(R["stages"][7]["engine"], "OWNER_APPROVAL")
        for s in ["OWNER_SELECT", "NEW_CANON", "PAID_GENERATE", "REAL_MEDIA_QA", "READY", "PUBLICATION"]:
            self.assertIn(s, R["explicit_no_auto"])
        self.assertFalse(R["cost_policy"]["budget_required_for_any_model"] is False)

    def test_required_critic_independence(self):
        roles = {x["id"]: x["role"] for x in R["stages"]}
        self.assertEqual(roles["N07"], "A6_A7_AND_ADVISORY_PERSPECTIVES")
        self.assertEqual(roles["N10"], "A6_A7_OPTIONAL_A8_TEXT")
        self.assertIn("no_silent_selection", R["stages"][7]["gate"])

    def test_default_concept_count_and_viability_different(self):
        self.assertIn("default_three_candidates", R["stages"][5]["gate"])
        self.assertIn("at_least_two_distinct_viable_options", R["stages"][5]["gate"])

    def test_json_boundaries_present_and_not_self_approving(self):
        defs = S["$defs"]
        self.assertEqual(len(defs), 8)
        required = {
            "IdeaIntake", "BriefCandidate", "FrozenBriefSnapshot", "ConceptCandidates",
            "ConceptReview", "OwnerConceptChoice", "ScriptCandidate", "DirectorPlan"}
        self.assertEqual(set(defs), required)
        self.assertEqual(defs["BriefCandidate"]["properties"]["status"]["const"], "CANDIDATE")
        self.assertIn("owner_verified_by_backend", defs["OwnerConceptChoice"]["required"])
        self.assertIn("approved_by_studio_owner", defs["FrozenBriefSnapshot"]["required"])
        self.assertEqual(defs["ConceptCandidates"]["properties"]["concepts"]["minItems"], 2)
        for v in defs.values():
            self.assertFalse(v["additionalProperties"])

    def test_dialogue_and_director_ids_preserved(self):
        script=S["$defs"]["ScriptCandidate"]["properties"]["scenes"]["items"]
        self.assertIn("dialogue", script["required"])
        self.assertIn("character_id", script["properties"]["dialogue"]["items"]["required"])
        director=S["$defs"]["DirectorPlan"]
        self.assertIn("asset_requests", director["required"])

    def test_no_default_paid_execution(self):
        self.assertEqual(R["runtime_provider"], "NONE_FOR_MOCK")
        self.assertEqual(R["cost_policy"]["mock_usd"], 0)
        self.assertEqual(R["source_context"]["test_material_status"], "SYNTHETIC_DEMO_INPUT")


if __name__ == "__main__":
    unittest.main()
