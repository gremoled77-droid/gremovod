"""Safe-behavior contracts: intentionally RED on the reviewed unfixed heads.

Not installed into the production suite. Run through run_offline.py, which supplies
an ephemeral source archive and STUDIO_DATA_DIR. All credentials and media are synthetic.
"""
from contextlib import contextmanager
import fnmatch
import ipaddress
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch


class Ga01Runtime(unittest.TestCase):
    def setUp(self):
        from backend import llm_guard, main, test_llm_settlement
        self.guard, self.main = llm_guard, main
        self.fixture = test_llm_settlement.LlmSettlementTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.prepare()

    def test_contradictory_zero_total_does_not_release_money(self):
        quote = self.fixture.quote()
        body = dict(provider='piapi', project_id=self.fixture.pid, model='gpt-5.6-luna',
                    messages=self.fixture.messages, max_tokens=500, approved=True,
                    quote_token=quote['quote_token'], max_cost_usd=quote['estimated_usd'], request_id='review-contradiction-1')
        value = {'usage': {'prompt_tokens': 120, 'completion_tokens': 40, 'total_tokens': 0}}
        with patch.object(self.main, 'request_piapi', AsyncMock(return_value=value)) as provider:
            self.fixture.client.post('/api/llm/chat', json=body)
        row = self.fixture.call_row(body['request_id'])
        self.assertEqual(provider.await_count, 1)
        self.assertEqual(row['status'], 'submission_unknown')
        self.assertGreater(row['usd'], 0)

    def test_nonfinite_price_returns_unknown_without_crashing(self):
        status, held, *_ = self.guard.settle_from_usage(float('nan'), 1, {'prompt_tokens': 1, 'completion_tokens': 1}, .1)
        self.assertEqual((status, held), ('submission_unknown', .1))

    def test_manual_settlement_reports_the_whole_confirmed_fact(self):
        from backend import test_llm_settlement
        # Reuse methods only; the already-entered fixture owns every temporary path.
        fixture = test_llm_settlement.AgentsReconcileTests()
        fixture.client = self.fixture.client
        fixture.prepare()
        good = {'prompt_tokens': 120, 'completion_tokens': 40}
        response, _ = fixture.run_agents('review-contract-reconcile', [('a', good), ('b', {}), ('c', good)])
        self.assertEqual(response.status_code, 200)
        row = fixture.split_row()
        result = fixture.reconcile(row['id'], {'outcome': 'done', 'unconfirmed_usd': .001, 'note': 'synthetic provider fact'}).json()
        self.assertEqual(result['confirmed_usd'], result['usd'])
        self.assertEqual(result['unknown_usd'], 0)
        with self.main.connect() as db:
            summary = self.guard.summary(db, {fixture.pid})
        self.assertEqual(summary['confirmed_usd'], summary['usd'])

    def test_ga02_prepare_works_without_helper_monkeypatches(self):
        spec = {'project_id': self.fixture.pid, 'stage': {'id': 'story', 'revision': 'r1', 'instruction': 'Write scene'},
                'model': 'minimax-m2.1', 'inputs': [{'id': 'brief', 'content': 'Synthetic brief', 'approved': True}],
                'skills': [], 'max_tokens': 500, 'response_format': 'text', 'request_id': 'review-task-lifecycle-1'}
        with patch.object(self.main, 'request_piapi', AsyncMock()) as provider:
            response = self.fixture.client.post('/api/llm/tasks', json=spec)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(provider.await_count, 0)


