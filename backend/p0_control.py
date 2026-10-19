"""P0 Studio ledger: five additive p0_* tables in the EXISTING Studio SQLite.

No HTTP routes, model calls or provider submission. All consent booleans are
INTERNAL TRUST-BOUNDARY PLACEHOLDERS, never pass untrusted n8n/HTTP fields to them.
A verified Studio session must supply owner identity before production wiring.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


SCHEMA = Path(__file__).resolve().parents[1] / "db" / "schema.sql"


class Blocked(ValueError):
    pass


class Conflict(ValueError):
    pass


def now_ms() -> int:
    return int(time.time() * 1000)


def sha256(payload) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def open_db(path: Path | str) -> sqlite3.Connection:
    db = sqlite3.connect(str(path), timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=10000")
    return db


def install_schema(db: sqlite3.Connection):
    """Only call on a disposable DB or after explicit backed-up migration approval."""
    db.executescript(SCHEMA.read_text(encoding="utf-8"))


@contextmanager
def atomic(db):
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise


def _one(db, sql, params):
    item = db.execute(sql, params).fetchone()
    if item is None:
        raise Blocked("record missing")
    return item


def create_run(db, *, run_id, project_id, snapshot_sha, source_revision):
    if not all((run_id, project_id, snapshot_sha, source_revision)):
        raise Blocked("run requires frozen source")
    t = now_ms()
    with atomic(db):
        db.execute("""INSERT INTO p0_runs(run_id,project_id,snapshot_sha,source_revision,
            created_at_ms,updated_at_ms) VALUES(?,?,?,?,?,?)""",
            (run_id,project_id,snapshot_sha,source_revision,t,t))


def create_envelope(db, *, envelope_id, run_id, owner_decision_ref, cap_cents,
                    max_calls, max_attempts_per_slot, stage, provider, model,
                    expires_at_ms, trusted_studio_owner):
    """trusted_studio_owner MUST be derived server-side from Studio session."""
    if trusted_studio_owner is not True or not owner_decision_ref:
        raise Blocked("owner budget permission not verified")
    if any(type(n) is not int for n in (cap_cents,max_calls,max_attempts_per_slot,expires_at_ms)):
        raise Blocked("budget integers required")
    if (cap_cents <= 0 or max_calls <= 0 or max_attempts_per_slot <= 0 or
            expires_at_ms <= now_ms() or not all((stage,provider,model))):
        raise Blocked("invalid budget envelope")
    t=now_ms()
    with atomic(db):
        _one(db,"SELECT run_id FROM p0_runs WHERE run_id=?",(run_id,))
        db.execute("""INSERT INTO p0_budget_envelopes(
            envelope_id,run_id,owner_decision_ref,cap_cents,max_calls,max_attempts_per_slot,
            allowed_stage,allowed_provider,allowed_model,expires_at_ms,created_at_ms)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (envelope_id,run_id,owner_decision_ref,cap_cents,max_calls,
             max_attempts_per_slot,stage,provider,model,expires_at_ms,t))


def create_intent(db, *, job_id, run_id, envelope_id, slot_id, kind, attempt_no,
                  stage, request_sha, snapshot_sha, source_revision, provider,
                  model, profile_revision):
    """Save the exact intent BEFORE any provider call. Never generate a second attempt automatically."""
    if any(not x for x in (job_id,run_id,envelope_id,slot_id,kind,stage,request_sha,
                           snapshot_sha,source_revision,provider,model,profile_revision)):
        raise Blocked("missing immutable request identifiers")
    if type(attempt_no) is not int or attempt_no < 1:
        raise Blocked("invalid attempt")
    t=now_ms()
    with atomic(db):
        r=_one(db,"SELECT * FROM p0_runs WHERE run_id=?",(run_id,))
        e=_one(db,"SELECT * FROM p0_budget_envelopes WHERE envelope_id=?",(envelope_id,))
        if (e["run_id"]!=run_id or r["snapshot_sha"]!=snapshot_sha or
                r["source_revision"]!=source_revision):
            raise Conflict("stale request or foreign envelope")
        db.execute("""INSERT INTO p0_jobs
            (job_id,run_id,envelope_id,slot_id,kind,attempt_no,stage,
             request_sha,snapshot_sha,source_revision,provider,model,profile_revision,state,
             created_at_ms,updated_at_ms)
             VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'INTENT_CREATED',?,?)""",
            (job_id,run_id,envelope_id,slot_id,kind,attempt_no,stage,
             request_sha,snapshot_sha,source_revision,provider,model,profile_revision,t,t))


