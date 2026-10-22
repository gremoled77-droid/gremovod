"""Offline regression tests for the CI contract checker."""
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import yaml

from tools.check_ci_contracts import (
    CONTRACT_WORKFLOW,
    ROOT,
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

    def test_the_offline_workflow_must_run_when_only_it_changes(self):
        """A pull request that edits only studio-offline-ci.yml has to run it, or a
        broken CI change is merged without a single real run of its jobs."""
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / ".github" / "workflows"
            directory.mkdir(parents=True)
            (directory / OFFLINE_WORKFLOW).write_text(GOOD_WORKFLOW, encoding="utf8")
            (directory / CONTRACT_WORKFLOW).write_text(GOOD_WORKFLOW, encoding="utf8")
            problems = check_candidate_workflow(Path(tmp))
            self.assertTrue(any("does not cover '.github/workflows/" in p for p in problems))
            covered = GOOD_WORKFLOW.replace(
                "      - 'backend/**'\n",
                f"      - 'backend/**'\n      - '.github/workflows/{OFFLINE_WORKFLOW}'\n")
            (directory / OFFLINE_WORKFLOW).write_text(covered, encoding="utf8")
            problems = check_candidate_workflow(Path(tmp))
            self.assertFalse(any("does not cover '.github/workflows/" in p for p in problems))

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


# A stand-in for sudo: it never runs apt, it only logs the call and plays the
# scenario chosen by the test. Update calls fail for the first FAIL_UPDATES calls,
# hang when HANG_UPDATE is set, and install exits with INSTALL_EXIT.
FAKE_SUDO = """#!/usr/bin/env bash
echo "$*" >> "$STUB_LOG"
case " $* " in
  *" update "*)
    if [ -n "$HANG_UPDATE" ]; then exec sleep 30; fi
    calls=$(grep -c ' update ' "$STUB_LOG")
    if [ "$calls" -le "${FAIL_UPDATES:-0}" ]; then exit 100; fi
    exit 0 ;;
  *" install "*) exit "${INSTALL_EXIT:-0}" ;;
esac
exit 99
"""


def _ffmpeg_install_step():
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / OFFLINE_WORKFLOW).read_text(encoding="utf8"))
    for step in workflow["jobs"]["backend-media"]["steps"]:
        if "Install FFmpeg" in str(step.get("name", "")):
            return step
    raise AssertionError("backend-media has no 'Install FFmpeg' step")


def _bash():
    bash = shutil.which("bash")
    # On Windows a bare "bash" can be the WSL launcher; only Git Bash is safe here.
    if bash is None or (os.name == "nt" and "system32" in bash.lower()):
        return None
    return bash


class FfmpegInstallStepTests(unittest.TestCase):
    """The FFmpeg install step of backend-media, run with a fake sudo: no real apt."""

    def setUp(self):
        self.bash = _bash()
        if self.bash is None:
            self.skipTest("bash is not available")
        self.step = _ffmpeg_install_step()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)
        stubs = self.dir / "bin"
        stubs.mkdir()
        (stubs / "sudo").write_bytes(FAKE_SUDO.encode("utf8"))
        (stubs / "sudo").chmod(0o755)
        self.log = self.dir / "calls.log"
        self.log.write_text("", encoding="utf8")
        # cd + pwd turns a Windows path into the form Git Bash puts on PATH.
        script = 'PATH="$(cd "$STUB_DIR" && pwd):$PATH"\n' + self.step["run"]
        self.script = self.dir / "step.sh"
        self.script.write_bytes(script.encode("utf8"))

    def run_step(self, **overrides):
        env = dict(os.environ, STUB_DIR=str(self.dir / "bin"), STUB_LOG=str(self.log))
        env.update({k: str(v) for k, v in (self.step.get("env") or {}).items()})
        env["APT_PAUSE"] = "0"
        env.update({k: str(v) for k, v in overrides.items()})
        started = time.monotonic()
        # The same shell flags GitHub uses for a `run:` step.
        result = subprocess.run(
            [self.bash, "--noprofile", "--norc", "-eo", "pipefail", str(self.script)],
            env=env, capture_output=True, timeout=120, check=False)
        output = result.stdout.decode("utf8", "replace") + result.stderr.decode("utf8", "replace")
        calls = self.log.read_text(encoding="utf8").splitlines()
        return result.returncode, output, calls, time.monotonic() - started

    @staticmethod
    def count(calls, word):
        return sum(f" {word} " in f" {c} " for c in calls)

    def test_success_on_the_first_attempt(self):
        code, output, calls, _ = self.run_step()
        self.assertEqual(code, 0, output)
        self.assertEqual((self.count(calls, "update"), self.count(calls, "install")), (1, 1))
        self.assertNotIn("::warning::", output)

    def test_a_transient_failure_is_retried(self):
        code, output, calls, _ = self.run_step(FAIL_UPDATES=1)
        self.assertEqual(code, 0, output)
        self.assertEqual((self.count(calls, "update"), self.count(calls, "install")), (2, 1))
        self.assertIn("::warning::apt attempt 1 of 3", output)

    def test_a_permanent_failure_turns_the_step_red(self):
        code, output, calls, _ = self.run_step(INSTALL_EXIT=100)
        self.assertNotEqual(code, 0)
        self.assertEqual((self.count(calls, "update"), self.count(calls, "install")), (3, 3))
        self.assertIn("::error::FFmpeg could not be installed after 3 attempts", output)

    def test_a_hanging_apt_is_cut_by_the_timeout_and_turns_the_step_red(self):
        code, output, calls, elapsed = self.run_step(HANG_UPDATE=1, APT_UPDATE_TIMEOUT=1)
        self.assertNotEqual(code, 0)
        self.assertEqual((self.count(calls, "update"), self.count(calls, "install")), (3, 0))
        self.assertIn("::error::", output)
        # three cut attempts, not three 30 s hangs
        self.assertLess(elapsed, 30)

    def test_every_attempt_fits_in_the_step_timeout(self):
        """All promised attempts at their worst case have to end before Actions kills
        the step, otherwise the last retry is a promise the step cannot keep."""
        env = self.step["env"]
        attempts = int(env["APT_ATTEMPTS"])
        worst = (attempts * (int(env["APT_UPDATE_TIMEOUT"]) + int(env["APT_INSTALL_TIMEOUT"]))
                 + (attempts - 1) * int(env["APT_PAUSE"]))
        self.assertLessEqual(worst, int(self.step["timeout-minutes"]) * 60)
        self.assertEqual(attempts, 3)


if __name__ == "__main__":
    unittest.main()
