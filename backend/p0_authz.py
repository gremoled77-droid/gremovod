"""Server-derived authorisation capabilities for the P0 ledger.

Trust is never a parameter. A caller cannot hand the ledger a boolean that
grants owner rights, approves a request or certifies provider evidence: a
boolean in an HTTP or n8n body is just a value the caller chose.

Instead the server issues a short-lived signed capability. The ledger
verifies the signature, the expiry and the binding to the exact immutable
request itself. A capability therefore grants exactly one action, for one
amount, for one request hash, and stops working when it is used elsewhere.

The signing key lives in the process environment (GREMOVOD_P0_SIGNING_KEY).
Without it a per-process key is used: capabilities then die with the
process, which is the safe default and never silently widens a grant.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

ENV_KEY = "GREMOVOD_P0_SIGNING_KEY"
_EPHEMERAL_KEY = secrets.token_bytes(32)

# Legacy trust parameters that used to be accepted by the ledger. They are
# rejected explicitly: forwarding them from an HTTP or n8n body must fail
# loudly instead of being interpreted as permission.
LEGACY_TRUST_FIELDS = (
    "trusted_studio_owner",
    "trusted_studio_request_authorization",
    "provider_evidence_verified",
)


class AuthzError(ValueError):
    """Capability missing, forged, expired or bound to something else."""


def now_ms() -> int:
    return int(time.time() * 1000)


def signing_key() -> bytes:
    raw = os.environ.get(ENV_KEY, "").strip()
    if raw:
        try:
            decoded = base64.urlsafe_b64decode(raw.encode())
            if decoded:
                return decoded
        except Exception:
            return raw.encode()
    return _EPHEMERAL_KEY


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def mint(purpose: str, binding: dict, *, ttl_ms: int = 120_000) -> str:
    """Issue a capability. Only the server side of the trust boundary calls this."""
    if not purpose or not isinstance(binding, dict):
        raise AuthzError("capability requires a purpose and a binding")
    payload = {
        "purpose": purpose,
        "binding": binding,
        "exp_ms": now_ms() + int(ttl_ms),
        "nonce": secrets.token_hex(8),
    }
    body = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    signature = _b64(hmac.new(signing_key(), body.encode("utf-8"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def verify(token: str, *, purpose: str, binding: dict) -> dict:
    """Verify a capability and return its payload. Anything else fails closed."""
    if not isinstance(token, str) or token.count(".") != 1:
        raise AuthzError("capability is missing or malformed")
    body, signature = token.split(".", 1)
    expected = _b64(hmac.new(signing_key(), body.encode("utf-8"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise AuthzError("capability signature is not valid")
    try:
        payload = json.loads(_unb64(body).decode("utf-8"))
    except Exception:
        raise AuthzError("capability payload is unreadable") from None
    if payload.get("purpose") != purpose:
        raise AuthzError("capability was issued for a different purpose")
    if int(payload.get("exp_ms", 0)) <= now_ms():
        raise AuthzError("capability is expired")
    if payload.get("binding") != binding:
        raise AuthzError("capability is bound to a different request")
    return payload


def mint_owner_capability(run_id: str, *, envelope_id: str, cap_cents: int, stage: str,
                          provider: str, model: str, ttl_ms: int = 120_000) -> str:
    return mint("envelope", {
        "run_id": run_id,
        "envelope_id": envelope_id,
        "cap_cents": int(cap_cents),
        "stage": stage,
        "provider": provider,
        "model": model,
    }, ttl_ms=ttl_ms)


def mint_request_capability(job_id: str, *, request_sha: str, upper_cents: int,
                            ttl_ms: int = 120_000) -> str:
    return mint("request", {
        "job_id": job_id,
        "request_sha": request_sha,
        "upper_cents": int(upper_cents),
    }, ttl_ms=ttl_ms)


def reject_legacy_trust(extra: dict) -> None:
    """Fail loudly when a caller forwards a trust boolean from the outside."""
    if not extra:
        return
    offending = sorted(set(extra) & set(LEGACY_TRUST_FIELDS))
    if offending:
        raise AuthzError(
            "caller-supplied trust fields are not accepted: " + ", ".join(offending)
        )
