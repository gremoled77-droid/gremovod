"""Generate project-only config. Default disabled; mock opt-in never starts a model."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["disabled", "mock"], default="disabled")
    parser.add_argument("--pr", type=int, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    local = root / ".minimax-mcp"
    project = root / ".codex" / "config.toml"
    if project.exists() or local.exists():
        raise SystemExit(
            "Existing project config/state preserved. Review it manually; no overwrite/reset."
        )
    branch = (
        subprocess.check_output(
            [
                "git",
                "-c",
                f"safe.directory={root.as_posix()}",
                "branch",
                "--show-current",
            ],
            cwd=root,
        )
        .decode()
        .strip()
    )
    if branch in {"", "main", "mavis/work", "codex/work"} or args.pr < 1:
        raise SystemExit("Separate task branch and PR required")
    local.mkdir()
    config = {
        "mode": args.mode,
        "worktree": str(root),
        "branch": branch,
        "pr_number": args.pr,
        "allowed_files": ["scripts/minimax-mcp/fixtures/value.py"],
        "state_dir": str(local / "state"),
        "timeout_seconds": 120,
        "max_calls": 1,
    }
    policy = local / "policy.json"
    policy.write_text(json.dumps(config, indent=2), encoding="utf-8")
    project.parent.mkdir(exist_ok=True)
    project.write_text(
        "[mcp_servers.minimax_bridge]\n"
        + "command = "
        + json.dumps(sys.executable.replace("\\", "/"))
        + "\n"
        + "args = "
        + json.dumps(
            [
                str(root / "scripts/minimax-mcp/server.py").replace("\\", "/"),
                "--config",
                policy.as_posix(),
            ]
        )
        + "\n"
        + "startup_timeout_sec = 30\ntool_timeout_sec = 20\nenabled = true\n"
        + 'enabled_tools = ["minimax_status", "minimax_execute", "minimax_result", "minimax_cancel"]\n',
        encoding="utf-8",
    )
    print(
        f"Project config: {project}\nMode: {args.mode}; model execution not authorized"
    )


if __name__ == "__main__":
    main()
