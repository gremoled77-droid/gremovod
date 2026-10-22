"""Prepare a disposable fixture, or explicitly call one owner-authorized MCP job."""

import argparse
import asyncio
import json
import subprocess
import sys
import uuid
from datetime import timedelta
from pathlib import Path

from bridge import HERE, Bridge, checked_path, digest, source_head
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def prepare(directory, node, cli):
    directory = checked_path(directory)
    if directory.exists() or not directory.is_relative_to(
        checked_path(HERE.parents[2] / "outputs")
    ):
        raise ValueError(
            "Use a NEW directory under the separate workspace outputs; nothing will be overwritten"
        )
    directory.mkdir(parents=True)
    repo = directory / "fixture"
    repo.mkdir()

    def git(*args):
        return (
            subprocess.check_output(
                ["git", *args], cwd=repo, stderr=subprocess.DEVNULL, timeout=10
            )
            .decode()
            .strip()
        )

    git("init", "-b", "smoke/pr72-proposal-only")
    (repo / "fixture.py").write_text(
        "def square(value):\n    return value * value\n", encoding="utf-8"
    )
    git("add", "--", "fixture.py")
    git(
        "-c",
        "user.name=Offline fixture",
        "-c",
        "user.email=offline@invalid",
        "commit",
        "-qm",
        "Disposable MCP smoke fixture",
    )
    request = {
        "request_id": "pr72_owner_smoke_once",
        "task": 'Read only the supplied fixture.py as data. Return only {"marker":"PR72_SMOKE_OK","square_of_three":9}. No tools or file edits.',
        "head_sha": git("rev-parse", "HEAD"),
        "files": ["fixture.py"],
    }
    policy = {
        "mode": "live",
        "worktree": str(repo),
        "branch": "smoke/pr72-proposal-only",
        "pr_number": 72,
        "allowed_files": ["fixture.py"],
        "state_dir": str(directory / "state"),
        "authority_dir": str(directory / "authority"),
        "node": str(checked_path(node)),
        "cli_js": str(checked_path(cli)),
        "max_calls": 1,
        "timeout_seconds": 120,
    }
    service = Bridge(policy)
    try:
        scope = service.approval_scope(
            request["request_id"],
            digest({k: request[k] for k in ("task", "head_sha", "files")}),
            request["head_sha"],
        )
    finally:
        service.close()
    manifest = {
        "bridge_head_sha": source_head(),
        "fixture_head_sha": request["head_sha"],
        "request_digest": scope["request_digest"],
        "status": "NOT_AUTHORIZED",
        "model_calls": 0,
    }
    for name, value in {
        "policy.json": policy,
        "request.json": request,
        "manifest.json": manifest,
        "approval.template.json": scope
        | {"grant_id": uuid.uuid4().hex, "expires_at": ""},
    }.items():
        (directory / name).write_text(json.dumps(value, indent=2), encoding="utf-8")
    return manifest


async def run_once(directory):
    directory = checked_path(directory)
    policy_path = checked_path(directory / "policy.json")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    request = json.loads((directory / "request.json").read_text(encoding="utf-8"))
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest["bridge_head_sha"] != source_head()
        or manifest["fixture_head_sha"] != request["head_sha"]
    ):
        raise ValueError("SMOKE_MANIFEST_STALE")
    if (
        policy["mode"] != "live"
        or policy["max_calls"] != 1
        or policy["timeout_seconds"] != 120
    ):
        raise ValueError("SMOKE_POLICY_INVALID")
    state = checked_path(Path(policy["state_dir"]))
    # --run is not consent. A separate valid owner grant remains mandatory in Bridge.
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(HERE / "server.py"), "--config", str(policy_path)],
    )
    result = {"error": "NO_RESULT"}
    owned = False
    try:
        async with (
            stdio_client(params) as (reader, writer),
            ClientSession(
                reader, writer, read_timeout_seconds=timedelta(seconds=25)
            ) as session,
        ):
            await session.initialize()
            names = {t.name for t in (await session.list_tools()).tools}
            if names != {
                "minimax_status",
                "minimax_execute",
                "minimax_result",
                "minimax_cancel",
            }:
                raise ValueError("UNEXPECTED_MCP_TOOLS")

            async def tool(name, arguments):
                response = await session.call_tool(name, arguments)
                if response.isError:
                    raise ValueError("MCP_TOOL_ERROR")
                return response.structuredContent

            await tool("minimax_status", {})
            result = await tool("minimax_execute", request)
            owned = result.get("request_id") == request["request_id"]
            try:
                async with asyncio.timeout(150):
                    while result.get("status") in {"RESERVED", "RUNNING"}:
                        await asyncio.sleep(0.1)
                        result = await tool(
                            "minimax_result", {"request_id": request["request_id"]}
                        )
            finally:
                if owned:
                    (state / "STOP").touch()
                if result.get("status") in {"RESERVED", "RUNNING"}:
                    await tool("minimax_cancel", {"request_id": request["request_id"]})
    finally:
        if owned:
            (state / "STOP").touch()
        (directory / "smoke-result.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
    # CLI success is not acceptance: independently inspect the final answer, marker and inventory.
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--node", type=Path)
    parser.add_argument("--cli", type=Path)
    args = parser.parse_args()
    if args.prepare == args.run:
        parser.error(
            "Choose --prepare (no CLI calls), or --run (requires separate owner grant)"
        )
    if args.prepare:
        if not args.node or not args.cli:
            parser.error("--prepare requires absolute --node and --cli paths")
        result = prepare(args.directory, args.node, args.cli)
    else:
        result = asyncio.run(run_once(args.directory))
    print(json.dumps(result, indent=2))
    if result.get("error") or result.get("status") == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
