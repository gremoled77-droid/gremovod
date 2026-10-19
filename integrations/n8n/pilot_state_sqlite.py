"""Reference SQLite control plane for an n8n pilot; NOT wired to production FastAPI.

Never pass LLM-supplied "approved" fields into these functions. Only authenticated
Studio routes may issue owner decisions and grants. All costs are upper-bound CENTS.
Media/READY remain blocked until trusted backend media provenance is implemented.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class Conflict(ValueError):
    """Stale, duplicate with changed body, or unsafe state transition."""


class Blocked(ValueError):
    """Missing permission, incomplete input, or insufficient budget."""


def stable_hash(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def connect(filename: str | Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(filename), isolation_level=None, timeout=4)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS runs (
      run_id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
      source_revision TEXT NOT NULL, current_snapshot TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS grants (
      grant_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, run_id TEXT NOT NULL,
      cap_cents INTEGER NOT NULL, max_calls INTEGER NOT NULL,
      reserved_cents INTEGER NOT NULL DEFAULT 0,
      spent_cents INTEGER NOT NULL DEFAULT 0,
      calls INTEGER NOT NULL DEFAULT 0, expires_at REAL NOT NULL,
      FOREIGN KEY(run_id) REFERENCES runs(run_id)
    );
    CREATE TABLE IF NOT EXISTS operations (
      operation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, project_id TEXT NOT NULL,
      request_sha TEXT NOT NULL, source_revision TEXT NOT NULL, snapshot_sha TEXT NOT NULL,
      provider TEXT NOT NULL, model TEXT NOT NULL, profile_revision TEXT NOT NULL,
      stage TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PREPARED', state_revision INTEGER NOT NULL DEFAULT 0,
      lease_owner TEXT, lease_until REAL, grant_id TEXT, reserved_cents INTEGER NOT NULL DEFAULT 0,
      provider_job_id TEXT, possible_charge INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY(run_id) REFERENCES runs(run_id)
    );
    CREATE TABLE IF NOT EXISTS events (
      operation_id TEXT NOT NULL, event_id TEXT NOT NULL, payload_sha TEXT NOT NULL,
      PRIMARY KEY(operation_id,event_id), FOREIGN KEY(operation_id) REFERENCES operations(operation_id)
    );
    CREATE TABLE IF NOT EXISTS validated_final_rounds (
      run_id TEXT NOT NULL, snapshot_sha TEXT NOT NULL, master_checksum TEXT NOT NULL,
      status TEXT NOT NULL, provenance TEXT NOT NULL,
      PRIMARY KEY(run_id,snapshot_sha), FOREIGN KEY(run_id) REFERENCES runs(run_id)
    );
    CREATE TABLE IF NOT EXISTS release_decisions (
      decision_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, snapshot_sha TEXT NOT NULL,
      owner_id TEXT NOT NULL, kind TEXT NOT NULL,
      FOREIGN KEY(run_id) REFERENCES runs(run_id)
    );
    CREATE TABLE IF NOT EXISTS ready (
      run_id TEXT PRIMARY KEY, snapshot_sha TEXT NOT NULL, decision_id TEXT NOT NULL UNIQUE,
      FOREIGN KEY(run_id) REFERENCES runs(run_id)
    );
    """)
    return db


def _tx(db, callback):
    db.execute("BEGIN IMMEDIATE")
    try:
        result = callback()
        db.execute("COMMIT")
        return result
    except BaseException:
        db.execute("ROLLBACK")
        raise


def new_run(db, *, run_id, project_id, source_revision, snapshot_sha):
    if not all((run_id, project_id, source_revision, snapshot_sha)):
        raise Blocked("missing trusted version fields")
    db.execute("INSERT INTO runs VALUES(?,?,?,?)", (run_id, project_id, source_revision, snapshot_sha))


def new_grant(db, *, grant_id, run_id, project_id, cap_cents, max_calls, expires_at, owner_authenticated):
    # A real adapter must derive owner_authenticated from verified Studio session, not input JSON.
    if owner_authenticated is not True or cap_cents <= 0 or max_calls <= 0 or expires_at <= time.time():
        raise Blocked("owner grant missing or invalid")
    def inner():
        r = db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if not r or r["project_id"] != project_id:
            raise Blocked("foreign project")
        db.execute("INSERT INTO grants(grant_id,project_id,run_id,cap_cents,max_calls,expires_at) VALUES(?,?,?,?,?,?)",
                   (grant_id, project_id, run_id, cap_cents, max_calls, expires_at))
    _tx(db, inner)


def prepare(db, *, operation_id, run_id, project_id, stage, request_sha, snapshot_sha,
            source_revision, provider, model, profile_revision):
    def inner():
        r = db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if not r or r["project_id"] != project_id or r["source_revision"] != source_revision or r["current_snapshot"] != snapshot_sha:
            raise Conflict("run snapshot or project changed")
        db.execute("""INSERT INTO operations
            (operation_id,run_id,project_id,stage,request_sha,snapshot_sha,source_revision,provider,model,profile_revision,status)
            VALUES(?,?,?,?,?,?,?,?,?,?,'PREPARED')""",
            (operation_id,run_id,project_id,stage,request_sha,snapshot_sha,source_revision,provider,model,profile_revision))
    _tx(db, inner)


