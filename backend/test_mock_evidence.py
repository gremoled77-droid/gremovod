"""Real mock FFmpeg evidence extraction, no STT or model calls."""
import shutil
import tempfile
import unittest
from pathlib import Path
from tools.mock_media_pilot import run_mock_pilot
from tools.mock_evidence import extract_n35_evidence


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"ffmpeg missing")
class MockEvidenceTests(unittest.TestCase):
    def test_three_timed_frames_and_audio_actual_media(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            assets=root/"assets"
            run_mock_pilot(assets)
            evidence=extract_n35_evidence(
                assets/"master_scene.mp4",folder=root/"evidence",
                script_text="Кадр 1, кадр 2, кадр 3 — это только тест",
                canon_revision="DEMO_NOT_APPROVED")
            self.assertEqual(evidence["status"],"EVIDENCE_EXTRACTED_NOT_FULL_QA")
            self.assertEqual(len(evidence["frames"]),3)
            self.assertEqual([f["time_ms"] for f in evidence["frames"]],[1000,4000,7000])
            self.assertTrue(evidence["actual_audio_extracted"])
            self.assertTrue(evidence["actual_frames_extracted"])
            self.assertEqual(evidence["audio"]["stt"],"BLOCKED_STT_NOT_AVAILABLE")
            self.assertFalse(evidence["motion_evaluated"])
            self.assertFalse(evidence["final_release_approved"])
            self.assertEqual({r["role"] for r in evidence["role_reviews"]},{"A6","A7","A8"})
            self.assertTrue(all(r["verdict"]=="BLOCKED" for r in evidence["role_reviews"]))

    def test_changed_script_changes_snapshot_not_master(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            run_mock_pilot(root/"assets")
            a=extract_n35_evidence(root/"assets"/"master_scene.mp4",folder=root/"one",
                                   script_text="Сценарий 1",canon_revision="v1")
            b=extract_n35_evidence(root/"assets"/"master_scene.mp4",folder=root/"two",
                                   script_text="Сценарий 2",canon_revision="v1")
            self.assertEqual(a["master_checksum"],b["master_checksum"])
            self.assertNotEqual(a["snapshot_hash"],b["snapshot_hash"])


if __name__=="__main__":
    unittest.main()
