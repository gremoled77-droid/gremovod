"""Preview by default. --apply snapshots SQLite and character files before changing ownership."""
import argparse
import json
import sqlite3
import sys
import zipfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import main
from backend.production_workspace import promote_workspace, sync_workspace_documents


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--production', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--expected-source', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--archive-source', action='store_true', help='Hide the old test project and frame, retaining files and costs')
    args = parser.parse_args()
    preview = promote_workspace(main, args.production, args.target, args.expected_source)
    print(json.dumps(preview, ensure_ascii=False, indent=2))
    if not args.apply or preview['already_applied']:
        return
    root = Path(__file__).resolve().parents[1]
    backup = root / 'runtime' / 'backups' / ('workspace-promotion-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(parents=True, exist_ok=False)
    with sqlite3.connect(main.DB) as source, sqlite3.connect(backup / 'studio.sqlite3') as destination:
        source.backup(destination)
    with zipfile.ZipFile(backup / 'character-and-project-documents.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for pid in (args.expected_source, args.target):
            directory = main.CHAR_ROOT / pid
            if directory.is_dir():
                for path in directory.rglob('*'):
                    if path.is_file(): archive.write(path, 'character_library/' + path.relative_to(main.CHAR_ROOT).as_posix())
        for path in main.PRODUCTIONS_ROOT.rglob('*'):
            if path.is_file() and path.suffix.lower() in {'.json', '.md'}:
                archive.write(path, 'projects/' + path.relative_to(main.PRODUCTIONS_ROOT).as_posix())
    (backup / 'plan.json').write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding='utf-8')
    result = promote_workspace(main, args.production, args.target, args.expected_source, apply=True)
    if args.archive_source:
        with main.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS project_archives(project_id TEXT PRIMARY KEY,reason TEXT NOT NULL,archived_at TEXT NOT NULL)')
            db.execute('INSERT OR IGNORE INTO project_archives VALUES(?,?,?)', (args.expected_source, 'Тест Seedream Lite; персонаж перенесён в общий GremoVOD', main.now()))
    sync_workspace_documents(main, args.production)
    print('Backup:', backup)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
