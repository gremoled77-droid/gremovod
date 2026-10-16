"""Reject known local data/credential paths in the staged Git changes; never print file contents."""
import subprocess
import sys
from pathlib import PurePosixPath


def blocked(path):
    parts = PurePosixPath(path.replace('\\', '/')).parts
    if not parts:
        return False
    name = parts[-1].lower()
    lower = '/'.join(parts).lower()
    prefixes = ('projects/', 'runtime/', '.worktrees/', '.venv/', 'backend/library/',
                'backend/media/', 'backend/character_library/', '.claude/')
    return (lower.startswith(prefixes) or 'node_modules' in parts
            or name.endswith('_api_key.txt')
            or (name.startswith('.env') and not name.endswith('.example'))
            or name.endswith(('.sqlite', '.sqlite3', '.sqlite3-wal', '.sqlite3-shm', '.sqlite3-journal', '.pem', '.key')))


def main():
    result = subprocess.run(['git', 'diff', '--cached', '--name-only', '--diff-filter=ACMR', '-z'],
                            check=True, capture_output=True)
    paths = [p.decode('utf-8', errors='replace') for p in result.stdout.split(b'\0') if p]
    rejected = [p for p in paths if blocked(p)]
    if rejected:
        print('Commit blocked: unstage local data/credential files; keep the files on disk.', file=sys.stderr)
        for path in rejected:
            print('  ' + path, file=sys.stderr)
        return 1
    print('Git file check: OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
