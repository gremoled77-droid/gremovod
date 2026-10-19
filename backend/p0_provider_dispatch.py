"""P0 adapter activation gate: mock fixtures only, paid operations fail closed.

This is intentionally NOT an HTTP integration or secret store. Real provider
connectors may be added only after budget/session validation and billing preflight.
"""
from dataclasses import dataclass
from typing import Literal

class ProviderDisabled(RuntimeError):
    pass

@dataclass(frozen=True)
class OperationProfile:
    kind: Literal["tts", "image", "video_generation", "lip_sync"]
    provider: str
    model: str
    profile_revision: str
    enabled: bool = False
    requires_owner_request_approval: bool = True
    media_inspection_required: bool = True


DEFAULT_PROFILES = {
    "tts":OperationProfile("tts", "not-configured", "not-configured", "v0"),
    "image":OperationProfile("image", "not-configured", "not-configured", "v0"),
    "video_generation":OperationProfile("video_generation", "not-configured", "not-configured", "v0"),
    "lip_sync":OperationProfile("lip_sync", "not-configured", "not-configured", "v0"),
}


def plan_dispatch(*, kind, mock_mode, verified_request_grant=False,
                  provider_capability_verified=False, cost_ceiling_known=False,
                  provider_profile=None):
    """Never submit to providers. Fail-closed even if a model says 'approved'."""
    if kind not in DEFAULT_PROFILES:
        raise ProviderDisabled("unsupported stage kind")
    if mock_mode is True:
        return {"kind":kind,"state":"MOCK_ONLY","provider_calls":0,
                "estimated_cost_cents":0,"production_approved":False}
    profile=provider_profile or DEFAULT_PROFILES[kind]
    missing=[]
    if not profile.enabled: missing.append("PROVIDER_NOT_ACTIVATED")
    if not verified_request_grant: missing.append("MISSING_TRUSTED_SPECIFIC_APPROVAL")
    if not provider_capability_verified: missing.append("PROVIDER_CAPABILITY_NOT_TESTED")
    if not cost_ceiling_known: missing.append("NO_VERIFIABLE_PRICE_CEILING")
    if missing: raise ProviderDisabled(",".join(missing))
    # This scaffold deliberately has no network/submission implementation.
    raise ProviderDisabled("REAL_SUBMISSION_ADAPTER_NOT_IMPLEMENTED_REQUIRES_CODEX")


def lip_sync_dependency(*, original_video_verified, original_provider_job_id,
                        approved_new_request, mock_mode):
    if mock_mode:
        return {"kind":"lip_sync","state":"MOCK_ONLY","regenerate_source_video":False}
    if not (original_video_verified and original_provider_job_id and approved_new_request):
        raise ProviderDisabled("LIP_SYNC_REQUIRES_SAVED_ORIGINAL_AND_SEPARATE_AUTHORIZATION")
    raise ProviderDisabled("REAL_LIPSYNC_ADAPTER_NOT_IMPLEMENTED")
