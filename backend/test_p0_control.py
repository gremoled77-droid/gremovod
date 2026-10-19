"""Only temporary SQLite! No real Studio DB, n8n workflow or paid API call."""
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from backend import p0_control as p


class P0SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/"studio.sqlite3"
        self.db=p.open_db(self.path)
        self.addCleanup(self.db.close)
        # Mimic a production LEGACY jobs table. Its payload must survive P0 install.
        self.db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY,request TEXT,status TEXT)")
        self.db.execute("INSERT INTO jobs VALUES('legacy-1','important-original','done')")
        p.install_schema(self.db)
        p.create_run(self.db,run_id="r1",project_id="proj",snapshot_sha="snapA",source_revision="v1")
        p.create_envelope(self.db,envelope_id="env",run_id="r1",owner_decision_ref="owner-session-decision",
                          cap_cents=500,max_calls=2,max_attempts_per_slot=1,stage="N29",
                          provider="mock",model="video-mock",expires_at_ms=p.now_ms()+100000,
                          trusted_studio_owner=True)

    def row(self,table,key_name,key):
        return self.db.execute(f"SELECT * FROM {table} WHERE {key_name}=?",(key,)).fetchone()

    def intent(self, id="j1", slot="shot_01", kind="video_generation", attempt=1, request="requestA"):
        p.create_intent(self.db,job_id=id,run_id="r1",envelope_id="env",slot_id=slot,kind=kind,
                        attempt_no=attempt,stage="N29",request_sha=request,snapshot_sha="snapA",
                        source_revision="v1",provider="mock",model="video-mock",profile_revision="prof1")

    def auth(self, id="j1", cents=250, request="requestA"):
        p.authorize(self.db,job_id=id,request_sha=request,profile_revision="prof1",
                    upper_cents=cents,trusted_studio_request_authorization=True)

    def submit(self, id="j1"):
        version=self.row("p0_jobs","job_id",id)["state_version"]
        v=p.claim_job(self.db,job_id=id,worker="workerA",expected_version=version)
        p.begin_submit(self.db,job_id=id,worker="workerA",expected_version=v,
                       request_sha="requestA",profile_revision="prof1")

    def test_exact_five_new_tables_and_legacy_jobs_untouched(self):
        names={r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        expected={"p0_runs","p0_budget_envelopes","p0_jobs","p0_scene_manifest","p0_review_snapshots"}
        self.assertEqual({n for n in names if n.startswith("p0_")},expected)
        self.assertEqual(self.row("jobs","id","legacy-1")["request"],"important-original")
        p.install_schema(self.db)  # migration is repeatable
        self.assertEqual(self.row("jobs","id","legacy-1")["status"],"done")

    def test_owner_grant_cannot_be_created_by_service(self):
        with self.assertRaises(p.Blocked):
            p.create_envelope(self.db,envelope_id="evil",run_id="r1",owner_decision_ref="fake",
                              cap_cents=10,max_calls=1,max_attempts_per_slot=1,stage="N29",
                              provider="mock",model="video-mock",expires_at_ms=p.now_ms()+9000,
                              trusted_studio_owner=False)

    def test_two_resume_clicks_only_one_wins_even_across_connections(self):
        con2=p.open_db(self.path)
        try:
            v=p.claim_run(self.db,run_id="r1",worker="one",expected_version=0,at_ms=1000)
            self.assertEqual(v,1)
            with self.assertRaises(p.Conflict):
                p.claim_run(con2,run_id="r1",worker="two",expected_version=0,at_ms=1000)
            with self.assertRaises(p.Conflict):
                p.claim_run(con2,run_id="r1",worker="two",expected_version=1,at_ms=1001)
            self.assertEqual(self.row("p0_runs","run_id","r1")["lease_owner"],"one")
        finally:
            con2.close()

    def test_no_request_without_specific_authorization(self):
        self.intent()
        with self.assertRaises(p.Blocked):
            p.authorize(self.db,job_id="j1",request_sha="requestA",profile_revision="prof1",
                        upper_cents=100,trusted_studio_request_authorization=False)
        self.assertEqual(self.row("p0_jobs","job_id","j1")["state"],"INTENT_CREATED")

    def test_prompt_or_profile_changed_after_approval_is_rejected(self):
        self.intent()
        with self.assertRaises(p.Conflict):
            self.auth(request="other-hash")
        with self.assertRaises(p.Conflict):
            p.authorize(self.db,job_id="j1",request_sha="requestA",profile_revision="different",
                        upper_cents=200,trusted_studio_request_authorization=True)
        self.assertEqual(self.row("p0_budget_envelopes","envelope_id","env")["reserved_cents"],0)

    def test_budget_ceiling_and_total_call_count(self):
        self.intent()
        self.auth(cents=400)
        self.intent("j2","shot_02")
        with self.assertRaises(p.Blocked):
            self.auth("j2",cents=200)
        self.auth("j2",cents=100)
        self.assertEqual(self.row("p0_budget_envelopes","envelope_id","env")["reserved_cents"],500)
        self.assertEqual(self.row("p0_budget_envelopes","envelope_id","env")["calls_reserved"],2)
        with self.assertRaises(p.Conflict):
            self.auth("j1",cents=1)

    def test_per_slot_attempt_limit_does_not_double_charge(self):
        self.intent()
        self.auth()
        self.intent("j2","shot_01",attempt=2)
        with self.assertRaises(p.Blocked):
            self.auth("j2")
        self.assertEqual(self.row("p0_budget_envelopes","envelope_id","env")["calls_reserved"],1)

    def test_source_changed_before_submit_blocks_billing(self):
        self.intent(); self.auth()
        v=p.claim_job(self.db,job_id="j1",worker="workerA",
                      expected_version=self.row("p0_jobs","job_id","j1")["state_version"])
        p.update_snapshot_revision(self.db,run_id="r1",expected_version=0,
                                   new_sha="snapB",new_revision="v2")
        with self.assertRaises(p.Conflict):
            p.begin_submit(self.db,job_id="j1",worker="workerA",expected_version=v,
                           request_sha="requestA",profile_revision="prof1")
        self.assertEqual(self.row("p0_jobs","job_id","j1")["submit_count"],0)

    def test_expired_envelope_before_submit_is_blocked(self):
        self.intent(); self.auth()
        v=p.claim_job(self.db,job_id="j1",worker="workerA",
                      expected_version=self.row("p0_jobs","job_id","j1")["state_version"])
        self.db.execute("UPDATE p0_budget_envelopes SET expires_at_ms=0 WHERE envelope_id='env'")
        with self.assertRaises(p.Blocked):
            p.begin_submit(self.db,job_id="j1",worker="workerA",expected_version=v,
                           request_sha="requestA",profile_revision="prof1")

    def test_timeout_AFTER_submit_unknown_and_never_post_again(self):
        self.intent(); self.auth()
        self.submit()
        p.mark_unknown(self.db,job_id="j1")
        job=self.row("p0_jobs","job_id","j1")
        self.assertEqual((job["state"],job["submit_count"],job["possible_charge"]),("UNKNOWN",1,1))
        self.assertEqual(self.row("p0_budget_envelopes","envelope_id","env")["reserved_cents"],250)
        with self.assertRaises(p.Conflict):
            p.claim_job(self.db,job_id="j1",worker="worker2",expected_version=job["state_version"])
        with self.assertRaises(p.Conflict):
            p.accept_provider_id(self.db,job_id="j1",provider_job_id="unknown-stale")
        with self.assertRaises(p.Blocked):
            p.update_snapshot_revision(self.db,run_id="r1",expected_version=0,
                                       new_sha="new",new_revision="v2")

    def test_late_provider_response_not_silently_rebound(self):
        self.intent();self.auth();self.submit();p.mark_unknown(self.db,job_id="j1")
        with self.assertRaises(p.Conflict):
            p.accept_provider_id(self.db,job_id="j1",provider_job_id="job-late")

    def test_provider_success_charges_once_and_no_duplicate_callbacks(self):
        self.intent();self.auth();self.submit()
        p.accept_provider_id(self.db,job_id="j1",provider_job_id="provider123")
        self.assertTrue(p.finish_verified(self.db,job_id="j1",event_id="event01",
                                         event_body={"status":"done"},charged_cents=180,
                                         provider_success=True,provider_evidence_verified=True))
        self.assertFalse(p.finish_verified(self.db,job_id="j1",event_id="event01",
                                          event_body={"status":"done"},charged_cents=180,
                                          provider_success=True,provider_evidence_verified=True))
        with self.assertRaises(p.Conflict):
            p.finish_verified(self.db,job_id="j1",event_id="event01",
                              event_body={"status":"tampered"},charged_cents=180,
                              provider_success=True,provider_evidence_verified=True)
        envelope=self.row("p0_budget_envelopes","envelope_id","env")
        self.assertEqual((envelope["spent_cents"],envelope["reserved_cents"]),(180,0))

    def test_unverified_provider_report_or_overbilling_cannot_release(self):
        self.intent();self.auth();self.submit()
        p.accept_provider_id(self.db,job_id="j1",provider_job_id="provider123")
        with self.assertRaises(p.Blocked):
            p.finish_verified(self.db,job_id="j1",event_id="event1",event_body={},
                              charged_cents=10,provider_success=True,provider_evidence_verified=False)
        with self.assertRaises(p.Blocked):
            p.finish_verified(self.db,job_id="j1",event_id="event2",event_body={},
                              charged_cents=999,provider_success=True,provider_evidence_verified=True)
        self.assertEqual(self.row("p0_budget_envelopes","envelope_id","env")["reserved_cents"],250)

    def test_manifest_needs_all_required_slots_and_current_assets(self):
        self.db.execute("""INSERT INTO p0_scene_manifest
            (run_id,slot_id,kind,required,source_revision,asset_sha,status,updated_at_ms)
            VALUES ('r1','shot_01','shot',1,'v1',NULL,'MISSING',0)""")
        self.assertFalse(p.manifest_ready(self.db,run_id="r1",expected_source_revision="v1"))
        self.db.execute("UPDATE p0_scene_manifest SET status='FULFILLED',asset_sha='hash1' WHERE slot_id='shot_01'")
        self.assertTrue(p.manifest_ready(self.db,run_id="r1",expected_source_revision="v1"))
        self.db.execute("""INSERT INTO p0_scene_manifest
            (run_id,slot_id,kind,required,source_revision,status,updated_at_ms)
            VALUES ('r1','music','music',0,'v1','SKIPPED',0)""")
        self.assertTrue(p.manifest_ready(self.db,run_id="r1",expected_source_revision="v1"))
        self.assertFalse(p.manifest_ready(self.db,run_id="r1",expected_source_revision="v2"))

    def test_no_automatic_ready_without_verified_media(self):
        rows=self.db.execute("SELECT * FROM p0_review_snapshots").fetchall()
        self.assertEqual(len(rows),0)
        self.assertNotIn("READY", [r["status"] for r in rows])

    def test_no_legacy_job_overwrite_from_p0_submit(self):
        self.intent();self.auth();self.submit();p.mark_unknown(self.db,job_id="j1")
        self.assertEqual(self.row("jobs","id","legacy-1")["request"],"important-original")


if __name__ == "__main__":
    unittest.main()