def authorize(db, *, job_id, request_sha, profile_revision, upper_cents,
              trusted_studio_request_authorization):
    """Atomic reserve. Owner's PACKAGE grant != specific immutable request approval."""
    if trusted_studio_request_authorization is not True:
        raise Blocked("specific request not authorized by trusted Studio")
    if type(upper_cents) is not int or upper_cents <= 0:
        raise Blocked("known upper price ceiling in integer cents is required")
    with atomic(db):
        j=_one(db,"SELECT * FROM p0_jobs WHERE job_id=?",(job_id,))
        e=_one(db,"SELECT * FROM p0_budget_envelopes WHERE envelope_id=?",(j["envelope_id"],))
        r=_one(db,"SELECT * FROM p0_runs WHERE run_id=?",(j["run_id"],))
        if j["state"]!="INTENT_CREATED":
            raise Conflict("request already authorized or attempted")
        if (j["request_sha"]!=request_sha or j["profile_revision"]!=profile_revision or
            j["snapshot_sha"]!=r["snapshot_sha"] or j["source_revision"]!=r["source_revision"]):
            raise Conflict("request hash/profile/revision changed after authorization")
        if (e["run_id"]!=j["run_id"] or e["allowed_stage"]!=j["stage"] or
            e["allowed_provider"]!=j["provider"] or e["allowed_model"]!=j["model"]):
            raise Blocked("stage/provider/model outside owner's grant")
        if (e["expires_at_ms"]<=now_ms() or e["reserved_cents"]+e["spent_cents"]+upper_cents>e["cap_cents"]
            or e["calls_reserved"]>=e["max_calls"]):
            raise Blocked("insufficient budget, calls or expired permission")
        prior=db.execute("SELECT COUNT(*) FROM p0_jobs WHERE run_id=? AND slot_id=? AND kind=? AND state!='INTENT_CREATED'",
                         (j["run_id"],j["slot_id"],j["kind"])).fetchone()[0]
        if prior>=e["max_attempts_per_slot"] or j["attempt_no"]>e["max_attempts_per_slot"]:
            raise Blocked("attempt limit reached")
        db.execute("UPDATE p0_budget_envelopes SET reserved_cents=reserved_cents+?,calls_reserved=calls_reserved+1 WHERE envelope_id=?",
                   (upper_cents,j["envelope_id"]))
        db.execute("""UPDATE p0_jobs SET state='AUTHORIZED',reserve_cents=?,
             state_version=state_version+1,updated_at_ms=? WHERE job_id=?""",
             (upper_cents,now_ms(),job_id))


def claim_run(db, *, run_id, worker, expected_version, lease_ms=120000, at_ms=None):
    """Two Resume clicks with the same revision cannot both win."""
    t=now_ms() if at_ms is None else at_ms
    if lease_ms<=0 or not worker:
        raise Blocked("invalid lease")
    with atomic(db):
        r=_one(db,"SELECT * FROM p0_runs WHERE run_id=?",(run_id,))
        if r["state_version"]!=expected_version or r["status"] not in ("CREATED","RUNNING","PAUSED"):
            raise Conflict("stale or terminal run")
        if r["lease_owner"] and r["lease_until_ms"] and r["lease_until_ms"]>t:
            raise Conflict("run already owned by another worker")
        db.execute("""UPDATE p0_runs SET state_version=state_version+1,lease_owner=?,
            lease_until_ms=?,status='RUNNING',updated_at_ms=? WHERE run_id=?""",
            (worker,t+lease_ms,t,run_id))
        return expected_version+1


def claim_job(db, *, job_id, worker, expected_version, lease_ms=120000, at_ms=None):
    t=now_ms() if at_ms is None else at_ms
    if lease_ms<=0 or not worker:
        raise Blocked("invalid lease")
    with atomic(db):
        j=_one(db,"SELECT * FROM p0_jobs WHERE job_id=?",(job_id,))
        if j["state"]!="AUTHORIZED" or j["state_version"]!=expected_version:
            raise Conflict("job not safe to claim (UNKNOWN is NEVER resumable)")
        if j["lease_owner"] and j["lease_until_ms"] and j["lease_until_ms"]>t:
            raise Conflict("job lease already owned")
        db.execute("""UPDATE p0_jobs SET lease_owner=?,lease_until_ms=?,
            state_version=state_version+1,updated_at_ms=? WHERE job_id=?""",
            (worker,t+lease_ms,t,job_id))
        return expected_version+1


def begin_submit(db, *, job_id, worker, expected_version, request_sha, profile_revision):
    """Transition persisted to SUBMITTING before HTTP POST; caller makes at most one POST."""
    t=now_ms()
    with atomic(db):
        j=_one(db,"SELECT * FROM p0_jobs WHERE job_id=?",(job_id,))
        r=_one(db,"SELECT * FROM p0_runs WHERE run_id=?",(j["run_id"],))
        e=_one(db,"SELECT * FROM p0_budget_envelopes WHERE envelope_id=?",(j["envelope_id"],))
        if (j["state"]!="AUTHORIZED" or j["state_version"]!=expected_version or
            j["lease_owner"]!=worker or (j["lease_until_ms"] or 0)<=t or j["submit_count"]!=0):
            raise Conflict("not authorized, lease expired or already submitted")
        if (j["request_sha"]!=request_sha or j["profile_revision"]!=profile_revision or
            r["snapshot_sha"]!=j["snapshot_sha"] or r["source_revision"]!=j["source_revision"]):
            raise Conflict("source or request changed before paid call")
        if e["expires_at_ms"]<=t or e["reserved_cents"]<j["reserve_cents"]:
            raise Blocked("expired grant or missing reserve")
        db.execute("""UPDATE p0_jobs SET state='SUBMITTING',submit_count=1,
            state_version=state_version+1,updated_at_ms=? WHERE job_id=?""",(t,job_id))


