"""Offline evidence adapter to Studio media_qc; no render or provider dispatch."""
from __future__ import annotations

from backend.media_qc import verdict
from scripts.blender.validate_manifests import validate


def assess(measurement: dict, shot: dict, *, decoded_frame_count: int | None) -> dict:
    """Require external measured evidence, including a complete ffmpeg decode.

    Callers must use existing media_qc.measure and count decoded frames with
    ffprobe. This function does not create or authenticate those measurements.
    """
    validate(shot)
    w, h = shot['resolution']
    count = shot['end_frame_exclusive'] - shot['start_frame']
    expected = {'width': w, 'height': h, 'fps': shot['fps'], 'fps_tolerance': .001,
                'duration_ms': round(1000 * count / shot['fps']),
                'duration_tolerance_ms': round(1000 / shot['fps']),
                'container': 'mp4', 'video_codec': 'h264', 'require_audio': False}
    result = verdict(measurement, expected)
    master = measurement.get('master') or {}
    if master.get('decodes') is not True or decoded_frame_count is None:
        result['status'] = 'BLOCKED'
    elif decoded_frame_count != count:
        result['status'] = 'FAIL'
    return {'technical': result, 'expected_frame_count': count,
            'decoded_frame_count': decoded_frame_count,
            'human': {'status': 'PENDING', 'reviewer_id': None, 'approval_id': None},
            'visibility': 'UNVERIFIED', 'master_integrity': 'UNVERIFIED'}
