"""PreToolUse guard: dangerous Git operations in the GremoVOD repository.

The guard separates the branch a command READS from the branch it WRITES:

* a task branch pulling the integration branch - ``git merge origin/mavis/work`` -
  is a normal synchronisation and stays allowed;
* anything that writes a protected branch (``main``, ``master``, ``mavis/work``)
  is refused.

Coverage limits are listed at the end of this file and in
``.claude/rules/guards.md``.
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

# A force flag inside a Git option cluster: -f, -fu, --force, --force-with-lease.
FORCE_FLAG = re.compile(r"^(--force[a-z-]*|-[a-zA-Z]*f[a-zA-Z]*)$")
# A force flag inside a Git option cluster for "git clean": -f, -fd, -fdx, --force.
CLEAN_FORCE = re.compile(r"\bclean\b[^|;&]*(-[a-zA-Z]*f[a-zA-Z]*|--force)\b")


def read_payload():
    """Read the hook payload from stdin.

    Returns ``(payload, state)`` where state is ``"empty"`` (nothing was sent),
    ``"invalid"`` (something arrived but is not a JSON object) or ``"ok"``.
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


def _git(repo, *args):
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", "replace").strip()


def current_branch(repo):
    """Name of the checked out branch, or None when it cannot be determined.

    ``git branch --show-current`` is used on purpose: ``rev-parse --abbrev-ref
    HEAD`` answers "HEAD" for a branch that has no commit yet, which would hide
    the protected branch name exactly when a fresh worktree is checked out.
    """
    if _git(repo, "rev-parse", "--is-inside-work-tree") != "true":
        return None
    name = _git(repo, "branch", "--show-current")
    if not name or name == "HEAD":
        return None
    return name


def upstream_branch(repo):
    """Upstream of the checked out branch, or None."""
    name = _git(repo, "rev-parse", "--abbrev-ref", "@{upstream}")
    if not name or name == "HEAD":
        return None
    return name


def local_branches(repo):
    """Names of the local branches of the repository."""
    out = _git(repo, "branch", "--format=%(refname:short)")
    if not out:
        return set()
    return {line.strip() for line in out.splitlines() if line.strip()}


def worktree_branches(repo):
    """Branches that are checked out in some worktree of the repository."""
    out = _git(repo, "worktree", "list", "--porcelain")
    if not out:
        return set()
    names = set()
    for line in out.splitlines():
        if line.startswith("branch "):
            names.add(line[len("branch "):].strip().replace("refs/heads/", "", 1))
    return names


def has_changes(repo):
    """True when the working tree or the index carries uncommitted changes."""
    out = _git(repo, "status", "--porcelain")
    return bool(out)


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


def _subcommand_index(words):
    """Index of the Git subcommand inside an invocation, skipping global options."""
    index = 1
    while index < len(words):
        word = words[index]
        if word.startswith("-"):
            if word in ("-C", "-c", "--git-dir", "--work-tree", "--exec-path"):
                index += 2
                continue
            index += 1
            continue
        return index
    return None


def _subcommand(words):
    """The Git subcommand of an invocation, skipping global options."""
    index = _subcommand_index(words)
    if index is None:
        return ""
    return words[index].lower()


def _repo_dir(words, cwd):
    """The repository a command acts on. ``git -C <path>`` switches it."""
    for index, word in enumerate(words):
        if word == "-C" and index + 1 < len(words):
            candidate = Path(words[index + 1])
            if not candidate.is_absolute():
                candidate = Path(cwd) / candidate
            return str(candidate)
    return cwd


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


def _positional(words):
    """Arguments of an invocation that are not options, without the subcommand."""
    index = _subcommand_index(words)
    if index is None:
        return []
    return [word for word in words[index + 1:] if not word.startswith("-")]


def _is_bulk_path(arg, repo):
    """True when a path argument names a whole tree rather than a single file.

    ``git checkout .``, ``git checkout tree`` and ``git restore .`` discard the
    changes of every file below the path, which is what the guard refuses.
    """
    if arg in (".", "./", "*", "**", ".\\"):
        return True
    normalised = arg.replace("\\", "/")
    if normalised.endswith("/.") or normalised.endswith("/.."):
        return True
    candidate = Path(repo) / normalised
    try:
        return candidate.is_dir()
    except OSError:
        return False


def _push_destinations(words):
    """Remote side branches a push would write.

    ``git push origin main`` writes ``main`` on the remote. ``git push origin
    HEAD:main`` writes ``main`` and reads ``HEAD``. Only the written side
    matters, so the destination after the colon is what is checked.
    """
    args = _positional(words)
    refs = args[1:] if len(args) >= 2 else []
    destinations = []
    for ref in refs:
        if ":" in ref:
            destinations.append(ref.split(":", 1)[1])
        else:
            destinations.append(ref)
    return destinations