class Ga01Migration(unittest.TestCase):
    def setUp(self):
        from backend import llm_guard, main
        from fastapi import FastAPI
        self.guard = llm_guard
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = Path(temp.name) / 'legacy.sqlite3'
        @contextmanager
        def connect():
            db = sqlite3.connect(path)
            db.row_factory = sqlite3.Row
            try:
                with db:
                    yield db
            finally:
                db.close()
        self.connect = connect
        with connect() as db:
            db.execute('CREATE TABLE llm_calls(id TEXT PRIMARY KEY,request_id TEXT UNIQUE,project_id TEXT NOT NULL,model TEXT NOT NULL,status TEXT NOT NULL,usd REAL NOT NULL,estimated_usd REAL NOT NULL,input_tokens INTEGER,output_tokens INTEGER,created_at TEXT NOT NULL,note TEXT)')
            for ident, status, usd, ti, to in [('done', 'done', .03, 120, 40), ('unknown', 'submission_unknown', .1, 240, 80), ('reserved', 'reserved', .1, None, None), ('failed', 'failed', 0, None, None)]:
                db.execute('INSERT INTO llm_calls VALUES(?,?,?,?,?,?,?,?,?,?,?)', (ident, ident, 'p', 'gpt-5.6-luna', status, usd, .1, ti, to, main.now(), None))
        app = FastAPI()
        llm_guard.register(app, SimpleNamespace(connect=connect))
        self.setup_schema = app.router.on_startup[-1]

    def rows(self):
        with self.connect() as db:
            return {row['id']: dict(row) for row in db.execute('SELECT * FROM llm_calls')}

    def test_normal_upgrade_and_reopen_preserve_confirmed_money(self):
        self.setup_schema()
        self.setup_schema()
        rows = self.rows()
        self.assertEqual(rows['done']['confirmed_usd'], .03)
        self.assertGreater(rows['unknown']['confirmed_usd'], 0)
        self.assertEqual(rows['reserved']['confirmed_usd'], 0)

    def test_interrupted_backfill_recovers_on_next_startup(self):
        with patch.object(self.guard, 'confirmed_from_tokens', side_effect=sqlite3.OperationalError('synthetic backfill interruption')):
            with self.assertRaises(sqlite3.OperationalError):
                self.setup_schema()
        self.setup_schema()
        rows = self.rows()
        self.assertEqual(rows['done']['confirmed_usd'], .03)
        self.assertGreater(rows['unknown']['confirmed_usd'], 0)

    def test_malformed_legacy_tokens_do_not_break_startup(self):
        with self.connect() as db:
            db.execute("UPDATE llm_calls SET input_tokens='bad' WHERE id='unknown'")
        self.setup_schema()
        self.setup_schema()
        row = self.rows()['unknown']
        self.assertEqual(row['status'], 'submission_unknown')
        self.assertGreater(row['usd'], 0)
        self.assertGreaterEqual(row['confirmed_usd'], 0)

    def test_legacy_negative_spend_cannot_lower_combined_budget(self):
        from backend import main
        with self.connect() as db:
            db.execute('INSERT INTO llm_calls VALUES(?,?,?,?,?,?,?,?,?,?,?)', ('negative', 'negative', 'p', 'gpt-5.6-luna', 'done', -.14, .1, -1000000, -1000000, main.now(), None))
        self.setup_schema()
        row = self.rows()['negative']
        self.assertGreaterEqual(row['usd'], 0)
        self.assertGreaterEqual(row['confirmed_usd'], 0)
        with self.connect() as db:
            self.assertGreaterEqual(self.guard.spent(db, 'p')[0], .23 - 1e-9)