def reserve_request(db, *, operation_id, grant_id, request_sha, provider, model,
                    profile_revision, upper_cents):
    if not isinstance(upper_cents, int) or upper_cents <= 0:
        raise Blocked("unknown price ceiling")
    def inner():
        op = db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
        grant = db.execute("SELECT * FROM grants WHERE grant_id=?", (grant_id,)).fetchone()
        if not op or not grant or op["status"] != "PREPARED":
            raise Conflict("operation not prepared")
        if (op["request_sha"],op["provider"],op["model"],op["profile_revision"]) != (request_sha,provider,model,profile_revision):
            raise Conflict("immutable request changed")
        if (op["run_id"],op["project_id"]) != (grant["run_id"],grant["project_id"]):
            raise Blocked("scope mismatch")
        if grant["expires_at"] <= time.time() or grant["reserved_cents"] + grant["spent_cents"] + upper_cents > grant["cap_cents"] or grant["calls"] >= grant["max_calls"]:
            raise Blocked("budget exhausted/expired")
        db.execute("UPDATE grants SET reserved_cents=reserved_cents+?, calls=calls+1 WHERE grant_id=?",(upper_cents,grant_id))
        db.execute("""UPDATE operations SET status='AUTHORIZED',state_revision=state_revision+1,
            grant_id=?,reserved_cents=? WHERE operation_id=?""",(grant_id,upper_cents,operation_id))
    _tx(db, inner)


def claim(db, *, operation_id, owner, expected_revision, ttl_seconds=120, now=None):
    now = time.time() if now is None else now
    if ttl_seconds <= 0:
        raise Blocked("invalid lease")
    def inner():
        op = db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
        if not op or op["state_revision"] != expected_revision or op["status"] not in ("PREPARED","AUTHORIZED"):
            raise Conflict("stale or unsafe operation; UNKNOWN cannot be resumed")
        if op["lease_owner"] and op["lease_until"] and op["lease_until"] > now:
            raise Conflict("operation already leased")
        db.execute("UPDATE operations SET lease_owner=?, lease_until=?, state_revision=state_revision+1 WHERE operation_id=?",
                   (owner,now+ttl_seconds,operation_id))
        return expected_revision+1
    return _tx(db, inner)


def mark_submitting(db, *, operation_id, owner, expected_revision, now=None):
    now = time.time() if now is None else now
    def inner():
        op = db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
        if not op or op["state_revision"] != expected_revision or op["status"] != "AUTHORIZED" or op["lease_owner"] != owner or (op["lease_until"] or 0)<=now:
            raise Conflict("not authorized/leased")
        db.execute("UPDATE operations SET status='SUBMITTING',state_revision=state_revision+1 WHERE operation_id=?", (operation_id,))
    _tx(db, inner)


