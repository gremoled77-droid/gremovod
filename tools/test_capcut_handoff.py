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
from unittest import mock

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

    def test_without_ffprobe_the_pack_is_not_blocked(self):
        self.make_clip("clips/shot01.mp4")
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])
        original = capcut_handoff.ffprobe_path
        capcut_handoff.ffprobe_path = lambda: None
        self.addCleanup(setattr, capcut_handoff, "ffprobe_path", original)

        manifest = self.export()

        self.assertTrue(manifest["ready_for_montage"])
        self.assertIsNone(manifest["clips"][0]["media"])
        self.assertNotIn("UNSUPPORTED_MEDIA", self.issue_codes(manifest))

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


    # ---------- 10. broken media must not pass as a ready pack ----------

    def test_corrupt_clip_blocks_montage(self):
        self.make_clip("clips/shot01.mp4")
        (self.media / "clips/shot02.mp4").write_bytes(b"\x00" * 4096)
        self.write_edit_list([make_row(1, "clips/shot01.mp4"), make_row(2, "clips/shot02.mp4")])

        manifest = self.export()

        self.assertFalse(manifest["ready_for_montage"])
        self.assertEqual(manifest["status"], "INCOMPLETE")
        self.assertIn("UNSUPPORTED_MEDIA", self.issue_codes(manifest, "blocking"))
        broken = [i for i in manifest["issues"] if i["code"] == "UNSUPPORTED_MEDIA"]
        self.assertIn("shot02.mp4", broken[0]["message"])

    def test_clip_without_video_stream_blocks_montage(self):
        self.make_clip("clips/shot01.mp4")
        self.make_voice("clips/only_audio.mp4", frequency=330)
        self.write_edit_list([make_row(1, "clips/shot01.mp4"), make_row(2, "clips/only_audio.mp4")])

        manifest = self.export()

        self.assertFalse(manifest["ready_for_montage"])
        self.assertIn("UNSUPPORTED_MEDIA", self.issue_codes(manifest, "blocking"))

    def test_missing_audio_file_blocks_montage(self):
        self.make_clip("clips/shot01.mp4")
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])

        manifest = self.export(audio_tracks={"voice": ["audio/absent.wav"]})

        self.assertFalse(manifest["ready_for_montage"])
        self.assertIn("MISSING_AUDIO", self.issue_codes(manifest, "blocking"))
        self.assertEqual(manifest["counts"]["audio"], 0)

    # ---------- 11. same file name in different audio tracks ----------

    def test_same_audio_name_in_two_tracks_is_not_a_conflict(self):
        self.make_clip("clips/shot01.mp4")
        self.make_voice("audio/vo.wav", frequency=330)
        self.make_voice("audio/same.wav", frequency=660)
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])

        manifest = self.export(audio_tracks={"voice": ["audio/same.wav"],
                                              "music": ["audio/same.wav"]})

        self.assertNotIn("DUPLICATE_DESTINATION_NAME", self.issue_codes(manifest))
        self.assertTrue(manifest["ready_for_montage"])
        self.assertTrue((self.output / "02_Audio/voice/same.wav").is_file())
        self.assertTrue((self.output / "02_Audio/music/same.wav").is_file())
        self.assertEqual(manifest["counts"]["audio"], 2)

    def test_same_audio_name_in_one_track_is_blocking(self):
        self.make_clip("clips/shot01.mp4")
        self.make_voice("audio/one/same.wav", frequency=330)
        self.make_voice("audio/two/same.wav", frequency=660)
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])

        manifest = self.export(audio_tracks={"voice": ["audio/one/same.wav", "audio/two/same.wav"]})

        self.assertFalse(manifest["ready_for_montage"])
        self.assertIn("DUPLICATE_DESTINATION_NAME", self.issue_codes(manifest, "blocking"))
        self.assertEqual(manifest["counts"]["audio"], 1)

    # ---------- 12. rows without an explicit order ----------

    def test_row_without_order_keeps_its_file_position(self):
        self.make_clip("clips/a.mp4", color="navy")
        self.make_clip("clips/b.mp4", color="teal")
        self.make_clip("clips/c.mp4", color="purple")
        rows = [make_row(1, "clips/a.mp4"),
                {"scene": 1, "frame": 2, "title": "Б", "video": "clips/b.mp4", "image": ""},
                make_row(3, "clips/c.mp4")]
        self.write_edit_list(rows)

        manifest = self.export()

        self.assertEqual([c["order"] for c in manifest["clips"]], [1, 2, 3])
        self.assertEqual([c["path"] for c in manifest["clips"]],
                         ["01_Clips/001_scene01_shot01.mp4",
                          "01_Clips/002_scene01_shot02.mp4",
                          "01_Clips/003_scene01_shot03.mp4"])
        self.assertTrue(manifest["ready_for_montage"])

    # ---------- 13. empty edit list ----------

    def test_empty_edit_list_blocks_montage(self):
        self.write_edit_list([])

        manifest = self.export()

        self.assertFalse(manifest["ready_for_montage"])
        self.assertEqual(manifest["status"], "INCOMPLETE")
        self.assertIn("EMPTY_EDIT_LIST", self.issue_codes(manifest, "blocking"))

    # ---------- 14. extra files in a finished pack ----------

    def test_verify_package_reports_a_file_that_is_not_in_the_manifest(self):
        self.make_clip("clips/shot01.mp4")
        self.write_edit_list([make_row(1, "clips/shot01.mp4")])
        self.export()

        self.assertTrue(capcut_handoff.verify_package(self.output)["ok"])
        (self.output / "01_Clips" / "stray.mp4").write_bytes(b"not in the manifest")

        report = capcut_handoff.verify_package(self.output)
        self.assertFalse(report["ok"])
        self.assertTrue(any("stray.mp4" in mismatch for mismatch in report["mismatches"]))

    # ---------- 15. Windows: cyrillic paths ----------

    def test_cyrillic_paths_are_packed_and_readable(self):
        self.make_clip("клипы/кадр_один.mp4", color="navy")
        self.make_voice("озвучка/голос_два.wav", frequency=330)
        self.write_edit_list([make_row(1, "клипы/кадр_один.mp4")])

        manifest = self.export(audio_tracks={"voice": ["озвучка/голос_два.wav"]})

        self.assertTrue(manifest["ready_for_montage"])
        self.assertTrue((self.output / "01_Clips/001_scene01_shot01.mp4").is_file())
        self.assertTrue((self.output / "02_Audio/voice/голос_два.wav").is_file())
        sheet = (self.output / "edit-list.csv").read_text(encoding="utf-8-sig")
        self.assertIn("01_Clips/001_scene01_shot01.mp4", sheet)

    # ---------- 16. edit-list warnings reach the person who montages ----------

    def test_edit_list_warnings_are_visible_in_the_pack_readme(self):
        self.make_clip("clips/shot01.mp4")
        self.write_edit_list([make_row(1, "clips/shot01.mp4")],
                             warnings=["Кадр 1.1 длится 12 с: монтажный ритм на таком кадре не ощущается."])

        self.export()

        readme = (self.output / "README_RU.md").read_text(encoding="utf-8")
        self.assertIn("12 с", readme)
        self.assertIn("монтажный ритм", readme)

    # ---------- 17. an incomplete pack keeps its integrity, but is not ready ----------

    def test_incomplete_package_keeps_integrity_but_is_not_ready(self):
        self.make_clip("clips/shot01.mp4")
        self.write_edit_list([make_row(1, "clips/shot01.mp4"),
                              make_row(2, "clips/absent.mp4")])

        manifest = self.export()

        self.assertEqual(manifest["status"], "INCOMPLETE")
        report = capcut_handoff.verify_package(self.output)
        self.assertTrue(report["ok"], report)
        self.assertFalse(report["ready_for_montage"])