class Ga04Scope(unittest.TestCase):
    def test_base_manifest_cannot_be_bypassed_by_changing_head_checker(self):
        from tools import check_agent_scope as scope
        manifest = json.loads(Path(scope.MANIFEST_PATH).read_text(encoding='utf8'))
        with tempfile.TemporaryDirectory(prefix='scope-regression-') as temp:
            root = Path(temp)
            def git(*args):
                result = subprocess.run(['git', '-c', 'user.name=Review Fixture', '-c', 'user.email=review@example.invalid', *args], cwd=root, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            git('init')
            (root / 'tools').mkdir()
            source = Path(scope.__file__).read_text(encoding='utf8')
            (root / scope.MANIFEST_PATH).write_text(json.dumps(manifest), encoding='utf8')
            checker = root / 'tools/check_agent_scope.py'
            checker.write_text(source, encoding='utf8')
            git('add', 'tools/check_agent_scope.py', scope.MANIFEST_PATH)
            git('commit', '-m', 'trusted fixture base')
            git('update-ref', 'refs/remotes/origin/mavis/work', 'HEAD')
            (root / 'backend').mkdir()
            (root / 'backend/main.py').write_text('# outside ga-05 scope\n', encoding='utf8')
            altered = source.replace('    role = role_for_branch(branch)\n', '    return []\n    role = role_for_branch(branch)\n', 1)
            self.assertNotEqual(source, altered, 'Checker implementation changed; update this adversarial fixture')
            checker.write_text(altered, encoding='utf8')
            git('add', 'backend/main.py', 'tools/check_agent_scope.py')
            git('commit', '-m', 'untrusted fixture change')
            result = subprocess.run([sys.executable, str(checker), '--branch', 'minimax/ga-05-probe', '--base', 'mavis/work'], cwd=root, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_ci_changes_trigger_the_heavy_retest(self):
        import yaml
        workflow = yaml.safe_load(Path('.github/workflows/studio-offline-ci.yml').read_text(encoding='utf8'))
        events = workflow.get('on', workflow.get(True))
        patterns = events['pull_request']['paths']
        for path in ('.github/workflows/studio-offline-ci.yml', 'tools/check_agent_scope.py'):
            with self.subTest(path=path):
                self.assertTrue(any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns))

    def test_scope_allow_deny_controls_still_work(self):
        from tools import check_agent_scope as scope
        manifest = json.loads(Path(scope.MANIFEST_PATH).read_text(encoding='utf8'))
        self.assertEqual(scope.forbidden_files('minimax/ga-05-probe', ['backend/remote_access.py'], manifest), [])
        self.assertEqual(scope.forbidden_files('minimax/ga-05-probe', ['backend/main.py'], manifest), ['backend/main.py'])
        self.assertEqual(scope.forbidden_files('minimax/ga-05-probe', ['canon/example.json'], manifest), ['canon/example.json'])

    def test_secret_diagnostic_does_not_echo_the_synthetic_value(self):
        from tools import check_no_secrets
        value = 'this-is-a-synthetic-secret'
        findings = check_no_secrets.scan_text("api_key = '" + value + "'", 'fixture.py')
        self.assertTrue(findings)
        self.assertNotIn(value, '\n'.join(findings))


class Ga05Proxy(unittest.TestCase):
    def setUp(self):
        from backend import main, remote_access, test_smoke
        self.main, self.remote = main, remote_access
        fixture = test_smoke.StudioSmokeTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        self.remote._fails.clear()
        self.addCleanup(self.remote._fails.clear)

    def deployed_app(self):
        from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
        cmd = next(line[4:] for line in Path('Dockerfile').read_text(encoding='utf8').splitlines() if line.startswith('CMD '))
        command = json.loads(cmd)
        if '--no-proxy-headers' in command:
            return self.main.app
        trust = command[command.index('--forwarded-allow-ips') + 1] if '--forwarded-allow-ips' in command else '127.0.0.1'
        return ProxyHeadersMiddleware(self.main.app, trusted_hosts=trust)

    def test_deployed_stack_does_not_bypass_login_throttle(self):
        from fastapi.testclient import TestClient
        client = TestClient(self.deployed_app(), base_url='https://studio.example.com', client=('198.51.100.20', 12345))
        self.addCleanup(client.close)
        with patch.dict(os.environ, {'STUDIO_REMOTE_HOSTS': 'studio.example.com', 'STUDIO_ACCESS_PASSWORD': 'correct-horse-battery'}):
            codes = [client.post('/api/login', json={'password': 'wrong'}, headers={'X-Forwarded-For': f'203.0.113.{i}'}).status_code for i in range(1, 8)]
        self.assertEqual(codes, [401] * 5 + [429] * 2)

    def test_deployed_stack_does_not_trust_spoofed_loopback(self):
        from fastapi.testclient import TestClient
        client = TestClient(self.deployed_app(), base_url='http://127.0.0.1', client=('198.51.100.20', 12345))
        self.addCleanup(client.close)
        with patch.dict(os.environ, {'STUDIO_REMOTE_HOSTS': 'studio.example.com', 'STUDIO_ACCESS_PASSWORD': 'correct-horse-battery'}):
            response = client.get('/api/session', headers={'X-Forwarded-For': '127.0.0.1'})
        self.assertEqual(response.status_code, 401)

    def test_untrusted_intermediate_is_not_skipped_as_a_proxy(self):
        request = SimpleNamespace(client=SimpleNamespace(host='10.0.0.2'), headers={'x-forwarded-for': '203.0.113.7, 198.51.100.20'})
        result = self.remote.client_ip(request, [ipaddress.ip_network('10.0.0.2')], 2)
        self.assertNotEqual(result, '203.0.113.7')

    def test_invalid_ipv6_suffixes_are_rejected(self):
        for value in ('[2001:db8::7]:bad', '[2001:db8::7]:999999', '[2001:db8::7]trailing'):
            with self.subTest(value=value):
                self.assertIsNone(self.remote._parse_ip(value))

    def test_alternative_proxy_addresses_do_not_imply_multiple_hops(self):
        with patch.dict(os.environ, {'STUDIO_TRUSTED_PROXIES': '10.0.0.1,10.0.0.2', 'STUDIO_TRUSTED_PROXY_HOPS': ''}):
            self.assertEqual(self.remote.trusted_hops(), 1)
