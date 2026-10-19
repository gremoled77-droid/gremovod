"""Dry run, snapshot-backup, additive schema and prior jobs intact."""
import tempfile
import unittest
from pathlib import Path
from backend import p0_control
from scripts.p0_migrate import migrate


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.path=self.folder/"studio.sqlite3"
        db=p0_control.open_db(self.path)
        db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        db.execute("INSERT INTO jobs VALUES ('legacy-job','keep it intact')")
        db.close()

    def test_dry_run_does_not_add_tables(self):
        before=migrate(self.path,apply=False)
        self.assertEqual(before["mode"],"DRY_RUN_NO_WRITES")
        db=p0_control.open_db(self.path)
        try:
            self.assertFalse([r for r in db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'p0_%'")])
            self.assertEqual(db.execute("SELECT payload FROM jobs").fetchone()[0],"keep it intact")
        finally:
            db.close()

    def test_online_backup_and_additive_schema(self):
        backup=self.folder/"safe-backup.sqlite3"
        result=migrate(self.path,apply=True,backup_path=backup)
        self.assertEqual(result["mode"],"APPLIED_WITH_BACKUP")
        self.assertEqual(len(result["after"]["p0_tables"]),5)
        original=p0_control.open_db(backup)
        migrated=p0_control.open_db(self.path)
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
            migrate(self.path,apply=True,backup_path=backup)
        self.assertEqual(backup.read_text(),"important preexisting backup")

    def test_refuses_nonexistent_source(self):
        with self.assertRaises(FileNotFoundError):
            migrate(self.folder/"absent.sqlite3",apply=False)


if __name__=="__main__":
    unittest.main()
