"""Offline regression tests for the CI contract checker."""
import tempfile
import unittest
from pathlib import Path

from tools.check_ci_contracts import (
    CONTRACT_WORKFLOW,
    OFFLINE_WORKFLOW,
    REQUIRED_CONTRACT_JOBS,
    REQUIRED_OFFLINE_JOBS,
    REQUIRED_PATH_FILTERS,
    REQUIRED_SCOPE_GUARD_MARKERS,
    SCOPE_GUARD_WORKFLOW,
    check_candidate_workflow,
    check_claude_hooks_job,
    check_dependency_lock,
    check_scope_guard_workflow,
    check_workflow_file,
    check_workflows,
)

GOOD_WORKFLOW = """
name: Good
on:
  pull_request:
    paths:
      - 'backend/**'
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - run: echo ok
"""


def write_workflow(directory, name, text):
    path = Path(directory) / name
    path.write_text(text, encoding="utf8")
    return path


class WorkflowContractTests(unittest.TestCase):
    def test_repository_workflows_are_valid(self):
        self.assertEqual(check_workflows(), [])

    def test_candidate_workflow_keeps_its_contract(self):
        self.assertEqual(check_candidate_workflow(), [])

    def test_dependency_lock_covers_direct_dependencies(self):
        self.assertEqual(check_dependency_lock(), [])

    def test_the_claude_hooks_tests_have_a_mandatory_check_of_their_own(self):
        """The guards of Claude Code are a security control, so their regression tests
        need a check that exists on every pull request. A check behind a path filter
        stays "skipped" when the pull request changes nothing relevant, and a skipped
        required check is a false green."""
        self.assertEqual(check_claude_hooks_job(), [])

    def test_a_contract_workflow_without_the_hooks_job_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / ".github" / "workflows"
            directory.mkdir(parents=True)
            (directory / CONTRACT_WORKFLOW).write_text(GOOD_WORKFLOW, encoding="utf8")
            problems = check_claude_hooks_job(Path(tmp))
            self.assertTrue(any("claude-hooks" in p for p in problems))

    def test_a_hooks_job_that_does_not_run_the_tests_is_reported(self):
        """A job that exists but runs nothing is a check that can never turn red."""
        text = GOOD_WORKFLOW.replace("  build:\n", "  claude-hooks:\n")
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / ".github" / "workflows"
            directory.mkdir(parents=True)
            (directory / CONTRACT_WORKFLOW).write_text(text, encoding="utf8")
            problems = check_claude_hooks_job(Path(tmp))
            self.assertTrue(any("tests.test_claude_hooks" in p for p in problems))

    def test_good_workflow_has_no_problems(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(check_workflow_file(write_workflow(tmp, "good.yml", GOOD_WORKFLOW)), [])

    def test_yaml_on_key_is_read_as_boolean(self):
        with tempfile.TemporaryDirectory() as tmp:
            # PyYAML resolves the bare key "on" to True; the checker must still find it.
            path = write_workflow(tmp, "bool_on.yml", GOOD_WORKFLOW)
            self.assertEqual(check_workflow_file(path), [])

    def test_missing_permissions_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = GOOD_WORKFLOW.replace("permissions:\n  contents: read\n", "")
            problems = check_workflow_file(write_workflow(tmp, "noperm.yml", text))
            self.assertTrue(any("permissions" in p for p in problems))

    def test_write_all_permissions_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = GOOD_WORKFLOW.replace("permissions:\n  contents: read\n",
                                         "permissions: write-all\n")
            problems = check_workflow_file(write_workflow(tmp, "writeall.yml", text))
            self.assertTrue(any("write-all" in p for p in problems))

    def test_unpinned_action_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = GOOD_WORKFLOW.replace("actions/checkout@v4", "actions/checkout@main")
            problems = check_workflow_file(write_workflow(tmp, "unpinned.yml", text))
            self.assertTrue(any("unpinned" in p for p in problems))

    def test_secret_reference_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = GOOD_WORKFLOW.replace("echo ok", "echo ${{ secrets.MY_TOKEN }}")
            problems = check_workflow_file(write_workflow(tmp, "secret.yml", text))
            self.assertTrue(any("secret" in p for p in problems))

    def test_pull_request_target_head_checkout_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = GOOD_WORKFLOW.replace(
                "  pull_request:\n", "  pull_request_target:\n")
            text = text.replace(
                "      - uses: actions/checkout@v4\n",
                "      - uses: actions/checkout@v4\n        with:\n"
                "          ref: ${{ github.event.pull_request.head.sha }}\n")
            problems = check_workflow_file(write_workflow(tmp, "prt.yml", text))
            self.assertTrue(any("pull_request_target" in p for p in problems))

    def test_job_without_timeout_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = GOOD_WORKFLOW.replace("    timeout-minutes: 5\n", "")
            problems = check_workflow_file(write_workflow(tmp, "notimeout.yml", text))
            self.assertTrue(any("timeout-minutes" in p for p in problems))

    def test_step_without_uses_or_run_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = GOOD_WORKFLOW.replace("      - run: echo ok\n", "      - name: nothing\n")
            problems = check_workflow_file(write_workflow(tmp, "empty_step.yml", text))
            self.assertTrue(any("neither uses nor run" in p for p in problems))

    def test_missing_candidate_workflow_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            problems = check_candidate_workflow(Path(tmp))
            self.assertTrue(any("missing" in p for p in problems))

    def test_candidate_contract_constants_cover_the_ga04_requirements(self):
        for required in ("backend/main.py", "backend/llm_guard.py",
                         "backend/character_voice.py", "backend/spend_ledger.py",
                         "frontend/**"):
            self.assertIn(required, REQUIRED_PATH_FILTERS)
        for required in REQUIRED_OFFLINE_JOBS + REQUIRED_CONTRACT_JOBS:
            self.assertTrue(required)

    def test_job_level_paths_is_rejected(self):
        """`paths` is not a valid job keyword: Actions refuses the whole file and
        the run ends with zero jobs."""
        with tempfile.TemporaryDirectory() as tmp:
            text = GOOD_WORKFLOW.replace(
                "    steps:\n",
                "    paths:\n      - 'backend/**'\n    steps:\n")
            problems = check_workflow_file(write_workflow(tmp, "jobpaths.yml", text))
            self.assertTrue(any("unknown keyword 'paths'" in p for p in problems))

    def test_unknown_job_keyword_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = GOOD_WORKFLOW.replace("    runs-on: ubuntu-latest\n",
                                         "    runs-on: ubuntu-latest\n    bogus-key: 1\n")
            problems = check_workflow_file(write_workflow(tmp, "bogus.yml", text))
            self.assertTrue(any("unknown keyword 'bogus-key'" in p for p in problems))

    def test_unknown_step_keyword_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = GOOD_WORKFLOW.replace("      - run: echo ok\n",
                                         "      - run: echo ok\n        bogus: 1\n")
            problems = check_workflow_file(write_workflow(tmp, "bogusstep.yml", text))
            self.assertTrue(any("unknown keyword 'bogus'" in p for p in problems))

    def test_the_contract_workflow_must_not_carry_a_path_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / ".github" / "workflows"
            directory.mkdir(parents=True)
            offline = GOOD_WORKFLOW.replace("name: Good", f"name: {OFFLINE_WORKFLOW[:-4]}")
            (directory / OFFLINE_WORKFLOW).write_text(offline, encoding="utf8")
            (directory / CONTRACT_WORKFLOW).write_text(
                GOOD_WORKFLOW.replace("  pull_request:\n",
                                      "  pull_request:\n    paths:\n      - 'docs/**'\n"),
                encoding="utf8")
            problems = check_candidate_workflow(Path(tmp))
            self.assertTrue(any("must not carry a path filter" in p for p in problems))

    def test_an_offline_job_must_not_be_continue_on_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / ".github" / "workflows"
            directory.mkdir(parents=True)
            offline = GOOD_WORKFLOW.replace("name: Good", f"name: {OFFLINE_WORKFLOW[:-4]}")
            offline = offline.replace("    timeout-minutes: 5\n",
                                      "    timeout-minutes: 5\n    continue-on-error: true\n")
            (directory / OFFLINE_WORKFLOW).write_text(offline, encoding="utf8")
            (directory / CONTRACT_WORKFLOW).write_text(
                GOOD_WORKFLOW.replace("name: Good", f"name: {CONTRACT_WORKFLOW[:-4]}"),
                encoding="utf8")
            problems = check_candidate_workflow(Path(tmp))
            self.assertTrue(any("continue-on-error" in p for p in problems))


class ScopeGuardContractTests(unittest.TestCase):
    """The scope guard wiring is a security contract, not a style choice."""

    @staticmethod
    def _guard_text(with_markers=True):
        """A workflow that carries the trusted control code protocol."""
        text = GOOD_WORKFLOW
        if with_markers:
            steps = "".join(f"      - run: echo {marker}\n"
                            for marker in REQUIRED_SCOPE_GUARD_MARKERS)
            text = text.replace("      - run: echo ok\n", steps)
        return text

    @staticmethod
    def _write_guard(directory, text):
        path = Path(directory) / ".github" / "workflows"
        path.mkdir(parents=True, exist_ok=True)
        (path / SCOPE_GUARD_WORKFLOW).write_text(text, encoding="utf8")

    def test_repository_scope_guard_keeps_its_contract(self):
        self.assertEqual(check_scope_guard_workflow(), [])

    def test_missing_scope_guard_workflow_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            problems = check_scope_guard_workflow(Path(tmp))
            self.assertTrue(any("missing" in p for p in problems))

    def test_a_guard_that_runs_the_pull_request_validator_is_reported(self):
        """The materialization has to happen outside the working tree of the pull
        request, and what runs has to be the materialized copy."""
        with tempfile.TemporaryDirectory() as tmp:
            text = self._guard_text()
            self._write_guard(tmp, text)
            self.assertEqual(check_scope_guard_workflow(Path(tmp)), [])
            # a guard that runs the validator from the working tree of the pull request
            text = text.replace("scope-guard/tools/check_agent_scope.py",
                                "tools/check_agent_scope.py")
            self._write_guard(tmp, text)
            problems = check_scope_guard_workflow(Path(tmp))
            self.assertTrue(any("trusted control code protocol" in p for p in problems))

    def test_a_guard_without_the_trusted_base_revision_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self._guard_text().replace("github.event.pull_request.base.sha",
                                              "github.sha")
            self._write_guard(tmp, text)
            problems = check_scope_guard_workflow(Path(tmp))
            self.assertTrue(any("trusted control code protocol" in p for p in problems))

    def test_a_guard_that_does_not_use_the_base_revision_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self._guard_text().replace("runner.temp", "workspace")
            self._write_guard(tmp, text)
            problems = check_scope_guard_workflow(Path(tmp))
            self.assertTrue(any("trusted control code protocol" in p for p in problems))

    def test_a_guard_on_pull_request_target_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = self._guard_text().replace("  pull_request:\n", "  pull_request_target:\n")
            self._write_guard(tmp, text)
            problems = check_scope_guard_workflow(Path(tmp))
            self.assertTrue(any("pull_request_target" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
