#!/usr/bin/env python3
"""Regenerate the sanitized Argon examples under docs/ai-review/examples/.

Everything here is synthetic: a throwaway Git repository in the system temp
folder, a fake provider and a fixed clock. The output is byte-reproducible so
the committed examples can be regenerated and diffed at any time.

No network call is made. The script only proves the shape of the request and
of the sanitized report.

    python -X utf8 scripts/make_argon_examples.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "ai_review"))

import argon_review  # noqa: E402
import build_review_packet as packets  # noqa: E402
import review_gate  # noqa: E402

OUT = ROOT / "docs" / "ai-review" / "examples"
PR_URL = "https://github.com/gremoled77-droid/gremovod/pull/29"
FIXED_ENV = {
    "GIT_AUTHOR_NAME": "Example Author",
    "GIT_AUTHOR_EMAIL": "example@example.org",
    "GIT_COMMITTER_NAME": "Example Author",
    "GIT_COMMITTER_EMAIL": "example@example.org",
    "GIT_AUTHOR_DATE": "2026-10-19T09:00:00+00:00",
    "GIT_COMMITTER_DATE": "2026-10-19T09:00:00+00:00",
}

BASE_SOURCE = """\
def verify(envelope):
    return envelope.signature == sign(envelope.payload)
"""

HEAD_SOURCE = """\
def verify(envelope):
    # example only: the check is deliberately weak so the reviewer has something to flag
    return envelope.payload is not None
"""


def git(repo, *args):
    env = dict(os.environ)
    env.update(FIXED_ENV)
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True,
                          encoding="utf-8", env=env)


def build_example_repo(root: Path) -> tuple[Path, str, str]:
    repo = root / "example-repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.name", "Example Author")
    git(repo, "config", "user.email", "example@example.org")
    (repo / "example_capability.py").write_text(BASE_SOURCE, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")
    base = git(repo, "rev-parse", "HEAD").stdout.strip()
    (repo / "example_capability.py").write_text(HEAD_SOURCE, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "weaken the capability check")
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    return repo, base, head


def mock_response() -> dict:
    verdict = {
        "verdict": "FINDINGS",
        "findings": [{
            "severity": "P1",
            "path": "example_capability.py",
            "line": 3,
            "evidence": "verify() returns True for any non-empty payload",
            "fix": "compare the signature before accepting the envelope",
            "test": "unittest: a tampered payload must be rejected",
        }],
        "requested_context": [],
    }
    return {
        "id": "chatcmpl-example-0001",
        "object": "chat.completion",
        "created": 1792400000,
        "model": "gemini-4-argon",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": json.dumps(verdict, ensure_ascii=False)},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 1200, "completion_tokens": 180, "total_tokens": 1380},
        "credits_consumed": 1.5,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        repo, base, head = build_example_repo(Path(tmp))
        state = Path(tmp) / "state"
        state.mkdir()

        packet = packets.build_packet(
            repo, base, head,
            pr_url=PR_URL,
            task_id="P0-AUTH",
            scope="Проверь, что проверка capability не подделывается; ищи P0-P2 дефекты.",
            summary="Пример: подпись capability теперь сравнивается с payload.",
            tests=[{"command": "python -X utf8 -m unittest discover -s tests -p test_*.py",
                    "status": "PASS", "exit_code": 0}],
            links=[f"{PR_URL}/files"],
        )
        messages = packets.make_packet_prompt(packet)
        request = {"messages": messages, "stream": False}

        (OUT / "argon_review_request.example.json").write_text(
            json.dumps(request, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        (OUT / "argon_review_response.example.json").write_text(
            json.dumps(mock_response(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        response = mock_response()
        calls = []

        def provider(messages, key):
            calls.append(messages)
            return {
                "content": response["choices"][0]["message"]["content"],
                "credits_consumed": response["credits_consumed"],
                "usage": response["usage"],
                "http_status": 200,
                "raw": response,
            }

        balances = [100.0, 98.5]

        def credits_reader(key):
            return balances.pop(0) if len(balances) > 1 else balances[0]

        approval = state / "approval.json"
        approval.write_text(json.dumps({"approved": True, "pr": PR_URL, "head_sha": head}),
                             encoding="utf-8")

        outcome = review_gate.run(
            repo=repo, base=base, head=head, pr_url=PR_URL, task_id="P0-AUTH",
            scope="Проверь, что проверка capability не подделывается; ищи P0-P2 дефекты.",
            summary="Пример: подпись capability теперь сравнивается с payload.",
            tests=[{"command": "python -X utf8 -m unittest discover -s tests -p test_*.py",
                    "status": "PASS", "exit_code": 0}],
            links=[f"{PR_URL}/files"],
            mode="live", policy=review_gate.Policy(
                max_kie_credits_per_day=100.0, max_kie_credits_per_call=10.0, min_kie_balance=5.0),
            state_dir=state, approval_path=approval, provider=provider,
            credits_reader=credits_reader, api_key="example-not-a-real-key",
            now=review_gate.dt.datetime(2026, 10, 19, 9, 30, 0, tzinfo=review_gate.dt.timezone.utc),
        )
        report = review_gate.render_report(outcome)
        (OUT / "argon_review_report.example.md").write_text(report, encoding="utf-8")

        print(f"status: {outcome['status']}")
        print(f"provider calls: {len(calls)}")
        print(f"payload bytes: {outcome['payload_bytes']} / {outcome['max_payload_bytes']}")
        for name in ("argon_review_request.example.json", "argon_review_response.example.json",
                     "argon_review_report.example.md"):
            print(f"written: {OUT / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
