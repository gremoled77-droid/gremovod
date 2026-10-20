"""Acceptance regressions from Codex review; temporary SQLite only, no providers."""
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from backend import p0_authz
from backend import p0_control as p
from backend import test_p0_control as fixtures
from scripts.p0_migrate import migrate


class DraftAcceptanceRegressions(unittest.TestCase):
    def setUp(self):
        p0_authz.allow_ephemeral_key()
        self.fixture = fixtures.P0SafetyTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db = self.fixture.db

    def test_unknown_blocks_new_attempt_for_same_slot(self):
        self.db.execute("UPDATE p0_budget_envelopes SET max_attempts_per_slot=3")
        self.fixture.intent()
        self.fixture.auth(cents=100)
        self.fixture.submit()
        p.mark_unknown(self.db, job_id="j1")
        self.fixture.intent("j2", "shot_01", attempt=2)
        try:
            self.fixture.auth("j2", cents=100)
            self.fixture.submit("j2")
        except (p.Blocked, p.Conflict):
            pass
        total = self.db.execute("SELECT SUM(submit_count) FROM p0_jobs").fetchone()[0]
        self.assertEqual(total, 1, "UNKNOWN must block a second submission under a new job ID")

    def test_new_envelope_cannot_bypass_unresolved_attempt(self):
        self.fixture.intent()
        self.fixture.auth(cents=100)
        self.fixture.submit()
        p.mark_unknown(self.db, job_id="j1")
        p.create_envelope(self.db, envelope_id="another", run_id="r1", owner_decision_ref="owner-2",
                          cap_cents=1000, max_calls=3, max_attempts_per_slot=3, stage="N29",
                          provider="mock", model="video-mock", expires_at_ms=p.now_ms()+100000,
                          owner_capability=p0_authz.mint_owner_capability("r1", envelope_id="another",
                              cap_cents=1000, stage="N29", provider="mock", model="video-mock"))
        p.create_intent(self.db,job_id="j2",run_id="r1",envelope_id="another",slot_id="shot_01",
                        kind="video_generation",attempt_no=2,stage="N29",request_sha="requestA",
                        snapshot_sha="snapA",source_revision="v1",provider="mock",
                        model="video-mock",profile_revision="prof1")
        with self.assertRaises(p.Blocked):
            self.fixture.auth("j2", cents=100)
        self.assertEqual(self.fixture.row("p0_budget_envelopes","envelope_id","another")["reserved_cents"],0)
        self.assertEqual(self.fixture.row("p0_budget_envelopes","envelope_id","env")["reserved_cents"],100)

    def test_guard_rechecked_at_submit_for_existing_authorized_job(self):
        self.db.execute("UPDATE p0_budget_envelopes SET max_attempts_per_slot=3")
        self.fixture.intent()
        self.fixture.auth(cents=100)
        self.fixture.intent("j2", "shot_01", attempt=2)
        # Simulate a duplicate authorization persisted by the prior release.
        self.db.execute("UPDATE p0_jobs SET state='UNKNOWN',possible_charge=1 WHERE job_id='j2'")
        with self.assertRaises(p.Blocked):
            self.fixture.submit()
        self.assertEqual(self.fixture.row("p0_jobs","job_id","j1")["submit_count"],0)

    def test_parallel_attempts_have_one_reservation_in_wal(self):
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("UPDATE p0_budget_envelopes SET max_attempts_per_slot=3")
        self.fixture.intent()
        self.fixture.intent("j2", "shot_01", attempt=2)
        barrier = threading.Barrier(2)

        def authorize(job_id):
            db = p.open_db(self.fixture.path, allow_disposable=True)
            try:
                barrier.wait(timeout=5)
                try:
                    p.authorize(db,job_id=job_id,request_sha="requestA",profile_revision="prof1",
                                upper_cents=100,request_capability=p0_authz.mint_request_capability(
                                    job_id, request_sha="requestA", upper_cents=100))
                    return "AUTHORIZED"
                except p.Blocked:
                    return "BLOCKED"
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertCountEqual(pool.map(authorize, ["j1","j2"]), ["AUTHORIZED","BLOCKED"])
        envelope = self.fixture.row("p0_budget_envelopes","envelope_id","env")
        self.assertEqual((envelope["reserved_cents"],envelope["calls_reserved"]),(100,1))

    def test_verified_terminal_failure_allows_new_attempt(self):
        self.db.execute("UPDATE p0_budget_envelopes SET max_attempts_per_slot=3")
        self.fixture.intent()
        self.fixture.auth(cents=100)
        self.fixture.submit()
        p.accept_provider_id(self.db,job_id="j1",provider_job_id="provider-1")
        p.finish_verified(self.db,job_id="j1",event_id="failed-1",event_body={"status":"failed"},
                          verify_evidence=lambda body: {"provider_job_id": "provider-1", "charged_cents": 0,
                                                     "success": False})
        self.fixture.intent("j2", "shot_01", attempt=2)
        self.fixture.auth("j2", cents=100)
        self.fixture.submit("j2")
        self.assertEqual(self.fixture.row("p0_jobs","job_id","j2")["submit_count"],1)

    def test_missing_planned_slot_cannot_pass_manifest(self):
        expected_slots = {"shot_01", "shot_02"}
        p.freeze_manifest(self.db, run_id="r1", expected_source_revision="v1", slots=[
            {"slot_id":slot, "kind":"shot", "required":True} for slot in sorted(expected_slots)])
        self.db.execute("UPDATE p0_scene_manifest SET asset_sha='hash1',status='FULFILLED' WHERE slot_id='shot_01'")
        self.db.execute("DELETE FROM p0_scene_manifest WHERE slot_id='shot_02'")
        actual_slots = {r[0] for r in self.db.execute("SELECT slot_id FROM p0_scene_manifest")}
        self.assertTrue(expected_slots - actual_slots)
        self.assertFalse(p.manifest_ready(self.db, run_id="r1", expected_source_revision="v1"),
                         "Frozen expected manifest must detect deleted shot_02")

    def test_failed_migration_leaves_schema_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "copy.sqlite3"
            db = p.open_db(path, allow_disposable=True)
            try:
                db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY, payload TEXT)")
                db.execute("INSERT INTO jobs VALUES('legacy', 'preserve')")
                db.execute("CREATE TABLE p0_jobs(job_id TEXT PRIMARY KEY)")
                before = list(db.execute("SELECT name, sql FROM sqlite_master ORDER BY name"))
            finally:
                db.close()
            with self.assertRaises(sqlite3.OperationalError):
                migrate(path, apply=True, backup_path=Path(folder) / "backup.sqlite3",
                        allow_disposable=True)
            db = p.open_db(path, allow_disposable=True)
            try:
                self.assertEqual(db.execute("SELECT payload FROM jobs").fetchone()[0], "preserve")
                after = list(db.execute("SELECT name, sql FROM sqlite_master ORDER BY name"))
                self.assertEqual([tuple(r) for r in after], [tuple(r) for r in before],
                                 "Migration failure must not leave partially applied DDL")
            finally:
                db.close()

    def test_manifest_required_flag_and_kind_cannot_be_changed_by_delivery(self):
        p.freeze_manifest(self.db,run_id="r1",expected_source_revision="v1",slots=[
            {"slot_id":"shot_01","kind":"shot","required":True}])
        self.db.execute("UPDATE p0_scene_manifest SET status='FULFILLED',asset_sha='hash1'")
        self.assertTrue(p.manifest_ready(self.db,run_id="r1",expected_source_revision="v1"))
        for mutation in ("required=0", "kind='voice'", "source_revision='old'", "asset_sha=NULL"):
            with self.subTest(mutation=mutation):
                self.db.execute("UPDATE p0_scene_manifest SET " + mutation)
                self.assertFalse(p.manifest_ready(self.db,run_id="r1",expected_source_revision="v1"))
                self.db.execute("UPDATE p0_scene_manifest SET required=1,kind='shot',source_revision='v1',asset_sha='hash1'")

    def test_manifest_freeze_is_immutable_and_validates_slots(self):
        slot = {"slot_id":"shot_01","kind":"shot","required":True}
        for bad in ([], [slot,slot], [{**slot,"required":"false"}], [{**slot,"kind":"unknown"}],
                    [{**slot,"slot_id":" "}], [{**slot,"extra":True}]):
            with self.subTest(slots=bad), self.assertRaises(p.Blocked):
                p.freeze_manifest(self.db,run_id="r1",expected_source_revision="v1",slots=bad)
        p.freeze_manifest(self.db,run_id="r1",expected_source_revision="v1",slots=[slot])
        p.freeze_manifest(self.db,run_id="r1",expected_source_revision="v1",slots=[slot])
        with self.assertRaises(p.Conflict):
            p.freeze_manifest(self.db,run_id="r1",expected_source_revision="v1",slots=[{**slot,"required":False}])

    def test_manifest_missing_freeze_or_production_already_started(self):
        self.db.execute("""INSERT INTO p0_scene_manifest
            (run_id,slot_id,kind,required,source_revision,asset_sha,status,updated_at_ms)
            VALUES('r1','shot_01','shot',1,'v1','hash1','FULFILLED',0)""")
        self.assertFalse(p.manifest_ready(self.db,run_id="r1",expected_source_revision="v1"))
        with self.assertRaises(p.Blocked):
            p.freeze_manifest(self.db,run_id="r1",expected_source_revision="v1",slots=[
                {"slot_id":"shot_01","kind":"shot","required":True}])

    def test_new_revision_invalidates_manifest_without_deleting_prior_assets(self):
        slot = {"slot_id":"shot_01","kind":"shot","required":True}
        p.freeze_manifest(self.db,run_id="r1",expected_source_revision="v1",slots=[slot])
        self.db.execute("UPDATE p0_scene_manifest SET status='FULFILLED',asset_sha='old-hash'")
        p.update_snapshot_revision(self.db,run_id="r1",expected_version=0,new_sha="snapB",new_revision="v2")
        self.assertFalse(p.manifest_ready(self.db,run_id="r1",expected_source_revision="v2"))
        p.freeze_manifest(self.db,run_id="r1",expected_source_revision="v2",slots=[slot])
        self.assertEqual(self.db.execute("SELECT asset_sha FROM p0_scene_manifest").fetchone()[0],"old-hash")
        self.assertFalse(p.manifest_ready(self.db,run_id="r1",expected_source_revision="v2"))
        self.db.execute("UPDATE p0_scene_manifest SET source_revision='v2',asset_sha='new-hash'")
        self.assertTrue(p.manifest_ready(self.db,run_id="r1",expected_source_revision="v2"))