def acknowledge_provider(db, *, operation_id, job_id):
    if not job_id:
        raise Blocked("no provider job ID")
    def inner():
        op = db.execute("SELECT * FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
        if not op or op["status"] != "SUBMITTING":
            raise Conflict("not submitting; do not bind a late response blindly")
        db.execute("UPDATE operations SET status='SUBMITTED',provider_job_id=?,lease_owner=NULL,lease_until=NULL,state_revision=state_revision+1 WHERE operation_id=?", (job_id,operation_id))
    _tx(db, inner)


def unknown_submit(db, *, operation_id):
    def inner():
        op = db.execute("SELECT status FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
        if not op or op["status"] != "SUBMITTING":
            raise Conflict("cannot mark this operation UNKNOWN")
        db.execute("UPDATE operations SET status='UNKNOWN',possible_charge=1,lease_owner=NULL,lease_until=NULL,state_revision=state_revision+1 WHERE operation_id=?", (operation_id,))
    _tx(db, inner)


def event_once(db, *, operation_id, event_id, payload):
    digest = stable_hash(payload)
    def inner():
        r=db.execute("SELECT payload_sha FROM events WHERE operation_id=? AND event_id=?",(operation_id,event_id)).fetchone()
        if r:
            if r["payload_sha"]!=digest: raise Conflict("same event ID, different payload")
            return False
        db.execute("INSERT INTO events VALUES(?,?,?)",(operation_id,event_id,digest))
        return True
    return _tx(db, inner)


def update_snapshot(db, *, run_id, expected_snapshot, new_snapshot, new_source_revision):
    def inner():
        r=db.execute("SELECT current_snapshot FROM runs WHERE run_id=?",(run_id,)).fetchone()
        if not r or r["current_snapshot"]!=expected_snapshot: raise Conflict("stale snapshot")
        db.execute("UPDATE runs SET current_snapshot=?,source_revision=? WHERE run_id=?",(new_snapshot,new_source_revision,run_id))
    _tx(db, inner)


def complete_manifest(expected_slots, delivered_slots):
    """Slots are trusted backend records, not LLM claims."""
    actual={x["slot_id"]:x for x in delivered_slots}
    if len(actual)!=len(delivered_slots): return False
    for e in expected_slots:
        if not e.get("required"): continue
        a=actual.get(e["slot_id"])
        if not a or a.get("revision")!=e["revision"] or a.get("checksum")!=e.get("checksum") or not a.get("checksum") or a.get("status")!="FULFILLED":
            return False
    return True


def final_gate(*, frozen_snapshot, active_snapshot, master_checksum, reviewers,
               required_evidence, media_capabilities_verified, expected_slots, delivered_slots):
    """Pure fail-closed gate. Media capabilities must come from trusted inspection."""
    roles=("A6","A7","A8")
    if not frozen_snapshot or frozen_snapshot!=active_snapshot or not master_checksum:
        return "BLOCKED_STALE_SNAPSHOT"
    if not complete_manifest(expected_slots,delivered_slots):
        return "BLOCKED_INCOMPLETE_MANIFEST"
    if not media_capabilities_verified or not required_evidence:
        return "BLOCKED_NO_MEDIA_EVIDENCE"
    if len(reviewers)!=3 or set(x.get("role") for x in reviewers)!=set(roles):
        return "BLOCKED_REVIEWER_SET"
    for r in reviewers:
        if r.get("snapshot_hash")!=frozen_snapshot or r.get("master_checksum")!=master_checksum or r.get("evidence_verified_by_backend") is not True:
            return "BLOCKED_STALE_OR_UNVERIFIED"
    if any(r.get("verdict")=="FAIL" for r in reviewers):
        return "CHANGES_REQUESTED"
    if any(r.get("verdict")!="PASS" for r in reviewers):
        return "BLOCKED_REVIEWER"
    return "AWAITING_OWNER_APPROVAL"


def record_trusted_final_round(db, *, run_id, frozen_snapshot, active_snapshot, master_checksum,
                               reviewers, required_evidence, media_capabilities_verified,
                               expected_slots, delivered_slots, trusted_backend_verifier):
    # trusted_backend_verifier MUST be established by authenticated backend code;
    # never map an n8n/LLM input field directly to this argument.
    if trusted_backend_verifier is not True:
        raise Blocked("backend evidence verifier required")
    status = final_gate(frozen_snapshot=frozen_snapshot,active_snapshot=active_snapshot,
                        master_checksum=master_checksum,reviewers=reviewers,
                        required_evidence=required_evidence,
                        media_capabilities_verified=media_capabilities_verified,
                        expected_slots=expected_slots,delivered_slots=delivered_slots)
    if status != "AWAITING_OWNER_APPROVAL":
        return status
    def inner():
        run=db.execute("SELECT current_snapshot FROM runs WHERE run_id=?",(run_id,)).fetchone()
        if not run or run["current_snapshot"]!=active_snapshot:
            raise Conflict("snapshot changed before final verdict was recorded")
        db.execute("""INSERT OR REPLACE INTO validated_final_rounds
            (run_id,snapshot_sha,master_checksum,status,provenance) VALUES(?,?,?,?,?)""",
            (run_id,frozen_snapshot,master_checksum,status,"trusted_backend_verified"))
    _tx(db, inner)
    return status


def owner_ready(db, *, decision_id, owner_id, run_id, snapshot_sha, gate_result, owner_session_verified):
    if owner_session_verified is not True or not owner_id or gate_result!="AWAITING_OWNER_APPROVAL":
        raise Blocked("owner session or QA not approved")
    def inner():
        run=db.execute("SELECT * FROM runs WHERE run_id=?",(run_id,)).fetchone()
        if not run or run["current_snapshot"]!=snapshot_sha: raise Conflict("stale owner decision")
        trusted=db.execute("SELECT * FROM validated_final_rounds WHERE run_id=? AND snapshot_sha=?",
                           (run_id,snapshot_sha)).fetchone()
        if not trusted or trusted["status"]!="AWAITING_OWNER_APPROVAL" or trusted["provenance"]!="trusted_backend_verified":
            raise Blocked("three trusted media verdicts on current snapshot required")
        old=db.execute("SELECT * FROM release_decisions WHERE decision_id=?",(decision_id,)).fetchone()
        if old:
            if (old["run_id"],old["snapshot_sha"],old["owner_id"]) != (run_id,snapshot_sha,owner_id):
                raise Conflict("decision key collision")
            return False
        existing=db.execute("SELECT * FROM ready WHERE run_id=?",(run_id,)).fetchone()
        if existing: raise Conflict("already READY with another decision")
        db.execute("INSERT INTO release_decisions VALUES(?,?,?,?,?)",(decision_id,run_id,snapshot_sha,owner_id,"READY"))
        db.execute("INSERT INTO ready VALUES(?,?,?)",(run_id,snapshot_sha,decision_id))
        return True
    return _tx(db, inner)
