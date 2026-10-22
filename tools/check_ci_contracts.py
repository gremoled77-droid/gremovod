"""Validate the CI contracts of this repository.

Offline. Never contacts GitHub, n8n, a paid provider or the running Studio.
Checks four things:

* every file in ``.github/workflows`` is a structurally valid Actions workflow, and
  uses only keywords the Actions schema actually accepts;
* the GA-04 workflows keep their required path filters and jobs;
* the pinned dependency lock still covers every direct dependency.

The keyword check matters: ``jobs.<id>.paths`` is accepted by YAML but rejected by
Actions, and such a file fails at run time with "workflow file issue" instead of
running any job at all.

Requires PyYAML. The CI job installs it explicitly; when it is missing this tool
fails closed instead of silently skipping, because a contract check that cannot run
is the "false skip" risk GA-04 is about.
"""
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only without PyYAML
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
REQUIREMENTS = ROOT / "backend" / "requirements.txt"
REQUIREMENTS_LOCK = ROOT / "backend" / "requirements.lock.txt"

# The heavy checks. They carry a workflow level path filter, so they only run when
# the change can actually affect them.
OFFLINE_WORKFLOW = "studio-offline-ci.yml"
# The contract checks. They carry no path filter and therefore produce a check on
# every pull request, which keeps the required-check story free of the path filter
# trap.
CONTRACT_WORKFLOW = "studio-ci-contract.yml"

# The scope guard. Its wiring is a security contract: the code that judges a pull
# request has to be the copy that lives in the base revision, otherwise a pull
# request can rewrite the checker that judges it.
SCOPE_GUARD_WORKFLOW = "agent-scope-guard.yml"

# Markers the scope guard workflow has to contain. They are not a style wish list:
# each of them is what keeps the verdict out of the pull request's hands.
REQUIRED_SCOPE_GUARD_MARKERS = (
    # the base revision of the pull request is where the control code comes from
    "github.event.pull_request.base.sha",
    # the control code is materialized outside the working tree of the pull request
    "runner.temp",
    # and what runs is the materialized copy, not the one in the pull request
    "scope-guard/tools/check_agent_scope.py",
)

# Paths that must trigger the offline workflow: a change to any of them has to run
# the backend suite or the frontend checks.
REQUIRED_PATH_FILTERS = (
    "backend/main.py",
    "backend/llm_guard.py",
    "backend/character_voice.py",
    "backend/spend_ledger.py",
    "frontend/**",
)

REQUIRED_OFFLINE_JOBS = (
    "backend-unit",
    "backend-media",
    "frontend-unit",
    "frontend-typecheck-build",
)
REQUIRED_CONTRACT_JOBS = (
    "ci-contract",
    "secret-scan",
)

# The Claude Code PreToolUse guards are a security control, so their regression tests
# need a check that exists on every pull request. A check behind a path filter stays
# "skipped" when the pull request changes nothing relevant, and a skipped required
# check is a false green. The job therefore has to exist in the contract workflow and
# has to actually run the hooks tests.
CLAUDE_HOOKS_JOB = "claude-hooks"
CLAUDE_HOOKS_TESTS = "tests.test_claude_hooks"

# Keywords the Actions schema accepts. A key outside these sets makes the whole
# workflow file invalid, and GitHub reports it as a run with zero jobs.
ALLOWED_WORKFLOW_KEYS = {
    "name", "run-name", "on", "permissions", "env", "defaults", "concurrency", "jobs",
}
ALLOWED_JOB_KEYS = {
    "name", "permissions", "needs", "if", "runs-on", "environment", "concurrency",
    "outputs", "env", "defaults", "steps", "timeout-minutes", "strategy",
    "continue-on-error", "container", "services", "uses", "with", "secrets",
}
ALLOWED_STEP_KEYS = {
    "id", "if", "name", "uses", "run", "with", "env", "continue-on-error",
    "timeout-minutes", "working-directory", "shell",
}

