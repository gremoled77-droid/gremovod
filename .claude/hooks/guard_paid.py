"""PreToolUse guard: a session must not spend money on its own.

Reads the Claude Code hook payload on stdin and answers whether the requested
shell command may run.

The hook is not an authorisation system. It only keeps a session from reaching
a paid provider by accident. The real authorisation for a paid generation is the
budget package, the owner approval and the idempotency ledger of the protected
Studio runtime; a session cannot grant itself any of that.

Two classes of command are treated differently:

* a **direct** provider call (``api.piapi.ai``, ``api.openai.com``, …) bypasses
  the Studio gate entirely, so it is refused always - there is no switch that
  opens it;
* a **gated** call goes through the local Studio, which enforces budget, owner
  approval and idempotency itself. It needs the explicit
  ``GREMOVOD_ALLOW_GATED_PAID=1`` in the session environment, and even then the
  Studio gate still decides.

Coverage limits:

* the guard sees the command line only. A script that reaches a paid provider
  from inside is not visible to it; the known direct scripts are listed below;
* it does not inspect HTTP calls made by imported libraries;
* it does not know whether the Studio would have approved a request.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Fallback used only when the repository script cannot be imported. Keep the
# hosts in sync with scripts/p0_paid_dispatch_audit.py.
FALLBACK_PAID_HOSTS = (
    "api.piapi.ai",
    "piapi.ai",
    "api.kie.ai",
    "api.openai.com",
    "api.anthropic.com",
    "api.minimax.io",
    "api.minimaxi.com",
)

try:  # pragma: no cover - depends on the repository layout
    from scripts.p0_paid_dispatch_audit import PAID_HOSTS  # noqa: E402
except Exception:  # pragma: no cover - fallback path
    PAID_HOSTS = FALLBACK_PAID_HOSTS

# Only API endpoints cost money. The bare site host serves documentation pages.
PAID_API_HOSTS = tuple(sorted({h for h in PAID_HOSTS if h.startswith("api.")}))

# Scripts that put money on the wire without passing the Studio gate.
DIRECT_SCRIPTS = {
    "live_piapi_test.py": "calls api.piapi.ai directly and spends money",
}

# Scripts that ask the local Studio, which enforces budget, owner approval and
# idempotency on its own.
GATED_SCRIPTS = {
    "watch_hunyuan_test.py": "asks the local studio for a Hunyuan video generation",
}

# The environment switch. It opens the gated path only. It is not a payment
# authorisation and it never opens a direct provider call.
GATED_ENV = "GREMOVOD_ALLOW_GATED_PAID"

# A flag that explicitly asks to spend money skips the estimate and the
# confirmation token, so it is refused like a direct provider call.
SPEND_FLAGS = re.compile(r"--(paid|spend|real-spend|live-spend)\b", re.IGNORECASE)


def read_payload():
    """Read the hook payload from stdin.

    Returns ``(payload, state)`` where state is ``"empty"``, ``"invalid"`` or
    ``"ok"``.
    """
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    except (OSError, ValueError):
        return {}, "invalid"
    raw = raw.strip()
    if not raw:
        return {}, "empty"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}, "invalid"
    if not isinstance(payload, dict):
        return {}, "invalid"
    return payload, "ok"


def tool_command(payload):
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    for key in ("command", "cmd", "script"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def paid_command(command):
    """Return ``(kind, reason)`` for a shell command.

    ``kind`` is ``""`` when nothing paid is visible, ``"direct"`` for a call
    that bypasses the Studio gate and ``"gated"`` for a call that goes through
    it.
    """
    if not command:
        return "", ""
    lowered = command.lower()
    for script, what in DIRECT_SCRIPTS.items():
        if script not in lowered:
            continue
        if script == "live_piapi_test.py" and "--dry-run" in lowered:
            continue
        return "direct", (
            f"'{script}' {what} without passing the Studio gate, so it is refused "
            "always. A paid generation needs the owner, a budget package and a "
            "separate permission for that concrete request."
        )
    for host in PAID_API_HOSTS:
        if host in lowered:
            return "direct", (
                f"The command reaches '{host}', a paid provider endpoint. A direct "
                "provider call bypasses the Studio budget, approval and idempotency "
                "gate, so it is refused always and no environment switch opens it."
            )
    if SPEND_FLAGS.search(command):
        return "direct", (
            "The command carries an explicit spend flag. It skips the price "
            "estimate and the confirmation token, so it is refused always."
        )
    for script, what in GATED_SCRIPTS.items():
        if script in lowered:
            return "gated", (
                f"'{script}' {what}. The Studio enforces the budget, the owner "
                "approval and the idempotency ledger; this guard only keeps the "
                "session from starting it silently."
            )
    return "", ""


def check(command):
    """Return ``(allowed, reason)`` for a shell command."""
    kind, reason = paid_command(command)
    if kind == "direct":
        return False, reason
    if kind == "gated":
        if os.environ.get(GATED_ENV) == "1":
            return True, (
                "Allowed by the session opt-in. The studio still decides: budget, "
                "owner approval and idempotency are enforced there, not here."
            )
        return False, (
            reason + f" Set {GATED_ENV}=1 only when the owner has granted this "
            "specific request; the variable is not a payment authorisation."
        )
    return True, ""


def main():
    payload, state = read_payload()
    if state == "invalid":
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "The hook payload could not be read, so the command was not "
                    "verified. Retry the command; if it still fails, report it."
                ),
            }
        }))
        return 0
    command = tool_command(payload)
    allowed, reason = check(command)
    if allowed:
        print(json.dumps({"continue": True}))
        return 0
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
