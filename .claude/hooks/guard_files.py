"""PreToolUse guard: secrets, media and real databases stay out of the repository.

Reads the Claude Code hook payload on stdin and answers whether the requested
file write may run.

The path rules are not duplicated here. ``scripts/check_git_files.py`` already
holds the single definition of a forbidden path, and the pre-commit hook and the
CI secret scan both use it. This guard reuses that function so the three layers
cannot drift apart.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_git_files import blocked  # noqa: E402  (needs ROOT on sys.path)

# Writes that are refused even when the path itself looks harmless.
EXTRA_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".pem", ".key", ".p12", ".pfx")


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


def target_path(payload):
    """The file the tool wants to write."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    for key in ("file_path", "path", "notebook_path", "filePath"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def normalise(path, cwd):
    """Repository relative POSIX path of a target."""
    if not path:
        return ""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path(cwd) / candidate
    try:
        relative = candidate.resolve().relative_to(ROOT.resolve())
    except (ValueError, OSError):
        return candidate.as_posix()
    return relative.as_posix()


def check(path, cwd):
    """Return ``(allowed, reason)`` for a write target."""
    if not path:
        return True, ""
    relative = normalise(path, cwd)
    lowered = relative.lower()
    name = lowered.rsplit("/", 1)[-1]
    if blocked(relative):
        return False, (
            f"'{relative}' is a local data or credential path (keys, .env, SQLite, "
            "media, runtime or project folders). Those files live on this machine "
            "only and must never be written by a session. Write code or docs instead."
        )
    if name.endswith(EXTRA_SUFFIXES):
        return False, (
            f"'{relative}' looks like a database or a private key file. Real data "
            "stays outside the repository; use a temporary directory for test data."
        )
    return True, ""


def main():
    payload = read_payload()
    path = target_path(payload)
    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or str(ROOT)
    allowed, reason = check(path, cwd)
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