# A `uses:` reference must be pinned to a release tag or a commit SHA, never to a
# moving branch. Tags look like v4, v4.1.0 or 1.2.3; SHAs are 40 hex characters.
PINNED_REF = re.compile(r"^(?:v?[0-9][0-9A-Za-z._-]*|[0-9a-f]{40})$")
SECRET_REFERENCE = re.compile(r"\$\{\{[^}]*\bsecrets\.[A-Za-z_][A-Za-z0-9_]*")
PR_HEAD_REF = re.compile(r"pull_request\.head")


def _triggers(workflow):
    """Return the trigger mapping of a workflow.

    YAML 1.1 resolves the bare key ``on`` to the boolean ``True``, so both spellings
    have to be looked up.
    """
    for key in ("on", True):
        if key in workflow:
            return workflow[key]
    return None


def _uses_ref(step):
    uses = step.get("uses")
    if not isinstance(uses, str):
        return None
    _, _, ref = uses.partition("@")
    return ref


def check_workflow_file(path):
    """Return a list of problems found in one workflow file."""
    problems = []
    try:
        text = path.read_text(encoding="utf8")
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{path.name}: cannot read as UTF-8 ({exc})"]
    if SECRET_REFERENCE.search(text):
        problems.append(f"{path.name}: references a repository secret; GA-04 forbids secrets in CI")
    try:
        workflow = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return problems + [f"{path.name}: not valid YAML ({exc})"]
    if not isinstance(workflow, dict):
        return problems + [f"{path.name}: root is not a mapping"]
    for key in workflow:
        if key not in ALLOWED_WORKFLOW_KEYS and key is not True:
            problems.append(f"{path.name}: unknown workflow keyword '{key}'")
    triggers = _triggers(workflow)
    if triggers is None:
        problems.append(f"{path.name}: no 'on:' trigger")
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict) or not jobs:
        return problems + [f"{path.name}: no jobs"]
    permissions = workflow.get("permissions")
    if permissions is None:
        problems.append(f"{path.name}: no top-level 'permissions'")
    elif permissions == "write-all" or (
        isinstance(permissions, dict) and "write-all" in permissions
    ):
        problems.append(f"{path.name}: permissions request write-all")
    has_target_trigger = False
    if isinstance(triggers, dict):
        has_target_trigger = "pull_request_target" in triggers
    for job_name, job in jobs.items():
        if not isinstance(job, dict):
            problems.append(f"{path.name}: job '{job_name}' is not a mapping")
            continue
        for key in job:
            if key not in ALLOWED_JOB_KEYS:
                problems.append(
                    f"{path.name}: job '{job_name}' uses unknown keyword '{key}'")
        if not job.get("runs-on"):
            problems.append(f"{path.name}: job '{job_name}' has no runs-on")
        if "timeout-minutes" not in job:
            problems.append(f"{path.name}: job '{job_name}' has no timeout-minutes")
        steps = job.get("steps")
        if not isinstance(steps, list) or not steps:
            problems.append(f"{path.name}: job '{job_name}' has no steps")
            continue
        for step in steps:
            if not isinstance(step, dict):
                problems.append(f"{path.name}: job '{job_name}' has a malformed step")
                continue
            for key in step:
                if key not in ALLOWED_STEP_KEYS:
                    problems.append(
                        f"{path.name}: job '{job_name}' has a step with unknown keyword '{key}'")
            if not step.get("uses") and not step.get("run"):
                problems.append(f"{path.name}: job '{job_name}' has a step with neither uses nor run")
            ref = _uses_ref(step)
            if ref and not PINNED_REF.match(ref):
                problems.append(
                    f"{path.name}: job '{job_name}' uses an unpinned action ref '{ref}'")
            if has_target_trigger and str(step.get("uses", "")).startswith("actions/checkout"):
                with_block = step.get("with") or {}
                if isinstance(with_block, dict) and PR_HEAD_REF.search(str(with_block.get("ref", ""))):
                    problems.append(
                        f"{path.name}: job '{job_name}' checks out the pull request head "
                        f"under pull_request_target")
    return problems


