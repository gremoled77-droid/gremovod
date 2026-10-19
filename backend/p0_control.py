"""P0 Studio ledger: five additive p0_* tables in the EXISTING Studio SQLite.

No HTTP routes, model calls or provider submission.

Trust boundary: the ledger never accepts a boolean that grants permission.
Owner rights arrive as a server-signed capability bound to one envelope, a
request approval as a capability bound to one immutable request hash, and
provider evidence is checked by a server-side callable. Forwarding the old
`trusted_*` fields from an HTTP or n8n body is rejected explicitly.

Budget boundary: this ledger and the legacy Studio share one spending
counter (backend/spend_ledger.py), so the second layer cannot spend what the
first layer still allows.

Database boundary: the ledger may only open the Studio SQLite; a second
writable database is refused (backend/studio_db.py).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from backend import p0_authz, spend_ledger, studio_db

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


def open_db(path: Path | str, *, allow_disposable: bool = False) -> sqlite3.Connection:
    """Open the Studio SQLite. A second writable database is refused.

    `allow_disposable` is for tests and for explicitly disposable copies of
    the Studio database; it must never be set on a production code path.
    """
    try:
        resolved = studio_db.resolve(path, allow_disposable=allow_disposable)
    except studio_db.ShadowState as exc:
        raise Blocked(str(exc)) from None
    db = sqlite3.connect(str(resolved), timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=10000")
    return db


def install_schema(db: sqlite3.Connection):
    """Only call on a disposable DB or after explicit backed-up migration approval."""
    if db.in_transaction:
        raise Blocked("schema installation requires its own transaction")
    script = SCHEMA.read_text(encoding="utf-8")
    reference = sqlite3.connect(":memory:")
    try:
        reference.executescript(script)
        expected = {
            name: {r[1]: tuple(r)[1:] for r in reference.execute(f"PRAGMA table_info({name})")}
            for (name,) in reference.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        reference.close()
    with atomic(db):
        for table, columns in expected.items():
            actual = {r[1]: tuple(r)[1:] for r in db.execute(f"PRAGMA table_info({table})")}
            prior = dict(columns)
            if table == "p0_runs" and "expected_media_manifest" not in actual:
                prior.pop("expected_media_manifest")
            if actual and actual != prior:
                raise sqlite3.OperationalError(f"incompatible P0 table: {table}")
        # executescript commits an existing transaction; execute complete statements individually.
        statement = ""
        for line in script.splitlines(keepends=True):
            statement += line
            if sqlite3.complete_statement(statement):
                db.execute(statement)
                statement = ""
        if statement.strip():
            raise sqlite3.OperationalError("incomplete P0 schema statement")
        if "expected_media_manifest" not in {r[1] for r in db.execute("PRAGMA table_info(p0_runs)")}:
            db.execute("ALTER TABLE p0_runs ADD COLUMN expected_media_manifest TEXT")
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise sqlite3.DatabaseError("P0 schema integrity failure")


@contextmanager
def atomic(db):
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.rollback()
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
                    expires_at_ms, owner_capability=None, **legacy):
    """Owner permission is a server-signed capability, never a caller-supplied flag.

    The capability is bound to this run, this envelope, this ceiling, stage,
    provider and model, so an approval for one grant cannot be replayed for
    another. Legacy `trusted_studio_owner` from an HTTP or n8n body is refused.
    """
    try:
        p0_authz.reject_legacy_trust(legacy)
    except p0_authz.AuthzError as exc:
        raise Blocked(str(exc)) from None
    if any(type(n) is not int for n in (cap_cents,max_calls,max_attempts_per_slot,expires_at_ms)):
        raise Blocked("budget integers required")
    if (cap_cents <= 0 or max_calls <= 0 or max_attempts_per_slot <= 0 or
            expires_at_ms <= now_ms() or not all((stage,provider,model))):
        raise Blocked("invalid budget envelope")
    try:
        p0_authz.verify(owner_capability, purpose="envelope", binding={
            "run_id": run_id, "envelope_id": envelope_id, "cap_cents": cap_cents,
            "stage": stage, "provider": provider, "model": model})
    except p0_authz.AuthzError as exc:
        raise Blocked(str(exc)) from None
    if not owner_decision_ref:
        raise Blocked("owner budget permission not verified")
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


def _block_unresolved_attempt(db, job):
    other = db.execute("""SELECT job_id FROM p0_jobs
        WHERE run_id=? AND slot_id=? AND kind=? AND job_id<>?
        AND (state IN ('AUTHORIZED','SUBMITTING','SUBMITTED','UNKNOWN','CANCEL_REQUESTED')
             OR possible_charge=1) LIMIT 1""",
        (job["run_id"], job["slot_id"], job["kind"], job["job_id"])).fetchone()
    if other:
        raise Blocked("previous slot operation unresolved; reconcile before another attempt")


def authorize(db, *, job_id, request_sha, profile_revision, upper_cents,
              request_capability=None, **legacy):
    """Atomic reserve. Owner's PACKAGE grant != specific immutable request approval.

    The approval is a server-signed capability bound to this job, this request
    hash and this ceiling. The combined Studio budget (legacy approvals plus
    P0 envelopes) is checked in the same transaction as the reserve, so the
    second ledger cannot spend what the first one still allows.
    """
    try:
        p0_authz.reject_legacy_trust(legacy)
    except p0_authz.AuthzError as exc:
        raise Blocked(str(exc)) from None
    if type(upper_cents) is not int or upper_cents <= 0:
        raise Blocked("known upper price ceiling in integer cents is required")
    try:
        p0_authz.verify(request_capability, purpose="request", binding={
            "job_id": job_id, "request_sha": request_sha, "upper_cents": upper_cents})
    except p0_authz.AuthzError as exc:
        raise Blocked(str(exc)) from None
    with atomic(db):
        j=_one(db,"SELECT * FROM p0_jobs WHERE job_id=?",(job_id,))
        e=_one(db,"SELECT * FROM p0_budget_envelopes WHERE envelope_id=?",(j["envelope_id"],))
        r=_one(db,"SELECT * FROM p0_runs WHERE run_id=?",(j["run_id"],))
        if j["state"]!="INTENT_CREATED":
            raise Conflict("request already authorized or attempted")
        _block_unresolved_attempt(db, j)
        if (j["request_sha"]!=request_sha or j["profile_revision"]!=profile_revision or
            j["snapshot_sha"]!=r["snapshot_sha"] or j["source_revision"]!=r["source_revision"]):
            raise Conflict("request hash/profile/revision changed after authorization")
        if (e["run_id"]!=j["run_id"] or e["allowed_stage"]!=j["stage"] or
            e["allowed_provider"]!=j["provider"] or e["allowed_model"]!=j["model"]):
            raise Blocked("stage/provider/model outside owner's grant")
        if (e["expires_at_ms"]<=now_ms() or e["reserved_cents"]+e["spent_cents"]+upper_cents>e["cap_cents"]
            or e["calls_reserved"]>=e["max_calls"]):
            raise Blocked("insufficient budget, calls or expired permission")
        try:
            spend_ledger.check_cents(db, r["project_id"], upper_cents)
        except spend_ledger.BudgetExceeded as exc:
            raise Blocked(str(exc)) from None
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
        _block_unresolved_attempt(db, j)
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
                    provider_success, verify_evidence=None, **legacy):
    """Backend checks provider authenticity; duplicated terminal callbacks do not recharge.

    `verify_evidence` is a server-side callable that authenticates the
    provider event. The ledger never accepts a boolean that says "this event is
    genuine": a caller could simply set it. Legacy
    `provider_evidence_verified` is refused.
    """
    try:
        p0_authz.reject_legacy_trust(legacy)
    except p0_authz.AuthzError as exc:
        raise Blocked(str(exc)) from None
    if not callable(verify_evidence):
        raise Blocked("server-side provider evidence verification is required")
    if verify_evidence(event_body) is not True:
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


def freeze_manifest(db, *, run_id, expected_source_revision, slots):
    """Freeze the complete trusted plan before jobs or media deliveries exist."""
    kinds = {'shot','voice','sfx','music','ambience','title','reference','other'}
    if not isinstance(slots, list) or not slots:
        raise Blocked("nonempty expected slot list required")
    plan = []
    for slot in slots:
        if (not isinstance(slot, dict) or set(slot) != {'slot_id','kind','required'} or
                not isinstance(slot['slot_id'], str) or not slot['slot_id'].strip() or
                not isinstance(slot['kind'], str) or slot['kind'] not in kinds or
                type(slot['required']) is not bool):
            raise Blocked("invalid expected slot")
        plan.append(dict(slot))
    if len({x['slot_id'] for x in plan}) != len(plan):
        raise Blocked("duplicate expected slot")
    plan.sort(key=lambda x: x['slot_id'])
    with atomic(db):
        r = _one(db, "SELECT * FROM p0_runs WHERE run_id=?", (run_id,))
        if r['source_revision'] != expected_source_revision:
            raise Conflict("stale manifest source")
        frozen = json.dumps({'snapshot_sha':r['snapshot_sha'], 'slots':plan},
                            sort_keys=True, separators=(',', ':'))
        if r['expected_media_manifest'] is not None:
            if r['expected_media_manifest'] != frozen:
                raise Conflict("expected manifest is immutable for this source")
            return
        if (db.execute("SELECT 1 FROM p0_jobs WHERE run_id=? AND source_revision=? LIMIT 1",
                       (run_id,expected_source_revision)).fetchone() or
                db.execute("SELECT 1 FROM p0_scene_manifest WHERE run_id=? AND source_revision=? LIMIT 1",
                           (run_id,expected_source_revision)).fetchone()):
            raise Blocked("freeze manifest before production")
        db.execute("UPDATE p0_runs SET expected_media_manifest=?,updated_at_ms=? WHERE run_id=?",
                   (frozen, now_ms(), run_id))
        db.executemany("""INSERT INTO p0_scene_manifest
            (run_id,slot_id,kind,required,source_revision,status,updated_at_ms)
            VALUES(?,?,?,?,?,'MISSING',?) ON CONFLICT(run_id,slot_id) DO NOTHING""",
            [(run_id,x['slot_id'],x['kind'],int(x['required']),expected_source_revision,now_ms()) for x in plan])


def manifest_ready(db, *, run_id, expected_source_revision):
    """Compare deliveries to the frozen plan, never infer the plan from deliveries."""
    with atomic(db):
        r = _one(db, "SELECT * FROM p0_runs WHERE run_id=?", (run_id,))
        if r['source_revision'] != expected_source_revision or r['expected_media_manifest'] is None:
            return False
        frozen = json.loads(r['expected_media_manifest'])
        if frozen['snapshot_sha'] != r['snapshot_sha']:
            return False
        plan = {x['slot_id']:x for x in frozen['slots']}
        rows = {x['slot_id']:x for x in db.execute("SELECT * FROM p0_scene_manifest WHERE run_id=? AND source_revision=?",
                                                 (run_id,expected_source_revision))}
        if rows.keys() - plan.keys() or not any(x['required'] for x in plan.values()):
            return False
        for slot_id, slot in plan.items():
            row = rows.get(slot_id)
            if row is None:
                if slot['required']:
                    return False
                continue
            if (row['kind'] != slot['kind'] or bool(row['required']) != slot['required'] or
                    row['source_revision'] != expected_source_revision):
                return False
            if slot['required'] and (row['status'] != 'FULFILLED' or not row['asset_sha']):
                return False
        return True


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
            lease_until_ms=NULL,expected_media_manifest=NULL,updated_at_ms=? WHERE run_id=?""",
            (new_sha,new_revision,now_ms(),run_id))
