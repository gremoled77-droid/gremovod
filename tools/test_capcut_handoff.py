"""Offline tests for the CapCut handoff pack builder.

No network, no Studio process, no SQLite, no paid API. Synthetic media comes from
the existing local mock-media engine in ``tools/mock_media_pilot.py`` — this file
does not create a second mock-media engine.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tools import capcut_handoff
from tools import mock_media_pilot

HAVE_MEDIA_TOOLS = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def make_row(order, video, image="", scene=1, frame=None, title="Кадр"):
    """One edit-list row in the shape produced by ``backend/edit_list.py``."""
    return {"order": order, "scene": scene, "frame": order if frame is None else frame,
            "title": title, "video": video, "image": image, "duration": 3.0}


@unittest.skipUnless(HAVE_MEDIA_TOOLS, "ffmpeg/ffprobe are required for synthetic media")
class CapCutHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.media = self.root / "media"
        (self.media / "clips").mkdir(parents=True)
        (self.media / "refs").mkdir(parents=True)
        (self.media / "audio").mkdir(parents=True)
        self.output = self.root / "out"
        self.list_path = self.root / "edit-list.json"

    # ---------- helpers ----------

    def write_edit_list(self, rows, warnings=None):
        payload = {"summary": {"shots": len(rows)}, "warnings": warnings or [], "rows": rows}
        self.list_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.list_path

    def make_clip(self, relative, color="navy", frequency=220):
        path = self.media / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        mock_media_pilot.make_video(path, color=color, frequency=frequency)
        return path

    def make_image(self, relative, color="teal"):
        path = self.media / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        mock_media_pilot.make_png(path, color)
        return path

    def make_voice(self, relative, frequency=330):
        path = self.media / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        mock_media_pilot.make_voice(path, frequency=frequency)
        return path

    def export(self, **kwargs):
        return capcut_handoff.export_handoff(self.list_path, self.media, self.output, **kwargs)

    def issue_codes(self, manifest, severity=None):
        return [i["code"] for i in manifest["issues"]
                if severity is None or i["severity"] == severity]

    # ---------- 1. three synthetic clips in edit-list order ----------

    def test_three_clips_are_exported_in_edit_list_order(self):
        self.make_clip("clips/shot01.mp4", color="navy", frequency=220)
        self.make_clip("clips/shot02.mp4", color="teal", frequency=275)
        self.make_clip("clips/shot03.mp4", color="purple", frequency=330)
        self.write_edit_list([
            make_row(1, "clips/shot01.mp4", title="Общий"),
            make_row(2, "clips/shot02.mp4", title="Крупный"),
            make_row(3, "clips/shot03.mp4", title="Реакция"),
        ])

        manifest = self.export()

        clips = sorted(p.name for p in (self.output / "01_Clips").iterdir())
        self.assertEqual(clips, ["001_scene01_shot01.mp4",
                                 "002_scene01_shot02.mp4",
                                 "003_scene01_shot03.mp4"])
        self.assertEqual([c["order"] for c in manifest["clips"]], [1, 2, 3])
        self.assertEqual([c["path"] for c in manifest["clips"]],
                         ["01_Clips/001_scene01_shot01.mp4",
                          "01_Clips/002_scene01_shot02.mp4",
                          "01_Clips/003_scene01_shot03.mp4"])
        self.assertTrue(manifest["ready_for_montage"])
        self.assertEqual(manifest["status"], "READY_FOR_MONTAGE")

    # ---------- 2. separate voice / music / sfx tracks ----------

    def test_separate_audio_tracks_voice_music_sfx(self):
        self.make_clip("clips/shot01.mp4")
        self.make_voice("audio/vo.wav", frequency=330)
        self.make_voice("audio/mu.wav", frequency=660)
        self.make_voice("audio/sx.wav", frequency=490)
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])

        manifest = self.export(audio_tracks={
            "voice": ["audio/vo.wav"],
            "music": ["audio/mu.wav"],
            "sfx": ["audio/sx.wav"],
        })

        self.assertTrue((self.output / "02_Audio/voice/vo.wav").is_file())
        self.assertTrue((self.output / "02_Audio/music/mu.wav").is_file())
        self.assertTrue((self.output / "02_Audio/sfx/sx.wav").is_file())
        self.assertEqual(manifest["audio_tracks"]["voice"][0]["path"], "02_Audio/voice/vo.wav")
        self.assertEqual(manifest["audio_tracks"]["music"][0]["path"], "02_Audio/music/mu.wav")
        self.assertEqual(manifest["audio_tracks"]["sfx"][0]["path"], "02_Audio/sfx/sx.wav")
        self.assertEqual(len(manifest["audio_tracks"]["voice"]), 1)

    def test_audio_track_not_passed_explicitly_is_not_filled(self):
        self.make_clip("clips/shot01.mp4")
        self.make_voice("audio/vo.wav", frequency=330)
        self.make_voice("audio/mu.wav", frequency=660)
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])

        manifest = self.export(audio_tracks={"voice": ["audio/vo.wav"]})

        self.assertTrue((self.output / "02_Audio/voice/vo.wav").is_file())
        self.assertEqual(list((self.output / "02_Audio/music").iterdir()), [])
        self.assertEqual(list((self.output / "02_Audio/sfx").iterdir()), [])
        self.assertEqual(manifest["audio_tracks"]["music"], [])
        self.assertEqual(manifest["audio_tracks"]["sfx"], [])

    def test_unknown_audio_track_is_rejected(self):
        self.make_clip("clips/shot01.mp4")
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])
        with self.assertRaises(capcut_handoff.HandoffError):
            self.export(audio_tracks={"ambience": ["audio/vo.wav"]})

    # ---------- 3. missing second clip ----------

    def test_missing_second_clip_is_reported_and_blocks_montage(self):
        self.make_clip("clips/shot01.mp4")
        self.make_clip("clips/shot03.mp4")
        self.write_edit_list([
            make_row(1, "clips/shot01.mp4"),
            make_row(2, "clips/shot02.mp4"),
            make_row(3, "clips/shot03.mp4"),
        ])

        manifest = self.export()

        self.assertFalse(manifest["ready_for_montage"])
        self.assertEqual(manifest["status"], "INCOMPLETE")
        self.assertIn("MISSING_CLIP", self.issue_codes(manifest, "blocking"))
        missing = [i for i in manifest["issues"] if i["code"] == "MISSING_CLIP"]
        self.assertIn("shot02.mp4", missing[0]["message"])
        self.assertTrue((self.output / "01_Clips/001_scene01_shot01.mp4").is_file())
        self.assertTrue((self.output / "01_Clips/003_scene01_shot03.mp4").is_file())
        self.assertFalse((self.output / "01_Clips/002_scene01_shot02.mp4").exists())
        # The manifest lists one clip entry per edit-list row: the gap stays visible.
        self.assertEqual(len(manifest["clips"]), 3)
        self.assertIsNone(manifest["clips"][1]["path"])
        self.assertEqual(manifest["counts"]["clips"], 2)

    # ---------- 4. repeated file names ----------

    def test_duplicate_destination_name_is_blocking_and_never_overwrites(self):
        first = self.make_clip("a/clip.mp4", color="navy")
        self.make_clip("b/clip.mp4", color="teal")
        original = mock_media_pilot.checksum(first)
        self.write_edit_list([
            make_row(1, "a/clip.mp4"),
            make_row(1, "b/clip.mp4"),
        ])

        manifest = self.export()

        self.assertFalse(manifest["ready_for_montage"])
        self.assertIn("DUPLICATE_DESTINATION_NAME", self.issue_codes(manifest, "blocking"))
        packed = list((self.output / "01_Clips").iterdir())
        self.assertEqual(len(packed), 1)
        self.assertEqual(mock_media_pilot.checksum(packed[0]), original)

    def test_reused_source_file_is_reported_without_blocking(self):
        source = self.make_clip("clips/shot01.mp4")
        self.write_edit_list([
            make_row(1, "clips/shot01.mp4"),
            make_row(2, "clips/shot01.mp4"),
        ])

        manifest = self.export()

        self.assertIn("DUPLICATE_SOURCE", self.issue_codes(manifest, "warning"))
        self.assertTrue(manifest["ready_for_montage"])
        self.assertEqual(len(list((self.output / "01_Clips").iterdir())), 2)
        self.assertEqual(mock_media_pilot.checksum(source), mock_media_pilot.checksum(source))

    # ---------- 5. source SHA changes between read and copy ----------

    def test_source_changed_during_export_is_detected(self):
        source = self.make_clip("clips/shot01.mp4")
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])
        original_copy = capcut_handoff.copy_file

        def mutate_after_copy(src, dest):
            original_copy(src, dest)
            src.write_bytes(src.read_bytes() + b"tampered-after-copy")

        capcut_handoff.copy_file = mutate_after_copy
        self.addCleanup(setattr, capcut_handoff, "copy_file", original_copy)

        manifest = self.export()

        self.assertFalse(manifest["ready_for_montage"])
        self.assertIn("SOURCE_CHANGED_DURING_EXPORT", self.issue_codes(manifest, "blocking"))

    def test_copy_content_mismatch_is_detected(self):
        self.make_clip("clips/shot01.mp4")
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])

        def corrupt_copy(src, dest):
            dest.write_bytes(b"not-the-source-bytes")

        original_copy = capcut_handoff.copy_file
        capcut_handoff.copy_file = corrupt_copy
        self.addCleanup(setattr, capcut_handoff, "copy_file", original_copy)

        manifest = self.export()

        self.assertFalse(manifest["ready_for_montage"])
        self.assertIn("COPY_MISMATCH", self.issue_codes(manifest, "blocking"))

    # ---------- 6. attempts to leave the allowed folder ----------

    def test_relative_path_escape_is_rejected(self):
        outside = self.root / "outside.mp4"
        outside.write_bytes(b"outside-the-root")
        self.write_edit_list([make_row(1, "../outside.mp4")])

        with self.assertRaises(capcut_handoff.HandoffError):
            self.export()

        self.assertFalse(self.output.exists())

    def test_absolute_path_outside_root_is_rejected(self):
        outside = self.root / "outside.mp4"
        outside.write_bytes(b"outside-the-root")
        self.write_edit_list([make_row(1, str(outside))])

        with self.assertRaises(capcut_handoff.HandoffError):
            self.export()

    def test_symlink_escape_is_rejected(self):
        outside = self.root / "outside.mp4"
        outside.write_bytes(b"outside-the-root")
        link = self.media / "clips" / "link.mp4"
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks are not available here: {exc}")
        self.write_edit_list([make_row(1, "clips/link.mp4")])

        with self.assertRaises(capcut_handoff.HandoffError):
            self.export()

    def test_audio_path_escape_is_rejected(self):
        outside = self.root / "outside.wav"
        outside.write_bytes(b"outside-the-root")
        self.make_clip("clips/shot01.mp4")
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])

        with self.assertRaises(capcut_handoff.HandoffError):
            self.export(audio_tracks={"voice": ["../outside.wav"]})

    # ---------- 7. export into a non-empty folder ----------

    def test_export_refuses_non_empty_output_directory(self):
        self.make_clip("clips/shot01.mp4")
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])
        self.output.mkdir(parents=True)
        keep = self.output / "user-file.txt"
        keep.write_text("do not overwrite", encoding="utf-8")

        with self.assertRaises(capcut_handoff.HandoffError):
            self.export()

        self.assertEqual(keep.read_text(encoding="utf-8"), "do not overwrite")
        self.assertEqual(list(self.output.iterdir()), [keep])

    def test_output_directory_inside_media_root_is_rejected(self):
        self.make_clip("clips/shot01.mp4")
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])

        with self.assertRaises(capcut_handoff.HandoffError):
            capcut_handoff.export_handoff(self.list_path, self.media, self.media / "handoff")

        self.assertFalse((self.media / "handoff").exists())

    # ---------- 8. integrity of the final manifest ----------

    def test_manifest_integrity_check_passes_and_detects_tampering(self):
        self.make_clip("clips/shot01.mp4")
        self.make_clip("clips/shot02.mp4")
        self.make_voice("audio/vo.wav", frequency=330)
        self.write_edit_list([make_row(1, "clips/shot01.mp4"),
                              make_row(2, "clips/shot02.mp4")])

        self.export(audio_tracks={"voice": ["audio/vo.wav"]})

        report = capcut_handoff.verify_package(self.output)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["mismatches"], [])
        self.assertGreaterEqual(report["checked"], 3)

        target = self.output / "01_Clips/001_scene01_shot01.mp4"
        target.write_bytes(target.read_bytes() + b"tampered")

        report = capcut_handoff.verify_package(self.output)
        self.assertFalse(report["ok"])
        self.assertTrue(report["mismatches"])
        self.assertTrue(any("001_scene01_shot01.mp4" in m for m in report["mismatches"]))

    def test_manifest_lists_sha256_for_every_included_file(self):
        self.make_clip("clips/shot01.mp4")
        self.make_image("refs/shot01.png")
        self.make_voice("audio/vo.wav", frequency=330)
        self.write_edit_list([make_row(1, "clips/shot01.mp4", image="refs/shot01.png")])

        manifest = self.export(audio_tracks={"voice": ["audio/vo.wav"]})

        entries = manifest["files"]
        self.assertEqual(len(entries), 3)
        for entry in entries:
            self.assertEqual(len(entry["sha256"]), 64)
            self.assertGreater(entry["bytes"], 0)
        self.assertTrue((self.output / "03_References/001_scene01_shot01.png").is_file())

    # ---------- 9. reading the finished package again ----------

    def test_finished_package_can_be_read_again(self):
        self.make_clip("clips/shot01.mp4")
        self.make_clip("clips/shot02.mp4")
        self.write_edit_list([make_row(1, "clips/shot01.mp4"),
                              make_row(2, "clips/shot02.mp4")])

        self.export()

        manifest = json.loads((self.output / "manifest.json").read_text(encoding="utf-8"))
        sheet = json.loads((self.output / "edit-list.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema"], capcut_handoff.SCHEMA)
        self.assertEqual([r["clip"] for r in sheet["rows"]],
                         ["01_Clips/001_scene01_shot01.mp4",
                          "01_Clips/002_scene01_shot02.mp4"])
        self.assertTrue((self.output / "edit-list.csv").is_file())
        self.assertTrue((self.output / "README_RU.md").is_file())
        self.assertTrue(capcut_handoff.verify_package(self.output)["ok"])

        with self.assertRaises(capcut_handoff.HandoffError):
            self.export()

        self.assertTrue(capcut_handoff.verify_package(self.output)["ok"])

    # ---------- 9:16 only when the file really exists ----------

    def test_vertical_variant_is_included_when_the_file_exists(self):
        self.make_clip("clips/shot01.mp4", color="navy")
        self.make_clip("clips/shot01_9x16.mp4", color="purple")
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])

        manifest = self.export()

        self.assertTrue((self.output / "01_Clips/001_scene01_shot01_9x16.mp4").is_file())
        self.assertEqual(manifest["clips"][0]["variant_9x16"],
                         "01_Clips/001_scene01_shot01_9x16.mp4")

    def test_missing_vertical_variant_is_not_fabricated(self):
        self.make_clip("clips/shot01.mp4")
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])

        manifest = self.export()

        self.assertIsNone(manifest["clips"][0]["variant_9x16"])
        self.assertFalse((self.output / "01_Clips/001_scene01_shot01_9x16.mp4").exists())
        self.assertTrue(manifest["ready_for_montage"])

    def test_explicit_vertical_map_is_used(self):
        self.make_clip("clips/shot01.mp4")
        self.make_clip("vertical/portrait.mp4", color="teal")
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])

        manifest = self.export(vertical_map={"clips/shot01.mp4": "vertical/portrait.mp4"})

        self.assertEqual(manifest["clips"][0]["variant_9x16"],
                         "01_Clips/001_scene01_shot01_9x16.mp4")
        self.assertTrue((self.output / "01_Clips/001_scene01_shot01_9x16.mp4").is_file())

    # ---------- probe metadata and source immutability ----------

    def test_clip_metadata_records_duration_resolution_and_fps(self):
        self.make_clip("clips/shot01.mp4")
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])

        manifest = self.export()

        media = manifest["clips"][0]["media"]
        self.assertIsNotNone(media)
        self.assertAlmostEqual(media["duration_seconds"], 3.0, delta=0.6)
        self.assertEqual(media["width"], 320)
        self.assertEqual(media["height"], 180)
        self.assertAlmostEqual(media["fps"], 15.0, delta=0.01)
        self.assertEqual(media["aspect_ratio"], "16:9")

    def test_source_media_is_not_modified_by_the_export(self):
        clip = self.make_clip("clips/shot01.mp4")
        image = self.make_image("refs/shot01.png")
        voice = self.make_voice("audio/vo.wav", frequency=330)
        before = {p: mock_media_pilot.checksum(p) for p in (clip, image, voice)}
        self.write_edit_list([make_row(1, "clips/shot01.mp4", image="refs/shot01.png")])

        self.export(audio_tracks={"voice": ["audio/vo.wav"]})

        after = {p: mock_media_pilot.checksum(p) for p in (clip, image, voice)}
        self.assertEqual(before, after)

    def test_package_has_the_documented_structure(self):
        self.make_clip("clips/shot01.mp4")
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])

        self.export()

        for relative in ("01_Clips", "02_Audio/voice", "02_Audio/music", "02_Audio/sfx",
                         "03_References", "edit-list.csv", "edit-list.json",
                         "manifest.json", "README_RU.md"):
            self.assertTrue((self.output / relative).exists(), relative)

    def test_malformed_edit_list_is_rejected(self):
        self.list_path.write_text("[]", encoding="utf-8")
        with self.assertRaises(capcut_handoff.HandoffError):
            self.export()

    def test_missing_edit_list_file_is_rejected(self):
        with self.assertRaises(capcut_handoff.HandoffError):
            capcut_handoff.export_handoff(self.root / "absent.json", self.media, self.output)


if __name__ == "__main__":
    unittest.main()
