"""One spending ledger for the whole Studio.

The legacy Studio counted approved generations in `generation_approvals` and
`jobs`. The P0 ledger counted its own `p0_budget_envelopes`. Two counters
mean two caps: the second layer can spend everything the first layer still
allows, and the owner sees only one of them. This module is the single place
where both sides are added up, so a project cap and a daily cap are enforced
against the same total.

Pure standard library: the P0 control plane and the migration scripts must
run without the web stack.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

MOSCOW = timezone(timedelta(hours=3))


class BudgetExceeded(ValueError):
    """The combined ledger is above the configured cap."""


def released(status, response) -> bool:
    """Резерв снимается только с заданий, которые точно ничего не стоили: провайдер отклонил заявку до создания
    задачи (в ответе только detail) или сам сообщил списание 0 (PiAPI: meta.usage.consume). Всё неясное остаётся в резерве."""
    if status not in {"failed", "cancelled"}:
        return False
    try:
        value = json.loads(response or "{}")
    except (TypeError, ValueError):
        return False
    if not isinstance(value, dict):
        return False
    task = value.get("data")
    if task is None:
        return "detail" in value and "task_id" not in value
    usage = ((task.get("meta") or {}).get("usage") or {}) if isinstance(task, dict) else {}
    consume = usage.get("consume")
    return isinstance(consume, (int, float)) and not isinstance(consume, bool) and consume == 0


def _rows(db, sql: str):
    try:
        return db.execute(sql).fetchall()
    except sqlite3.OperationalError:
        # A database that never carried this side of the Studio has no rows here.
        return []


def legacy_reservations(db):
    """Legacy Studio approvals that still hold money."""
    rows = _rows(db, "SELECT a.estimated_usd,j.project_id,j.created_at,j.status,j.response "
                     "FROM generation_approvals a JOIN jobs j ON j.id=a.job_id")
    return [r for r in rows if not released(r["status"], r["response"])]


def p0_reservations(db):
    """P0 envelopes that still hold money.

    `reserved_cents` includes money reserved for an UNKNOWN submit: it is only
    released by a verified terminal event, so an ambiguous provider call keeps
    blocking new spend. `spent_cents` is money that is already gone.
    """
    rows = _rows(db, "SELECT r.project_id,e.reserved_cents,e.spent_cents,e.created_at_ms "
                     "FROM p0_budget_envelopes e JOIN p0_runs r ON r.run_id=e.run_id")
    return [{"project_id": r["project_id"],
             "reserved_cents": r["reserved_cents"],
             "spent_cents": r["spent_cents"],
             "created_at_ms": r["created_at_ms"]} for r in rows]


def limits(db):
    """Configured project and daily caps in USD. Missing table = no money allowed."""
    row = _rows(db, "SELECT project_usd,daily_usd FROM spending_limits WHERE id=1")
    if not row:
        return {"project_usd": 0.0, "daily_usd": 0.0}
    return {"project_usd": row[0]["project_usd"], "daily_usd": row[0]["daily_usd"]}


def _day(value) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, MOSCOW).date().isoformat()
    return datetime.fromisoformat(value).astimezone(MOSCOW).date().isoformat()


def state(db, project_id: str) -> dict:
    """Combined view of everything that already holds or spent money."""
    config = limits(db)
    today = datetime.now(MOSCOW).date().isoformat()
    legacy = legacy_reservations(db)
    p0 = p0_reservations(db)

    legacy_project = sum(r["estimated_usd"] for r in legacy if r["project_id"] == project_id)
    legacy_daily = sum(r["estimated_usd"] for r in legacy if _day(r["created_at"]) == today)
    p0_project = sum((r["reserved_cents"] + r["spent_cents"]) / 100
                      for r in p0 if r["project_id"] == project_id)
    p0_daily = sum((r["reserved_cents"] + r["spent_cents"]) / 100
                   for r in p0 if _day(r["created_at_ms"]) == today)
    return {
        "project_limit_usd": config["project_usd"],
        "daily_limit_usd": config["daily_usd"],
        "project_reserved_usd": round(legacy_project + p0_project, 6),
        "daily_reserved_usd": round(legacy_daily + p0_daily, 6),
        "legacy_reserved_usd": round(legacy_project, 6),
        "p0_reserved_usd": round(p0_project, 6),
        "day_moscow": today,
    }


def check(db, project_id: str, cost_usd: float) -> None:
    """Raise BudgetExceeded when the combined ledger would pass a cap."""
    value = state(db, project_id)
    if value["project_reserved_usd"] + cost_usd > value["project_limit_usd"] + 1e-9:
        raise BudgetExceeded("Превышен серверный бюджет проекта. Измени лимит в разделе «Экономика».")
    if value["daily_reserved_usd"] + cost_usd > value["daily_limit_usd"] + 1e-9:
        raise BudgetExceeded("Превышен дневной серверный бюджет. Измени лимит в разделе «Экономика».")


def check_cents(db, project_id: str, cost_cents: int) -> None:
    """Cent-precise variant for the P0 ledger, which never handles floats."""
    if type(cost_cents) is not int or cost_cents < 0:
        raise BudgetExceeded("cost in integer cents is required")
    check(db, project_id, cost_cents / 100)