def mark_unknown(db, *, job_id):
    """Lost acknowledgement: NEVER re-send, NEVER free reserved money without proof."""
    with atomic(db):
        j=_one(db,"SELECT state FROM p0_jobs WHERE job_id=?",(job_id,))
        if j["state"]!="SUBMITTING":
            raise Conflict("ambiguous submit only after SUBMITTING")
        db.execute("""UPDATE p0_jobs SET state='UNKNOWN',possible_charge=1,
            lease_owner=NULL,lease_until_ms=NULL,state_version=state_version+1,
            updated_at_ms=? WHERE job_id=?""",(now_ms(),job_id))


def accept_provider_id(db, *, job_id, provider_job_id):
    if not provider_job_id:
        raise Blocked("provider job ID missing")
    with atomic(db):
        j=_one(db,"SELECT state FROM p0_jobs WHERE job_id=?",(job_id,))
        if j["state"]!="SUBMITTING":
            raise Conflict("lost response or duplicate submit; manual reconcile")
        db.execute("""UPDATE p0_jobs SET state='SUBMITTED',provider_job_id=?,
            lease_owner=NULL,lease_until_ms=NULL,state_version=state_version+1,
            updated_at_ms=? WHERE job_id=?""",(provider_job_id,now_ms(),job_id))


def finish_verified(db, *, job_id, event_id, event_body, charged_cents,
                    provider_success, provider_evidence_verified):
    """Backend checks provider authenticity; duplicated terminal callbacks do not recharge."""
    if provider_evidence_verified is not True:
        raise Blocked("provider evidence not verified by backend")
    if type(charged_cents) is not int or charged_cents < 0 or not event_id:
        raise Blocked("invalid confirmed cost/event")
    event_sha=sha256(event_body)
    with atomic(db):
        j=_one(db,"SELECT * FROM p0_jobs WHERE job_id=?",(job_id,))
        if j["last_event_id"]==event_id:
            if j["last_event_sha"]!=event_sha:
                raise Conflict("event ID reused with changed payload")
            return False
        if j["state"]!="SUBMITTED":
            raise Conflict("cannot finish job without provider acknowledgement")
        if charged_cents>j["reserve_cents"]:
            raise Blocked("provider cost exceeds reserved ceiling, manual reconciliation")
        e=_one(db,"SELECT * FROM p0_budget_envelopes WHERE envelope_id=?",(j["envelope_id"],))
        if e["reserved_cents"]<j["reserve_cents"]:
            raise Conflict("reserve missing")
        db.execute("""UPDATE p0_budget_envelopes SET reserved_cents=reserved_cents-?,
              spent_cents=spent_cents+? WHERE envelope_id=?""",
              (j["reserve_cents"],charged_cents,j["envelope_id"]))
        db.execute("""UPDATE p0_jobs SET state=?,last_event_id=?,last_event_sha=?,
              reserve_cents=0,spent_cents=?,possible_charge=0,
              state_version=state_version+1,updated_at_ms=? WHERE job_id=?""",
              ("COMPLETED" if provider_success else "FAILED",
               event_id,event_sha,charged_cents,now_ms(),job_id))
        return True


def manifest_ready(db, *, run_id, expected_source_revision):
    """Skip optional slots. A missing or stale required asset blocks assembly."""
    r=_one(db,"SELECT source_revision FROM p0_runs WHERE run_id=?",(run_id,))
    if r["source_revision"]!=expected_source_revision:
        return False
    rows=db.execute("SELECT * FROM p0_scene_manifest WHERE run_id=?",(run_id,)).fetchall()
    required=[x for x in rows if x["required"]]
    return bool(required) and all(x["status"]=="FULFILLED" and x["asset_sha"] and
                                  x["source_revision"]==expected_source_revision for x in required)


def update_snapshot_revision(db, *, run_id, expected_version, new_sha, new_revision):
    """Owner/canon/input change invalidates authorized but unsubmitted operations."""
    with atomic(db):
        r=_one(db,"SELECT state_version FROM p0_runs WHERE run_id=?",(run_id,))
        if r["state_version"]!=expected_version:
            raise Conflict("stale run revision")
        pending=db.execute("""SELECT COUNT(*) FROM p0_jobs
            WHERE run_id=? AND state IN ('SUBMITTING','SUBMITTED','UNKNOWN')""",(run_id,)).fetchone()[0]
        if pending:
            raise Blocked("cannot silently change source while paid jobs may still charge")
        db.execute("""UPDATE p0_runs SET snapshot_sha=?,source_revision=?,
            state_version=state_version+1,status='PAUSED',lease_owner=NULL,
            lease_until_ms=NULL,updated_at_ms=? WHERE run_id=?""",
            (new_sha,new_revision,now_ms(),run_id))