class ManifestVerificationTests(unittest.TestCase):
    """Verification of a finished pack: structure, boundaries and readiness.

    Only synthetic packages in a temporary folder — no ffmpeg, no network, no
    owner media. The checks here answer one question: may a person trust the
    result of ``verify_package()`` and start importing the pack by hand?
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pack = self.root / "pack"
        self.pack.mkdir()

    # ---------- helpers ----------

    def write_file(self, relative, content=b"data"):
        path = self.pack / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def write_manifest(self, manifest):
        (self.pack / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_manifest(self):
        return json.loads((self.pack / "manifest.json").read_text(encoding="utf-8"))

    def entry_for(self, relative):
        """A manifest entry that describes the file as it is right now."""
        target = self.pack / relative
        return {"path": relative, "sha256": capcut_handoff.sha256_file(target),
                "bytes": target.stat().st_size}

    def build_pack(self, *, status="READY_FOR_MONTAGE", ready=True, documents=True,
                   clip="01_Clips/001_scene01_shot01.mp4"):
        """A minimal but correct handoff v1 package."""
        self.write_file(clip, b"clip-bytes")
        files = [self.entry_for(clip)]
        listed_documents = []
        if documents:
            for name, content in ((capcut_handoff.EDIT_LIST_CSV, "a;b\n"),
                                  (capcut_handoff.EDIT_LIST_JSON, "{}\n"),
                                  (capcut_handoff.README_NAME, "# Пакет\n")):
                self.write_file(name, content.encode("utf-8"))
                listed_documents.append(self.entry_for(name))
        self.write_manifest({"schema": capcut_handoff.SCHEMA, "status": status,
                             "ready_for_montage": ready, "files": files,
                             "documents": listed_documents})
        return self.pack

    def report(self, pack=None):
        """The verification result; a refusal is reported as ok=False."""
        try:
            return capcut_handoff.verify_package(pack or self.pack)
        except capcut_handoff.HandoffError as exc:
            return {"ok": False, "checked": 0, "mismatches": [str(exc)],
                    "status": None, "ready_for_montage": None}

    def rejected(self, pack=None):
        """True when the pack is refused — by an error or by ok=False."""
        return self.report(pack)["ok"] is False

    def hash_spy(self):
        """Record every hashed path and fail loudly on a file outside the pack."""
        calls = []
        original = capcut_handoff.sha256_file
        root = self.pack.resolve()

        def spy(path):
            resolved = Path(path).resolve()
            calls.append(resolved)
            if not resolved.is_relative_to(root):
                raise AssertionError(f"файл вне пакета был прочитан: {resolved}")
            return original(path)

        return calls, spy

    # ---------- a correct pack ----------

    def test_correct_package_passes(self):
        self.build_pack()

        report = capcut_handoff.verify_package(self.pack)

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["mismatches"], [])
        self.assertEqual(report["checked"], 4)
        self.assertTrue(report["ready_for_montage"])

    def test_changed_file_is_reported(self):
        self.build_pack()
        (self.pack / "01_Clips/001_scene01_shot01.mp4").write_bytes(b"changed")

        report = capcut_handoff.verify_package(self.pack)

        self.assertFalse(report["ok"], report)
        self.assertTrue(any("SHA-256" in m for m in report["mismatches"]), report)

    def test_extra_file_in_the_package_is_reported(self):
        self.build_pack()
        self.write_file("01_Clips/stray.mp4", b"stray")

        report = capcut_handoff.verify_package(self.pack)

        self.assertFalse(report["ok"], report)
        self.assertTrue(any("stray.mp4" in m for m in report["mismatches"]), report)

    def test_correct_incomplete_package_keeps_integrity_but_is_not_ready(self):
        self.build_pack(status="INCOMPLETE", ready=False)

        report = capcut_handoff.verify_package(self.pack)

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["mismatches"], [])
        self.assertFalse(report["ready_for_montage"])
        self.assertEqual(report["status"], "INCOMPLETE")

    # ---------- a manifest that is not a handoff v1 ----------

    def test_empty_ready_manifest_is_rejected(self):
        self.write_manifest({"schema": capcut_handoff.SCHEMA, "status": "READY_FOR_MONTAGE",
                             "ready_for_montage": True, "files": [], "documents": []})

        report = self.report()

        self.assertFalse(report["ok"], report)
        self.assertTrue(any("edit-list.csv" in m for m in report["mismatches"]), report)

    def test_non_object_manifest_is_a_controlled_rejection(self):
        (self.pack / "manifest.json").write_text("[]", encoding="utf-8")

        try:
            report = capcut_handoff.verify_package(self.pack)
        except capcut_handoff.HandoffError as exc:
            self.assertIn("неверную структуру", str(exc))
            return
        except (AttributeError, TypeError) as exc:
            self.fail(f"повреждённый манифест дал {type(exc).__name__}: {exc}")
        self.assertFalse(report["ok"], report)

    def test_manifest_of_another_schema_is_rejected(self):
        self.build_pack()
        manifest = self.read_manifest()
        manifest["schema"] = "gremovod.capcut-handoff/99"
        self.write_manifest(manifest)

        self.assertTrue(self.rejected())

    def test_manifest_without_file_lists_is_rejected(self):
        self.write_manifest({"schema": capcut_handoff.SCHEMA, "status": "READY_FOR_MONTAGE",
                             "ready_for_montage": True, "files": {}, "documents": []})

        self.assertTrue(self.rejected())

    def test_malformed_entry_is_reported_without_a_crash(self):
        self.build_pack()
        manifest = self.read_manifest()
        manifest["files"].append("не объект")
        manifest["files"].append({"sha256": "0" * 64})
        manifest["files"].append({"path": 42})
        self.write_manifest(manifest)

        report = self.report()

        self.assertFalse(report["ok"], report)
        self.assertTrue(any("не является объектом" in m for m in report["mismatches"]), report)
        self.assertTrue(any("без пути" in m for m in report["mismatches"]), report)

    def test_duplicate_path_in_the_manifest_is_reported(self):
        self.build_pack()
        manifest = self.read_manifest()
        manifest["files"].append(dict(manifest["files"][0]))
        self.write_manifest(manifest)

        report = self.report()

        self.assertFalse(report["ok"], report)
        self.assertTrue(any("дважды" in m for m in report["mismatches"]), report)

    def test_missing_required_document_is_reported(self):
        self.build_pack()
        (self.pack / capcut_handoff.EDIT_LIST_CSV).unlink()

        report = self.report()

        self.assertFalse(report["ok"], report)
        self.assertTrue(any("обязательный документ" in m for m in report["mismatches"]), report)

    def test_inconsistent_readiness_is_reported(self):
        self.build_pack(status="INCOMPLETE", ready=True)

        report = self.report()

        self.assertFalse(report["ok"], report)
        self.assertTrue(any("ready_for_montage=true" in m for m in report["mismatches"]), report)

    # ---------- the package boundary ----------

    def test_manifest_path_outside_the_package_is_rejected_and_not_read(self):
        outside = self.root / "outside.txt"
        outside.write_text("SYNTHETIC-OUTSIDE-MARKER", encoding="utf-8")
        self.build_pack()
        manifest = self.read_manifest()
        manifest["files"].append({"path": "../outside.txt",
                                  "sha256": capcut_handoff.sha256_file(outside),
                                  "bytes": outside.stat().st_size})
        self.write_manifest(manifest)

        calls, spy = self.hash_spy()
        with mock.patch.object(capcut_handoff, "sha256_file", spy):
            report = self.report()

        self.assertFalse(report["ok"], report)
        self.assertTrue(any("outside.txt" in m for m in report["mismatches"]), report)
        self.assertNotIn(outside.resolve(), calls)

    def test_absolute_path_in_the_manifest_is_rejected_and_not_read(self):
        outside = self.root / "outside.txt"
        outside.write_text("SYNTHETIC-OUTSIDE-MARKER", encoding="utf-8")
        self.build_pack()
        manifest = self.read_manifest()
        manifest["files"].append({"path": str(outside),
                                  "sha256": capcut_handoff.sha256_file(outside),
                                  "bytes": outside.stat().st_size})
        self.write_manifest(manifest)

        calls, spy = self.hash_spy()
        with mock.patch.object(capcut_handoff, "sha256_file", spy):
            report = self.report()

        self.assertFalse(report["ok"], report)
        self.assertNotIn(outside.resolve(), calls)

    def test_symlink_out_of_the_package_is_rejected_and_not_read(self):
        outside = self.root / "outside.txt"
        outside.write_text("SYNTHETIC-OUTSIDE-MARKER", encoding="utf-8")
        self.build_pack()
        link = self.pack / "01_Clips" / "link.mp4"
        try:
            os.symlink(outside, link)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks are not available here: {exc}")
        manifest = self.read_manifest()
        manifest["files"].append({"path": "01_Clips/link.mp4",
                                  "sha256": capcut_handoff.sha256_file(outside),
                                  "bytes": outside.stat().st_size})
        self.write_manifest(manifest)

        calls, spy = self.hash_spy()
        with mock.patch.object(capcut_handoff, "sha256_file", spy):
            report = self.report()

        self.assertFalse(report["ok"], report)
        self.assertNotIn(outside.resolve(), calls)


if __name__ == "__main__":
    unittest.main()
