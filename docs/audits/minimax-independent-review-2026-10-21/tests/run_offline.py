"""Run review tests against disposable Git archives; never use working Studio data."""
import argparse
from contextlib import ExitStack
import io
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import subprocess
import sys
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REFS = json.loads((PACKAGE / 'evidence/reviewed_refs.json').read_text(encoding='utf8'))


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True)
    if result.returncode:
        raise RuntimeError('Git object unavailable or command failed. Fetch the reviewed PR refs first.\n'
                           + result.stderr.decode('utf8', 'replace'))
    return result.stdout


def extract(repo, sha, target):
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('A full 40-character commit SHA is required')
    archive = git(repo, 'archive', '--format=tar', sha)
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(target, filter='data')


def forbid_external(event, args):
    if event != 'socket.connect':
        return
    address = args[1]
    if isinstance(address, tuple):
        try:
            local = ipaddress.ip_address(address[0]).is_loopback
        except ValueError:
            local = address[0] == 'localhost'
        if not local:
            raise RuntimeError('Review forbids outbound connections')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', choices=['ga01', 'ga04', 'ga05', 'combined'])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--reproduce', action='store_true', help='Characterize the reviewed bugs; exit 0 is NOT product acceptance')
    mode.add_argument('--existing', action='store_true', help='Repeat the existing reviewed pytest selection')
    parser.add_argument('--ref', help='Full SHA of a later candidate for regression retest; not valid for combined')
    args = parser.parse_args()
    if args.target == 'combined' and (args.ref or args.reproduce):
        parser.error('combined supports contract regressions or --existing, with the three fixed reviewed heads')
    repo = Path(git(PACKAGE, 'rev-parse', '--show-toplevel').decode().strip())
    with ExitStack() as cleanup:
        temp = cleanup.enter_context(tempfile.TemporaryDirectory(prefix='minimax-independent-review-'))
        cleanup.callback(os.chdir, repo)
        root = Path(temp)
        snapshot = root / 'snapshot'
        snapshot.mkdir()
        sha = args.ref or REFS['prs'][args.target if args.target != 'combined' else 'ga04']['head_sha']
        extract(repo, sha, snapshot)
        if args.target == 'combined':
            seen = set()
            for key in ('ga01', 'ga05'):
                head = REFS['prs'][key]['head_sha']
                paths = git(repo, 'diff', '--name-only', '-z', REFS['base_sha'] + '...' + head).decode().split('\0')
                for name in filter(None, paths):
                    path = PurePosixPath(name)
                    if path.is_absolute() or '..' in path.parts or name in seen:
                        raise ValueError('Unsafe or overlapping overlay path: ' + name)
                    seen.add(name)
                    destination = snapshot / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(git(repo, 'show', head + ':' + name))
        os.chdir(snapshot)
        sys.path.insert(0, str(snapshot))
        sys.dont_write_bytecode = True
        for name in list(os.environ):
            if name.endswith(('API_KEY', 'ACCESS_TOKEN')) or name.startswith(('STUDIO_REMOTE', 'STUDIO_ACCESS', 'STUDIO_TRUSTED', 'STUDIO_SERVICE')):
                os.environ.pop(name, None)
        os.environ['STUDIO_DATA_DIR'] = str(root / 'runtime')
        os.environ['PYTHONUTF8'] = '1'
        sys.addaudithook(forbid_external)
        print(json.dumps({'target': args.target, 'source_sha': sha, 'temporary_data': True,
                          'mode': 'reproduce' if args.reproduce else 'existing' if args.existing else 'safe_contract_regression'}), flush=True)
        if args.reproduce:
            sys.argv = [str(HERE / ('reproduce_' + args.target + '.py'))]
            runpy.run_path(sys.argv[0], run_name='__main__')
            return 0
        if args.existing:
            import pytest
            selected = {
                'ga01': ['backend/test_llm_settlement.py', 'backend/test_llm_guard.py', 'backend/test_money_boundary.py', 'backend/test_unified_budget.py', 'backend/test_n8n_spend.py', 'backend/test_budget_release.py'],
                'ga04': ['tools/test_ci_contracts.py', 'tools/test_no_secrets.py', 'tools/test_agent_scope.py', 'tools/test_agent_coordination.py'],
                'ga05': ['backend/test_remote_access.py'],
                'combined': ['backend'],
            }[args.target]
            # The one repository-diff scanner test needs refs; archives intentionally have no .git.
            if args.target == 'ga04':
                raise RuntimeError('Run the 63 existing GA-04 tests in a separate Git checkout, as documented in TEST_RESULTS.md')
            return pytest.main([*selected, '-q', '--disable-warnings', '-p', 'no:cacheprovider'])
        module = runpy.run_path(str(HERE / 'regression_contracts.py'))
        prefix = {'ga01': 'Ga01', 'ga04': 'Ga04', 'ga05': 'Ga05', 'combined': 'Ga'}[args.target]
        suite = unittest.TestSuite()
        for name, cls in sorted(module.items()):
            if name.startswith(prefix) and isinstance(cls, type) and issubclass(cls, unittest.TestCase):
                suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(cls))
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
