"""Scope guard for NEW agent task PRs.

Designed to prevent accidental cross-agent edits. Only branch names recognized in
the manual are enforced. Existing codex/work or claude/work branches are not
retroactively blocked. This CI does not substitute GitHub branch protection.

Two independent mechanisms live here:

* ``role_for_branch`` — the original per-agent allowlist (``build/*``, ``codex/*``,
  ``coordination/*``). Unchanged behaviour.
* ``task_key_for_branch`` — the newer MiniMax/owner task branches (``minimax/ga-NN-*``,
  ``mavis/ga-NN-*``). Their allowed paths come from ``tools/minimax_task_scopes.json``.

The task manifest is read from the BASE commit, never from the pull request head, so
a task branch cannot widen its own scope in the same pull request. The very pull
request that introduces the manifest is the bootstrap case: it declares its scope
loudly (``SCOPE_BOOTSTRAP``) and is enforced against that declaration.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = "tools/minimax_task_scopes.json"

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


def changed_files(base):
    result = subprocess.run(
        ["git", "diff", "--name-only", "-z", f"origin/{base}...HEAD"],
        check=True, capture_output=True,
    )
    return [p.decode("utf8") for p in result.stdout.split(b"\0") if p]


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
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", required=True)
    parser.add_argument("--base", required=True)
    args = parser.parse_args()
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
