"""Одноразовая интеграционная копия кандидата BETA-02: закреплённые SHA сливаются по порядку.

Ничего не публикует и не меняет исходные ветки: `git worktree add --detach` во временную папку и
`git merge` закреплённых коммитов. Сборка идёт только по точным SHA и останавливается на первом расхождении:

- манифест: полный SHA (40 hex), без повторов SHA и PR;
- каждый SHA — существующий коммит, и `git rev-parse` возвращает ровно его;
- дрейф: голова `origin/<ветка>` обязана совпадать с закреплённым SHA (нужен свежий `git fetch`;
  сеть сама команда не трогает). Расхождение = повторная оценка, а не сборка по старому SHA;
- после checkout HEAD равен базе, после каждого merge закреплённый коммит — предок HEAD;
- `--harness <sha>` — коммит самого гейта (ветка #88), сливается последним с теми же проверками.

    python tools/beta02_candidate.py --dest <папка вне репозитория> [--harness <sha>] [--sources tools/beta02_sources.json]
Код выхода 0 — копия собрана и проверена, 1 — нет. Удаление копии вручную: `git worktree remove --force <папка>`.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r'^[0-9a-f]{40}$')
# Переменные, которыми git можно незаметно направить в другой репозиторий или индекс.
GIT_REDIRECTS = ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY',
                 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_COMMON_DIR', 'GIT_NAMESPACE', 'GIT_CEILING_DIRECTORIES')


def git(args, cwd):
    env = {key: value for key, value in os.environ.items() if key not in GIT_REDIRECTS}
    return subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True, env=env)


def manifest_errors(manifest):
    """Ошибки формы манифеста. Пустой список — манифест годен. Чистая функция."""
    errors = []
    if not isinstance(manifest, dict) or manifest.get('version') != 1:
        return ['манифест: нужен объект с version=1']
    base, sources = manifest.get('base'), manifest.get('sources')
    if not isinstance(base, dict) or not isinstance(base.get('branch'), str) or not base.get('branch'):
        errors.append('base: нужна ветка')
    if not isinstance(base, dict) or not isinstance(base.get('sha'), str) or not SHA.match(base.get('sha', '')):
        errors.append('base: SHA должен быть полным (40 символов hex, нижний регистр)')
    if not isinstance(sources, list) or not sources:
        return errors + ['sources: нужен непустой список']
    seen_sha, seen_pr = {base.get('sha') if isinstance(base, dict) else None}, set()
    for index, item in enumerate(sources):
        name = f'sources[{index}]'
        if not isinstance(item, dict):
            errors.append(f'{name}: нужен объект')
            continue
        if type(item.get('pr')) is not int or item['pr'] <= 0:
            errors.append(f'{name}: pr — положительное целое')
        elif item['pr'] in seen_pr:
            errors.append(f'{name}: PR #{item["pr"]} повторяется')
        else:
            seen_pr.add(item['pr'])
        if not isinstance(item.get('branch'), str) or not item.get('branch'):
            errors.append(f'{name}: нужна ветка')
        sha = item.get('sha')
        if not isinstance(sha, str) or not SHA.match(sha):
            errors.append(f'{name}: SHA должен быть полным (40 символов hex, нижний регистр)')
        elif sha in seen_sha:
            errors.append(f'{name}: SHA {sha[:12]} повторяется')
        else:
            seen_sha.add(sha)
    return errors


def load_manifest(path):
    """(манифест, ошибки). Нечитаемый или неверный манифест — ошибки, а не исключение."""
    try:
        manifest = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        return None, [f'манифест не прочитан: {type(error).__name__}']
    return manifest, manifest_errors(manifest)


def commit_exists(sha, cwd):
    """SHA — существующий коммит, и git разрешает его ровно в этот SHA."""
    done = git(['rev-parse', '--verify', '--quiet', f'{sha}^{{commit}}'], cwd)
    return done.returncode == 0 and done.stdout.strip() == sha


def remote_head(branch, cwd):
    """Голова origin/<ветка> по локальным ссылкам (без сети) или None, если ссылки нет."""
    done = git(['rev-parse', '--verify', '--quiet', f'refs/remotes/origin/{branch}^{{commit}}'], cwd)
    return done.stdout.strip() if done.returncode == 0 and SHA.match(done.stdout.strip()) else None


def is_ancestor(sha, cwd):
    """True / False / None (git не смог ответить: неизвестный коммит или сбой)."""
    code = git(['merge-base', '--is-ancestor', sha, 'HEAD'], cwd).returncode
    return {0: True, 1: False}.get(code)


def check_pins(manifest, cwd):
    """Сверка каждого закреплённого SHA: существует ли и совпадает ли с головой origin/<ветка>."""
    rows = []
    for item in [{'pr': None, **manifest['base']}, *manifest['sources']]:
        head = remote_head(item['branch'], cwd)
        row = {'pr': item['pr'], 'branch': item['branch'], 'sha': item['sha'], 'exists': commit_exists(item['sha'], cwd),
               'remote_head': head, 'drift': None if head is None else head != item['sha']}
        if not row['exists']:
            row['problem'] = 'коммит не найден: выполни git fetch origin ' + item['branch']
        elif head is None:
            row['problem'] = f'нет ссылки origin/{item["branch"]}: дрейф не проверен (git fetch origin {item["branch"]})'
        elif row['drift']:
            row['problem'] = f'дрейф: origin/{item["branch"]} = {head[:12]}, закреплён {item["sha"][:12]}'
        rows.append(row)
    return rows


def build(dest: Path, sources: Path, harness: str = '', allow_drift: bool = False, root: Path = ROOT):
    manifest, errors = load_manifest(sources)
    log = {'sources': str(sources), 'dest': str(dest), 'merges': [], 'status': 'OK', 'allow_drift': allow_drift}
    if harness and not SHA.match(harness):
        errors = [*errors, '--harness: нужен полный SHA (40 символов hex, нижний регистр)']
    if errors:
        return {**log, 'status': 'INVALID', 'errors': errors}
    log['base'] = manifest['base']
    pins = check_pins(manifest, root)
    log['pins'] = pins
    missing = [row for row in pins if not row['exists']]
    if harness and not commit_exists(harness, root):
        missing.append({'sha': harness, 'problem': 'коммит гейта не найден'})
    if missing:
        return {**log, 'status': 'ERROR', 'errors': [row['problem'] for row in missing]}
    unchecked = [row['problem'] for row in pins if 'problem' in row]
    if unchecked and not allow_drift:
        return {**log, 'status': 'DRIFT', 'errors': unchecked}
    if dest.exists():
        return {**log, 'status': 'ERROR', 'errors': ['папка назначения уже существует']}
    made = git(['worktree', 'add', '--detach', str(dest), manifest['base']['sha']], root)
    if made.returncode:
        return {**log, 'status': 'ERROR', 'errors': [made.stderr.strip()[-300:]]}
    head = git(['rev-parse', 'HEAD'], dest).stdout.strip()
    if head != manifest['base']['sha']:
        return {**log, 'status': 'ERROR', 'errors': [f'после checkout HEAD {head[:12]} не равен базе']}
    plan = [{'pr': item['pr'], 'sha': item['sha']} for item in manifest['sources']]
    if harness:
        plan.append({'pr': 'harness', 'sha': harness})
    for item in plan:
        merged = git(['-c', 'user.name=beta02', '-c', 'user.email=beta02@localhost', 'merge', '--no-edit', '-q', item['sha']], dest)
        entry = {'pr': item['pr'], 'sha': item['sha']}
        if merged.returncode:
            unmerged = git(['diff', '--name-only', '--diff-filter=U'], dest).stdout.split()
            entry.update(result='CONFLICT' if unmerged else 'ERROR', files=unmerged,
                         error='' if unmerged else merged.stderr.strip()[-300:])
            git(['merge', '--abort'], dest)
            log['merges'].append(entry)
            log['status'] = entry['result']
            break
        if is_ancestor(item['sha'], dest) is not True:
            entry['result'] = 'ERROR'
            entry['error'] = 'после merge закреплённый коммит не является предком HEAD'
            log['merges'].append(entry)
            log['status'] = 'ERROR'
            break
        entry['result'] = 'CLEAN'
        log['merges'].append(entry)
    log['head'] = git(['rev-parse', 'HEAD'], dest).stdout.strip()
    if log['status'] == 'OK':
        absent = [item['sha'][:12] for item in [manifest['base'], *plan] if is_ancestor(item['sha'], dest) is not True]
        if absent:
            log['status'], log['errors'] = 'ERROR', ['в итоговом дереве нет коммитов: ' + ', '.join(absent)]
        if git(['status', '--porcelain'], dest).stdout.strip():
            log['status'], log['errors'] = 'ERROR', [*log.get('errors', []), 'копия грязная после сборки']
    return log


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dest', required=True)
    parser.add_argument('--sources', default=str(ROOT / 'tools' / 'beta02_sources.json'))
    parser.add_argument('--harness', default='', help='полный SHA коммита гейта (ветка PR #88), сливается последним')
    parser.add_argument('--allow-drift', action='store_true',
                        help='собрать по закреплённым SHA, даже если origin ушёл вперёд (только для воспроизведения; гейт даст BLOCKED)')
    args = parser.parse_args(argv)
    log = build(Path(args.dest).resolve(), Path(args.sources), args.harness, args.allow_drift)
    print(json.dumps(log, ensure_ascii=False, indent=2))
    return 0 if log['status'] == 'OK' else 1


if __name__ == '__main__':
    sys.exit(main())
