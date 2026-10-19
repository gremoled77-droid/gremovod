"""Контракт `dev-run-summary/1` — валидация машинного отчёта.

Требование (Issue #27, P1.1): единый версионированный JSON-контракт, который
описывает состояние прогона так, чтобы GitHub и n8n показывали одно и то же.
Валидатор не делает сетевых вызовов и не зависит от сторонних пакетов.

Правила намеренно жёсткие: неизвестный статус не считается PASS, отсутствие
данных не превращается в «нулевой расход», а расход без подтверждённого
источника запрещён.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

CONTRACT_VERSION = "dev-run-summary/1"

MODES = ("MOCK", "OFFLINE", "LIVE")
TEST_STATUSES = ("PASS", "FAIL", "NOT_RUN", "UNKNOWN")
REVIEW_STATUSES = (
    "PASS",
    "FINDINGS",
    "UNCERTAIN",
    "API_ERROR",
    "QUOTA_EXHAUSTED",
    "STALE_REVIEW",
    "NOT_RUN",
)
OWNER_DECISIONS = ("PENDING", "APPROVED", "REJECTED")
SEVERITIES = ("P1", "P2", "P3")

#: Поля, которые обязаны присутствовать и быть нужного типа.
REQUIRED_FIELDS: dict[str, tuple[type, ...]] = {
    "schema_version": (str,),
    "task_id": (str,),
    "run_id": (str,),
    "agent": (str,),
    "provider": (str,),
    "mode": (str,),
    "base_sha": (str,),
    "head_sha": (str,),
    "diff_sha256": (str,),
    "branch": (str,),
    "code_changes": (list,),
    "tests_status": (str,),
    "review_status": (str,),
    "owner_decision": (str,),
    "last_updated": (str,),
    "findings": (list,),
}

#: Поля, которые обязаны присутствовать, но могут быть None.
NULLABLE_FIELDS: dict[str, tuple[type, ...]] = {
    "scope": (str,),
    "reviewer_model": (str,),
    "reviewed_sha": (str,),
    "pr_url": (str,),
    "actions_run_url": (str,),
    "n8n_execution_url": (str,),
    "provider_usage": (dict,),
    "actual_cost": (dict,),
    "quota": (dict,),
    "blocked_reason": (str,),
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
URL_RE = re.compile(r"^https://[^\s]+$")


class ContractError(ValueError):
    """Контракт нарушен. Список проблем — в атрибуте `problems`."""

    def __init__(self, problems: list[str]):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems) or "contract violated")


def _iso(value: str) -> bool:
    try:
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return True


def _check_enum(data: dict[str, Any], key: str, allowed: tuple[str, ...], problems: list[str]) -> None:
    value = data.get(key)
    if value is None:
        return
    if value not in allowed:
        problems.append(f"{key}: {value!r} is not one of {list(allowed)}")


def validate_summary(data: Any) -> list[str]:
    """Вернуть список нарушений контракта. Пустой список — контракт соблюдён."""
    problems: list[str] = []

    if not isinstance(data, dict):
        return ["summary must be a JSON object"]

    for key, types in REQUIRED_FIELDS.items():
        if key not in data:
            problems.append(f"missing required field: {key}")
        elif not isinstance(data[key], types):
            problems.append(f"{key}: expected {types[0].__name__}, got {type(data[key]).__name__}")

    for key, types in NULLABLE_FIELDS.items():
        if key not in data:
            problems.append(f"missing required field: {key}")
        elif data[key] is not None and not isinstance(data[key], types):
            problems.append(f"{key}: expected null or {types[0].__name__}, got {type(data[key]).__name__}")

    if data.get("schema_version") != CONTRACT_VERSION:
        problems.append(f"schema_version must be {CONTRACT_VERSION!r}")

    for key in ("task_id", "run_id", "agent", "provider", "branch"):
        value = data.get(key)
        if isinstance(value, str) and not value.strip():
            problems.append(f"{key}: must not be empty")

    _check_enum(data, "mode", MODES, problems)
    _check_enum(data, "tests_status", TEST_STATUSES, problems)
    _check_enum(data, "review_status", REVIEW_STATUSES, problems)
    _check_enum(data, "owner_decision", OWNER_DECISIONS, problems)

    for key in ("base_sha", "head_sha"):
        value = data.get(key)
        if isinstance(value, str) and value and not GIT_SHA_RE.match(value):
            problems.append(f"{key}: not a git sha: {value!r}")

    digest = data.get("diff_sha256")
    if isinstance(digest, str) and digest and not SHA256_RE.match(digest):
        problems.append(f"diff_sha256: not a sha256 hex digest: {digest!r}")

    if not _iso(data.get("last_updated", "")):
        problems.append("last_updated: not an ISO-8601 timestamp")

    for key in ("pr_url", "actions_run_url", "n8n_execution_url"):
        value = data.get(key)
        if isinstance(value, str) and value and not URL_RE.match(value):
            problems.append(f"{key}: not an https URL: {value!r}")

    findings = data.get("findings")
    if isinstance(findings, list):
        for index, finding in enumerate(findings):
            if not isinstance(finding, dict):
                problems.append(f"findings[{index}]: expected object")
                continue
            for key in ("severity", "file", "evidence"):
                if key not in finding:
                    problems.append(f"findings[{index}]: missing {key}")
            severity = finding.get("severity")
            if severity is not None and severity not in SEVERITIES:
                problems.append(f"findings[{index}].severity: {severity!r} not in {list(SEVERITIES)}")
            file_name = finding.get("file")
            if file_name is not None and not isinstance(file_name, str):
                problems.append(f"findings[{index}].file: expected string")
            evidence = finding.get("evidence")
            if evidence is not None and not isinstance(evidence, str):
                problems.append(f"findings[{index}].evidence: expected string")

    cost = data.get("actual_cost")
    if isinstance(cost, dict):
        for key in ("amount", "currency", "source"):
            if key not in cost:
                problems.append(f"actual_cost: missing {key}")
        amount = cost.get("amount")
        if amount is not None and not isinstance(amount, (int, float)):
            problems.append("actual_cost.amount: expected number")
        if cost.get("source") not in ("M_PLAN_QUOTA", "CREDIT_PACK", "PAYG", "UNKNOWN"):
            problems.append(f"actual_cost.source: {cost.get('source')!r} is not an allowed source")

    usage = data.get("provider_usage")
    if isinstance(usage, dict):
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = usage.get(key)
            if value is not None and not isinstance(value, int):
                problems.append(f"provider_usage.{key}: expected int")

    quota = data.get("quota")
    if isinstance(quota, dict):
        if not quota.get("checked_at") or not _iso(str(quota.get("checked_at"))):
            problems.append("quota.checked_at: not an ISO-8601 timestamp")

    # Смысловые (не формальные) правила.
    if data.get("review_status") == "PASS" and isinstance(findings, list) and findings:
        problems.append("review_status=PASS requires an empty findings list")

    if data.get("tests_status") == "FAIL" and data.get("review_status") == "PASS":
        problems.append("tests_status=FAIL forbids review_status=PASS")

    if data.get("mode") in ("MOCK", "OFFLINE"):
        if data.get("provider_usage") is not None:
            problems.append(f"mode={data.get('mode')}: provider_usage must be null (no provider call happened)")
        if data.get("actual_cost") is not None:
            problems.append(f"mode={data.get('mode')}: actual_cost must be null (no spend may be claimed)")

    if data.get("review_status") == "STALE_REVIEW":
        reviewed = data.get("reviewed_sha")
        head = data.get("head_sha")
        if isinstance(reviewed, str) and isinstance(head, str) and reviewed and reviewed != head:
            pass
        elif not reviewed:
            problems.append("review_status=STALE_REVIEW requires reviewed_sha")

    if data.get("review_status") in ("NOT_RUN", "QUOTA_EXHAUSTED", "API_ERROR"):
        if data.get("owner_decision") != "PENDING":
            problems.append(
                f"review_status={data.get('review_status')} requires owner_decision=PENDING"
            )

    return problems


def assert_valid(data: Any) -> None:
    problems = validate_summary(data)
    if problems:
        raise ContractError(problems)


def build_summary(**kwargs: Any) -> dict[str, Any]:
    """Собрать корректный summary с безопасными значениями по умолчанию."""
    summary: dict[str, Any] = {
        "schema_version": CONTRACT_VERSION,
        "task_id": kwargs.get("task_id", ""),
        "run_id": kwargs.get("run_id", ""),
        "agent": kwargs.get("agent", "minimax-code"),
        "provider": kwargs.get("provider", "mock"),
        "mode": kwargs.get("mode", "MOCK"),
        "base_sha": kwargs.get("base_sha", ""),
        "head_sha": kwargs.get("head_sha", ""),
        "diff_sha256": kwargs.get("diff_sha256", ""),
        "branch": kwargs.get("branch", ""),
        "scope": kwargs.get("scope"),
        "code_changes": list(kwargs.get("code_changes") or []),
        "tests_status": kwargs.get("tests_status", "NOT_RUN"),
        "review_status": kwargs.get("review_status", "NOT_RUN"),
        "reviewer_model": kwargs.get("reviewer_model"),
        "reviewed_sha": kwargs.get("reviewed_sha"),
        "findings": list(kwargs.get("findings") or []),
        "pr_url": kwargs.get("pr_url"),
        "actions_run_url": kwargs.get("actions_run_url"),
        "n8n_execution_url": kwargs.get("n8n_execution_url"),
        "provider_usage": kwargs.get("provider_usage"),
        "actual_cost": kwargs.get("actual_cost"),
        "quota": kwargs.get("quota"),
        "owner_decision": kwargs.get("owner_decision", "PENDING"),
        "last_updated": kwargs.get("last_updated", dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")),
        "blocked_reason": kwargs.get("blocked_reason"),
    }
    return summary
