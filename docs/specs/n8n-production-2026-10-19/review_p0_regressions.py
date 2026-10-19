"""Acceptance regressions from Codex review; temporary SQLite only, no providers.

Run from repository root with: python -m unittest discover -s
docs/specs/n8n-production-2026-10-19 -p review_p0_regressions.py -v
These tests intentionally expose uncorrected defects in the reviewed draft.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend import p0_control as p
from backend import test_p0_control as fixtures
from scripts.p0_migrate import migrate


class DraftAcceptanceRegressions(unittest.TestCase):
    def setUp(self):
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

    def test_missing_planned_slot_cannot_pass_manifest(self):
        expected_slots = {"shot_01", "shot_02"}
        self.db.execute("""INSERT INTO p0_scene_manifest
            (run_id,slot_id,kind,required,source_revision,asset_sha,status,updated_at_ms)
            VALUES ('r1','shot_01','shot',1,'v1','hash1','FULFILLED',0)""")
        actual_slots = {r[0] for r in self.db.execute("SELECT slot_id FROM p0_scene_manifest")}
        self.assertTrue(expected_slots - actual_slots)
        self.assertFalse(p.manifest_ready(self.db, run_id="r1", expected_source_revision="v1"),
                         "No frozen expected manifest exists to detect missing shot_02")

    def test_failed_migration_leaves_schema_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "copy.sqlite3"
            db = p.open_db(path)
            try:
                db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY, payload TEXT)")
                db.execute("INSERT INTO jobs VALUES('legacy', 'preserve')")
                db.execute("CREATE TABLE p0_jobs(job_id TEXT PRIMARY KEY)")
                before = list(db.execute("SELECT name, sql FROM sqlite_master ORDER BY name"))
            finally:
                db.close()
            with self.assertRaises(sqlite3.OperationalError):
                migrate(path, apply=True, backup_path=Path(folder) / "backup.sqlite3")
            db = p.open_db(path)
            try:
                self.assertEqual(db.execute("SELECT payload FROM jobs").fetchone()[0], "preserve")
                after = list(db.execute("SELECT name, sql FROM sqlite_master ORDER BY name"))
                self.assertEqual([tuple(r) for r in after], [tuple(r) for r in before],
                                 "Migration failure must not leave partially applied DDL")
            finally:
                db.close()
