"""Offline contract tests. These tests never start Blender."""

from __future__ import annotations

import hashlib

import pytest

from scripts.blender.example_manifests import examples
from scripts.blender.validate_manifests import InvalidManifest, digest, relative_file, validate


def valid_pair():
    stage, shot = examples()
    return stage, shot


def test_example_stage_and_eight_second_shot_validate():
    stage, shot = valid_pair()
    assert stage["asset_policy"] == "NON_CANONICAL_PROXY"
    assert shot["end_frame_exclusive"] - shot["start_frame"] == 8 * shot["fps"]
    assert validate(stage)["status"] == "PASS_SCHEMA_SEMANTIC"
    assert validate(shot, stage=stage)["status"] == "PASS_SCHEMA_SEMANTIC"


@pytest.mark.parametrize(("aspect", "resolution"), [("16:9", [960, 540]), ("9:16", [540, 960])])
def test_both_aspects_validate(aspect, resolution):
    stage, shot = valid_pair()
    shot["aspect"] = aspect
    shot["resolution"] = resolution
    assert validate(shot, stage=stage)["status"] == "PASS_SCHEMA_SEMANTIC"


def test_rejects_aspect_resolution_mismatch():
    stage, shot = valid_pair()
    shot["resolution"] = [960, 540]
    shot["aspect"] = "9:16"
    with pytest.raises(InvalidManifest, match="ASPECT_RESOLUTION"):
        validate(shot, stage=stage)


def test_rejects_owner_mismatch():
    stage, shot = valid_pair()
    with pytest.raises(InvalidManifest, match="OWNER_MISMATCH"):
        validate(stage, owner=("other-production", stage["node_id"]))


def test_rejects_camera_below_ground():
    stage, shot = valid_pair()
    shot["camera"]["keys"][1]["position_m"][2] = 0.05
    shot["stage_sha256"] = digest(stage)
    with pytest.raises(InvalidManifest, match="CAMERA_GROUND_OR_TARGET"):
        validate(shot, stage=stage)


def test_rejects_camera_collision_with_protected_proxy_bounds():
    stage, shot = valid_pair()
    shot["camera"]["keys"][1]["position_m"] = [0.0, 0.0, 1.0]
    with pytest.raises(InvalidManifest, match="CAMERA_ASSET_COLLISION"):
        validate(shot, stage=stage)


def test_rejects_frame_range_over_contract_limit():
    stage, shot = valid_pair()
    shot["end_frame_exclusive"] = 1441
    shot["camera"]["keys"][-1]["frame"] = 1440
    with pytest.raises(InvalidManifest, match="FRAME_INTERVAL"):
        validate(shot, stage=stage)


def test_rejects_inverted_protected_bounds():
    stage, _ = valid_pair()
    stage["protected_bounds_m"] = [[4.0, -1.0, 0.0], [3.0, 1.0, 2.0]]
    with pytest.raises(InvalidManifest, match="INVALID_PROTECTED_BOUNDS"):
        validate(stage)


def test_rejects_reserved_windows_device_identifier():
    stage, _ = valid_pair()
    stage["production_id"] = "CON"
    with pytest.raises(InvalidManifest, match="INVALID_ID"):
        validate(stage)


@pytest.mark.parametrize("path", ["../outside.blend", "C:/outside.blend", "\\\\server\\share\\x.blend", "https://host/x.blend"])
def test_rejects_untrusted_or_escaping_asset_paths(tmp_path, path):
    root = tmp_path.resolve()
    with pytest.raises(InvalidManifest, match="INVALID_PATH"):
        relative_file(root, path)


def test_rejects_registry_asset_hash_mismatch(tmp_path):
    stage, _ = valid_pair()
    asset = stage["assets"][0]
    data = b"synthetic proxy bytes"
    asset_path = tmp_path / "proxy.bin"
    asset_path.write_bytes(data)
    registry = {
        asset["file_id"]: {
            "entity_id": asset["entity_id"],
            "version": asset["version"],
            "sha256": asset["sha256"],
            "production_id": stage["production_id"],
            "node_id": stage["node_id"],
            "relative_path": "proxy.bin",
        }
    }
    assert hashlib.sha256(data).hexdigest() != asset["sha256"]
    with pytest.raises(InvalidManifest, match="ASSET_BYTES_MISMATCH"):
        validate(stage, registry=registry, data_root=tmp_path, owner=(stage["production_id"], stage["node_id"]))


def test_registry_hash_accepts_matching_local_bytes(tmp_path):
    stage, _ = valid_pair()
    data = b"synthetic proxy bytes"
    asset_path = tmp_path / "proxy.bin"
    asset_path.write_bytes(data)
    asset = stage["assets"][0]
    asset["sha256"] = hashlib.sha256(data).hexdigest()
    registry = {
        asset["file_id"]: {
            "entity_id": asset["entity_id"],
            "version": asset["version"],
            "sha256": asset["sha256"],
            "production_id": stage["production_id"],
            "node_id": stage["node_id"],
            "relative_path": "proxy.bin",
        }
    }
    result = validate(stage, registry=registry, data_root=tmp_path, owner=(stage["production_id"], stage["node_id"]))
    assert result["asset_bytes_verified"] is True
