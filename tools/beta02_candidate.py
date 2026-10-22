"""Одноразовая интеграционная копия кандидата BETA-02: закреплённые SHA сливаются по порядку.

Ничего не публикует и не меняет исходные ветки: `git worktree add --detach` во временную папку и
`git merge` закреплённых коммитов. Конфликт останавливает сборку и попадает в журнал.

    python tools/beta02_candidate.py --dest <папка вне репозитория> [--sources tools/beta02_sources.json]
Удаление копии — вручную: `git worktree remove --force <папка>`.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(args, cwd):
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)


def build(dest: Path, sources: Path):
    manifest = json.loads(sources.read_text(encoding='utf-8'))
    log = {'base': manifest['base'], 'merges': [], 'status': 'OK'}
    made = git(['worktree', 'add', '--detach', str(dest), manifest['base']['sha']], ROOT)
    if made.returncode:
        return {**log, 'status': 'ERROR', 'error': made.stderr.strip()[-300:]}
    for item in manifest['sources']:
        merged = git(['-c', 'user.name=beta02', '-c', 'user.email=beta02@localhost', 'merge', '--no-edit', '-q', item['sha']], dest)
        entry = {'pr': item['pr'], 'sha': item['sha'], 'result': 'CLEAN' if merged.returncode == 0 else 'CONFLICT'}
        if merged.returncode:
            entry['files'] = git(['diff', '--name-only', '--diff-filter=U'], dest).stdout.split()
            git(['merge', '--abort'], dest)
            log['status'] = 'CONFLICT'
            log['merges'].append(entry)
            break
        log['merges'].append(entry)
    log['head'] = git(['rev-parse', 'HEAD'], dest).stdout.strip()
    return log


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dest', required=True)
    parser.add_argument('--sources', default=str(ROOT / 'tools' / 'beta02_sources.json'))
    args = parser.parse_args(argv)
    log = build(Path(args.dest).resolve(), Path(args.sources))
    print(json.dumps(log, ensure_ascii=False, indent=2))
    return 0 if log['status'] == 'OK' else 1


if __name__ == '__main__':
    sys.exit(main())
