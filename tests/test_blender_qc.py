from __future__ import annotations

from scripts.blender.qc_preview import assess


def valid_shot() -> dict:
    return {
        "kind": "shot_manifest",
        "schema_version": "1.0",
        "episode_id": "episode-01",
        "scene_id": "scene-01",
        "shot_id": "shot-01",
        "stage_id": "stage-01",
        "stage_sha256": "a" * 64,
        "aspect": "16:9",
        "fps": 24,
        "start_frame": 0,
        "end_frame_exclusive": 192,
        "camera": {
            "lens_mm": 35,
            "sensor_width_mm": 36,
            "interpolation": "linear",
            "keys": [
                {"frame": 0, "position_m": [0, -4, 2], "look_at_m": [0, 0, 0]},
                {"frame": 191, "position_m": [1, -4, 2], "look_at_m": [0, 0, 0]},
            ],
            "clip_start_m": 0.1,
            "clip_end_m": 100,
        },
        "beats": [],
        "continuity": {"previous_shot_id": None, "required_last_visible_ids": []},
        "production_id": "production-01",
        "node_id": "node-01",
        "resolution": [960, 540],
    }


def passing_measurement() -> dict:
    return {
        "master": {
            "width": 960,
            "height": 540,
            "fps": 24,
            "duration_ms": 8000,
            "format": "mov,mp4,m4a,3gp,3g2,mj2",
            "video_codec": "h264",
            "decodes": True,
        },
        "observations": {},
    }


def test_valid_measured_media_passes_technical_qc_and_keeps_human_pending():
    shot = valid_shot()
    result = assess(passing_measurement(), shot, decoded_frame_count=192)
    assert result["technical"]["status"] == "PASS_TECHNICAL"
    assert result["expected_frame_count"] == 192
    assert result["decoded_frame_count"] == 192
    assert result["human"] == {
        "status": "PENDING",
        "reviewer_id": None,
        "approval_id": None,
    }


def test_wrong_decoded_frame_count_fails_qc():
    result = assess(passing_measurement(), valid_shot(), decoded_frame_count=191)
    assert result["technical"]["status"] == "FAIL"
    assert result["decoded_frame_count"] == 191


def test_corrupt_decode_is_blocked():
    measurement = passing_measurement()
    measurement["master"]["decodes"] = False
    result = assess(measurement, valid_shot(), decoded_frame_count=192)
    assert result["technical"]["status"] == "BLOCKED"


def test_missing_decode_evidence_is_blocked():
    result = assess(passing_measurement(), valid_shot(), decoded_frame_count=None)
    assert result["technical"]["status"] == "BLOCKED"
