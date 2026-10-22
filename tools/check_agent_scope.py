"""Scope guard for NEW agent task PRs.

Designed to prevent accidental cross-agent edits. Only branch names recognized in
the manual are enforced. Existing codex/work or claude/work branches are not
retroactively blocked. This CI does not substitute GitHub branch protection.

Two independent mechanisms live here:

* ``role_for_branch`` — the original per-agent allowlist (``build/*``, ``codex/*``,
  ``coordination/*``). Unchanged behaviour.
* ``task_key_for_branch`` — the newer MiniMax/owner task branches (``minimax/ga-NN-*``,
  ``mavis/ga-NN-*``). Their allowed paths come from ``tools/minimax_task_scopes.json``.

Trust model
-----------
This file is the control code of the scope guard, so it must not be able to judge
itself. Two rules follow from that:

* the task manifest is read from the BASE commit, never from the pull request head,
  so a task branch cannot widen its own scope in the same pull request;
* the CI workflow runs the copy of this file that lives in the base revision, so a
  pull request that replaces this validator cannot decide its own verdict.

The very pull request that introduces the scope guard is the bootstrap case: the
base revision has no trusted control code yet, the pull request's own validator runs
instead, and the check says so loudly (``SCOPE_BOOTSTRAP``). Such a pull request is
protected by an owner review, not by CI.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = "tools/minimax_task_scopes.json"

# Bumped whenever the way this tool is driven changes. The CI workflow asks the
# base revision for this number before it trusts the copy: a base revision that
# predates the trusted interface cannot judge a pull request, and the workflow
# falls back to the bootstrap path instead of running a half-understood tool.
TRUSTED_INTERFACE_VERSION = 2

# The files that make up the guard itself. A pull request that changes them does
# not change the verdict of that same pull request (the verdict comes from the
# base revision), but the change takes effect for every later pull request, so the
# check reports it by name.
CONTROL_FILES = (
    ".github/workflows/agent-scope-guard.yml",
    "tools/check_agent_scope.py",
    "tools/minimax_task_scopes.json",
)

DEFAULT_MANIFEST = {
    "version": 1,
    "branch_prefixes": ["minimax/", "mavis/"],
    "task_key_pattern": "^[a-z]+-[0-9]+$",
    "tasks": {},
}


def role_for_branch(branch):
    if branch.startswith("build/claude/"):
        return "claude"
    if branch.startswith("build/argon/"):
        return "argon"
    if branch.startswith("codex/review-") or branch.startswith("codex/spec-"):
        return "codex"
    if branch.startswith("coordination/"):
        return "coordination"
    return None


OWNED = {
    "claude": (
        "backend/", "db/", "scripts/", "tools/", "prompts/", "tests/",
        "docs/agent_handoffs/claude-",
        # One exact workflow, never .github/ or .github/workflows/: the scope guard
        # workflow and every other workflow stay closed to this role.
        ".github/workflows/studio-offline-ci.yml",
    ),
    "argon": (
        "workflows/", "integrations/n8n/",
        "docs/agent_handoffs/argon-", "tests/argon_", "tests/test_argon_",
    ),
    "codex": (
        "docs/specs/", "docs/CODEX_DECISIONS.md",
        "docs/CODEX_NEXT_ACTIONS.md", "docs/agent_handoffs/codex-",
    ),
    "coordination": (
        "AGENT_BUILD_MANUAL.md", "AGENTS.md", "STATUS.md",
        "docs/CODEX_REVIEW_PACKET.md", "docs/AGENT_ROLE_MATRIX.md",
        "docs/agent_handoffs/",
        "workflows/",       # bootstrap PR only; subsequent implementation owned by Argon
        "prompts/README.md",
        "tools/test_agent_coordination.py", "tools/check_agent_scope.py",
        "tools/test_agent_scope.py",
        ".github/workflows/agent-coordination.yml",
        ".github/workflows/agent-scope-guard.yml",
    ),
}


def path_allowed(path, prefixes):
    """A path is allowed when it equals a prefix, or starts with a directory/dash prefix."""
    return any(
        path == prefix
        or ((prefix.endswith("/") or prefix.endswith("-")) and path.startswith(prefix))
        for prefix in prefixes
    )


def path_denied(path, prefixes):
    """A path is denied when it equals a prefix or sits inside a denied directory."""
    return any(
        path == prefix or (prefix.endswith("/") and path.startswith(prefix))
        for prefix in prefixes
    )


def task_key_for_branch(branch):
    """Return the task key of a task branch, or None when the branch is not one.

    ``minimax/ga-04-studio-offline-ci`` -> ``ga-04``.
    ``mavis/work``, ``minimax/p0-budget-authz`` and ``feature/*`` -> None.
    """
    for prefix in DEFAULT_MANIFEST["branch_prefixes"]:
        if not branch.startswith(prefix):
            continue
        rest = branch[len(prefix):]
        parts = rest.split("-")
        if len(parts) < 2:
            return None
        key = f"{parts[0]}-{parts[1]}"
        if re.match(DEFAULT_MANIFEST["task_key_pattern"], key):
            return key
    return None


def manifest_tasks(manifest):
    if not manifest:
        return {}
    tasks = manifest.get("tasks")
    return tasks if isinstance(tasks, dict) else {}


def validate_manifest(manifest):
    """Return a list of problems with a task manifest. Empty list means usable."""
    problems = []
    if not isinstance(manifest, dict):
        return ["manifest is not a JSON object"]
    tasks = manifest.get("tasks")
    if not isinstance(tasks, dict):
        return ["manifest has no 'tasks' object"]
    pattern = manifest.get("task_key_pattern") or DEFAULT_MANIFEST["task_key_pattern"]
    for key, entry in tasks.items():
        if not re.match(pattern, key):
            problems.append(f"task key '{key}' does not match {pattern}")
        if not isinstance(entry, dict):
            problems.append(f"task '{key}' is not an object")
            continue
        allow = entry.get("allow")
        if not isinstance(allow, list) or not allow:
            problems.append(f"task '{key}' has an empty or non-list 'allow'")
            continue
        for item in allow:
            if not isinstance(item, str) or not item.strip():
                problems.append(f"task '{key}' has a non-string allow entry")
    return problems


def forbidden_files(branch, paths, manifest=None):
    """Return the changed paths that the branch is not allowed to touch.

    Unknown task branches fail closed: every changed path is reported as forbidden.
    For a task branch the effective allowlist is the task scope plus the shared
    allowlist, and the shared denylist always wins over both.
    """
    role = role_for_branch(branch)
    if role is not None:
        return [p for p in paths if not path_allowed(p, OWNED[role])]
    key = task_key_for_branch(branch)
    if key is None:
        return []
    tasks = manifest_tasks(manifest)
    if key not in tasks:
        return list(paths)
    entry = tasks[key]
    task_allow = entry.get("allow") if isinstance(entry, dict) else None
    if not isinstance(task_allow, list) or not task_allow:
        return list(paths)
    shared = manifest or {}
    allow = list(task_allow) + list(shared.get("common_allow") or [])
    deny = list(shared.get("common_deny") or [])
    return [p for p in paths
            if path_denied(p, deny) or not path_allowed(p, allow)]


def changed_files(base, head="HEAD"):
    """Return the paths the pull request changes, relative to the base branch.

    ``base`` is a branch name on the remote (``origin/<base>``); ``head`` is the
    commit-ish the pull request head is at. The default keeps the historical
    behaviour: the working tree is checked out at the pull request head.
    """
    result = subprocess.run(
        ["git", "diff", "--name-only", "-z", f"origin/{base}...{head}"],
        check=True, capture_output=True,
    )
    return [p.decode("utf8") for p in result.stdout.split(b"\0") if p]


def control_file_changes(paths):
    """Return the changed paths that belong to the scope guard itself."""
    return [p for p in paths if p in CONTROL_FILES]


def event_refs():
    """Return the (base, head) branch names of the pull request event.

    The event payload is written by GitHub, so it cannot be forged by the pull
    request the way a command line argument can. Returns ``(None, None)`` when
    the tool runs outside GitHub Actions.
    """
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not os.path.isfile(path):
        return None, None
    try:
        payload = json.loads(Path(path).read_text(encoding="utf8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None, None
    pull_request = payload.get("pull_request") if isinstance(payload, dict) else None
    if not isinstance(pull_request, dict):
        return None, None
    base = pull_request.get("base")
    head = pull_request.get("head")
    base_ref = base.get("ref") if isinstance(base, dict) else None
    head_ref = head.get("ref") if isinstance(head, dict) else None
    return base_ref, head_ref


def _git_show_base(base):
    """Read the manifest as of the base commit. Returns None when absent there."""
    result = subprocess.run(
        ["git", "show", f"origin/{base}:{MANIFEST_PATH}"],
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout.decode("utf8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def load_manifest(base, root=ROOT):
    """Load the scope manifest in force for a base branch.

    Returns ``(manifest, bootstrapped, in_force)``. The base commit is authoritative
    so a task branch cannot widen its own scope in the same pull request. When the
    base has no manifest at all the pull request that introduces it is the bootstrap
    case.

    ``in_force`` is False only when the manifest exists neither in the base nor in
    the branch. That is the window before the manifest is merged: task branches
    created in that window must not be failed closed, otherwise a branch that simply
    predates the manifest would be blocked for touching its own files.
    """
    base_manifest = _git_show_base(base)
    if base_manifest is not None:
        return base_manifest, False, True
    working = Path(root) / MANIFEST_PATH
    if working.is_file():
        try:
            return json.loads(working.read_text(encoding="utf8")), True, True
        except (UnicodeDecodeError, json.JSONDecodeError):
            return dict(DEFAULT_MANIFEST), True, True
    return dict(DEFAULT_MANIFEST), False, False


def main():
    # The CI workflow asks the base revision for its interface version before it
    # trusts the copy. This has to work without any other argument, so it is
    # answered before the parser validates its required arguments.
    if "--interface-version" in sys.argv:
        print(TRUSTED_INTERFACE_VERSION)
        return 0
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", required=True)
    parser.add_argument("--base", required=True)
    args = parser.parse_args()
    event_base, event_head = event_refs()
    if event_base and args.base != event_base:
        print(f"SCOPE_ERROR: base '{args.base}' does not match the pull request base "
              f"'{event_base}' from the event payload", file=sys.stderr)
        return 2
    if event_head and args.branch != event_head:
        print(f"SCOPE_ERROR: branch '{args.branch}' does not match the pull request head "
              f"'{event_head}' from the event payload", file=sys.stderr)
        return 2
    role = role_for_branch(args.branch)
    key = task_key_for_branch(args.branch)
    if role is None and key is None:
        print(f"LEGACY_BRANCH_NOT_ENFORCED: {args.branch}. Codex review still required.")
        return 0
    try:
        paths = changed_files(args.base)
    except subprocess.CalledProcessError as exc:
        print(f"SCOPE_ERROR: cannot diff against origin/{args.base}: {exc}", file=sys.stderr)
        return 2
    for path in control_file_changes(paths):
        print(f"CONTROL_FILE_CHANGE: {path}")
    if control_file_changes(paths):
        print("SCOPE_CONTROL_FILES: this pull request changes the scope guard itself.")
        print("The verdict below does not depend on that change; it only takes effect for")
        print("later pull requests and needs an owner review.")
    manifest, bootstrapped, in_force = load_manifest(args.base)
    if not in_force:
        print(f"NO_SCOPE_MANIFEST: {MANIFEST_PATH} отсутствует ни в origin/{args.base}, "
              f"ни в этой ветке; области task-веток ещё не введены.")
        print(f"LEGACY_BRANCH_NOT_ENFORCED: {args.branch}. Codex review still required.")
        return 0
    problems = validate_manifest(manifest)
    if problems:
        print(f"SCOPE_ERROR: {MANIFEST_PATH} is invalid in origin/{args.base}:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 2
    tasks = manifest_tasks(manifest)
    if role is None and key not in tasks:
        print(f"UNKNOWN_TASK_SCOPE: '{args.branch}' declares no scope for task '{key}' "
              f"in {MANIFEST_PATH}.")
        print("Declare the scope in a reviewed change to the manifest before merging this PR.")
        for path in paths:
            print(f"UNSCOPED_CHANGE: {path}")
        return 1
    bad = forbidden_files(args.branch, paths, manifest)
    if bootstrapped:
        print(f"SCOPE_BOOTSTRAP: {MANIFEST_PATH} is absent in origin/{args.base}; "
              f"this PR introduces it and is enforced against its own declaration.")
    label = f"role={role}" if role else f"role=task:{key}"
    print(f"AGENT_SCOPE: {label}, changed={len(paths)}, forbidden={len(bad)}")
    if bad:
        for path in bad:
            print(f"CROSS_OWNER_CHANGE: {path}")
        print("Create a separate PR from the responsible agent or record an approved handoff.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
