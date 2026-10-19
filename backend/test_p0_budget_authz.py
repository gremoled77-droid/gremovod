"""Regressions for R-05 (trust from the caller), R-04 (two budget counters) and
P0-DB (a second writable Studio database). Temporary SQLite only, no providers.

Each test states the defect it closes, so a reviewer can check the fix without
reading the whole history.
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend import p0_authz, p0_control as p, spend_ledger, studio_db
from backend import test_p0_control as fixtures
from scripts.p0_migrate import migrate

MOSCOW = timezone(timedelta(hours=3))


class P0TrustAndBudgetTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.P0SafetyTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db = self.fixture.db

    # ---------------------------------------------------------------- R-05

    def test_caller_supplied_owner_flag_is_refused(self):
        """R-05: a boolean from an HTTP/n8n body is not a permission."""
        with self.assertRaises(p.Blocked):
            p.create_envelope(self.db, envelope_id="evil", run_id="r1", owner_decision_ref="fake",
                              cap_cents=10, max_calls=1, max_attempts_per_slot=1, stage="N29",
                              provider="mock", model="video-mock", expires_at_ms=p.now_ms() + 9000,
                              trusted_studio_owner=True)
        self.assertIsNone(self.fixture.row("p0_budget_envelopes", "envelope_id", "evil"))

    def test_forged_owner_capability_is_refused(self):
        with self.assertRaises(p.Blocked):
            p.create_envelope(self.db, envelope_id="evil", run_id="r1", owner_decision_ref="fake",
                              cap_cents=10, max_calls=1, max_attempts_per_slot=1, stage="N29",
                              provider="mock", model="video-mock", expires_at_ms=p.now_ms() + 9000,
                              owner_capability="forged-owner-capability")

    def test_owner_capability_is_bound_to_its_envelope(self):
        """An approval for one grant must not open another."""
        capability = p0_authz.mint_owner_capability(
            "r1", envelope_id="other", cap_cents=500, stage="N29", provider="mock", model="video-mock")
        with self.assertRaises(p.Blocked):
            p.create_envelope(self.db, envelope_id="evil", run_id="r1", owner_decision_ref="owner-session-decision",
                              cap_cents=500, max_calls=2, max_attempts_per_slot=1, stage="N29",
                              provider="mock", model="video-mock", expires_at_ms=p.now_ms() + 90000,
                              owner_capability=capability)

    def test_expired_owner_capability_is_refused(self):
        capability = p0_authz.mint_owner_capability(
            "r1", envelope_id="env2", cap_cents=500, stage="N29", provider="mock", model="video-mock",
            ttl_ms=-1)
        with self.assertRaises(p.Blocked):
            p.create_envelope(self.db, envelope_id="env2", run_id="r1", owner_decision_ref="owner-session-decision",
                              cap_cents=500, max_calls=2, max_attempts_per_slot=1, stage="N29",
                              provider="mock", model="video-mock", expires_at_ms=p.now_ms() + 90000,
                              owner_capability=capability)

    def test_caller_supplied_request_flag_is_refused(self):
        self.fixture.intent()
        with self.assertRaises(p.Blocked):
            p.authorize(self.db, job_id="j1", request_sha="requestA", profile_revision="prof1",
                        upper_cents=100, trusted_studio_request_authorization=True)
        self.assertEqual(self.fixture.row("p0_jobs", "job_id", "j1")["state"], "INTENT_CREATED")
        self.assertEqual(self.fixture.row("p0_budget_envelopes", "envelope_id", "env")["reserved_cents"], 0)

    def test_request_capability_is_bound_to_its_request_hash(self):
        self.fixture.intent()
        capability = p0_authz.mint_request_capability("j1", request_sha="requestA", upper_cents=100)
        with self.assertRaises(p.Blocked):
            p.authorize(self.db, job_id="j1", request_sha="requestB", profile_revision="prof1",
                        upper_cents=100, request_capability=capability)
        self.assertEqual(self.fixture.row("p0_budget_envelopes", "envelope_id", "env")["reserved_cents"], 0)

    def test_request_capability_cannot_be_replayed_on_another_job(self):
        self.fixture.intent()
        self.fixture.intent("j2", "shot_02")
        capability = p0_authz.mint_request_capability("j1", request_sha="requestA", upper_cents=100)
        with self.assertRaises(p.Blocked):
            p.authorize(self.db, job_id="j2", request_sha="requestA", profile_revision="prof1",
                        upper_cents=100, request_capability=capability)
        self.assertEqual(self.fixture.row("p0_jobs", "job_id", "j2")["state"], "INTENT_CREATED")

    def test_provider_evidence_flag_is_refused(self):
        self.fixture.intent(); self.fixture.auth(); self.fixture.submit()
        p.accept_provider_id(self.db, job_id="j1", provider_job_id="provider-1")
        with self.assertRaises(p.Blocked):
            p.finish_verified(self.db, job_id="j1", event_id="event1", event_body={"status": "done"},
                              charged_cents=10, provider_success=True, provider_evidence_verified=True)

    def test_provider_evidence_needs_a_server_side_verifier(self):
        self.fixture.intent(); self.fixture.auth(); self.fixture.submit()
        p.accept_provider_id(self.db, job_id="j1", provider_job_id="provider-1")
        with self.assertRaises(p.Blocked):
            p.finish_verified(self.db, job_id="j1", event_id="event1", event_body={"status": "done"},
                              charged_cents=10, provider_success=True, verify_evidence=False)
        with self.assertRaises(p.Blocked):
            p.finish_verified(self.db, job_id="j1", event_id="event1", event_body={"status": "done"},
                              charged_cents=10, provider_success=True,
                              verify_evidence=lambda body: False)
        self.assertEqual(self.fixture.row("p0_budget_envelopes", "envelope_id", "env")["reserved_cents"], 250)

    def test_verified_evidence_settles_the_reserve(self):
        self.fixture.intent(); self.fixture.auth(); self.fixture.submit()
        p.accept_provider_id(self.db, job_id="j1", provider_job_id="provider-1")
        self.assertTrue(p.finish_verified(self.db, job_id="j1", event_id="event1",
                                          event_body={"status": "done"}, charged_cents=180,
                                          provider_success=True, verify_evidence=lambda body: True))
        envelope = self.fixture.row("p0_budget_envelopes", "envelope_id", "env")
        self.assertEqual((envelope["spent_cents"], envelope["reserved_cents"]), (180, 0))

    # ---------------------------------------------------------------- R-04

    def _legacy_approval(self, project, usd, status="completed"):
        # The shared fixture keeps a minimal legacy `jobs` table; the Studio
        # budget reads the real one, so the test installs that shape.
        self.db.execute("DROP TABLE IF EXISTS jobs")
        self.db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY, project_id TEXT, kind TEXT,"
                        " provider TEXT, task_id TEXT, status TEXT, request TEXT, response TEXT, created_at TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS generation_approvals(job_id TEXT PRIMARY KEY,"
                        " estimated_usd REAL, actual_usd REAL, created_at TEXT, note TEXT)")
        created = datetime.now(MOSCOW).isoformat()
        self.db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)",
                        ("legacy-approval-1", project, "video", "piapi", "task", status, "{}", json.dumps({}), created))
        self.db.execute("INSERT INTO generation_approvals VALUES(?,?,?,?,?)",
                        ("legacy-approval-1", usd, usd, created, "documentation_estimate"))

    def test_p0_reserve_and_legacy_approval_share_one_project_cap(self):
        """R-04: the second counter must not be able to spend what the first still allows."""
        self.db.execute("UPDATE spending_limits SET project_usd=0.5, daily_usd=0.5")
        self._legacy_approval("proj", 0.4)
        self.fixture.intent()
        with self.assertRaises(p.Blocked):
            self.fixture.auth(cents=200)  # 0.4 + 0.2 > 0.5
        self.assertEqual(self.fixture.row("p0_budget_envelopes", "envelope_id", "env")["reserved_cents"], 0)

    def test_p0_spend_is_visible_in_the_studio_budget_state(self):
        self._legacy_approval("proj", 0.25)
        self.fixture.intent()
        self.fixture.auth(cents=100)
        state = spend_ledger.state(self.db, "proj")
        self.assertAlmostEqual(state["legacy_reserved_usd"], 0.25)
        self.assertAlmostEqual(state["p0_reserved_usd"], 1.0)
        self.assertAlmostEqual(state["project_reserved_usd"], 1.25)

    def test_unknown_submit_keeps_holding_the_studio_budget(self):
        """Money reserved for an ambiguous provider call keeps blocking new spend."""
        self.db.execute("UPDATE spending_limits SET project_usd=2.6, daily_usd=2.6")
        self.fixture.intent()
        self.fixture.auth(cents=250)
        self.fixture.submit()
        p.mark_unknown(self.db, job_id="j1")
        self.fixture.intent("j2", "shot_02")
        with self.assertRaises(p.Blocked):
            self.fixture.auth("j2", cents=100)
        self.assertEqual(self.fixture.row("p0_budget_envelopes", "envelope_id", "env")["reserved_cents"], 250)

    def test_missing_spending_limits_means_no_money_at_all(self):
        self.db.execute("DROP TABLE spending_limits")
        self.fixture.intent()
        with self.assertRaises(p.Blocked):
            self.fixture.auth(cents=1)

    # ---------------------------------------------------------------- P0-DB

    def test_second_writable_database_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "shadow.sqlite3"
            with self.assertRaises(p.Blocked):
                p.open_db(path)
            db = p.open_db(path, allow_disposable=True)
            db.close()

    def test_migration_refuses_a_second_database(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "shadow.sqlite3"
            db = p.open_db(path, allow_disposable=True)
            db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY)")
            db.close()
            with self.assertRaises(p.Blocked):
                migrate(path, apply=False)

    def test_reference_pilot_refuses_a_production_database(self):
        from integrations.n8n import pilot_state_sqlite as pilot
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pilot.sqlite3"
            with self.assertRaises(pilot.Blocked):
                pilot.connect(path)
            with self.assertRaises(pilot.Blocked):
                pilot.connect(studio_db.studio_db_path(), allow_disposable=True)
            db = pilot.connect(path, allow_disposable=True)
            db.close()

    def test_studio_db_path_follows_the_studio_data_dir(self):
        import os
        previous = os.environ.get("STUDIO_DATA_DIR")
        os.environ["STUDIO_DATA_DIR"] = str(Path(tempfile.gettempdir()) / "gremovod-studio-data")
        try:
            resolved = studio_db.studio_db_path()
            self.assertEqual(resolved.name, "studio.sqlite3")
            self.assertEqual(resolved.parent.name, "gremovod-studio-data")
        finally:
            if previous is None:
                os.environ.pop("STUDIO_DATA_DIR", None)
            else:
                os.environ["STUDIO_DATA_DIR"] = previous


if __name__ == "__main__":
    unittest.main()
