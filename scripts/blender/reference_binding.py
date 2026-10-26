"""Offline quote binding only. No provider transport, upload or charge capability."""
from __future__ import annotations

try:
    from .validate_manifests import digest, validate, InvalidManifest
except ImportError:
    from validate_manifests import digest, validate, InvalidManifest


def quote_binding(*, model: str, payload: dict, references: dict,
                  master_sha256: str, review_id: str) -> str:
    validate(references)
    if references['kind'] != 'reference_manifest':
        raise InvalidManifest('REFERENCE_MANIFEST_REQUIRED')
    if not review_id or len(master_sha256) != 64 or any(c not in '0123456789abcdef' for c in master_sha256):
        raise InvalidManifest('MISSING_MASTER_OR_REVIEW')
    if master_sha256 == '0' * 64:
        raise InvalidManifest('PLACEHOLDER_HASH')
    # Lists preserve order; role, tag, provider slot and restrictions are hashed.
    return digest({'model': model, 'payload': payload, 'references': references,
                   'master_sha256': master_sha256, 'review_id': review_id})


def preview_request(**inputs) -> dict:
    return {'status': 'BLOCKED_P1', 'binding_sha256': quote_binding(**inputs),
            'dispatch_enabled': False, 'cost_state': 'UNKNOWN',
            'upload_executed': False, 'hold_created': False,
            'required': ['G1-G5 P0 evidence', 'verified adapter and price',
                         'GenerationReview confirmation bound to immutable inputs']}
