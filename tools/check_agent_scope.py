"""Scope guard for NEW agent task PRs.

Designed to prevent accidental cross-agent edits. Only branch names recognized in
the manual are enforced. Existing codex/work or claude/work branches are not
retroactively blocked. This CI does not substitute GitHub branch protection.
"""
import argparse
import subprocess
import sys


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


def forbidden_files(branch, paths):
    role = role_for_branch(branch)
    if role is None:
        return []
    return [p for p in paths if not any(
        p == prefix or ((prefix.endswith("/") or prefix.endswith("-")) and p.startswith(prefix)) for prefix in OWNED[role]
    )]


def changed_files(base):
    result = subprocess.run(
        ["git", "diff", "--name-only", "-z", f"origin/{base}...HEAD"],
        check=True, capture_output=True,
    )
    return [p.decode("utf8") for p in result.stdout.split(b"\0") if p]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--branch", required=True)
    parser.add_argument("--base", required=True)
    args = parser.parse_args()
    role = role_for_branch(args.branch)
    if role is None:
        print(f"LEGACY_BRANCH_NOT_ENFORCED: {args.branch}. Codex review still required.")
        return 0
    paths = changed_files(args.base)
    bad = forbidden_files(args.branch, paths)
    print(f"AGENT_SCOPE: role={role}, changed={len(paths)}, forbidden={len(bad)}")
    if bad:
        for path in bad:
            print(f"CROSS_OWNER_CHANGE: {path}")
        print("Create a separate PR from the responsible agent or record an approved handoff.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
