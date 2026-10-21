"""Fixed offline fixture, never imports or invokes a model CLI."""

import json
import os
import subprocess
import sys
import time

payload = json.load(sys.stdin)
scenario = payload["task"]
if scenario == "mock:pause":
    time.sleep(0.5)
if scenario == "mock:timeout":
    time.sleep(30)
if scenario == "mock:tree":
    child = subprocess.Popen(
        [sys.executable, "-I", "-c", "import time; time.sleep(30)"], shell=False
    )
    print(json.dumps({"child_pid": child.pid}), flush=True)
    time.sleep(30)
if scenario == "mock:error":
    print("synthetic auth error; access_token=not-a-real-token", file=sys.stderr)
    sys.exit(23)
if scenario == "mock:invalid":
    print("not json")
    sys.exit(0)
if scenario == "mock:overflow":
    print("x" * 100_000)
    sys.exit(0)
if scenario == "mock:environment":
    assert not any(
        k in os.environ
        for k in (
            "OPENAI_API_KEY",
            "MINIMAX_API_KEY",
            "NODE_OPTIONS",
            "PYTHONPATH",
            "CODEX_HOME",
            "HTTPS_PROXY",
        )
    )
    assert os.environ["MINIMAX_DATA_DIR"] == os.environ["MAVIS_DATA_DIR"]
    assert os.environ["HOME"] == os.environ["USERPROFILE"]
    assert not os.listdir(os.getcwd())
print(
    json.dumps(
        {
            "mock": True,
            "head_sha": payload["head_sha"],
            "files": list(payload["files"]),
            "proposal": "No files changed; offline fixture completed.",
        }
    )
)
