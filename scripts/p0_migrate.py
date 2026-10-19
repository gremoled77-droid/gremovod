"""Opt-in additive P0 migration for the EXISTING Studio SQLite.

Default = no write. --apply first creates a consistent SQLite backup, then
installs p0_* tables. Never used at API startup or through n8n/LLM.
"""
import argparse
import sqlite3
from pathlib import Path

from backend import p0_control as p
from backend import studio_db

TABLES={"p0_runs","p0_budget_envelopes","p0_jobs","p0_scene_manifest","p0_review_snapshots"}


def inspect(db):
    names={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {"existing_tables":len(names),"has_legacy_jobs":"jobs" in names,
            "p0_tables":sorted(names & TABLES),"missing_p0_tables":sorted(TABLES-names),
            "integrity":db.execute("PRAGMA quick_check").fetchone()[0]}


def migrate(path: Path, *, apply: bool, backup_path: Path | None = None,
            allow_disposable: bool = False):
    try:
        path=studio_db.resolve(path, allow_disposable=allow_disposable)
    except studio_db.ShadowState as exc:
        raise p.Blocked(str(exc)) from None
    if not path.is_file():
        raise FileNotFoundError(f"Studio DB not found: {path}")
    db=p.open_db(path,allow_disposable=True)
    try:
        before=inspect(db)
        if before["integrity"]!="ok":
            raise RuntimeError("SQLite integrity failure: refusing migration")
        if not apply:
            return {"mode":"DRY_RUN_NO_WRITES","database":str(path),"before":before}
        backup=backup_path.resolve() if backup_path else path.with_name(path.name+".p0-backup.sqlite3")
        if backup==path or backup.exists():
            raise FileExistsError("Backup must be a new, distinct path")
        backup.parent.mkdir(parents=True,exist_ok=True)
        with backup.open("xb"):
            pass  # Reserve the backup name exclusively before SQLite opens it.
        dest=p.open_db(backup,allow_disposable=True)
        try:
            db.backup(dest)  # includes WAL state, produces a consistent snapshot
        finally:
            dest.close()
        p.install_schema(db)  # Preflight + DDL + integrity check commit or roll back together.
        return {"mode":"APPLIED_WITH_BACKUP","database":str(path),
                "backup":str(backup),"before":before,"after":inspect(db)}
    finally:
        db.close()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description="Safe P0 Studio SQLite additive migration")
    parser.add_argument("--db",required=True,type=Path)
    parser.add_argument("--apply",action="store_true",help="Explicitly modify DB after snapshot backup")
    parser.add_argument("--backup",type=Path,help="New backup pathname (must not exist)")
    args=parser.parse_args()
    import json
    print(json.dumps(migrate(args.db,apply=args.apply,backup_path=args.backup),
                     ensure_ascii=False,indent=2))
