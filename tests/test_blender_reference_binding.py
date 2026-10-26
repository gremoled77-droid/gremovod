from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.blender.reference_binding import preview_request, quote_binding
from scripts.blender.validate_manifests import InvalidManifest


MASTER_HASH = "a" * 64


def valid_references() -> dict:
    return {
        "kind": "reference_manifest",
        "schema_version": "1.0",
        "shot_id": "shot-01",
        "provider": "provider-demo",
        "model": "model-demo",
        "ordered_refs": [
            {
                "role": "vehicle_identity",
                "source": {
                    "entity_id": "vehicle-01",
                    "file_id": "file-vehicle-01",
                    "version": "v2",
                    "sha256": "1" * 64,
                },
                "provider_slot": "reference_1",
                "tag": "vehicle",
                "duration_s": None,
                "restrictions": ["vehicle-01"],
            },
            {
                "role": "location_layout",
                "source": {
                    "entity_id": "location-01",
                    "file_id": "file-location-01",
                    "version": "v5",
                    "sha256": "2" * 64,
                },
                "provider_slot": "reference_2",
                "tag": "layout",
                "duration_s": 3,
                "restrictions": ["location-01"],
            },
        ],
    }


def bind(*, model="model-demo", payload=None, references=None, master_sha256=MASTER_HASH, review_id="review-1"):
    return quote_binding(
        model=model,
        payload=payload if payload is not None else {"prompt": "slow orbit", "seed": 17},
        references=references if references is not None else valid_references(),
        master_sha256=master_sha256,
        review_id=review_id,
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["ordered_refs"][0]["source"].update(sha256="3" * 64),
        lambda r: r["ordered_refs"][0].update(role="motion_only"),
        lambda r: r["ordered_refs"][0].update(provider_slot="reference_3"),
        lambda r: r["ordered_refs"][0].update(tag="motion"),
        lambda r: r["ordered_refs"][0].update(restrictions=["vehicle-01", "location-01"]),
        lambda r: r["ordered_refs"].reverse(),
    ],
    ids=["asset-hash", "role", "provider-slot", "tag", "restrictions", "order"],
)
def test_each_reference_change_invalidates_binding(change):
    original = valid_references()
    changed = deepcopy(original)
    change(changed)
    assert bind(references=changed) != bind(references=original)


def test_master_payload_model_and_review_changes_invalidate_binding():
    original = bind()
    assert bind(master_sha256="b" * 64) != original
    assert bind(payload={"prompt": "fast orbit", "seed": 17}) != original
    assert bind(model="model-other") != original
    assert bind(review_id="review-2") != original


def test_preview_is_blocked_without_upload_dispatch_or_hold():
    result = preview_request(
        model="model-demo",
        payload={"prompt": "slow orbit"},
        references=valid_references(),
        master_sha256=MASTER_HASH,
        review_id="review-1",
    )
    assert result["status"] == "BLOCKED_P1"
    assert result["dispatch_enabled"] is False
    assert result["cost_state"] == "UNKNOWN"
    assert result["upload_executed"] is False
    assert result["hold_created"] is False
    assert len(result["binding_sha256"]) == 64


@pytest.mark.parametrize(
    "kwargs",
    [
        {"master_sha256": "0" * 64},
        {"master_sha256": "not-a-hash"},
        {"review_id": ""},
    ],
    ids=["placeholder-master", "invalid-master", "missing-review"],
)
def test_invalid_master_or_missing_review_is_rejected(kwargs):
    with pytest.raises(InvalidManifest):
        bind(**kwargs)
