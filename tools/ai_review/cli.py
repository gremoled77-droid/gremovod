"""CLI ревьюера GremoVOD.

    python -m tools.ai_review.cli review   --base <sha> --head <sha> --scope "..."
    python -m tools.ai_review.cli validate artifacts/ai-review/<run>/summary.json
    python -m tools.ai_review.cli report   artifacts/ai-review/<run>/summary.json
    python -m tools.ai_review.cli quota    --consent   # только чтение остатка M Plan

Режим по умолчанию — MOCK: без сети, без ключей, без расхода квоты.
Живой вызов требует `--mode LIVE` и явного `--consent`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import quota as quota_guard
from .contract import assert_valid, build_summary, validate_summary
from .localscan import LocalScanError, collect_diff
from .payload import build_payload
from .report import render_report, render_short_summary
from .reviewer import ReviewRequest, get_reviewer

DEFAULT_ARTIFACTS = Path("artifacts/ai-review")
AGENT_NAME = "minimax-code"


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _branch(repo: Path) -> str:
    import subprocess

    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        check=False,
    )
    return proc.stdout.decode("utf-8", errors="replace").strip() or "unknown"


def cmd_review(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    run_id = args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    task_id = args.task_id or run_id

    try:
        collected = collect_diff(repo, args.base, args.head, allowed_paths=args.allowed_paths or None)
    except LocalScanError as ex:
        print(f"[BLOCKED] локальная проверка отклонила материал: {ex}", file=sys.stderr)
        return 2

    payload = build_payload(
        scope=args.scope or "Задача не описана",
        files=collected["files"],
        diff=collected["diff"],
        diff_sha256=collected["diff_sha256"],
        base_sha=collected["base_sha"],
        head_sha=collected["head_sha"],
        tests_status=args.tests_status,
        tests_summary=args.tests_summary,
    )

    reviewer = _make_reviewer(args)
    request = ReviewRequest(
        task_id=task_id,
        run_id=run_id,
        scope=args.scope or "Задача не описана",
        mode=args.mode,
        base_sha=collected["base_sha"],
        head_sha=collected["head_sha"],
        diff_sha256=collected["diff_sha256"],
        files=collected["files"],
        diff=collected["diff"],
        tests_status=args.tests_status,
        tests_summary=args.tests_summary,
        payload=payload,
    )

    outcome = reviewer.review(request)

    summary = build_summary(
        task_id=task_id,
        run_id=run_id,
        agent=AGENT_NAME,
        provider=outcome.provider,
        mode=args.mode,
        base_sha=collected["base_sha"],
        head_sha=collected["head_sha"],
        diff_sha256=collected["diff_sha256"],
        branch=_branch(repo),
        scope=args.scope,
        code_changes=collected["files"],
        tests_status=args.tests_status,
        review_status=outcome.status,
        reviewer_model=outcome.reviewer_model,
        reviewed_sha=collected["head_sha"] if outcome.status in ("PASS", "FINDINGS") else None,
        findings=outcome.findings,
        pr_url=args.pr_url,
        actions_run_url=args.actions_run_url,
        n8n_execution_url=args.n8n_execution_url,
        provider_usage=outcome.usage if args.mode == "LIVE" else None,
        actual_cost=None,
        quota=outcome_quota(outcome, reviewer),
        owner_decision="PENDING",
        last_updated=_now_iso(),
        blocked_reason=outcome.blocked_reason or outcome.error,
    )

    problems = validate_summary(summary)
    if problems:
        print("[FAIL] контракт dev-run-summary/1 нарушен:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 3
    assert_valid(summary)

    out_dir = Path(args.out_dir) / run_id if args.out_dir else DEFAULT_ARTIFACTS / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "summary.json"
    report_path = out_dir / "report.md"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_report(summary), encoding="utf-8")

    print(f"review_status = {outcome.status}")
    print(f"summary  -> {summary_path}")
    print(f"report   -> {report_path}")
    if args.print_short:
        print()
        print(render_short_summary(summary))
    return 0


def outcome_quota(outcome: Any, reviewer: Any = None) -> dict[str, Any] | None:
    """Достать снимок квоты из ревьюера, если он его приложил."""
    snapshot = getattr(reviewer, "quota_snapshot", None)
    if isinstance(snapshot, quota_guard.QuotaSnapshot):
        return snapshot.as_dict()
    for attr in ("quota",):
        value = getattr(outcome, attr, None)
        if isinstance(value, dict):
            return value
    return None


def _make_reviewer(args: argparse.Namespace):
    if args.provider == "minimax":
        from .adapters.minimax_adapter import MiniMaxReviewer

        snapshot = None
        if args.mode == "LIVE":
            api_key = os.environ.get("MINIMAX_SUBSCRIPTION_KEY", "")
            snapshot = quota_guard.fetch_quota(api_key) if api_key else None
        return MiniMaxReviewer(
            api_key=os.environ.get("MINIMAX_SUBSCRIPTION_KEY", ""),
            consent=args.consent,
            quota_snapshot=snapshot,
        )
    if args.provider == "argon":
        from .adapters.argon_adapter import ArgonReviewer

        return ArgonReviewer(
            api_key=os.environ.get("ARGON_API_KEY", ""),
            consent=args.consent,
            live=args.consent,
        )
    return get_reviewer(args.provider)


def cmd_validate(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.path).read_text(encoding="utf-8"))
    problems = validate_summary(data)
    if problems:
        print(f"[FAIL] нарушений: {len(problems)}")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("[OK] контракт dev-run-summary/1 соблюдён")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    data = json.loads(Path(args.path).read_text(encoding="utf-8"))
    text = render_report(data)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"report -> {args.out}")
    else:
        print(text)
    return 0


def cmd_quota(args: argparse.Namespace) -> int:
    api_key = os.environ.get("MINIMAX_SUBSCRIPTION_KEY", "")
    if not api_key:
        print("[BLOCKED] MINIMAX_SUBSCRIPTION_KEY не задан — остаток квоты неизвестен", file=sys.stderr)
        return 2
    snapshot = quota_guard.fetch_quota(api_key)
    print(json.dumps(snapshot.as_dict(), ensure_ascii=False, indent=2))
    decision = quota_guard.evaluate_quota(snapshot)
    print(f"[{decision.code}] {decision.reason}")
    return 0 if decision.allowed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tools.ai_review.cli", description="AI-ревьюер GremoVOD")
    sub = parser.add_subparsers(dest="command", required=True)

    review = sub.add_parser("review", help="локальное ревью (MOCK по умолчанию)")
    review.add_argument("--repo", default=".")
    review.add_argument("--base", required=True)
    review.add_argument("--head", required=True)
    review.add_argument("--scope", default="")
    review.add_argument("--task-id", default="")
    review.add_argument("--run-id", default="")
    review.add_argument("--provider", default="mock", choices=["mock", "minimax", "argon"])
    review.add_argument("--mode", default="MOCK", choices=["MOCK", "OFFLINE", "LIVE"])
    review.add_argument("--tests-status", default="NOT_RUN", choices=["PASS", "FAIL", "NOT_RUN", "UNKNOWN"])
    review.add_argument("--tests-summary", default=None)
    review.add_argument("--allowed-paths", action="append", default=[])
    review.add_argument("--consent", action="store_true", help="явное согласие владельца на сетевой запрос")
    review.add_argument("--pr-url", default=None)
    review.add_argument("--actions-run-url", default=None)
    review.add_argument("--n8n-execution-url", default=None)
    review.add_argument("--out-dir", default=None)
    review.add_argument("--print-short", action="store_true")
    review.set_defaults(func=cmd_review)

    validate = sub.add_parser("validate", help="проверить summary.json по контракту")
    validate.add_argument("path")
    validate.set_defaults(func=cmd_validate)

    report = sub.add_parser("report", help="собрать Markdown-отчёт из summary.json")
    report.add_argument("path")
    report.add_argument("--out", default=None)
    report.set_defaults(func=cmd_report)

    quota = sub.add_parser("quota", help="проверить остаток квоты M Plan (только чтение)")
    quota.set_defaults(func=cmd_quota)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
