"""Dry run, snapshot-backup, additive schema and prior jobs intact."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend import p0_control
from scripts.p0_migrate import migrate


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.path=self.folder/"studio.sqlite3"
        db=p0_control.open_db(self.path, allow_disposable=True)
        db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        db.execute("INSERT INTO jobs VALUES ('legacy-job','keep it intact')")
        db.close()

    def test_dry_run_does_not_add_tables(self):
        before=migrate(self.path,apply=False,allow_disposable=True)
        self.assertEqual(before["mode"],"DRY_RUN_NO_WRITES")
        db=p0_control.open_db(self.path, allow_disposable=True)
        try:
            self.assertFalse([r for r in db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'p0_%'")])
            self.assertEqual(db.execute("SELECT payload FROM jobs").fetchone()[0],"keep it intact")
        finally:
            db.close()

    def test_online_backup_and_additive_schema(self):
        backup=self.folder/"safe-backup.sqlite3"
        result=migrate(self.path,apply=True,backup_path=backup,allow_disposable=True)
        self.assertEqual(result["mode"],"APPLIED_WITH_BACKUP")
        self.assertEqual(len(result["after"]["p0_tables"]),5)
        original=p0_control.open_db(backup, allow_disposable=True)
        migrated=p0_control.open_db(self.path, allow_disposable=True)
        try:
            self.assertEqual(original.execute("SELECT payload FROM jobs").fetchone()[0],"keep it intact")
            self.assertEqual(migrated.execute("SELECT payload FROM jobs").fetchone()[0],"keep it intact")
            self.assertEqual(original.execute("SELECT name FROM sqlite_master WHERE name='p0_runs'").fetchone(),None)
            self.assertIsNotNone(migrated.execute("SELECT name FROM sqlite_master WHERE name='p0_runs'").fetchone())
        finally:
            original.close()
            migrated.close()

    def test_does_not_overwrite_existing_backup(self):
        backup=self.folder/"backup.sqlite3"
        backup.write_text("important preexisting backup")
        with self.assertRaises(FileExistsError):
            migrate(self.path,apply=True,backup_path=backup,allow_disposable=True)
        self.assertEqual(backup.read_text(),"important preexisting backup")

    def test_refuses_nonexistent_source(self):
        with self.assertRaises(FileNotFoundError):
            migrate(self.folder/"absent.sqlite3",apply=False,allow_disposable=True)

    def test_mid_ddl_failure_rolls_back_every_created_table(self):
        db=p0_control.open_db(self.path, allow_disposable=True)
        try:
            before=db.execute("SELECT name,sql FROM sqlite_master ORDER BY name").fetchall()
            def deny_index(action, name, *_):
                return sqlite3.SQLITE_DENY if action==sqlite3.SQLITE_CREATE_INDEX and name=='idx_p0_jobs_run_state' else sqlite3.SQLITE_OK
            db.set_authorizer(deny_index)
            with self.assertRaises(sqlite3.DatabaseError):
                p0_control.install_schema(db)
            db.set_authorizer(None)
            self.assertFalse(db.in_transaction)
            after=db.execute("SELECT name,sql FROM sqlite_master ORDER BY name").fetchall()
            self.assertEqual([tuple(r) for r in after],[tuple(r) for r in before])
            self.assertEqual(db.execute("SELECT payload FROM jobs").fetchone()[0],"keep it intact")
        finally:
            db.close()

    def test_previous_p0_schema_upgrade_preserves_runs_and_backup(self):
        old_schema=p0_control.SCHEMA.read_text(encoding="utf-8").replace(
            ",\n  expected_media_manifest TEXT      -- frozen source snapshot + complete slot plan; NULL blocks assembly", "")
        db=p0_control.open_db(self.path, allow_disposable=True)
        try:
            db.executescript(old_schema)
            p0_control.create_run(db,run_id="old-run",project_id="proj",snapshot_sha="snap",source_revision="v1")
        finally:
            db.close()
        backup=self.folder/"v1-backup.sqlite3"
        migrate(self.path,apply=True,backup_path=backup,allow_disposable=True)
        db=p0_control.open_db(self.path, allow_disposable=True)
        original=p0_control.open_db(backup, allow_disposable=True)
        try:
            row=db.execute("SELECT * FROM p0_runs WHERE run_id='old-run'").fetchone()
            self.assertEqual(row["snapshot_sha"],"snap")
            self.assertIsNone(row["expected_media_manifest"])
            self.assertFalse(p0_control.manifest_ready(db,run_id="old-run",expected_source_revision="v1"))
            self.assertNotIn("expected_media_manifest",{r[1] for r in original.execute("PRAGMA table_info(p0_runs)")})
            p0_control.install_schema(db)
        finally:
            original.close()
            db.close()

    def test_failed_upgrade_rolls_back_added_column(self):
        db=p0_control.open_db(self.path, allow_disposable=True)
        try:
            # Real legacy schema before the new frozen manifest column existed.
            schema=p0_control.SCHEMA.read_text(encoding="utf-8").replace(
                ",\n  expected_media_manifest TEXT      -- frozen source snapshot + complete slot plan; NULL blocks assembly", "")
            db.executescript(schema)
            def deny_integrity_check(action, name, *_):
                return sqlite3.SQLITE_DENY if action==sqlite3.SQLITE_PRAGMA and name=='quick_check' else sqlite3.SQLITE_OK
            db.set_authorizer(deny_integrity_check)
            with self.assertRaises(sqlite3.DatabaseError):
                p0_control.install_schema(db)
            db.set_authorizer(None)
            self.assertNotIn("expected_media_manifest",{r[1] for r in db.execute("PRAGMA table_info(p0_runs)")})
            self.assertFalse(db.in_transaction)
        finally:
            db.close()

    def test_install_does_not_commit_callers_transaction(self):
        db=p0_control.open_db(self.path, allow_disposable=True)
        try:
            db.execute("BEGIN")
            db.execute("INSERT INTO jobs VALUES('pending','not committed')")
            with self.assertRaises(p0_control.Blocked):
                p0_control.install_schema(db)
            db.rollback()
            self.assertIsNone(db.execute("SELECT 1 FROM jobs WHERE id='pending'").fetchone())
        finally:
            db.close()

    def test_backup_race_never_overwrites_another_file(self):
        backup=self.folder/"racing-backup.sqlite3"
        real_open=Path.open
        def race_open(path, mode='r', *args, **kwargs):
            if path==backup and mode=='xb':
                with real_open(path,'w') as output:
                    output.write('concurrently created backup')
            return real_open(path,mode,*args,**kwargs)
        with patch.object(Path,'open',race_open), self.assertRaises(FileExistsError):
            migrate(self.path,apply=True,backup_path=backup,allow_disposable=True)
        self.assertEqual(backup.read_text(),'concurrently created backup')


if __name__=="__main__":
    unittest.main()
