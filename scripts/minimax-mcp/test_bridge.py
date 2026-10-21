import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import jsonschema
from bridge import Bridge, Child, checked_path, digest, isolated_environment
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
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
            "pr_number": 70,
            "allowed_files": ["value.py"],
            "state_dir": str(self.root / "state"),
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
        config = self.config | changes
        service = Bridge(config)
        self.bridges.append(service)
        return service

    def execute(self, service, task="mock:ok", request_id="one"):
        return service.execute(request_id, task, self.sha, ["value.py"])

    def wait(self, service, request_id="one"):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            result = service.result(request_id)
            if result.get("status") not in {"RESERVED", "RUNNING"}:
                return result
            time.sleep(0.02)
        self.fail("mock did not terminate")

    def tearDown(self):
        for service in reversed(self.bridges):
            if not service.closed:
                service.close()
        self.temp.cleanup()


class BridgeTests(Fixture):
    def test_state_write_failure_halts_before_launch(self):
        service = self.make()
        with (
            patch("bridge.os.replace", side_effect=OSError("synthetic disk failure")),
            patch("bridge.Child") as child,
            self.assertRaises(OSError),
        ):
            self.execute(service)
        child.assert_not_called()
        self.assertTrue(service.status()["halted"])

    def test_journal_failure_persists_halt_before_launch(self):
        service = self.make()
        with (
            patch(
                "bridge.open",
                side_effect=OSError("synthetic journal failure"),
                create=True,
            ),
            patch("bridge.Child") as child,
            self.assertRaises(OSError),
        ):
            self.execute(service)
        child.assert_not_called()
        self.assertTrue(
            json.loads((service.directory / "state.json").read_text())["halted"]
        )

    @unittest.skipUnless(os.name == "nt", "Windows Job Object")
    def test_job_assignment_failure_leaves_no_suspended_child(self):
        original = subprocess.Popen
        started = []

        def spawn(*args, **kwargs):
            process = original(*args, **kwargs)
            started.append(process)
            return process

        with (
            patch("bridge.subprocess.Popen", side_effect=spawn),
            patch(
                "win32job.AssignProcessToJobObject",
                side_effect=OSError("synthetic assignment failure"),
            ),
            self.assertRaises(OSError),
        ):
            Child(
                [sys.executable, "-I", str(HERE / "mock_worker.py")],
                self.repo,
                isolated_environment(self.root / "child", self.root / "profile"),
            )
        self.assertEqual(len(started), 1)
        self.assertIsNotNone(started[0].poll())
        self.assertTrue(started[0].stdin.closed)

    def test_child_creation(self):
        child = Child(
            [sys.executable, "-I", str(HERE / "mock_worker.py")],
            self.repo,
            isolated_environment(self.root / "child", self.root / "profile"),
        )
        try:
            output, _ = child.process.communicate(
                json.dumps(
                    {"task": "mock:ok", "head_sha": self.sha, "files": {}}
                ).encode(),
                timeout=5,
            )
            self.assertTrue(json.loads(output)["mock"])
        finally:
            if child.process.poll() is None:
                child.kill()
            child.close()

    def test_default_disabled_never_launches(self):
        service = self.make(mode="disabled")
        with patch(
            "bridge.subprocess.Popen", side_effect=AssertionError("must not spawn")
        ):
            self.assertEqual(self.execute(service)["error"], "MODELS_DISABLED")
            self.assertEqual(service.status()["calls_reserved"], 0)

    def test_mock_result_sha_exit_and_persistence(self):
        service = self.make()
        self.execute(service)
        result = self.wait(service)
        self.assertEqual(result["status"], "SUCCEEDED", result)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["result_sha"], self.sha)
        self.assertTrue(json.loads(result["stdout"])["mock"])
        service.close()
        restarted = self.make()
        self.assertEqual(restarted.result("one"), result)
        self.assertEqual(restarted.status()["calls_reserved"], 1)

    def test_deduplication_and_conflicting_id(self):
        service = self.make()
        self.execute(service)
        self.wait(service)
        self.assertEqual(self.execute(service)["status"], "SUCCEEDED")
        self.assertEqual(
            self.execute(service, task="different")["error"], "REQUEST_ID_CONFLICT"
        )
        self.assertEqual(service.status()["calls_reserved"], 1)

    def test_busy_and_cancel(self):
        service = self.make()
        self.execute(service, task="mock:timeout")
        self.assertEqual(self.execute(service, request_id="two")["error"], "BUSY")
        service.cancel("one")
        self.assertEqual(self.wait(service)["error"], "CANCELLED")
        self.assertEqual(
            self.execute(service, request_id="two")["error"], "BRIDGE_HALTED"
        )

    def test_timeout(self):
        service = self.make(timeout_seconds=1)
        self.execute(service, task="mock:timeout")
        result = self.wait(service)
        self.assertEqual(result["error"], "TIMEOUT", result)
        self.assertIsNotNone(result["exit_code"])

    @unittest.skipUnless(os.name == "nt", "Windows Job Object")
    def test_timeout_terminates_child_tree(self):
        import pywintypes
        import win32api
        import win32process

        service = self.make(timeout_seconds=1)
        self.execute(service, task="mock:tree")
        result = self.wait(service)
        self.assertEqual(result["error"], "TIMEOUT", result)
        pid = json.loads(result["stdout"])["child_pid"]
        try:
            handle = win32api.OpenProcess(0x1000, False, pid)
        except pywintypes.error as error:
            self.assertEqual(error.winerror, 87)  # Already removed from process table.
        else:
            try:
                self.assertNotEqual(win32process.GetExitCodeProcess(handle), 259)
            finally:
                handle.Close()

    def test_exact_exit_and_redacted_stderr(self):
        service = self.make()
        self.execute(service, task="mock:error")
        result = self.wait(service)
        self.assertEqual(result["exit_code"], 23, result)
        self.assertEqual(result["error"], "CLI_FAILED")
        self.assertIn("[REDACTED]", result["stderr"])
        self.assertNotIn(
            "not-a-real-token", (service.directory / "state.json").read_text()
        )
        self.assertNotIn(
            "synthetic auth", (service.directory / "events.jsonl").read_text()
        )

    def test_invalid_json_halts(self):
        service = self.make()
        self.execute(service, task="mock:invalid")
        self.assertEqual(self.wait(service)["error"], "INVALID_OUTPUT")
        self.assertTrue(service.status()["halted"])

    def test_output_limit(self):
        service = self.make()
        self.execute(service, task="mock:overflow")
        result = self.wait(service)
        self.assertEqual(result["error"], "OUTPUT_LIMIT", result)
        self.assertLessEqual(len(result["stdout"]), 16_384)

    def test_environment_and_empty_workspace(self):
        service = self.make()
        dirty = {
            "OPENAI_API_KEY": "fake-key",
            "MINIMAX_API_KEY": "fake-key",
            "NODE_OPTIONS": "--bad",
            "PYTHONPATH": "outside",
            "CODEX_HOME": "outside",
            "HTTPS_PROXY": "outside",
            "MINIMAX_DATA_DIR": "foreign",
            "MAVIS_DATA_DIR": "foreign",
        }
        with patch.dict(os.environ, dirty):
            self.execute(service, task="mock:environment")
            result = self.wait(service)
        self.assertEqual(result["status"], "SUCCEEDED", result)

    def test_call_limit_persists(self):
        service = self.make(max_calls=1)
        self.execute(service)
        self.wait(service)
        service.close()
        restarted = self.make(max_calls=1)
        self.assertEqual(
            self.execute(restarted, request_id="two")["error"], "CALL_LIMIT"
        )

    def test_stop_file(self):
        service = self.make()
        (service.directory / "STOP").touch()
        self.assertEqual(self.execute(service)["error"], "BRIDGE_HALTED")

    def test_stop_cancels_active(self):
        service = self.make()
        self.execute(service, task="mock:timeout")
        time.sleep(0.1)
        (service.directory / "STOP").touch()
        self.assertEqual(self.wait(service)["error"], "CANCELLED")

    def test_single_server_lock(self):
        self.make()
        with self.assertRaisesRegex(ValueError, "BRIDGE_ALREADY_RUNNING"):
            self.make()

    def test_unknown_after_restart_keeps_reservation(self):
        service = self.make()
        service.state["calls"] = 1
        service.state["jobs"]["one"] = {"status": "RUNNING"}
        service.save()
        service.close()
        restarted = self.make()
        self.assertEqual(restarted.result("one")["status"], "UNKNOWN")
        self.assertTrue(restarted.status()["halted"])
        self.assertEqual(restarted.status()["calls_reserved"], 1)

    def test_new_head_before_launch(self):
        service = self.make()
        self.assertEqual(
            service.execute("one", "mock:ok", "0" * 40, ["value.py"])["error"],
            "HEAD_CHANGED",
        )

    def test_head_changes_during_run(self):
        service = self.make()
        # Mock sleeps long enough to change HEAD without racing subprocess startup.
        self.execute(service, task="mock:pause")
        self.git(
            "-c",
            "user.name=Offline",
            "-c",
            "user.email=offline@invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "head changed",
        )
        self.assertEqual(self.wait(service)["error"], "HEAD_CHANGED")

    def test_dirty_or_foreign_file_denied(self):
        service = self.make()
        for name in ("../value.py", "C:/outside/value.py", ".env", "elsewhere.py"):
            self.assertEqual(
                service.execute("one", "mock:ok", self.sha, [name])["error"],
                "FILE_NOT_ALLOWED",
            )
        (self.repo / "value.py").write_text("changed\n")
        self.assertEqual(self.execute(service)["error"], "FILE_DIRTY")

    def test_secret_content_denied(self):
        (self.repo / "value.py").write_text("api_key = 'fake-private-credential'\n")
        self.git("add", "value.py")
        self.git(
            "-c",
            "user.name=Offline",
            "-c",
            "user.email=offline@invalid",
            "commit",
            "-qm",
            "synthetic secret",
        )
        self.sha = self.git("rev-parse", "HEAD")
        self.assertEqual(self.execute(self.make())["error"], "SECRET_INPUT_DENIED")

    def test_windows_junction_rejected(self):
        if os.name != "nt":
            self.skipTest("Windows junction")
        target, junction = self.root / "target", self.root / "junction"
        target.mkdir()
        # Fixed test paths, no deletion through cmd; TemporaryDirectory unlinks junction safely.
        subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(junction), str(target)],
            check=True,
            capture_output=True,
        )
        with self.assertRaisesRegex(ValueError, "PATH_ALIAS_DENIED"):
            checked_path(junction / "new-state")
        self.assertTrue(target.exists())

    def test_hardlink_rejected(self):
        link = self.repo / "linked.py"
        os.link(self.repo / "value.py", link)
        with self.assertRaisesRegex(ValueError, "HARDLINK_DENIED"):
            checked_path(link)

    def live_request(self):
        service = self.make(
            mode="live",
            node=str(self.root / "missing-node"),
            cli_js=str(self.root / "missing-cli.js"),
        )
        grant = {
            "request_digest": digest(
                {"task": "mock:ok", "head_sha": self.sha, "files": ["value.py"]}
            ),
            "head_sha": self.sha,
            "pr_number": 70,
            "capability": "lightweight-no-tools",
            "max_calls": 1,
            "subscription_only": True,
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        }
        return service, grant

    def test_missing_owner_approval_no_cli(self):
        service, _ = self.live_request()
        # Git reads are expected; no model launch or authorization query is possible.
        with patch.object(
            service, "command", side_effect=AssertionError("must not construct launch")
        ):
            self.assertEqual(self.execute(service)["error"], "OWNER_APPROVAL_REQUIRED")
        self.assertEqual(service.status()["calls_reserved"], 0)

    def test_expired_owner_approval(self):
        service, grant = self.live_request()
        grant["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        (service.directory / "owner-approval.json").write_text(json.dumps(grant))
        self.assertEqual(self.execute(service)["error"], "OWNER_APPROVAL_INVALID")

    def test_missing_cli(self):
        service, grant = self.live_request()
        (service.directory / "owner-approval.json").write_text(json.dumps(grant))
        self.assertEqual(self.execute(service)["error"], "CLI_MISSING")

    def test_missing_auth_and_foreign_profile(self):
        service, grant = self.live_request()
        node, cli = self.root / "node.exe", self.root / "cli.js"
        node.touch()
        cli.touch()
        cli.with_name("package.json").write_text(
            json.dumps({"name": "@minimax-ai/code", "version": "0.6.12"})
        )
        service.config.update(node=str(node), cli_js=str(cli))
        (service.directory / "owner-approval.json").write_text(json.dumps(grant))
        self.assertEqual(self.execute(service)["error"], "ISOLATED_AUTH_MISSING")
        profile = service.directory / "minimax-profile"
        (profile / "auth" / "global").mkdir(parents=True)
        (profile / "auth" / "global" / "auth.json").write_text("{}")
        (profile / "auth" / "global" / "auth-state.json").write_text(
            json.dumps({"status": "authenticated", "region": "en", "buildEnv": "prod"})
        )
        (profile / "v2" / "plugin-cache").mkdir(parents=True)
        # Foreign capability state in the owner profile is never handed to the
        # CLI: the runtime profile holds the auth subtree and nothing else.
        record = self.execute(service)
        self.assertNotIn("error", record)
        self.wait(service)
        runtime = service.directory / "runtime-one"
        self.assertEqual(
            sorted(item.relative_to(runtime).as_posix() for item in runtime.rglob("*")),
            [
                "auth",
                "auth/global",
                "auth/global/auth-state.json",
                "auth/global/auth.json",
            ],
        )

    def prepared_live(self):
        service, grant = self.live_request()
        node, cli = self.root / "node.exe", self.root / "cli.js"
        node.touch()
        cli.touch()
        cli.with_name("package.json").write_text(
            json.dumps({"name": "@minimax-ai/code", "version": "0.6.12"})
        )
        service.config.update(node=str(node), cli_js=str(cli))
        (service.directory / "owner-approval.json").write_text(json.dumps(grant))
        auth = service.directory / "minimax-profile/auth/global/auth.json"
        auth.parent.mkdir(parents=True)
        auth.write_text("{}")
        (auth.parent / "auth-state.json").write_text(
            json.dumps({"status": "authenticated", "region": "en", "buildEnv": "prod"})
        )
        return service

    def test_live_command_contract_with_mocked_transport(self):
        service = self.prepared_live()
        provider = {
            "minimaxModelSource": "token_plan",
            "providers": [{"providerId": "minimax_oauth", "active": True}],
        }
        replies = [
            (None, 0, {"stdout": json.dumps(provider), "stderr": ""}),
            # The real ExecResult carries a status; only "succeeded" is accepted.
            (
                None,
                0,
                {
                    "stdout": json.dumps({"status": "succeeded", "synthetic": True}),
                    "stderr": "",
                },
            ),
        ]
        with patch.object(service, "capture", side_effect=replies) as transport:
            self.execute(service)
            result = self.wait(service)
        self.assertEqual(result["status"], "SUCCEEDED", result)
        argv = transport.call_args_list[1].args[0]
        self.assertEqual(argv[argv.index("--permission") + 1], "smart")
        self.assertEqual(argv[argv.index("--mode") + 1], "lightweight")
        self.assertNotIn("full", argv)
        self.assertNotIn("--continue", argv)
        self.assertNotIn("--session", argv)
        self.assertEqual(service.status()["calls_reserved"], 1)

    def test_api_provider_never_launches_model(self):
        service = self.prepared_live()
        provider = {
            "minimaxModelSource": "api_key",
            "providers": [{"providerId": "minimax_api", "active": True}],
        }
        with patch.object(
            service,
            "capture",
            return_value=(None, 0, {"stdout": json.dumps(provider), "stderr": ""}),
        ) as transport:
            self.execute(service)
            result = self.wait(service)
        self.assertEqual(result["error"], "SUBSCRIPTION_AUTH_UNVERIFIED")
        self.assertEqual(transport.call_count, 1)


class ProtocolTests(Fixture):
    @asynccontextmanager
    async def session(self, mode="mock"):
        config_path = self.root / "config.json"
        config_path.write_text(json.dumps(self.config | {"mode": mode}))
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(HERE / "server.py"), "--config", str(config_path)],
        )
        async with (
            stdio_client(params) as (reader, writer),
            ClientSession(
                reader, writer, read_timeout_seconds=timedelta(seconds=10)
            ) as session,
        ):
            initialized = await session.initialize()
            self.assertEqual(initialized.serverInfo.name, "GremoVOD MiniMax Bridge")
            yield session

    def test_initialize_list_schemas_and_mock_tools(self):
        async def exercise():
            async with self.session() as session:
                tools = (await session.list_tools()).tools
                self.assertEqual(
                    {t.name for t in tools},
                    {
                        "minimax_status",
                        "minimax_execute",
                        "minimax_result",
                        "minimax_cancel",
                    },
                )
                for tool in tools:
                    jsonschema.Draft202012Validator.check_schema(tool.inputSchema)
                    self.assertIsNotNone(tool.outputSchema)
                    jsonschema.Draft202012Validator.check_schema(tool.outputSchema)
                args = {
                    "request_id": "protocol",
                    "task": "mock:ok",
                    "head_sha": self.sha,
                    "files": ["value.py"],
                }
                executed = await session.call_tool("minimax_execute", args)
                self.assertFalse(executed.isError, executed)
                for _ in range(100):
                    reply = await session.call_tool(
                        "minimax_result", {"request_id": "protocol"}
                    )
                    result = reply.structuredContent
                    if result.get("status") not in {"RESERVED", "RUNNING"}:
                        break
                    await asyncio.sleep(0.03)
                self.assertEqual(result["status"], "SUCCEEDED", result)
                self.assertEqual(result["result_sha"], self.sha)
                status = (
                    await session.call_tool("minimax_status", {})
                ).structuredContent
                self.assertEqual(status["calls_reserved"], 1)
                cancelled = (
                    await session.call_tool(
                        "minimax_cancel", {"request_id": "protocol"}
                    )
                ).structuredContent
                self.assertEqual(cancelled["status"], "SUCCEEDED")
                invalid = await session.call_tool("minimax_execute", {"request_id": 9})
                self.assertTrue(invalid.isError)

        asyncio.run(exercise())

    def test_disabled_over_mcp(self):
        async def exercise():
            async with self.session(mode="disabled") as session:
                reply = await session.call_tool(
                    "minimax_execute",
                    {
                        "request_id": "denied",
                        "task": "test",
                        "head_sha": self.sha,
                        "files": [],
                    },
                )
                self.assertEqual(reply.structuredContent["error"], "MODELS_DISABLED")

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
