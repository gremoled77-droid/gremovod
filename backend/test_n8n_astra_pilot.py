"""Offline tests only. NEVER connect to production SQLite, n8n, or any provider."""
import tempfile
import time
import unittest
from pathlib import Path

from integrations.n8n import pilot_state_sqlite as s


class PilotStateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/"pilot.sqlite3"
        self.db=s.connect(self.path)
        s.new_run(self.db,run_id="r1",project_id="p1",source_revision="v1",snapshot_sha="snap1")
        s.new_grant(self.db,grant_id="g1",run_id="r1",project_id="p1",cap_cents=50,max_calls=2,
                    expires_at=time.time()+10000,owner_authenticated=True)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def op(self,oid="o1",request_sha="req",profile="v1"):
        s.prepare(self.db,operation_id=oid,run_id="r1",project_id="p1",stage="text",
                  request_sha=request_sha,snapshot_sha="snap1",source_revision="v1",
                  provider="mock",model="echo",profile_revision=profile)

    def reserve(self,oid="o1",price=20,request_sha="req",profile="v1"):
        s.reserve_request(self.db,operation_id=oid,grant_id="g1",
                          request_sha=request_sha,provider="mock",model="echo",
                          profile_revision=profile,upper_cents=price)

    def row(self,oid="o1"):
        return self.db.execute("SELECT * FROM operations WHERE operation_id=?",(oid,)).fetchone()

    def test_grant_must_be_authenticated(self):
        with self.assertRaises(s.Blocked):
            s.new_grant(self.db,grant_id="g2",run_id="r1",project_id="p1",
                        cap_cents=1,max_calls=1,expires_at=time.time()+100,owner_authenticated=False)

    def test_foreign_project_stale_revision_cannot_prepare(self):
        with self.assertRaises(s.Conflict):
            s.prepare(self.db,operation_id="bad",run_id="r1",project_id="p2",
                      stage="text",request_sha="req",snapshot_sha="snap1",
                      source_revision="v1",provider="mock",model="echo",profile_revision="v1")
        with self.assertRaises(s.Conflict):
            s.prepare(self.db,operation_id="old",run_id="r1",project_id="p1",
                      stage="text",request_sha="req",snapshot_sha="stale",
                      source_revision="v1",provider="mock",model="echo",profile_revision="v1")

    def test_immutable_request_hash_or_profile_blocks_paid_submit(self):
        self.op()
        for args in [{"request_sha":"altered"},{"profile":"changed"}]:
            with self.assertRaises(s.Conflict):
                self.reserve(**args)
        self.assertEqual(self.row()["status"],"PREPARED")

    def test_cap_and_call_count_enforced_transactionally(self):
        self.op();self.reserve(price=30)
        self.op("o2")
        with self.assertRaises(s.Blocked):
            self.reserve("o2",price=30)
        self.reserve("o2",price=20)
        self.op("o3")
        with self.assertRaises(s.Blocked):
            self.reserve("o3",price=1)
        g=self.db.execute("SELECT * FROM grants WHERE grant_id='g1'").fetchone()
        self.assertEqual(g["reserved_cents"],50)
        self.assertEqual(g["calls"],2)

    def test_missing_price_ceiling_fails(self):
        self.op()
        with self.assertRaises(s.Blocked):
            self.reserve(price=0)

    def test_two_resumers_only_one_lease(self):
        self.op();self.reserve()
        first=self.row()["state_revision"]
        next_rev=s.claim(self.db,operation_id="o1",owner="w1",expected_revision=first,now=1000)
        self.assertEqual(next_rev,first+1)
        other=s.connect(self.path)
        try:
            with self.assertRaises(s.Conflict):
                s.claim(other,operation_id="o1",owner="w2",expected_revision=first,now=1000)
            with self.assertRaises(s.Conflict):
                s.claim(other,operation_id="o1",owner="w2",expected_revision=next_rev,now=1010)
        finally:
            other.close()

    def test_unknown_timeout_leaves_reservation_and_no_resume(self):
        self.op();self.reserve()
        rev=self.row()["state_revision"]
        rev=s.claim(self.db,operation_id="o1",owner="worker",expected_revision=rev)
        s.mark_submitting(self.db,operation_id="o1",owner="worker",expected_revision=rev)
        s.unknown_submit(self.db,operation_id="o1")
        op=self.row()
        self.assertEqual((op["status"],op["possible_charge"],op["reserved_cents"]),("UNKNOWN",1,20))
        with self.assertRaises(s.Conflict):
            s.claim(self.db,operation_id="o1",owner="worker",expected_revision=op["state_revision"])
        g=self.db.execute("SELECT reserved_cents FROM grants WHERE grant_id='g1'").fetchone()
        self.assertEqual(g["reserved_cents"],20)

    def test_snapshot_changed_after_reservation_blocks_submit(self):
        self.op();self.reserve()
        rev=s.claim(self.db,operation_id="o1",owner="worker",expected_revision=self.row()["state_revision"])
        s.update_snapshot(self.db,run_id="r1",expected_snapshot="snap1",
                          new_snapshot="snap2",new_source_revision="v2")
        with self.assertRaises(s.Conflict):
            s.mark_submitting(self.db,operation_id="o1",owner="worker",expected_revision=rev)
        self.assertEqual(self.row()["status"],"AUTHORIZED")

    def test_grant_expired_between_reservation_and_submit(self):
        self.op();self.reserve()
        rev=s.claim(self.db,operation_id="o1",owner="worker",expected_revision=self.row()["state_revision"])
        self.db.execute("UPDATE grants SET expires_at=? WHERE grant_id='g1'",(time.time()-1,))
        with self.assertRaises(s.Blocked):
            s.mark_submitting(self.db,operation_id="o1",owner="worker",expected_revision=rev)
        self.assertEqual(self.row()["status"],"AUTHORIZED")

    def test_normal_submit_acknowledged_once(self):
        self.op();self.reserve()
        rev=s.claim(self.db,operation_id="o1",owner="w",expected_revision=self.row()["state_revision"])
        s.mark_submitting(self.db,operation_id="o1",owner="w",expected_revision=rev)
        s.acknowledge_provider(self.db,operation_id="o1",job_id="provider-123")
        with self.assertRaises(s.Conflict):
            s.acknowledge_provider(self.db,operation_id="o1",job_id="provider-456")
        self.assertEqual(self.row()["provider_job_id"],"provider-123")

    def test_callback_replay_and_changed_payload(self):
        self.op()
        self.assertTrue(s.event_once(self.db,operation_id="o1",event_id="e1",payload={"status":"done"}))
        self.assertFalse(s.event_once(self.db,operation_id="o1",event_id="e1",payload={"status":"done"}))
        with self.assertRaises(s.Conflict):
            s.event_once(self.db,operation_id="o1",event_id="e1",payload={"status":"failed"})

    def test_stale_source_after_update(self):
        s.update_snapshot(self.db,run_id="r1",expected_snapshot="snap1",
                          new_snapshot="snap2",new_source_revision="v2")
        with self.assertRaises(s.Conflict):
            s.update_snapshot(self.db,run_id="r1",expected_snapshot="snap1",
                              new_snapshot="snap3",new_source_revision="v3")
        with self.assertRaises(s.Conflict):
            self.op()

    def test_mandatory_slot_missing_or_wrong_version(self):
        expected=[{"slot_id":"shot-1","required":True,"revision":"v1","checksum":"sha:a"},
                  {"slot_id":"music","required":False,"revision":"v1","checksum":"sha:b"}]
        self.assertFalse(s.complete_manifest(expected,[]))
        self.assertFalse(s.complete_manifest(expected,[{"slot_id":"shot-1","revision":"v2","checksum":"sha:a","status":"FULFILLED"}]))
        self.assertTrue(s.complete_manifest(expected,[{"slot_id":"shot-1","revision":"v1","checksum":"sha:a","status":"FULFILLED"}]))

    def reviewers(self,snapshot="snap1"):
        return [{"role":role,"verdict":"PASS","snapshot_hash":snapshot,"master_checksum":"sha:master",
                 "evidence_verified_by_backend":True} for role in ("A6","A7","A8")]

    def gate(self,**kwargs):
        base=dict(frozen_snapshot="snap1",active_snapshot="snap1",master_checksum="sha:master",
                  reviewers=self.reviewers(),required_evidence=True,media_capabilities_verified=True,
                  expected_slots=[],delivered_slots=[])
        base.update(kwargs)
        return s.final_gate(**base)

    def test_no_media_no_ready(self):
        self.assertEqual(self.gate(media_capabilities_verified=False),"BLOCKED_NO_MEDIA_EVIDENCE")
        self.assertEqual(self.gate(required_evidence=False),"BLOCKED_NO_MEDIA_EVIDENCE")

    def test_three_pass_one_snapshot_and_evidence_required(self):
        self.assertEqual(self.gate(),"AWAITING_OWNER_APPROVAL")
        self.assertEqual(self.gate(active_snapshot="snap2"),"BLOCKED_STALE_SNAPSHOT")
        self.assertEqual(self.gate(reviewers=self.reviewers("old")),"BLOCKED_STALE_OR_UNVERIFIED")
        a=self.reviewers();a[2]["verdict"]="BLOCKED"
        self.assertEqual(self.gate(reviewers=a),"BLOCKED_REVIEWER")
        a=self.reviewers();a[1]["verdict"]="FAIL"
        self.assertEqual(self.gate(reviewers=a),"CHANGES_REQUESTED")
        self.assertEqual(self.gate(reviewers=self.reviewers()[:2]),"BLOCKED_REVIEWER_SET")
        a=self.reviewers();a[2]["role"]="A7"
        self.assertEqual(self.gate(reviewers=a),"BLOCKED_REVIEWER_SET")

    def trusted_round(self):
        return s.record_trusted_final_round(
            self.db,run_id="r1",frozen_snapshot="snap1",active_snapshot="snap1",
            master_checksum="sha:master",reviewers=self.reviewers(),required_evidence=True,
            media_capabilities_verified=True,expected_slots=[],delivered_slots=[],
            trusted_backend_verifier=True)

    def test_duplicate_expected_slot_blocks_mount(self):
        duplicate=[{"slot_id":"shot1","required":True,"revision":"v1","checksum":"h"},
                   {"slot_id":"shot1","required":True,"revision":"v1","checksum":"h"}]
        supplied=[{"slot_id":"shot1","revision":"v1","checksum":"h","status":"FULFILLED"}]
        self.assertFalse(s.complete_manifest(duplicate,supplied))

    def test_trusted_round_cannot_be_replaced_with_new_master(self):
        self.trusted_round()
        with self.assertRaises(s.Conflict):
            s.record_trusted_final_round(
                self.db,run_id="r1",frozen_snapshot="snap1",active_snapshot="snap1",
                master_checksum="sha:DIFFERENT",
                reviewers=[{**x,"master_checksum":"sha:DIFFERENT"} for x in self.reviewers()],
                required_evidence=True,media_capabilities_verified=True,
                expected_slots=[],delivered_slots=[],trusted_backend_verifier=True)

    def test_owner_ready_without_persisted_media_gate_blocked(self):
        with self.assertRaises(s.Blocked):
            s.owner_ready(self.db,decision_id="unsafe",owner_id="person",run_id="r1",
                          snapshot_sha="snap1",gate_result="AWAITING_OWNER_APPROVAL",
                          owner_session_verified=True)

    def test_trusted_round_cannot_be_claimed_by_n8n(self):
        with self.assertRaises(s.Blocked):
            s.record_trusted_final_round(
                self.db,run_id="r1",frozen_snapshot="snap1",active_snapshot="snap1",
                master_checksum="sha:master",reviewers=self.reviewers(),required_evidence=True,
                media_capabilities_verified=True,expected_slots=[],delivered_slots=[],
                trusted_backend_verifier=False)

    def test_owner_ready_idempotent_and_stale_denied(self):
        self.trusted_round()
        with self.assertRaises(s.Blocked):
            s.owner_ready(self.db,decision_id="d1",owner_id="person",run_id="r1",snapshot_sha="snap1",
                          gate_result="AWAITING_OWNER_APPROVAL",owner_session_verified=False)
        self.assertTrue(s.owner_ready(self.db,decision_id="d1",owner_id="person",run_id="r1",snapshot_sha="snap1",
                                      gate_result="AWAITING_OWNER_APPROVAL",owner_session_verified=True))
        self.assertFalse(s.owner_ready(self.db,decision_id="d1",owner_id="person",run_id="r1",snapshot_sha="snap1",
                                       gate_result="AWAITING_OWNER_APPROVAL",owner_session_verified=True))
        with self.assertRaises(s.Conflict):
            s.owner_ready(self.db,decision_id="d2",owner_id="person",run_id="r1",snapshot_sha="snap1",
                          gate_result="AWAITING_OWNER_APPROVAL",owner_session_verified=True)

    def test_changed_canon_invalidates_owner_decision(self):
        s.update_snapshot(self.db,run_id="r1",expected_snapshot="snap1",
                          new_snapshot="canon-revised",new_source_revision="v2")
        with self.assertRaises(s.Conflict):
            s.owner_ready(self.db,decision_id="d1",owner_id="person",run_id="r1",snapshot_sha="snap1",
                          gate_result="AWAITING_OWNER_APPROVAL",owner_session_verified=True)


if __name__=="__main__":
    unittest.main()
