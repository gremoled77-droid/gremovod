"""PreToolUse guard: dangerous Git operations in the GremoVOD repository.

Reads the Claude Code hook payload on stdin, decides whether the requested shell
command may run, and answers with a permission decision on stdout.

Rules enforced:

* push / merge / rebase / checkout may not target or run on a protected
  branch (``main``, ``master``, ``mavis/work``);
* ``git push --force`` is refused: the repository contract requires an explicit
  owner permission for a force push;
* ``git clean`` with a force flag is refused: it destroys untracked local media,
  keys and databases that live only on this machine;
* deleting a branch or a worktree that is not the current one is refused, so a
  session cannot destroy another agent's work.

The guard never runs Git commands with side effects. It only reads the current
branch and the working tree state.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Branches that must only ever be changed through a reviewed pull request.
DEFAULT_PROTECTED_BRANCHES = ("main", "master", "mavis/work")

# A Git invocation inside a shell line. Shell operators are treated as
# separators so that "ls && git push" is seen as a Git command too.
GIT_TOKEN = re.compile(r"(?<![\w./-])git(?=\s|$)")
SPLIT = re.compile(r"(?:&&|\|\||;|\||\n)")
WORD = re.compile(r"""["']?([^\s"';&|]+)["']?""")

FORCE_FLAGS = {"-f", "--force", "--force-with-lease"}
# A force flag inside a Git option cluster: -f, -fd, -fdx, --force.
CLEAN_FORCE = re.compile(r"\bclean\b[^|;&]*(-[a-zA-Z]*f[a-zA-Z]*|--force)\b")


def read_payload():
    """Read the hook payload from stdin. Returns an empty dict on any problem."""
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
    """Extract the shell command from a PreToolUse payload."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    for key in ("command", "cmd", "script"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def protected_branches():
    """Protected branch names, extendable through GREMOVOD_PROTECTED_BRANCHES."""
    names = set(DEFAULT_PROTECTED_BRANCHES)
    extra = os.environ.get("GREMOVOD_PROTECTED_BRANCHES", "")
    for name in extra.replace(";", ",").split(","):
        name = name.strip()
        if name:
            names.add(name)
    return names


def project_dir(payload):
    """Directory the session runs in."""
    for candidate in (payload.get("cwd"), os.environ.get("CLAUDE_PROJECT_DIR"), os.getcwd()):
        if candidate and Path(candidate).is_dir():
            return str(Path(candidate).resolve())
    return os.getcwd()


def _git(cwd, *args):
    try:
        result = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", "replace").strip()


def current_branch(cwd):
    """Name of the checked out branch, or None when it cannot be determined.

    ``git branch --show-current`` is used on purpose: ``rev-parse --abbrev-ref
    HEAD`` answers "HEAD" for a branch that has no commit yet, which would hide
    the protected branch name exactly when a fresh worktree is checked out.
    """
    if _git(cwd, "rev-parse", "--is-inside-work-tree") != "true":
        return None
    name = _git(cwd, "branch", "--show-current")
    if not name or name == "HEAD":
        return None
    return name


def git_commands(command):
    """Split a shell line into the Git invocations it contains."""
    found = []
    for chunk in SPLIT.split(command):
        chunk = chunk.strip()
        if not chunk:
            continue
        if not GIT_TOKEN.search(chunk):
            continue
        words = [m.group(1) for m in WORD.finditer(chunk)]
        index = None
        for position, word in enumerate(words):
            if word.lower() == "git":
                index = position
                break
        if index is None:
            continue
        found.append(words[index:])
    return found


def _subcommand(words):
    """The Git subcommand of an invocation, skipping global options."""
    index = 1
    while index < len(words):
        word = words[index]
        if word.startswith("-"):
            if word in ("-C", "-c", "--git-dir", "--work-tree", "--exec-path"):
                index += 2
                continue
            index += 1
            continue
        return word.lower()
    return ""


