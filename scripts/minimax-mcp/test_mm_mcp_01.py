"""MM-MCP-01 offline review tests: mock subprocess only, no model, no network.

Covers the review checklist for the MiniMax MCP Bridge: successful JSON
answer, launch failure, non-zero exit code, timeout, cancellation, repeated
request, corrupted JSON, authorization refusal and a Windows path that
contains spaces.

Run:
    python -X utf8 -m unittest discover -s scripts/minimax-mcp \
        -p test_mm_mcp_01.py -q
"""

import json
import subprocess
import tempfile
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from bridge import AUTH_FILES, Bridge, digest, seed_profile

SPACED = "bridge state with spaces"


class MockSubprocessFixture(unittest.TestCase):
    """Drives the bridge against the shipped mock_worker.py subprocess."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "work tree with spaces"
        self.repo.mkdir()
        self.git("init", "-b", "test/mcp")
        (self.repo / "value.py").write_text("value = 1\n", encoding="utf-8")
        self.git("add", "value.py")
        self.git(
            "-c",
            "user.name=Offline",
            "-c",
            "user.email=offline@invalid",
            "commit",
            "-qm",
            "fixture",
        )
        self.sha = self.git("rev-parse", "HEAD")
        self.config = {
            "mode": "mock",
            "worktree": str(self.repo),
            "branch": "test/mcp",
            "pr_number": 72,
            "allowed_files": ["value.py"],
            "state_dir": str(self.root / SPACED / "state"),
            "max_calls": 3,
            "timeout_seconds": 2,
        }
        self.bridges = []

    def git(self, *args):
        return (
            subprocess.check_output(
                ["git", *args], cwd=self.repo, stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )

    def make(self, **changes):
        service = Bridge(self.config | changes)
        self.bridges.append(service)
        return service

    def execute(self, service, task="mock:ok", request_id="one", files=None):
        return service.execute(
            request_id, task, self.sha, ["value.py"] if files is None else files
        )

    def wait(self, service, request_id="one"):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            result = service.result(request_id)
            if result.get("status") not in {"RESERVED", "RUNNING"}:
                return result
            time.sleep(0.02)
        self.fail("mock subprocess did not terminate")

    def tearDown(self):
        for service in reversed(self.bridges):
            if not service.closed:
                service.close()
        self.temp.cleanup()


class OfflineScenarioTests(MockSubprocessFixture):
    def test_successful_json_answer(self):
        service = self.make()
        self.execute(service)
        result = self.wait(service)
        self.assertEqual(result["status"], "SUCCEEDED", result)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["result_sha"], self.sha)
        self.assertEqual(result["head_sha"], self.sha)
        self.assertEqual(result["request_id"], "one")
        self.assertTrue(json.loads(result["stdout"])["mock"])
        self.assertIsNone(result["error"])

    def test_launch_failure_is_recorded(self):
        service = self.make()
        # Patch Child, not subprocess.Popen: the bridge calls git through the
        # same module, so patching Popen would break the preflight reads too.
        with patch("bridge.Child", side_effect=OSError("synthetic launch failure")):
            self.execute(service)
            result = self.wait(service)
        self.assertEqual(result["status"], "FAILED", result)
        self.assertEqual(result["error"], "PROCESS_ERROR", result)
        self.assertIsNone(result["exit_code"])
        self.assertTrue(service.status()["halted"])

    def test_nonzero_exit_code_is_preserved(self):
        service = self.make()
        self.execute(service, task="mock:error")
        result = self.wait(service)
        self.assertEqual(result["exit_code"], 23, result)
        self.assertEqual(result["error"], "CLI_FAILED", result)

    def test_timeout_is_bounded(self):
        service = self.make(timeout_seconds=1)
        self.execute(service, task="mock:timeout")
        result = self.wait(service)
        self.assertEqual(result["error"], "TIMEOUT", result)
        self.assertIsNotNone(result["exit_code"])

    def test_cancellation_is_honoured(self):
        service = self.make(timeout_seconds=30)
        self.execute(service, task="mock:timeout")
        time.sleep(0.3)
        service.cancel("one")
        result = self.wait(service)
        self.assertEqual(result["error"], "CANCELLED", result)

    def test_repeated_request_is_deduplicated(self):
        service = self.make()
        self.execute(service)
        first = self.wait(service)
        again = self.execute(service)
        self.assertEqual(again["status"], first["status"])
        self.assertEqual(again["started_at"], first["started_at"])
        self.assertEqual(service.status()["calls_reserved"], 1)
        conflict = self.execute(service, task="mock:other")
        self.assertEqual(conflict["error"], "REQUEST_ID_CONFLICT")

    def test_corrupted_json_output_halts(self):
        service = self.make()
        self.execute(service, task="mock:invalid")
        result = self.wait(service)
        self.assertEqual(result["error"], "INVALID_OUTPUT", result)
        self.assertTrue(service.status()["halted"])

    def test_authorization_refusal_never_launches(self):
        service = self.make(mode="live")
        with patch("bridge.Child") as child:
            self.assertEqual(self.execute(service)["error"], "OWNER_APPROVAL_REQUIRED")
        child.assert_not_called()
        self.assertEqual(service.status()["calls_reserved"], 0)

    def test_windows_path_with_spaces(self):
        service = self.make()
        self.assertIn(" ", str(service.directory))
        self.assertIn(" ", str(service.worktree))
        self.execute(service)
        result = self.wait(service)
        self.assertEqual(result["status"], "SUCCEEDED", result)
        self.assertEqual(result["exit_code"], 0)

    def test_live_non_succeeded_status_fails_closed(self):
        service = self.make(mode="live")
        node, cli = self.root / "node.exe", self.root / "cli.js"
        node.touch()
        cli.touch()
        cli.with_name("package.json").write_text(
            json.dumps({"name": "@minimax-ai/code", "version": "0.6.12"}),
            encoding="utf-8",
        )
        service.config.update(node=str(node), cli_js=str(cli))
        grant = {
            "request_digest": digest(
                {"task": "mock:ok", "head_sha": self.sha, "files": ["value.py"]}
            ),
            "head_sha": self.sha,
            "pr_number": 72,
            "capability": "lightweight-no-tools",
            "max_calls": 1,
            "subscription_only": True,
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        }
        (service.directory / "owner-approval.json").write_text(
            json.dumps(grant), encoding="utf-8"
        )
        auth = service.directory / "minimax-profile" / "auth" / "global" / "auth.json"
        auth.parent.mkdir(parents=True)
        auth.write_text("{}", encoding="utf-8")
        (auth.parent / "auth-state.json").write_text(
            json.dumps({"status": "authenticated", "region": "en", "buildEnv": "prod"}),
            encoding="utf-8",
        )
        provider = {
            "minimaxModelSource": "token_plan",
            "providers": [{"providerId": "minimax_oauth", "active": True}],
        }
        replies = [
            (None, 0, {"stdout": json.dumps(provider), "stderr": ""}),
            # Exit code 0 but a non-succeeded ExecResult status: must fail closed.
            (None, 0, {"stdout": json.dumps({"status": "timeout"}), "stderr": ""}),
        ]
        with patch.object(service, "capture", side_effect=replies):
            self.execute(service)
            result = self.wait(service)
        self.assertEqual(result["error"], "INVALID_OUTPUT", result)
        self.assertNotIn("result_sha", result)


class RuntimeProfileTests(MockSubprocessFixture):
    """The runtime profile must stay login-only while the CLI writes into it."""

    def owner_profile(self, service, foreign=True):
        profile = service.directory / "minimax-profile"
        auth = profile / "auth" / "prod" / "en" / "mcode-public"
        auth.mkdir(parents=True)
        (auth / "auth.json").write_text("{}", encoding="utf-8")
        (auth / "auth-state.json").write_text(
            json.dumps({"status": "authenticated", "region": "en", "buildEnv": "prod"}),
            encoding="utf-8",
        )
        (auth / "auth.lock").write_text("", encoding="utf-8")
        if foreign:
            (profile / "mcp.json").write_text("{}", encoding="utf-8")
            (profile / "config.yaml").write_text(
                "custom_provider:\n  kie:\n    apiKey: fake-key\n", encoding="utf-8"
            )
            (profile / "integrations" / "lark").mkdir(parents=True)
            (profile / "plugins" / "custom").mkdir(parents=True)
        return profile

    def test_foreign_owner_state_is_not_copied(self):
        service = self.make(mode="live")
        owner = self.owner_profile(service)
        target = service.directory / "runtime-one"
        seed_profile(owner, target)
        copied = sorted(
            item.relative_to(target).as_posix() for item in target.rglob("*")
        )
        self.assertEqual(
            copied,
            [
                "auth",
                "auth/prod",
                "auth/prod/en",
                "auth/prod/en/mcode-public",
                "auth/prod/en/mcode-public/auth-state.json",
                "auth/prod/en/mcode-public/auth.json",
            ],
        )
        self.assertFalse((target / "mcp.json").exists())
        self.assertFalse((target / "config.yaml").exists())
        self.assertFalse((target / "integrations").exists())
        self.assertFalse((target / "plugins").exists())

    def test_cli_bootstrap_does_not_break_the_second_grant_check(self):
        service = self.make(mode="live")
        self.owner_profile(service)
        runtime = service.directory / "runtime-one"
        runtime.mkdir(parents=True)
        (runtime / "config.yaml").write_text("logLevel: info\n", encoding="utf-8")
        (runtime / "v2" / "sqlite").mkdir(parents=True)
        (runtime / ".builtin-skills" / "docx").mkdir(parents=True)
        (runtime / "auth" / "prod" / "en" / "mcode-public").mkdir(parents=True)
        (runtime / "auth" / "prod" / "en" / "mcode-public" / "auth.json").write_text(
            "{}", encoding="utf-8"
        )
        # The runtime profile is bridge-created: the CLI may add its own trees,
        # the grant check must still pass and must not rescan the profile.
        grant = {
            "request_digest": digest(
                {"task": "mock:ok", "head_sha": self.sha, "files": ["value.py"]}
            ),
            "head_sha": self.sha,
            "pr_number": 72,
            "capability": "lightweight-no-tools",
            "max_calls": 1,
            "subscription_only": True,
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        }
        (service.directory / "owner-approval.json").write_text(
            json.dumps(grant), encoding="utf-8"
        )
        service.live_grant(grant["request_digest"], self.sha)

    def test_seed_profile_requires_auth(self):
        service = self.make(mode="live")
        profile = service.directory / "minimax-profile"
        profile.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "ISOLATED_AUTH_MISSING"):
            seed_profile(profile, service.directory / "runtime-x")

    def test_seed_profile_requires_an_authenticated_state(self):
        service = self.make(mode="live")
        owner = self.owner_profile(service, foreign=False)
        state = owner / "auth" / "prod" / "en" / "mcode-public" / "auth-state.json"
        state.write_text(json.dumps({"status": "expired"}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SUBSCRIPTION_AUTH_UNVERIFIED"):
            seed_profile(owner, service.directory / "runtime-x")

    def test_seed_profile_requires_a_state_file(self):
        service = self.make(mode="live")
        owner = self.owner_profile(service, foreign=False)
        (owner / "auth" / "prod" / "en" / "mcode-public" / "auth-state.json").unlink()
        with self.assertRaisesRegex(ValueError, "SUBSCRIPTION_AUTH_UNVERIFIED"):
            seed_profile(owner, service.directory / "runtime-x")

    def test_seed_profile_rejects_unknown_auth_files(self):
        service = self.make(mode="live")
        owner = self.owner_profile(service, foreign=False)
        (owner / "auth" / "prod" / "en" / "mcode-public" / "extra.json").write_text(
            "{}", encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "PROFILE_NOT_LOGIN_ONLY"):
            seed_profile(owner, service.directory / "runtime-x")

    def test_auth_files_allowlist(self):
        self.assertIn("auth.json", AUTH_FILES)
        self.assertIn("auth-state.json", AUTH_FILES)
        self.assertNotIn("auth.lock", AUTH_FILES)


class DiagnosticsTests(MockSubprocessFixture):
    def test_diagnostics_are_bounded_and_redacted(self):
        service = self.make()
        self.execute(service, task="mock:error")
        result = self.wait(service)
        self.assertIn("[REDACTED]", result["stderr"])
        self.assertNotIn("not-a-real-token", result["stderr"])
        state = (service.directory / "state.json").read_text(encoding="utf-8")
        self.assertNotIn("not-a-real-token", state)
        events = (service.directory / "events.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("synthetic auth", events)
        self.assertIn('"head_sha"', events)
        self.assertLessEqual(len(result["stdout"]), 16_384)

    def test_events_record_the_exact_sha(self):
        service = self.make()
        self.execute(service)
        self.wait(service)
        events = (service.directory / "events.jsonl").read_text(encoding="utf-8")
        record = json.loads(events.strip().splitlines()[-1])
        self.assertEqual(record["head_sha"], self.sha)
        self.assertEqual(record["request_id"], "one")
        self.assertEqual(record["exit_code"], 0)
        self.assertIn("status", record)

    def test_output_limit_is_enforced(self):
        service = self.make()
        self.execute(service, task="mock:overflow")
        result = self.wait(service)
        self.assertEqual(result["error"], "OUTPUT_LIMIT", result)
        self.assertLessEqual(len(result["stdout"]), 16_384)


if __name__ == "__main__":
    unittest.main()
