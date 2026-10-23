"""PreToolUse guard: secrets, media and real databases stay out of the repository.

Reads the Claude Code hook payload on stdin and answers whether the requested
file write may run.

The path rules are not duplicated here. ``scripts/check_git_files.py`` already
holds the single definition of a forbidden path, and the pre-commit hook and the
CI secret scan both use it. This guard reuses that function so the three layers
cannot drift apart.

Two rules are added on top of it, because they concern the act of writing and
not the act of committing:

* a write is resolved to its real target, so a symlink cannot smuggle a write
  out of the worktree;
* temporary test data is allowed only inside the designated temporary roots.

Coverage limits: the guard sees one tool call at a time. It cannot see what a
script writes afterwards and it does not read file contents.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_git_files import blocked  # noqa: E402  (needs ROOT on sys.path)

# Private keys and credentials are refused everywhere, including inside a
# temporary folder.
SECRET_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


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


def project_root():
    """Resolved repository root."""
    try:
        return ROOT.resolve()
    except OSError:
        return ROOT


def temp_roots():
    """Directories where a session may create temporary test data."""
    roots = []
    try:
        roots.append(Path(tempfile.gettempdir()).resolve())
    except (OSError, ValueError):
        pass
    repo_tmp = project_root() / "tmp"
    try:
        roots.append(repo_tmp.resolve())
    except OSError:
        roots.append(repo_tmp)
    extra = os.environ.get("GREMOVOD_TEMP_ROOTS", "")
    for item in extra.replace(";", ",").split(","):
        item = item.strip()
        if item:
            try:
                roots.append(Path(item).resolve())
            except OSError:
                roots.append(Path(item))
    return roots


def _is_inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def canonical(path, cwd):
    """The real target of a write, with symlinks resolved."""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path(cwd) / candidate
    try:
        return candidate.resolve()
    except (OSError, ValueError):
        return candidate


def is_secret_shaped(name):
    """True for a file name that carries credentials rather than data."""
    lower = name.lower()
    if lower.endswith("_api_key.txt"):
        return True
    if lower.startswith(".env") and not lower.endswith(".example"):
        return True
    if lower.endswith(SECRET_SUFFIXES):
        return True
    return False


def check(path, cwd):
    """Return ``(allowed, reason)`` for a write target."""
    if not path:
        return False, (
            "The tool call did not name a file, so the write could not be verified. "
            "Repeat the call with an explicit file path."
        )
    resolved = canonical(path, cwd)
    name = resolved.name.lower()
    if is_secret_shaped(name):
        return False, (
            f"'{resolved.name}' looks like a credential file. Keys, .env files and "
            "private keys stay on this machine and are never written by a session."
        )
    for root in temp_roots():
        if _is_inside(resolved, root):
            # Designated temporary area: test data is allowed here.
            return True, ""
    project = project_root()
    if not _is_inside(resolved, project):
        return False, (
            f"'{resolved}' resolves outside the worktree. A session writes inside the "
            "project directory, or into a designated temporary folder."
        )
    try:
        relative = resolved.relative_to(project).as_posix()
    except ValueError:
        relative = resolved.as_posix()
    if blocked(relative):
        return False, (
            f"'{relative}' is a local data or credential path (keys, .env, SQLite, "
            "media, runtime or project folders). Those files live on this machine "
            "only and must never be written by a session. Write code or docs instead."
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
                    "The hook payload could not be read, so the write was not "
                    "verified. Retry the call; if it still fails, report it."
                ),
            }
        }))
        return 0
    path = target_path(payload)
    cwd = payload.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or str(project_root())
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
