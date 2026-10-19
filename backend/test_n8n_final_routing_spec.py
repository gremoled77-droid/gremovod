"""Contract-only regression tests; no provider, no FFmpeg, no actual MP4 review."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]/"docs/specs/n8n-production-2026-10-19"
NODES=json.loads((ROOT/"nodes.json").read_text(encoding="utf-8"))
SCHEMA=json.loads((ROOT/"contracts/final-runtime-v1_2.schema.json").read_text(encoding="utf-8"))
LOOKUP={x["id"]:x for x in NODES["nodes"]}


class FinalReviewRuntimeSpec(unittest.TestCase):
    def test_versioned_spec_not_live(self):
        self.assertEqual(NODES["status"],"SPECIFIED_NOT_EXECUTED")
        self.assertEqual(len(LOOKUP),52)
        self.assertEqual(NODES["astra_runtime_model_matrix"],"N34_N41_RUNTIME_MODEL_MATRIX.md")

    def test_machine_contracts_present(self):
        req={"TechnicalQCResult","FrozenReviewPacket","ReviewerPacket","CriticVerdict",
             "DecisionEnvelope","OwnerReviewDecision","ReadyManifest"}
        self.assertEqual(set(SCHEMA["$defs"]),req)
        for name in req:
            d=SCHEMA["$defs"][name]
            self.assertEqual(d["type"],"object")
            self.assertFalse(d["additionalProperties"])
            self.assertGreater(len(d.get("required",[])),0)

    def test_no_llm_for_technical_or_owner_steps(self):
        for n in ("N34","N35","N39","N40","N41"):
            meta=LOOKUP[n]["astra_v1_2"]
            self.assertIn("NONE",meta["runtime_model_class"])
            self.assertEqual(meta["llm_calls"],0)
        self.assertIn("без LLM",LOOKUP["N34"]["name"])
        self.assertIn("ffprobe",LOOKUP["N34"]["executor"].lower())

    def test_creative_reviewers_are_bounded_and_separate(self):
        for n in ("N36","N37","N38"):
            meta=LOOKUP[n]["astra_v1_2"]
            self.assertEqual(meta["default_max_initial_calls"],1)
            self.assertIn("CriticVerdict",meta["output_contract"])
            self.assertGreater(len(meta["required_evidence"]),0)
            self.assertGreater(len(meta["blocked_without"]),1)
        self.assertEqual(LOOKUP["N38"]["astra_v1_2"]["runtime_status"],
                         "DISABLED_BLOCKED_UNTIL_MP4_AND_BUDGET")

    def test_n8n_cloud_is_not_local_media_worker(self):
        self.assertIn("not n8n Cloud",LOOKUP["S06"]["astra_v1_2"]["local_media_worker"])
        self.assertIn("Whisper",LOOKUP["S06"]["astra_v1_2"]["stt"])

    def test_review_binding_and_role_cardinality(self):
        snap=SCHEMA["$defs"]["FrozenReviewPacket"]["properties"]
        for name in ("master_checksum","snapshot_hash","media_manifest_hash","review_round_id"):
            self.assertIn(name,snap)
        self.assertEqual(snap["reviewer_packets"]["minItems"],3)
        self.assertEqual(snap["reviewer_packets"]["maxItems"],3)
        verdict=SCHEMA["$defs"]["CriticVerdict"]["properties"]
        self.assertEqual(set(verdict["verdict"]["enum"]),{"PASS","FAIL","BLOCKED"})
        self.assertEqual(set(verdict["role"]["enum"]),{"A6","A7","A8"})
        self.assertIn("checks",verdict)

    def test_media_proof_is_not_text(self):
        required=LOOKUP["N38"]["astra_v1_2"]["required_evidence"]
        self.assertIn("video_motion",required)
        self.assertIn("sound_listening",required)
        self.assertIn("actual_mp4",LOOKUP["N38"]["astra_v1_2"]["blocked_without"])

    def test_owner_gate_and_release_are_not_models(self):
        self.assertIn("owner_session",LOOKUP["N40"]["astra_v1_2"]["blocked_without"])
        self.assertIn("persisted_trusted_round",LOOKUP["N41"]["astra_v1_2"]["blocked_without"])
        decision=SCHEMA["$defs"]["OwnerReviewDecision"]["properties"]
        self.assertIn("verified_by_studio_session",decision)
        ready=SCHEMA["$defs"]["ReadyManifest"]["properties"]
        self.assertIn("stored_checksum",ready)

    def test_stt_cost_is_separate_from_llm(self):
        content=(ROOT/"N34_N41_RUNTIME_MODEL_MATRIX.md").read_text(encoding="utf-8")
        self.assertIn("платный",content)
        self.assertIn("Whisper",content)
        self.assertIn("n8n Cloud Execute Command",content)
        self.assertIn("1fps",content)

if __name__=="__main__":
    unittest.main()