def _refspec_targets(words):
    """Branch names that appear as an argument of an invocation."""
    targets = []
    for word in words[1:]:
        if word.startswith("-"):
            continue
        name = word.split(":", 1)[-1] if ":" in word else word
        name = name.split("^")[0]
        if name:
            targets.append(name.lower())
    return targets


def _is_protected(name, protected):
    """True when a branch name is one of the protected branches.

    Only an exact name, or a remote/ref prefix of it, counts. A feature branch
    called ``feature/main`` is not the protected ``main`` branch.
    """
    if not name:
        return False
    name = name.lower()
    if name in protected:
        return True
    for prefix in ("origin/", "refs/heads/", "refs/remotes/origin/"):
        if name.startswith(prefix) and name[len(prefix):] in protected:
            return True
    return False


def _push_target(words, cwd):
    """Resolve what a push would update.

    Returns ``("explicit", name)`` when the command names a protected branch and
    ``("current", name)`` when the push follows the checked out branch.
    """
    protected = protected_branches()
    for name in _refspec_targets(words):
        if _is_protected(name, protected):
            return "explicit", name
    branch = current_branch(cwd)
    if branch and _is_protected(branch, protected):
        return "current", branch
    return None, None


def check(command, cwd):
    """Return ``(allowed, reason)`` for a shell command."""
    if not command or not command.strip():
        return True, ""
    protected = protected_branches()
    branch = current_branch(cwd)
    for words in git_commands(command):
        sub = _subcommand(words)
        if not sub:
            continue
        if sub == "push":
            if any(word.lower() in FORCE_FLAGS for word in words):
                return False, (
                    "Force push is blocked for this repository. The owner contract "
                    "requires a separate explicit permission for force-push; use a "
                    "normal push to a task branch instead."
                )
            kind, name = _push_target(words, cwd)
            if kind:
                return False, (
                    f"Push to the protected branch '{name}' is blocked. Push only your "
                    "own task branch and open a draft pull request for review."
                )
        elif sub in ("merge", "rebase", "cherry-pick"):
            if branch and _is_protected(branch, protected):
                return False, (
                    f"'{sub}' is blocked while the checked out branch is the protected "
                    f"branch '{branch}'. Work on a task branch instead."
                )
            for name in _refspec_targets(words):
                if _is_protected(name, protected):
                    return False, (
                        f"'{sub}' into the protected branch '{name}' is blocked. "
                        "Protected branches change only through a reviewed pull request."
                    )
        elif sub in ("reset", "restore", "revert"):
            if branch and _is_protected(branch, protected):
                return False, (
                    f"'{sub}' is blocked while the checked out branch is the protected "
                    f"branch '{branch}'. Work on a task branch instead."
                )
        elif sub in ("checkout", "switch"):
            for name in _refspec_targets(words):
                if _is_protected(name, protected):
                    return False, (
                        f"Switching to the protected branch '{name}' is blocked in an "
                        "agent worktree. The protected branch belongs to the owner."
                    )
        elif sub == "clean":
            if CLEAN_FORCE.search(" ".join(words)):
                return False, (
                    "'git clean -f' is blocked: untracked local media, keys and "
                    "databases exist only on this machine and cannot be restored."
                )
        elif sub == "branch":
            if "-D" in words or "--delete" in words:
                for name in _refspec_targets(words):
                    if _is_protected(name, protected):
                        return False, f"Deleting the protected branch '{name}' is blocked."
                    if branch and name == branch.lower():
                        return False, "Deleting the checked out branch is blocked."
        elif sub == "worktree":
            if "remove" in [word.lower() for word in words]:
                for name in _refspec_targets(words):
                    if name == "remove":
                        continue
                    if Path(name).resolve() == Path(cwd).resolve():
                        return False, "Removing the current worktree is blocked."
                    return False, (
                        f"Removing worktree '{name}' is blocked: another session may "
                        "still own it. Remove it manually after checking the owner."
                    )
    return True, ""


def main():
    payload = read_payload()
    command = tool_command(payload)
    cwd = project_dir(payload)
    allowed, reason = check(command, cwd)
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
