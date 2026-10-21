import fnmatch
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
import yaml
from tools import check_agent_scope as scope, check_ci_contracts as contracts, check_no_secrets as scanner

manifest = json.loads(Path(scope.MANIFEST_PATH).read_text(encoding='utf8'))
assert scope.forbidden_files('minimax/ga-05-probe', ['backend/main.py'], manifest) == ['backend/main.py']
assert scope.forbidden_files('minimax/ga-05-probe', ['backend/remote_access.py'], manifest) == []
assert scope.forbidden_files('minimax/ga-05-probe', ['canon/example.json'], manifest) == ['canon/example.json']
print(json.dumps({'case':'normal_scope_allow_deny', 'passed':True}))

with tempfile.TemporaryDirectory(prefix='scope-proof-') as temp:
    root = Path(temp)
    def git(*args):
        r = subprocess.run(['git', '-c', 'user.name=Review Fixture', '-c', 'user.email=review@example.invalid', *args], cwd=root, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return r.stdout.strip()
    git('init')
    (root/'tools').mkdir()
    code = Path(scope.__file__).read_text(encoding='utf8')
    (root/scope.MANIFEST_PATH).write_text(json.dumps(manifest), encoding='utf8')
    (root/'tools/check_agent_scope.py').write_text(code, encoding='utf8')
    git('add', 'tools/check_agent_scope.py', scope.MANIFEST_PATH)
    git('commit', '-m', 'trusted base fixture')
    git('update-ref', 'refs/remotes/origin/mavis/work', 'HEAD')
    (root/'backend').mkdir()
    (root/'backend/main.py').write_text('# outside ga-05 scope fixture\n', encoding='utf8')
    bypass = code.replace('    role = role_for_branch(branch)\n', '    return []\n    role = role_for_branch(branch)\n', 1)
    assert bypass != code
    (root/'tools/check_agent_scope.py').write_text(bypass, encoding='utf8')
    git('add', 'backend/main.py', 'tools/check_agent_scope.py')
    git('commit', '-m', 'untrusted pull request fixture')
    r = subprocess.run([sys.executable, 'tools/check_agent_scope.py', '--branch', 'minimax/ga-05-probe', '--base', 'mavis/work'], cwd=root, capture_output=True, text=True)
    print(json.dumps({'case':'head_checker_bypass_with_base_manifest', 'exit':r.returncode, 'output':r.stdout.strip()}))
    assert r.returncode == 0 and 'forbidden=0' in r.stdout

workflow = yaml.safe_load(Path('.github/workflows/studio-offline-ci.yml').read_text(encoding='utf8'))
patterns = workflow[True]['pull_request']['paths']
for path in ('backend/main.py','backend/llm_guard.py','backend/character_voice.py','backend/spend_ledger.py','frontend/src/StageSummary.tsx','docs/only.md','.github/workflows/studio-offline-ci.yml','tools/check_agent_scope.py'):
    matches = any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)
    print(json.dumps({'case':'path_filter', 'path':path, 'runs_heavy':matches}))

fixture = 'this-is-a-synthetic-secret'
sample = "api_key = '" + fixture + "'"
assert scanner.scan_text(sample, 'fixture.py')
assert not any(fixture in finding for finding in scanner.scan_text(sample, 'fixture.py'))
for path in ('frontend/src/releaseGate.test.mjs','frontend/releaseGate.test.mjs','backend/test_release_gate.py'):
    bad = scope.forbidden_files('minimax/ga-03-probe', [path], manifest)
    print(json.dumps({'case':'future_ga03_scope', 'path':path, 'allowed':not bad}))

import re
matches = []
for name in ('banana-prompting.html','banana21-model.html','banana-framework.html'):
    values = re.findall(r'AIza[0-9A-Za-z_-]{35}', (Path('docs/official-prompts') / name).read_text(encoding='utf8'))
    matches.extend(values)
    print(json.dumps({'case':'legacy_google_key_patterns', 'file':name, 'occurrences':len(values)}))
print(json.dumps({'case':'legacy_google_key_patterns_total', 'occurrences':len(matches), 'distinct_strings':len(set(matches)), 'validity_tested':False}))
