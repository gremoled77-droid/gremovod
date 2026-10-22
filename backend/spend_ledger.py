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
import math
import sqlite3
from datetime import datetime, timedelta, timezone

MOSCOW = timezone(timedelta(hours=3))

# Статусы платных LLM-вызовов, удерживающие деньги: резерв, подтверждённый факт и
# неопределённый исход. Единственное определение на оба контура: журнал вызовов и
# этот счётчик не должны решать, какие вызовы держат деньги, по-разному.
LLM_HOLDING_STATUSES = ("reserved", "done", "submission_unknown")


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


def _rows(db, sql: str, params=()):
    try:
        return db.execute(sql, params).fetchall()
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


def llm_reservations(db):
    """Paid LLM calls that still hold money: reserve, confirmed fact, unknown outcome.

    `usd` is the estimate for a call that is still reserved and the confirmed amount
    after settlement, so summing it never loses money. A call the provider refused
    (`failed`) is not here: nothing was charged.
    """
    placeholders = ",".join("?" * len(LLM_HOLDING_STATUSES))
    rows = _rows(db, f"SELECT project_id,usd,created_at FROM llm_calls WHERE status IN ({placeholders})",
                 LLM_HOLDING_STATUSES)
    return [{"project_id": r["project_id"], "usd": r["usd"], "created_at": r["created_at"]} for r in rows]


def n8n_counted_usd(status, reserved_usd, usd):
    """Сколько денег держит расход n8n-агента.

    Правило одно на оба контура: резерв держит потолок шага, подтверждённый факт —
    сам факт (он может быть больше потолка, и тогда перерасход виден в счётчике),
    отказ — ноль, неопределённый исход — по-прежнему держит потолок.
    """
    if status == 'done':
        return float(usd or 0.0)
    if status == 'failed':
        return 0.0
    return float(reserved_usd or 0.0)


def n8n_reservations(db):
    """Расходы n8n-агентов, которые держат или уже потратили деньги."""
    rows = _rows(db, "SELECT project_id,role,reserved_usd,usd,status,created_at FROM n8n_spend")
    return [{"project_id": r["project_id"], "role": r["role"],
             "usd": n8n_counted_usd(r["status"], r["reserved_usd"], r["usd"]),
             "created_at": r["created_at"]} for r in rows]


def p0_obligations(db):
    """Money the provider took beyond the owner's ceiling.

    The envelope keeps `reserved_cents + spent_cents <= cap_cents`, so an
    excess charge has nowhere to live there. It is booked here instead: the
    money is really gone and the combined ledger must show it.
    """
    rows = _rows(db, "SELECT project_id,overrun_cents,created_at_ms "
                     "FROM p0_spend_obligations")
    return [{"project_id": r["project_id"],
             "overrun_cents": r["overrun_cents"],
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
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        # A timestamp without a timezone is Studio time, not machine time.
        moment = moment.replace(tzinfo=MOSCOW)
    return moment.astimezone(MOSCOW).date().isoformat()


def _readable(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def state(db, project_id: str) -> dict:
    """Combined view of everything that already holds or spent money.

    One counter for the whole Studio: legacy media approvals, paid LLM calls, spend of
    n8n agents, P0 envelopes and the excess a provider charged beyond the owner's
    ceiling. Every paid path is checked against this total, so no layer can spend what
    another layer still allows.
    """
    config = limits(db)
    today = datetime.now(MOSCOW).date().isoformat()
    legacy = legacy_reservations(db)
    p0 = p0_reservations(db)
    llm = llm_reservations(db)
    # Нечитаемая сумма (llm_guard.UNREADABLE_AMOUNT) не слагаемое и не ноль: её считают отдельно.
    broken = [r for r in llm if not _readable(r["usd"])]
    llm = [r for r in llm if _readable(r["usd"])]
    n8n = n8n_reservations(db)

    legacy_project = sum(r["estimated_usd"] for r in legacy if r["project_id"] == project_id)
    legacy_daily = sum(r["estimated_usd"] for r in legacy if _day(r["created_at"]) == today)
    llm_project = sum(r["usd"] for r in llm if r["project_id"] == project_id)
    llm_daily = sum(r["usd"] for r in llm if _day(r["created_at"]) == today)
    n8n_project = sum(r["usd"] for r in n8n if r["project_id"] == project_id)
    n8n_daily = sum(r["usd"] for r in n8n if _day(r["created_at"]) == today)
    p0_project = sum((r["reserved_cents"] + r["spent_cents"]) / 100
                      for r in p0 if r["project_id"] == project_id)
    p0_daily = sum((r["reserved_cents"] + r["spent_cents"]) / 100
                   for r in p0 if _day(r["created_at_ms"]) == today)
    obligations = p0_obligations(db)
    overrun_project = sum(r["overrun_cents"] / 100
                           for r in obligations if r["project_id"] == project_id)
    overrun_daily = sum(r["overrun_cents"] / 100
                        for r in obligations if _day(r["created_at_ms"]) == today)
    return {
        "project_limit_usd": config["project_usd"],
        "daily_limit_usd": config["daily_usd"],
        "project_reserved_usd": round(legacy_project + llm_project + n8n_project + p0_project + overrun_project, 6),
        "daily_reserved_usd": round(legacy_daily + llm_daily + n8n_daily + p0_daily + overrun_daily, 6),
        "media_reserved_usd": round(legacy_project, 6),
        "llm_reserved_usd": round(llm_project, 6),
        "n8n_reserved_usd": round(n8n_project, 6),
        "legacy_reserved_usd": round(legacy_project, 6),
        "p0_reserved_usd": round(p0_project, 6),
        "overrun_reserved_usd": round(overrun_project, 6),
        "day_moscow": today,
        "llm_unreadable_project": sum(1 for r in broken if r["project_id"] == project_id),
        # Неизвестная сегодняшняя сумма могла войти в дневной лимит любого проекта.
        "llm_unreadable_daily": sum(1 for r in broken if _day(r["created_at"]) == today),
    }


def check(db, project_id: str, cost_usd: float) -> None:
    """Raise BudgetExceeded when the combined ledger would pass a cap."""
    value = state(db, project_id)
    if value["llm_unreadable_project"] or value["llm_unreadable_daily"]:
        raise BudgetExceeded("Учёт расходов повреждён: запись LLM с нечитаемой суммой. "
                             "Траты остановлены до решения владельца.")
    if value["project_reserved_usd"] + cost_usd > value["project_limit_usd"] + 1e-9:
        raise BudgetExceeded("Превышен серверный бюджет проекта. Измени лимит в разделе «Экономика».")
    if value["daily_reserved_usd"] + cost_usd > value["daily_limit_usd"] + 1e-9:
        raise BudgetExceeded("Превышен дневной серверный бюджет. Измени лимит в разделе «Экономика».")


def check_cents(db, project_id: str, cost_cents: int) -> None:
    """Cent-precise variant for the P0 ledger, which never handles floats."""
    if type(cost_cents) is not int or cost_cents < 0:
        raise BudgetExceeded("cost in integer cents is required")
    check(db, project_id, cost_cents / 100)
