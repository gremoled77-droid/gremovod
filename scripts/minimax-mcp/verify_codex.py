"""No inference: Codex initialize -> ephemeral thread -> MCP calls, never turn/start."""

import argparse
import hashlib
import json
import os
import queue
import subprocess
import threading
import time
import uuid
from importlib.metadata import version
from pathlib import Path

from bridge import Child, now


class Rpc:
    def __init__(self, argv, cwd, env):
        self.child = Child(argv, cwd, env)
        self.queue = queue.Queue()
        self.number = 0
        self.methods = []
        self.stderr_bytes = 0

        def read():
            for line in self.child.process.stdout:
                if len(line) > 2_000_000:
                    self.queue.put({"failure": "OUTPUT_LIMIT"})
                    return
                self.queue.put(json.loads(line))
            self.queue.put({"failure": "CODEX_EXITED"})

        def stderr():
            # Do not retain Codex diagnostic text or provider/config details.
            while value := self.child.process.stderr.read(4096):
                self.stderr_bytes += len(value)
                if self.stderr_bytes > 1_000_000:
                    self.child.kill()
                    return

        self.readers = [
            threading.Thread(target=read, daemon=True),
            threading.Thread(target=stderr, daemon=True),
        ]
        for reader in self.readers:
            reader.start()

    def send(self, message):
        self.child.process.stdin.write(json.dumps(message).encode() + b"\n")
        self.child.process.stdin.flush()

    def call(self, method, params):
        if method not in {
            "initialize",
            "thread/start",
            "mcpServerStatus/list",
            "mcpServer/tool/call",
        }:
            raise ValueError("Only non-inference protocol methods are allowed")
        self.methods.append(method)
        self.number += 1
        self.send({"id": self.number, "method": method, "params": params})
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            message = self.queue.get(timeout=max(0.1, deadline - time.monotonic()))
            if "failure" in message:
                raise RuntimeError(message["failure"])
            if message.get("id") == self.number and (
                "result" in message or "error" in message
            ):
                if "error" in message:
                    raise RuntimeError(json.dumps(message["error"]))
                return message["result"]
            if "id" in message and "method" in message:
                self.send(
                    {
                        "id": message["id"],
                        "error": {
                            "code": -32000,
                            "message": "Offline verification denies approvals",
                        },
                    }
                )
        raise TimeoutError(method)

    def close(self):
        self.child.process.stdin.close()
        try:
            self.child.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.child.kill()
            self.child.process.wait(timeout=5)
        self.child.close()
        for reader in self.readers:
            reader.join(timeout=5)
        self.child.process.stdout.close()
        self.child.process.stderr.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--codex", type=Path, required=True, help="Absolute codex.exe; no .cmd or shell"
    )
    args = parser.parse_args()
    if (
        args.codex.suffix.lower() != ".exe"
        or not args.codex.is_absolute()
        or not args.codex.is_file()
    ):
        raise SystemExit("Absolute codex.exe required")
    root = Path(__file__).resolve().parents[2]
    policy_path = root / ".minimax-mcp/policy.json"
    policy_bytes = policy_path.read_bytes()
    policy = json.loads(policy_bytes)
    if policy["mode"] != "disabled":
        raise SystemExit(
            "Project must remain disabled; verifier makes its own temporary mock policy"
        )
    global_config = Path.home() / ".codex/config.toml"
    global_before = (
        hashlib.sha256(global_config.read_bytes()).hexdigest()
        if global_config.exists()
        else None
    )
    sha = (
        subprocess.check_output(
            ["git", "-c", f"safe.directory={root.as_posix()}", "rev-parse", "HEAD"],
            cwd=root,
        )
        .decode()
        .strip()
    )
    output = root / ".minimax-mcp" / ("verification-" + uuid.uuid4().hex[:12])
    home = output / "codex-home"
    home.mkdir(parents=True)
    (home / "config.toml").write_text(
        'model_provider = "offline"\nmodel = "offline"\n'
        '[model_providers.offline]\nname = "Offline verification"\n'
        'base_url = "http://127.0.0.1:9/v1"\nwire_api = "responses"\nrequires_openai_auth = false\n'
        + f'\n[projects.{json.dumps(str(root))}]\ntrust_level = "trusted"\n',
        encoding="utf-8",
    )
    env = {
        k: os.environ[k]
        for k in (
            "PATH",
            "PATHEXT",
            "SystemRoot",
            "WINDIR",
            "TEMP",
            "TMP",
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
        )
        if k in os.environ
    }
    env.update(CODEX_HOME=str(home), RUST_LOG="error")
    trust = f'projects.{json.dumps(root.as_posix())}.trust_level="trusted"'
    registration = subprocess.run(
        [str(args.codex), "-c", trust, "mcp", "list", "--json"],
        cwd=root,
        env=env,
        capture_output=True,
        timeout=20,
        check=True,
    )
    registered = json.loads(registration.stdout)
    assert any(item["name"] == "minimax_bridge" for item in registered), (
        "Project MCP not registered"
    )
    report = {
        "at": now(),
        "head_sha": sha,
        "pr_number": policy["pr_number"],
        "model_turns": 0,
        "mcp_sdk_version": version("mcp"),
        "source_sha256": {
            p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((root / "scripts/minimax-mcp").rglob("*"))
            if p.is_file()
            and p.suffix in {".py", ".txt"}
            and "__pycache__" not in p.parts
        },
        "codex_version": subprocess.check_output(
            [str(args.codex), "--version"], env=env
        )
        .decode()
        .strip(),
        "registered": [item["name"] for item in registered],
        "runs": [],
    }
    for mode in ("disabled", "mock"):
        argv = [str(args.codex), "-c", trust]
        if mode == "mock":
            mock_policy = output / "mock-policy.json"
            mock_policy.write_text(
                json.dumps(
                    policy | {"mode": "mock", "state_dir": str(output / "mock-state")}
                ),
                encoding="utf-8",
            )
            server_args = [
                str(root / "scripts/minimax-mcp/server.py"),
                "--config",
                str(mock_policy),
            ]
            argv += ["-c", "mcp_servers.minimax_bridge.args=" + json.dumps(server_args)]
        argv += ["app-server", "--listen", "stdio://"]
        rpc = Rpc(argv, root, env)
        try:
            rpc.call(
                "initialize",
                {
                    "clientInfo": {
                        "name": "gremovod_offline_bridge_check",
                        "version": "1.0.0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            )
            rpc.send({"method": "initialized"})
            thread = rpc.call(
                "thread/start",
                {
                    "cwd": str(root),
                    "ephemeral": True,
                    "approvalPolicy": "never",
                    "sandbox": "read-only",
                },
            )
            thread_id = thread["thread"]["id"]
            inventory = rpc.call(
                "mcpServerStatus/list",
                {"threadId": thread_id, "serverName": "minimax_bridge"},
            )
            entry = next(x for x in inventory["data"] if x["name"] == "minimax_bridge")
            names = sorted(entry["tools"])
            assert names == [
                "minimax_cancel",
                "minimax_execute",
                "minimax_result",
                "minimax_status",
            ], names

            def tool(name, arguments, rpc=rpc, thread_id=thread_id):
                reply = rpc.call(
                    "mcpServer/tool/call",
                    {
                        "threadId": thread_id,
                        "server": "minimax_bridge",
                        "tool": name,
                        "arguments": arguments,
                    },
                )
                assert not reply.get("isError"), reply
                return reply["structuredContent"]

            status = tool("minimax_status", {})
            assert status["mode"] == mode
            executed = tool(
                "minimax_execute",
                {
                    "request_id": "codex_offline",
                    "task": "mock:environment",
                    "head_sha": sha,
                    "files": policy["allowed_files"],
                },
            )
            if mode == "disabled":
                assert executed["error"] == "MODELS_DISABLED", executed
                result = executed
            else:
                for _ in range(100):
                    result = tool("minimax_result", {"request_id": "codex_offline"})
                    if result["status"] not in {"RESERVED", "RUNNING"}:
                        break
                    time.sleep(0.05)
                assert (
                    result["status"] == "SUCCEEDED" and result["result_sha"] == sha
                ), result
                tool("minimax_cancel", {"request_id": "codex_offline"})
            report["runs"].append(
                {"mode": mode, "tools": names, "result": result, "methods": rpc.methods}
            )
        finally:
            rpc.close()
    global_after = (
        hashlib.sha256(global_config.read_bytes()).hexdigest()
        if global_config.exists()
        else None
    )
    assert global_before == global_after and policy_path.read_bytes() == policy_bytes
    report.update(
        global_config_unchanged=True,
        project_policy_unchanged=True,
        live_minimax_launches=0,
    )
    evidence = output / "evidence.json"
    evidence.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        f"PASS: Codex discovery, four tools, disabled denial, mock result SHA.\nEvidence: {evidence}"
    )


if __name__ == "__main__":
    main()
