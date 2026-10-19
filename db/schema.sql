-- GremoVOD P0 pilot schema, 2026-10-19.
-- Apply ONLY to a BACKED-UP COPY of the existing Studio SQLite via explicit migration.
-- Prefix p0_ avoids collision with LEGACY "jobs" table in backend/main.py.
-- Exactly five P0 domain tables. Never drop, rename or truncate legacy tables.
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS p0_runs (
  run_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  phase TEXT NOT NULL DEFAULT 'INTAKE',
  state_version INTEGER NOT NULL DEFAULT 0 CHECK(state_version >= 0),
  snapshot_sha TEXT NOT NULL,
  source_revision TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'CREATED'
    CHECK(status IN ('CREATED','RUNNING','PAUSED','BLOCKED','COMPLETED','FAILED')),
  lease_owner TEXT,
  lease_until_ms INTEGER,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_p0_runs_project ON p0_runs(project_id,updated_at_ms);

CREATE TABLE IF NOT EXISTS p0_budget_envelopes (
  envelope_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES p0_runs(run_id),
  owner_decision_ref TEXT NOT NULL,   -- must come from verified Studio session, never n8n JSON
  cap_cents INTEGER NOT NULL CHECK(cap_cents >= 0),
  reserved_cents INTEGER NOT NULL DEFAULT 0 CHECK(reserved_cents >= 0),
  spent_cents INTEGER NOT NULL DEFAULT 0 CHECK(spent_cents >= 0),
  max_calls INTEGER NOT NULL CHECK(max_calls >= 0),
  calls_reserved INTEGER NOT NULL DEFAULT 0 CHECK(calls_reserved >= 0),
  max_attempts_per_slot INTEGER NOT NULL CHECK(max_attempts_per_slot > 0),
  allowed_stage TEXT NOT NULL,
  allowed_provider TEXT NOT NULL,
  allowed_model TEXT NOT NULL,
  expires_at_ms INTEGER NOT NULL,
  created_at_ms INTEGER NOT NULL,
  CHECK(reserved_cents + spent_cents <= cap_cents),
  CHECK(calls_reserved <= max_calls)
);
CREATE INDEX IF NOT EXISTS idx_p0_envelopes_run ON p0_budget_envelopes(run_id);

CREATE TABLE IF NOT EXISTS p0_jobs (
  job_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES p0_runs(run_id),
  envelope_id TEXT NOT NULL REFERENCES p0_budget_envelopes(envelope_id),
  slot_id TEXT NOT NULL,
  kind TEXT NOT NULL,                 -- video_generation != lip_sync
  attempt_no INTEGER NOT NULL CHECK(attempt_no >= 1),
  stage TEXT NOT NULL,
  request_sha TEXT NOT NULL,          -- SHA-256 of frozen request, computed by trusted backend
  snapshot_sha TEXT NOT NULL,
  source_revision TEXT NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  profile_revision TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN
    ('INTENT_CREATED','AUTHORIZED','SUBMITTING','SUBMITTED','COMPLETED',
     'FAILED','UNKNOWN','CANCEL_REQUESTED','CANCELLED')),
  state_version INTEGER NOT NULL DEFAULT 0 CHECK(state_version >= 0),
  lease_owner TEXT,
  lease_until_ms INTEGER,
  reserve_cents INTEGER NOT NULL DEFAULT 0 CHECK(reserve_cents >= 0),
  spent_cents INTEGER NOT NULL DEFAULT 0 CHECK(spent_cents >= 0),
  submit_count INTEGER NOT NULL DEFAULT 0 CHECK(submit_count IN (0,1)),
  provider_job_id TEXT,
  last_event_id TEXT,
  last_event_sha TEXT,
  possible_charge INTEGER NOT NULL DEFAULT 0 CHECK(possible_charge IN (0,1)),
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL,
  UNIQUE(run_id,slot_id,kind,attempt_no)
);
CREATE INDEX IF NOT EXISTS idx_p0_jobs_run_state ON p0_jobs(run_id,state);
CREATE INDEX IF NOT EXISTS idx_p0_jobs_provider_task ON p0_jobs(provider,provider_job_id);

CREATE TABLE IF NOT EXISTS p0_scene_manifest (
  run_id TEXT NOT NULL REFERENCES p0_runs(run_id),
  slot_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK(kind IN ('shot','voice','sfx','music','ambience','title','reference','other')),
  required INTEGER NOT NULL CHECK(required IN (0,1)),
  source_revision TEXT NOT NULL,
  asset_sha TEXT,                    -- SHA-256 from trusted file worker
  status TEXT NOT NULL DEFAULT 'MISSING' CHECK(status IN ('MISSING','CANDIDATE','FULFILLED','SKIPPED','BLOCKED')),
  selected_take_id TEXT,
  updated_at_ms INTEGER NOT NULL,
  PRIMARY KEY(run_id,slot_id)
);

CREATE TABLE IF NOT EXISTS p0_review_snapshots (
  review_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES p0_runs(run_id),
  snapshot_sha TEXT NOT NULL,
  master_sha TEXT NOT NULL,
  script_sha TEXT NOT NULL,
  requirements_sha TEXT NOT NULL,
  canon_sha TEXT NOT NULL,
  manifest_sha TEXT NOT NULL,
  review_bar_sha TEXT NOT NULL,
  roles_expected TEXT NOT NULL DEFAULT 'A6,A7,A8',
  verified_roles INTEGER NOT NULL DEFAULT 0 CHECK(verified_roles BETWEEN 0 AND 3),
  status TEXT NOT NULL DEFAULT 'BLOCKED'
    CHECK(status IN ('BLOCKED','CHANGES_REQUESTED','AWAITING_OWNER','READY')),
  owner_decision_ref TEXT,
  created_at_ms INTEGER NOT NULL,
  UNIQUE(run_id,snapshot_sha)
);