def check(command, cwd):
    """Return ``(allowed, reason)`` for a shell command."""
    if not command or not command.strip():
        return True, ""
    protected = protected_branches()
    for words in git_commands(command):
        sub = _subcommand(words)
        if not sub:
            continue
        repo = _repo_dir(words, cwd)
        branch = current_branch(repo)
        if sub == "push":
            if any(FORCE_FLAG.match(word.lower()) for word in words):
                return False, (
                    "Force push is blocked for this repository. The owner contract "
                    "requires a separate explicit permission for force-push; use a "
                    "normal push to a task branch instead."
                )
            if "--mirror" in words:
                return False, (
                    "'git push --mirror' is blocked: it copies every ref of the "
                    "repository, including the protected branches."
                )
            destinations = _push_destinations(words)
            if "--all" in words:
                protected_local = sorted(
                    name for name in local_branches(repo) if _is_protected(name, protected))
                if protected_local:
                    return False, (
                        f"'git push --all' would publish the protected branch "
                        f"'{protected_local[0]}'. Push the task branch explicitly."
                    )
            elif not destinations:
                upstream = upstream_branch(repo)
                if upstream:
                    destinations = [upstream]
                elif branch:
                    destinations = [branch]
            for name in destinations:
                if _is_protected(name, protected):
                    return False, (
                        f"Push to the protected branch '{name}' is blocked. Push only "
                        "your own task branch and open a draft pull request for review."
                    )
            if branch and _is_protected(branch, protected):
                return False, (
                    f"Push from the protected branch '{branch}' is blocked. Switch to "
                    "a task branch first."
                )
        elif sub in ("merge", "rebase", "cherry-pick", "reset", "restore", "revert"):
            # The written branch is the current one. The argument is only the
            # source, so a protected source is a normal synchronisation.
            if branch and _is_protected(branch, protected):
                return False, (
                    f"'{sub}' writes the protected branch '{branch}' and is blocked. "
                    "Work on a task branch instead."
                )
            if sub == "reset" and any(word.lower() in ("--hard", "--merge") for word in words):
                if has_changes(repo):
                    return False, (
                        "'git reset --hard' would discard uncommitted work in the "
                        "working tree. Commit or stash the changes first."
                    )
            if sub == "restore":
                index_only = "--staged" in words and "--worktree" not in words
                paths = _positional(words)
                if not index_only:
                    if not paths:
                        return False, (
                            "'git restore' without a path would discard every "
                            "changed file in the working tree. Restore the files "
                            "one by one instead."
                        )
                    for name in paths:
                        if _is_bulk_path(name, repo):
                            return False, (
                                f"'git restore {name}' would discard every "
                                "uncommitted change below that path. Restore the "
                                "files one by one instead."
                            )
        elif sub == "checkout":
            for name in _positional(words):
                if _is_bulk_path(name, repo):
                    return False, (
                        f"'git checkout {name}' would discard every uncommitted "
                        "change below that path. Discard the files one by one "
                        "instead."
                    )
                if _is_protected(name, protected):
                    return False, (
                        f"Switching to the protected branch '{name}' is blocked in an "
                        "agent worktree. The protected branch belongs to the owner."
                    )
        elif sub == "switch":
            for name in _positional(words):
                if _is_protected(name, protected):
                    return False, (
                        f"Switching to the protected branch '{name}' is blocked in an "
                        "agent worktree. The protected branch belongs to the owner."
                    )
        elif sub == "stash":
            if "clear" in [word.lower() for word in words]:
                return False, (
                    "'git stash clear' destroys every stashed change, including "
                    "work another session put aside. Drop the stash you own instead."
                )
        elif sub == "clean":
            if CLEAN_FORCE.search(" ".join(words)):
                return False, (
                    "'git clean -f' is blocked: untracked local media, keys and "
                    "databases exist only on this machine and cannot be restored."
                )
        elif sub == "branch":
            if "-D" in words or "--delete" in words:
                busy = worktree_branches(repo)
                for name in _positional(words):
                    if _is_protected(name, protected):
                        return False, f"Deleting the protected branch '{name}' is blocked."
                    if branch and name == branch.lower():
                        return False, "Deleting the checked out branch is blocked."
                    if name in busy:
                        return False, (
                            f"Branch '{name}' is checked out in another worktree. "
                            "Deleting it would break another session."
                        )
        elif sub == "worktree":
            if "remove" in [word.lower() for word in words]:
                for name in _positional(words):
                    if name.lower() == "remove":
                        continue
                    if Path(name).resolve() == Path(cwd).resolve():
                        return False, "Removing the current worktree is blocked."
                    return False, (
                        f"Removing worktree '{name}' is blocked: another session may "
                        "still own it. Remove it manually after checking the owner."
                    )
    return True, ""


def main():
    payload, state = read_payload()
    if state == "invalid":
        # A payload that cannot be read cannot be checked, and the guard exists
        # to stop a wrong action, not to excuse one.
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