def check_workflows(root=ROOT):
    """Return problems across every workflow file."""
    problems = []
    directory = root / ".github" / "workflows"
    if not directory.is_dir():
        return ["no .github/workflows directory"]
    files = sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))
    if not files:
        return ["no workflow files found"]
    for path in files:
        problems.extend(check_workflow_file(path))
    return problems


def _event_path_filters(workflow):
    """Collect the path filters declared by the events of a workflow."""
    filters = set()
    triggers = _triggers(workflow)
    if not isinstance(triggers, dict):
        return filters
    for event in triggers.values():
        if not isinstance(event, dict):
            continue
        for key in ("paths", "paths-ignore"):
            value = event.get(key)
            if isinstance(value, list):
                filters.update(str(item) for item in value)
    return filters


def _covers(filter_pattern, path):
    """Return True when a GitHub path filter matches a repository path."""
    if filter_pattern == path:
        return True
    if filter_pattern.endswith("/**"):
        return path.startswith(filter_pattern[:-2])
    if filter_pattern.endswith("/"):
        return path.startswith(filter_pattern)
    return False


def _read_workflow(root, name):
    path = root / ".github" / "workflows" / name
    if not path.is_file():
        return None, [f"{name}: missing"]
    workflow = yaml.safe_load(path.read_text(encoding="utf8"))
    if not isinstance(workflow, dict):
        return None, [f"{name}: root is not a mapping"]
    return workflow, []


def check_candidate_workflow(root=ROOT):
    """Return problems with the GA-04 workflow contracts."""
    problems = []
    offline, issues = _read_workflow(root, OFFLINE_WORKFLOW)
    problems.extend(issues)
    if offline is not None:
        jobs = offline.get("jobs") or {}
        for job_name in REQUIRED_OFFLINE_JOBS:
            if job_name not in jobs:
                problems.append(f"{OFFLINE_WORKFLOW}: missing job '{job_name}'")
        for job_name, job in jobs.items():
            if isinstance(job, dict) and job.get("continue-on-error"):
                problems.append(
                    f"{OFFLINE_WORKFLOW}: job '{job_name}' is continue-on-error; "
                    f"a broken test would not turn the check red")
        # A pull request that only edits this workflow must still run it, otherwise a
        # change to the CI itself is merged without one real run of the changed jobs.
        own_path = f".github/workflows/{OFFLINE_WORKFLOW}"
        pull_request = (_triggers(offline) or {}).get("pull_request")
        pr_paths = pull_request.get("paths") if isinstance(pull_request, dict) else None
        if isinstance(pr_paths, list) and not any(_covers(str(f), own_path) for f in pr_paths):
            problems.append(
                f"{OFFLINE_WORKFLOW}: the pull_request path filter does not cover "
                f"'{own_path}'; a change to the workflow would run none of its jobs")
        filters = _event_path_filters(offline)
        for required in REQUIRED_PATH_FILTERS:
            covering = sorted(f for f in filters if _covers(f, required))
            if not covering:
                problems.append(
                    f"{OFFLINE_WORKFLOW}: no path filter covers '{required}'")
    contract, issues = _read_workflow(root, CONTRACT_WORKFLOW)
    problems.extend(issues)
    if contract is not None:
        jobs = contract.get("jobs") or {}
        for job_name in REQUIRED_CONTRACT_JOBS:
            if job_name not in jobs:
                problems.append(f"{CONTRACT_WORKFLOW}: missing job '{job_name}'")
        filters = _event_path_filters(contract)
        if filters:
            problems.append(
                f"{CONTRACT_WORKFLOW}: must not carry a path filter, otherwise a "
                f"pull request that changes nothing relevant gets no check at all")
    return problems


