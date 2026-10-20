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
ENV_ALLOW_EPHEMERAL = "GREMOVOD_P0_ALLOW_EPHEMERAL_KEY"
_EPHEMERAL_KEY = secrets.token_bytes(32)

# Legacy trust parameters that used to be accepted by the ledger. They are
# rejected explicitly: forwarding them from an HTTP or n8n body must fail
# loudly instead of being interpreted as permission.
LEGACY_TRUST_FIELDS = (
    "trusted_studio_owner",
    "trusted_studio_request_authorization",
    "provider_evidence_verified",
)

# Settlement facts that used to be accepted from the caller. The amount, the
# provider job id and the success flag are now read ONLY from the verified
# evidence, because a caller could otherwise claim a charge of 0 for a paid
# generation.
CALLER_SETTLEMENT_FIELDS = (
    "charged_cents",
    "provider_success",
    "provider_job_id",
)


class AuthzError(ValueError):
    """Capability missing, forged, expired or bound to something else."""


def now_ms() -> int:
    return int(time.time() * 1000)


def ephemeral_allowed() -> bool:
    """Explicit opt-in for single-process development and tests."""
    return os.environ.get(ENV_ALLOW_EPHEMERAL, "").strip().lower() in {"1", "true", "yes", "on"}


def allow_ephemeral_key() -> None:
    """Test/local opt-in: capabilities live and die with this process.

    Without it a capability minted in one process cannot be verified in
    another, which is exactly the cross-process case a deployment needs.
    """
    os.environ[ENV_ALLOW_EPHEMERAL] = "1"


def signing_key() -> bytes:
    """The shared signing key, or a refusal.

    A missing key blocks capability issuance AND execution. Falling back to a
    silent per-process key would make a capability unverifiable across
    processes while still looking like it worked inside one of them.
    """
    raw = os.environ.get(ENV_KEY, "").strip()
    if raw:
        try:
            decoded = base64.urlsafe_b64decode(raw.encode())
            if decoded:
                return decoded
        except Exception:
            return raw.encode()
    if not ephemeral_allowed():
        raise AuthzError(
            f"{ENV_KEY} is not configured: capability issuance and execution are blocked. "
            f"Set {ENV_KEY} for a shared key, or {ENV_ALLOW_EPHEMERAL}=1 for a "
            "single-process development run."
        )
    return _EPHEMERAL_KEY


def key_id() -> str:
    """Short fingerprint of the key in use, recorded in every capability."""
    return hashlib.sha256(signing_key()).hexdigest()[:12]



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
        "kid": key_id(),
    }
    body = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    signature = _b64(hmac.new(signing_key(), body.encode("utf-8"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def _peek_kid(body: str) -> str:
    """Read the key id from an UNVERIFIED payload. Diagnostic only, never trusted."""
    try:
        payload = json.loads(_unb64(body).decode("utf-8"))
    except Exception:
        return ""
    kid = payload.get("kid")
    return kid if isinstance(kid, str) else ""


def verify(token: str, *, purpose: str, binding: dict) -> dict:
    """Verify a capability and return its payload. Anything else fails closed."""
    if not isinstance(token, str) or token.count(".") != 1:
        raise AuthzError("capability is missing or malformed")
    body, signature = token.split(".", 1)
    expected = _b64(hmac.new(signing_key(), body.encode("utf-8"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        # A capability minted under another key is a deployment fault, not a
        # forgery. Say so: otherwise a worker looks like an attacker.
        other = _peek_kid(body)
        if other and other != key_id():
            raise AuthzError(
                "capability was issued under a different signing key "
                f"(kid {other}); every process must share {ENV_KEY}"
            )
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


def mint_reconcile_capability(job_id: str, *, obligation_id: str,
                              ttl_ms: int = 120_000) -> str:
    """Permission to settle one spend obligation by hand.

    Manual reconciliation is a privileged action, so it carries its own
    capability instead of a boolean from a request body.
    """
    return mint("reconcile", {
        "job_id": job_id,
        "obligation_id": obligation_id,
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


def reject_caller_settlement(extra: dict) -> None:
    """Fail loudly when a caller states the cost, the success or the job id.

    These facts must come from the verified provider evidence; a caller that
    states them itself is claiming a charge of zero for a paid generation.
    """
    if not extra:
        return
    offending = sorted(set(extra) & set(CALLER_SETTLEMENT_FIELDS))
    if offending:
        raise AuthzError(
            "settlement facts are read from the verified evidence, not from the caller: "
            + ", ".join(offending)
        )
