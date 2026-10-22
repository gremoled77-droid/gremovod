"""PreToolUse guard: no session may spend money without an explicit permission.

Reads the Claude Code hook payload on stdin and answers whether the requested
shell command may run.

The repository contract is simple: a paid generation needs the owner, a budget
package and a separate permission for that concrete request. A shell command
issued by a session is never that permission, so this guard refuses the known
paid entry points and any direct call to a paid provider host.

The host list is not invented here. It comes from
``scripts/p0_paid_dispatch_audit.py``, which is the repository's own definition
of "hosts that cost money".

Set ``GREMOVOD_ALLOW_PAID=1`` in the environment of the session to grant a
one-off permission. That is the only way past the guard, and it is deliberate.
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

# Scripts that put money on the wire, directly or through the running studio.
PAID_SCRIPTS = {
    "live_piapi_test.py": "a live PiAPI model call",
    "watch_hunyuan_test.py": "a live Hunyuan video generation through the studio",
}

# A command that can talk to the network at all.
NETWORK_CLIENT = re.compile(
    r"\b(curl|wget|Invoke-WebRequest|Invoke-RestMethod|iwr|irm|httpx|requests|"
    r"urllib|http\.client|urlopen)\b",
    re.IGNORECASE,
)

SPEND_FLAGS = re.compile(r"--(paid|spend|real-spend|live-spend)\b", re.IGNORECASE)


def read_payload():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    except (OSError, ValueError):
        return {}
    raw = raw.strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


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
    """Return ``(is_paid, reason)`` for a shell command."""
    if not command:
        return False, ""
    lowered = command.lower()
    for script, what in PAID_SCRIPTS.items():
        if script not in lowered:
            continue
        if script == "live_piapi_test.py" and "--dry-run" in lowered:
            continue
        return True, (
            f"'{script}' triggers {what} and costs money. A paid generation needs the "
            "owner, a budget package and a separate permission for that concrete "
            "request. Set GREMOVOD_ALLOW_PAID=1 only when the owner has granted it."
        )
    if SPEND_FLAGS.search(command):
        return True, (
            "The command asks for a paid run. A paid generation needs a separate "
            "owner permission. Set GREMOVOD_ALLOW_PAID=1 only when it was granted."
        )
    if NETWORK_CLIENT.search(command):
        for host in PAID_API_HOSTS:
            if host in lowered:
                return True, (
                    f"The command talks to '{host}', a paid provider endpoint. A paid "
                    "generation needs a separate owner permission. Set "
                    "GREMOVOD_ALLOW_PAID=1 only when it was granted."
                )
    return False, ""


def check(command):
    if os.environ.get("GREMOVOD_ALLOW_PAID") == "1":
        return True, ""
    is_paid, reason = paid_command(command)
    if is_paid:
        return False, reason
    return True, ""


def main():
    payload = read_payload()
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
