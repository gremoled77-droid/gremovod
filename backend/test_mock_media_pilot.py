"""Zero-dollar media tests, actual local ffmpeg+ffprobe on disposable files."""
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.mock_media_pilot import MockMediaError, n34_technical_qc, run_mock_pilot


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),
                     "FFmpeg/ffprobe are required for actual mock-media acceptance")
class MockMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output=Path(self.temp.name)/"pilot"

    def test_three_shots_montage_and_repair_actual_ffmpeg(self):
        r=run_mock_pilot(self.output)
        self.assertTrue(r["MOCK_MODE"])
        self.assertEqual(r["media_count"],3)
        self.assertEqual(r["sound_stems"],3)
        self.assertEqual(r["repaired_slot_id"],"shot_02")
        self.assertTrue(r["unaffected_shots_reused"])
        self.assertNotEqual(r["new_shot_checksum"],r["previous_shot_checksum"])
        self.assertEqual(r["n34_technical_only"]["status"],"PASS_TECHNICAL_ONLY")
        self.assertGreaterEqual(r["total_duration_seconds"],8.5)
        self.assertFalse(r["production_ready"])
        self.assertFalse(r["owner_ready"])
        self.assertEqual(r["paid_provider_calls"],0)
        self.assertEqual(r["A6_A7_A8"],"BLOCKED_NOT_REAL_USER_MEDIA")

    def test_missing_master_fails_closed(self):
        status=n34_technical_qc(self.output/"no-such-video.mp4")
        self.assertEqual(status["status"],"BLOCKED_NO_MEDIA")

    def test_rejects_nonempty_media_destination(self):
        self.output.mkdir()
        (self.output/"important-user-file.txt").write_text("do not overwrite")
        with self.assertRaises(MockMediaError):
            run_mock_pilot(self.output)
        self.assertEqual((self.output/"important-user-file.txt").read_text(),"do not overwrite")


if __name__=="__main__":
    unittest.main()