def check_claude_hooks_job(root=ROOT):
    """Return problems with the Claude hooks test job of the contract workflow.

    The job has to live in the workflow without a path filter, so it produces a check
    on every pull request, and it has to run the hooks tests: a job that exists but
    runs nothing is a check that can never turn red.
    """
    problems = []
    workflow, issues = _read_workflow(root, CONTRACT_WORKFLOW)
    problems.extend(issues)
    if workflow is None:
        return problems
    jobs = workflow.get("jobs") or {}
    job = jobs.get(CLAUDE_HOOKS_JOB)
    if not isinstance(job, dict):
        problems.append(
            f"{CONTRACT_WORKFLOW}: missing job '{CLAUDE_HOOKS_JOB}'; the Claude Code "
            f"guard tests need a check of their own to stay mandatory")
        return problems
    steps = job.get("steps") or []
    commands = "\n".join(
        str(step.get("run") or "") for step in steps if isinstance(step, dict))
    if CLAUDE_HOOKS_TESTS not in commands:
        problems.append(
            f"{CONTRACT_WORKFLOW}: job '{CLAUDE_HOOKS_JOB}' does not run "
            f"'{CLAUDE_HOOKS_TESTS}'")
    return problems


def _requirement_names(text):
    names = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        name = re.split(r"[<>=!~\[\s;]", line, maxsplit=1)[0].strip()
        if name:
            names.append(name.lower())
    return names


def check_dependency_lock(root=ROOT):
    """Return problems when the pinned lock does not cover every direct dependency."""
    problems = []
    if not REQUIREMENTS.is_file() or not REQUIREMENTS_LOCK.is_file():
        return ["backend/requirements.txt or backend/requirements.lock.txt is missing"]
    direct = _requirement_names(REQUIREMENTS.read_text(encoding="utf8"))
    locked = set(_requirement_names(REQUIREMENTS_LOCK.read_text(encoding="utf8")))
    for name in direct:
        if name not in locked:
            problems.append(f"requirements.lock.txt does not pin '{name}'")
    return problems


def check_scope_guard_workflow(root=ROOT):
    """Return problems with the wiring of the scope guard.

    The guard is the only thing that stops a task branch from touching foreign
    files, so its own wiring is a contract: the validator that judges a pull
    request has to be the copy from the base revision.
    """
    problems = []
    path = root / ".github" / "workflows" / SCOPE_GUARD_WORKFLOW
    if not path.is_file():
        return [f"{SCOPE_GUARD_WORKFLOW}: missing"]
    text = path.read_text(encoding="utf8")
    try:
        workflow = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [f"{SCOPE_GUARD_WORKFLOW}: not valid YAML ({exc})"]
    triggers = _triggers(workflow)
    if not isinstance(triggers, dict) or "pull_request" not in triggers:
        problems.append(
            f"{SCOPE_GUARD_WORKFLOW}: must trigger on pull_request; it is the only "
            f"check that keeps a task branch inside its scope")
    if "pull_request_target" in triggers:
        problems.append(
            f"{SCOPE_GUARD_WORKFLOW}: must not use pull_request_target; that trigger "
            f"takes the workflow from the default branch, which does not carry the "
            f"guard, so the check would silently stop running")
    for marker in REQUIRED_SCOPE_GUARD_MARKERS:
        if marker not in text:
            problems.append(
                f"{SCOPE_GUARD_WORKFLOW}: the trusted control code protocol is missing "
                f"'{marker}'; the guard has to run the validator of the base revision")
    return problems


def check_all(root=ROOT):
    """Return every contract problem found."""
    problems = []
    problems.extend(check_workflows(root))
    problems.extend(check_candidate_workflow(root))
    problems.extend(check_scope_guard_workflow(root))
    problems.extend(check_claude_hooks_job(root))
    problems.extend(check_dependency_lock(root))
    return problems


def main():
    if yaml is None:
        print("CI_CONTRACT_ERROR: PyYAML is not installed; install 'pyyaml==6.0.3' to run "
              "the workflow contract check.", file=sys.stderr)
        return 2
    problems = check_all()
    if problems:
        print("CI_CONTRACT: FAILED")
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print("CI_CONTRACT: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
