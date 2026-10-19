"""Plan draft skill updates from a pinned Git commit. Never calls n8n or creates skills."""
import argparse
import hashlib
import json
import posixpath
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root).decode('utf-8')


def package(root, commit, name):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,99}', name):
        raise ValueError('Invalid skill name')
    prefix = f'skills/{name}/'
    tree = git(root, 'ls-tree', '-rz', commit, '--', 'skills', 'docs')
    blobs = {}
    for line in tree.split('\0'):
        if not line:
            continue
        meta, path = line.split('\t', 1)
        mode, kind, sha = meta.split()
        if mode == '100644' and kind == 'blob' and path.endswith('.md'):
            blobs[path] = sha
    entry = prefix + 'SKILL.md'
    pending = {entry} | {p for p in blobs if p.startswith(prefix + 'references/')}
    files = {}
    while pending:
        path = min(pending)
        pending.remove(path)
        if path in files:
            continue
        if path not in blobs:
            raise ValueError(f'Missing or unsupported reference: {path}')
        text = git(root, 'cat-file', 'blob', blobs[path])
        if len(text) > 200000 or len(files) >= 300:
            raise ValueError('Skill package exceeds review limits')
        files[path] = text
        for link in re.findall(r'\]\(([^)]+)\)', text):
            if '://' in link or link.startswith('#'):
                continue
            target = posixpath.normpath(posixpath.join(posixpath.dirname(path), unquote(link.split('#')[0])))
            if target not in files:
                pending.add(target)
    # shortcut: repository single-line YAML fields only; block complex frontmatter until a YAML parser is available.
    match = re.match(r'\A---\n(.*?)\n---\n', files[entry], re.S)
    fields = {}
    if match:
        for line in match[1].splitlines():
            key, sep, value = line.partition(':')
            if key not in {'name', 'description'} or not sep or not value.strip() or value.strip()[0] in '|>':
                raise ValueError('Unsupported frontmatter; adapt and review before sync')
            fields[key] = value.strip().strip('\"\'')
    if fields.get('name') != name or not fields.get('description'):
        raise ValueError('Missing name/description frontmatter')
    hashes = {p: hashlib.sha256(text.encode()).hexdigest() for p, text in sorted(files.items())}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'name': name, 'description': fields['description'], 'content_sha256': digest,
            'files': hashes, 'source_commit_sha': commit, 'package_version': 1}


def plan(root, commit, manifest, bindings):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Use a full pinned commit SHA')
    if git(root, 'rev-parse', commit + '^{commit}').strip() != commit:
        raise ValueError('Commit not available locally')
    existing = {}
    for binding in bindings:
        if not all(isinstance(binding.get(k), str) and binding[k] for k in ('agent_id', 'name', 'skill_id')):
            raise ValueError('Bindings require nonempty agent_id, name and skill_id')
        key = (binding['agent_id'], binding['name'])
        if key in existing or any(b['agent_id'] == binding['agent_id'] and b['skill_id'] == binding['skill_id'] for b in existing.values()):
            raise ValueError('Duplicate skill binding')
        existing[key] = binding
    changes = []
    seen = set()
    for agent in manifest['agents']:
        for skill in agent['skills']:
            if not skill['source'].startswith('https://github.com/gremoled77-droid/gremovod/blob/'):
                continue
            key = (agent['id'], skill['name'])
            if key in seen:
                raise ValueError('Duplicate skill assignment')
            seen.add(key)
            row = {'agent_id': agent['id'], 'name': skill['name'], 'publish': False}
            try:
                row.update(package(root, commit, skill['name']))
                bound = existing.get(key)
                if not bound:
                    row['action'] = 'bind_existing'
                elif bound.get('content_sha256') == row['content_sha256']:
                    row.update(action='noop', skill_id=bound['skill_id'])
                elif not all(bound.get(k) for k in ('skill_id', 'baseSkillHash', 'baseConfigHash')):
                    row.update(action='blocked', error='Refresh remote skill/config hashes before updating')
                else:
                    row.update(action='update_draft', **{k: bound[k] for k in ('skill_id', 'baseSkillHash', 'baseConfigHash')})
            except ValueError as exc:
                row.update(action='blocked', error=str(exc))
            changes.append(row)
    return {'source_commit_sha': commit, 'mode': 'plan_only', 'changes': changes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--bindings', type=Path, required=True, help='Local JSON list of existing skill IDs and concurrency hashes')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(git(root, 'show', args.commit + ':integrations/n8n/agent-manifest.json'))
    print(json.dumps(plan(root, args.commit, manifest, json.loads(args.bindings.read_text(encoding='utf-8'))), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
