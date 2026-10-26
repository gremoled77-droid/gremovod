"""Small, synthetic manifests for offline schema and contract checks."""

from __future__ import annotations

from copy import deepcopy

from scripts.blender.validate_manifests import digest


def examples() -> tuple[dict, dict]:
    """Return a stage and matching eight-second 16:9 shot manifest.

    The asset is explicitly a neutral proxy and has no associated .blend file.
    The geometric bounds describe a seven-metre proxy vehicle for contract
    examples only; no Blender process or project asset is loaded.
    """
    stage = {
        "kind": "stage_bible",
        "schema_version": "1.0",
        "stage_id": "proxy-stage-01",
        "units": "m",
        "axes": "X_forward_Y_left_Z_up",
        "physical_left": "+Y",
        "north": [0.0, 1.0, 0.0],
        "assets": [
            {
                "entity_id": "vehicle-proxy",
                "file_id": "synthetic-proxy-v1",
                "version": "1",
                "sha256": "a" * 64,
            }
        ],
        "landmarks": {"ground_origin": [0.0, 0.0, 0.0]},
        "invariants": ["proxy_only", "no_canonical_asset"],
        "production_id": "demo-production",
        "node_id": "demo-node",
        "asset_policy": "NON_CANONICAL_PROXY",
        "approval_id": None,
        "protected_bounds_m": [[-3.5, -1.0, 0.0], [3.5, 1.0, 2.0]],
    }
    shot = {
        "kind": "shot_manifest",
        "schema_version": "1.0",
        "episode_id": "demo-episode",
        "scene_id": "demo-scene",
        "shot_id": "demo-shot",
        "stage_id": stage["stage_id"],
        "stage_sha256": digest(stage),
        "aspect": "16:9",
        "fps": 24,
        "start_frame": 0,
        "end_frame_exclusive": 192,
        "camera": {
            "lens_mm": 35.0,
            "sensor_width_mm": 36.0,
            "interpolation": "linear",
            "keys": [
                {"frame": 0, "position_m": [4.6, 1.2, 1.3], "look_at_m": [3.3, 0.0, 1.0]},
                {"frame": 96, "position_m": [7.0, 8.0, 3.0], "look_at_m": [0.0, 0.0, 1.0]},
                {"frame": 191, "position_m": [10.0, 12.0, 5.0], "look_at_m": [0.0, 0.0, 1.0]},
            ],
            "clip_start_m": 0.1,
            "clip_end_m": 100.0,
        },
        "beats": [
            {"frame": 0, "entity_id": "vehicle-proxy", "action": "front_detail", "visible_ids": ["vehicle-proxy", "ground_origin"]},
            {"frame": 96, "entity_id": "vehicle-proxy", "action": "three_quarter_reveal", "visible_ids": ["vehicle-proxy"]},
            {"frame": 191, "entity_id": "vehicle-proxy", "action": "hold_full_proxy", "visible_ids": ["vehicle-proxy"]},
        ],
        "continuity": {"previous_shot_id": None, "required_last_visible_ids": ["vehicle-proxy"]},
        "production_id": stage["production_id"],
        "node_id": stage["node_id"],
        "resolution": [960, 540],
    }
    return deepcopy(stage), deepcopy(shot)
