"""BETA-02 — интеграционные случаи приёмки: контракт HTTP, перезапуск, резервная копия, fail-closed, деньги.

Без сети и платных вызовов: платный провайдер заменён на ловушку, данные во временной папке,
ролики собирает локальный ffmpeg. Случаи, зависящие от GA-01 (#79), пропускаются с явной причиной и
харнесс считает такой пропуск BLOCKED, а не зелёным.
Режим BETA02_FAULT=b1|owner|ledger искусственно ломает продукт — случаи обязаны упасть (проверка самого гейта).
"""
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend import connections, main, media_qc, release_gate, spend_ledger

FFMPEG = shutil.which('ffmpeg')
FFPROBE = shutil.which('ffprobe')
OWNER = 'beta02-owner'
TOKEN = 'beta02-machine-token'
FAULT = os.environ.get('BETA02_FAULT', '')
HAS_R3 = hasattr(spend_ledger, '_readable')
GATE_KEYS = {
    'artifact_id': str, 'project_id': str, 'state': str, 'master_sha256': str, 'qc_verdict': str, 'qc_stale': bool,
    'qc_reason': str, 'content_sha256': str, 'decision': str, 'decision_stale': bool, 'decision_stale_code': str,
    'approve_blockers': list, 'can_approve': bool, 'can_reject': bool, 'n35_evidence': dict, 'history': list,
}
MANIFEST = {'container': 'mp4', 'require_audio': True}


def make_video(path: Path, audio=True) -> Path:
    args = [FFMPEG, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=10:duration=1']
    if audio:
        args += ['-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', '-c:a', 'aac', '-shortest']
    subprocess.run(args + ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)], check=True, timeout=180)
    return path


@unittest.skipUnless(FFMPEG and FFPROBE, 'ffmpeg/ffprobe не установлены: синтетические ролики собрать нельзя')
class Beta02Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.paid = AsyncMock(side_effect=AssertionError('BETA-02: платный провайдер вызван'))
        self.patches = {
            'DB': patch.object(main, 'DB', self.root / 'studio.sqlite3'),
            'LIB': patch.object(main, 'LIBRARY_ROOT', self.root / 'library'),
            'PROD': patch.object(main, 'PRODUCTIONS_ROOT', self.root / 'projects'),
            'KEY': patch.object(main, 'PIAPI_KEY_FILE', self.root / 'PIAPI_API_KEY.txt'),
            'MEDIA': patch.object(main, 'MEDIA', self.root / 'media'),
            'CHAR': patch.object(main, 'CHAR_ROOT', self.root / 'characters'),
            'CROOT': patch.object(connections, 'ROOT', self.root),  # реальные файлы ключей не читаются
            'LEGACY': patch.object(connections, 'ELEVENLABS_LEGACY_FILE', self.root / 'legacy-key.txt'),
            'DPAPI': patch.object(connections, 'KIE_DPAPI_FILES', []),
            'CHECKS': patch.object(connections, 'CHECKS', {}),
            'KEYENV': patch.dict(main.os.environ, {p['env']: '' for p in connections.PROVIDERS.values()}),
            'PAID': patch.object(main, 'request_piapi', self.paid),
            'ENV': patch.dict(os.environ, {'GREMOVOD_OWNER_ID': OWNER}),
        }
        for item in self.patches.values():
            item.start()
            self.addCleanup(item.stop)
        os.environ.pop('STUDIO_SERVICE_TOKENS', None)
        if FAULT == 'b1':  # возвращаем дефект B1: старый QC наследуется изменённым файлом
            original = media_qc.master_facts

            def broken(*args, **kwargs):
                facts = original(*args, **kwargs)
                if facts['qc_stale']:
                    facts['qc_stale'], facts['qc_verdict'] = False, 'PASS_TECHNICAL'
                return facts

            patcher = patch.object(media_qc, 'master_facts', broken)
            patcher.start()
            self.addCleanup(patcher.stop)
        if FAULT == 'owner':  # владелец не проверяется
            patcher = patch.object(release_gate, 'require_owner', lambda request, owner_id: OWNER)
            patcher.start()
            self.addCleanup(patcher.stop)
        if FAULT == 'ledger' and HAS_R3:  # бухгалтерия принимает нечитаемую сумму за число (дефект до R3)
            patcher = patch.object(spend_ledger, '_readable', lambda value: True)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = None
        self.open()
        self.pid = self.client.post('/api/projects', json={'title': 'BETA-02', 'state': {'scene': 1}}).json()['id']
        self.video = make_video(self.root / 'master.mp4')
        self.aid = self.upload(self.video)['id']

    # -- помощники -----------------------------------------------------------------
    def open(self):
        if self.client is not None:
            self.client.__exit__(None, None, None)
        client = TestClient(main.app, base_url='http://127.0.0.1')
        client.__enter__()
        client.headers['X-Studio-Session'] = client.get('/api/session').json()['token']
        self.client = client
        self.addCleanup(client.__exit__, None, None, None)

    @property
    def base(self):
        return f'/api/projects/{self.pid}/release-artifacts/{self.aid}'

    def revision(self):
        return self.client.get(f'/api/projects/{self.pid}').json()['revision']

    def upload(self, path, revision=None):
        with Path(path).open('rb') as source:
            response = self.client.post(f'/api/projects/{self.pid}/release-artifacts',
                                        data={'project_revision': str(self.revision() if revision is None else revision), 'title': 'Мастер'},
                                        files={'file': ('master.mp4', source, 'video/mp4')})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def gate(self):
        response = self.client.get(self.base + '/gate')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def qc(self, manifest=None):
        response = self.client.post(self.base + '/qc/measure', json={'manifest': MANIFEST if manifest is None else manifest})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def decide(self, decision='APPROVED', **over):
        body = {'decision': decision, 'owner_id': OWNER, 'processing_rights_confirmed': True, 'note': '',
                'expected_master_sha256': self.gate()['master_sha256']}
        body.update(over)
        return self.client.post(self.base + '/decision', json=body)

    def code(self, response, status, code):
        self.assertEqual(response.status_code, status, response.text)
        self.assertEqual(response.json()['detail']['code'], code, response.text)

    def stored(self):
        return next(main.LIBRARY_ROOT.glob('*.mp4'))

    def assertSchema(self, gate):
        for key, kind in GATE_KEYS.items():
            self.assertIn(key, gate)
            self.assertIsInstance(gate[key], kind, key)
        self.assertIn(gate['state'], ('IMPORTED', 'TECHNICAL_PASS', 'OWNER_APPROVED', 'REJECTED'))

    def counts(self):
        with main.connect() as db:
            return {table: db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                    for table in ('llm_calls', 'generation_approvals', 'release_decisions', 'release_artifacts')}


class ReleaseFlowTests(Beta02Base):
    def test_full_flow_http_contract_restart(self):
        gate = self.gate()
        self.assertSchema(gate)
        self.assertEqual(gate['state'], 'IMPORTED')
        self.assertEqual(len(gate['master_sha256']), 64)
        self.assertEqual(self.client.get(f'/api/projects/{self.pid}/release-artifacts').json()[0]['status'], 'imported')
        self.assertEqual(self.decide('REJECTED', note='черновик').json()['gate']['state'], 'REJECTED')  # без QC
        self.assertEqual(self.qc()['verdict'], 'PASS_TECHNICAL')
        gate = self.gate()
        self.assertEqual(gate['state'], 'REJECTED')  # успешная проверка не снимает отказ владельца: нужно новое решение
        self.assertEqual(gate['n35_evidence']['coverage_status'], 'CONFIRMED')
        sha = gate['master_sha256']
        approved = self.decide().json()
        self.assertFalse(approved['duplicate'])
        self.assertEqual(approved['gate']['state'], 'OWNER_APPROVED')
        self.assertEqual(approved['gate']['history'][0]['master_sha256'], sha)
        self.open()  # перезапуск приложения над той же SQLite
        again = self.gate()
        self.assertSchema(again)
        self.assertEqual((again['state'], again['master_sha256']), ('OWNER_APPROVED', sha))
        self.assertEqual([x['decision'] for x in again['history']], ['APPROVED', 'REJECTED'])

    def test_only_current_approval_counts_after_restart(self):
        self.qc()
        first = self.decide().json()['gate']['master_sha256']
        self.open()
        with self.stored().open('ab') as handle:
            handle.write(b'\0changed')
        self.open()
        gate = self.gate()
        self.assertNotEqual(gate['state'], 'OWNER_APPROVED')
        self.assertTrue(gate['decision_stale'])
        self.qc()  # новая проверка нового файла: решение по старым байтам не воскресает
        gate = self.gate()
        self.assertEqual(gate['state'], 'TECHNICAL_PASS')
        self.assertNotEqual(gate['master_sha256'], first)
        self.assertEqual(self.decide().json()['gate']['state'], 'OWNER_APPROVED')
        self.assertEqual(len(self.gate()['history']), 2)

    def test_backup_restore_keeps_decision_and_integrity(self):
        self.qc()
        self.decide()
        sha = self.gate()['master_sha256']
        restored = Path(tempfile.mkdtemp(prefix='beta02-restore-', dir=self.root))
        source = sqlite3.connect(main.DB)
        target = sqlite3.connect(restored / 'studio.sqlite3')
        with target:
            source.backup(target)
        for db in (source, target):
            self.assertEqual(db.execute('PRAGMA quick_check').fetchone()[0], 'ok')
        source.close(), target.close()
        shutil.copytree(main.LIBRARY_ROOT, restored / 'library')
        with patch.object(main, 'DB', restored / 'studio.sqlite3'), patch.object(main, 'LIBRARY_ROOT', restored / 'library'):
            self.open()
            gate = self.gate()
        self.assertEqual((gate['state'], gate['master_sha256']), ('OWNER_APPROVED', sha))
        self.open()

    def test_restore_without_the_file_is_not_an_approval(self):
        self.qc()
        self.decide()
        restored = Path(tempfile.mkdtemp(prefix='beta02-nofile-', dir=self.root))
        source = sqlite3.connect(main.DB)
        target = sqlite3.connect(restored / 'studio.sqlite3')
        with target:
            source.backup(target)
        source.close(), target.close()
        (restored / 'library').mkdir()
        with patch.object(main, 'DB', restored / 'studio.sqlite3'), patch.object(main, 'LIBRARY_ROOT', restored / 'library'):
            self.open()
            gate = self.gate()
        self.assertNotEqual(gate['state'], 'OWNER_APPROVED')
        self.assertEqual(gate['master_sha256'], '')
        self.open()

    def test_repeating_qc_changes_neither_hash_nor_approval(self):
        self.qc()
        self.decide()
        before = self.gate()
        self.qc(), self.qc()
        after = self.gate()
        self.assertEqual((before['master_sha256'], after['state'], len(after['history'])),
                         (after['master_sha256'], 'OWNER_APPROVED', 1))

    def test_release_actions_do_not_touch_money_or_provider(self):
        with main.connect() as db:
            ledger_before = spend_ledger.state(db, self.pid)
        counts_before = {k: v for k, v in self.counts().items() if k in ('llm_calls', 'generation_approvals')}
        self.qc()
        self.decide()
        self.decide('REJECTED', note='передумали')
        with main.connect() as db:
            ledger_after = spend_ledger.state(db, self.pid)
        self.assertEqual(ledger_before, ledger_after)
        self.assertEqual(counts_before, {k: v for k, v in self.counts().items() if k in counts_before})
        self.paid.assert_not_called()


class FailClosedTests(Beta02Base):
    def test_matrix(self):
        self.qc()
        with self.subTest('неверный SHA'):
            self.code(self.decide(expected_master_sha256='0' * 64), 409, 'MASTER_CHANGED')
        with self.subTest('пустой SHA'):
            self.code(self.decide(expected_master_sha256=''), 409, 'MASTER_CHANGED')
        with self.subTest('чужой владелец'):
            self.code(self.decide(owner_id='intruder'), 409, 'OWNER_ID_MISMATCH')
        with self.subTest('нет права на обработку'):
            self.code(self.decide(processing_rights_confirmed=False), 409, 'PROCESSING_RIGHTS_NOT_CONFIRMED')
        with self.subTest('владелец не настроен'):
            with patch.dict(os.environ, {'GREMOVOD_OWNER_ID': ''}):
                self.code(self.decide(), 409, 'OWNER_ID_NOT_CONFIGURED')
                self.code(self.decide('REJECTED', note='x'), 409, 'OWNER_ID_NOT_CONFIGURED')
        with self.subTest('устаревшая ревизия проекта при импорте'):
            stale = self.revision()
            self.client.post('/api/projects', json={'id': self.pid, 'title': 'BETA-02', 'state': {'scene': 2}, 'base_revision': stale})
            with self.video.open('rb') as source:
                response = self.client.post(f'/api/projects/{self.pid}/release-artifacts', data={'project_revision': str(stale)},
                                            files={'file': ('m.mp4', source, 'video/mp4')})
            self.code(response, 409, 'PROJECT_REVISION_CONFLICT')
        self.assertEqual(self.gate()['history'], [])  # ни один отказ не оставил записи решения

    def test_machine_token_cannot_decide_or_read_release_through_other_paths(self):
        self.qc()
        os.environ['STUDIO_SERVICE_TOKENS'] = f'{TOKEN}:{self.pid}'
        body = {'decision': 'APPROVED', 'owner_id': OWNER, 'processing_rights_confirmed': True,
                'expected_master_sha256': self.gate()['master_sha256']}
        auth = {'Authorization': f'Bearer {TOKEN}'}
        self.code(self.client.post(self.base + '/decision', json=body, headers=auth), 403, 'MACHINE_TOKEN_FORBIDDEN')
        bare = TestClient(main.app, base_url='http://127.0.0.1')
        self.addCleanup(bare.close)
        for method, path, kwargs in (('post', self.base + '/decision', {'json': body}), ('get', self.base + '/gate', {}),
                                     ('post', self.base + '/qc/measure', {'json': {'manifest': {}}})):
            with self.subTest(path=path):
                self.assertEqual(getattr(bare, method)(path, headers=auth, **kwargs).status_code, 401)
        self.assertEqual(self.gate()['history'], [])

    def test_bytes_changed_after_qc_cannot_be_approved(self):
        self.qc()
        with self.stored().open('ab') as handle:
            handle.write(b'\0tail')
        gate = self.gate()
        self.assertNotEqual(gate['state'], 'TECHNICAL_PASS')
        self.assertTrue(gate['qc_stale'])
        self.assertEqual(self.decide().status_code, 409)
        self.assertEqual(self.gate()['history'], [])

    def test_missing_file_is_never_success(self):
        self.qc()
        self.decide()
        self.stored().unlink()
        gate = self.gate()
        self.assertNotEqual(gate['state'], 'OWNER_APPROVED')
        self.assertEqual(gate['master_sha256'], '')
        self.code(self.decide(expected_master_sha256=''), 409, 'MASTER_FILE_MISSING')

    def test_concurrent_approvals_write_one_decision(self):
        self.qc()
        body = {'decision': 'APPROVED', 'owner_id': OWNER, 'processing_rights_confirmed': True,
                'expected_master_sha256': self.gate()['master_sha256']}
        barrier, codes = threading.Barrier(5), []

        def go():
            barrier.wait()
            codes.append(self.client.post(self.base + '/decision', json=body).status_code)

        threads = [threading.Thread(target=go) for _ in range(5)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(codes, [200] * 5)
        self.assertEqual(len(self.gate()['history']), 1)

    def test_rejection_without_qc_and_without_file(self):
        self.stored().unlink()
        response = self.decide('REJECTED', note='файл потерян', expected_master_sha256='')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['gate']['state'], 'REJECTED')


class MoneyCoexistenceTests(Beta02Base):
    """GA-01 (#79) рядом с выпуском: неизвестная сумма не становится нулём и держит траты."""

    def seed_unreadable(self, project_id, days_ago=3):
        created = (datetime.now(timezone.utc) - __import__('datetime').timedelta(days=days_ago)).isoformat()
        with main.connect() as db:
            db.execute('INSERT INTO llm_calls(id,request_id,project_id,model,status,usd,estimated_usd,created_at,note,confirmed_usd) '
                       'VALUES(?,?,?,?,?,?,?,?,?,?)',
                       ('b02u1', 'b02request0001', project_id, 'gpt-5.6-luna', 'submission_unknown',
                        __import__('backend').llm_guard.UNREADABLE_AMOUNT, 0.3, created, 'OWNER_DECISION_REQUIRED', 0.0))

    def media(self, project_id, request_id):
        main.PIAPI_KEY_FILE.write_text('test-key', encoding='utf-8')
        body = {'project_id': project_id, 'model_id': 'seedream-5-lite', 'prompt': 'Ночной Минск', 'request_id': request_id,
                'approved': True, 'max_cost_usd': 0.052}
        estimate = self.client.post('/api/model-jobs/estimate', json=body)
        self.assertEqual(estimate.status_code, 200, estimate.text)
        body['quote_token'] = estimate.json()['quote_token']
        return self.client.post('/api/model-jobs', json=body)

    @unittest.skipUnless(HAS_R3, 'GA-01 R3 (#79) нет в этом дереве: проверка денег BLOCKED')
    def test_unreadable_amount_blocks_spend_survives_restart_and_leaves_release_working(self):
        self.seed_unreadable(self.pid)
        for number, phase in enumerate(('до перезапуска', 'после перезапуска')):
            with self.subTest(phase):
                budget = self.client.get('/api/budgets/' + self.pid)
                self.assertEqual(budget.status_code, 200, budget.text)
                self.assertEqual(budget.json()['llm_unreadable_project'], 1)
                response = self.media(self.pid, f'beta02-money-request-{number}-123456')
                self.assertEqual(response.status_code, 400, response.text)
                self.assertIn('повреждён', response.text)
                report = self.client.get('/api/economics', params={'project_id': self.pid}).json()
                self.assertFalse(report['costs_complete'])
            self.open()
        self.paid.assert_not_called()
        # свободные действия выпуска остаются доступными: выпуск ничего не списывает
        self.qc()
        self.assertEqual(self.decide().json()['gate']['state'], 'OWNER_APPROVED')

    @unittest.skipUnless(HAS_R3, 'GA-01 R3 (#79) нет в этом дереве: проверка денег BLOCKED')
    def test_old_unreadable_row_does_not_stop_an_independent_project(self):
        other = self.client.post('/api/projects', json={'title': 'Другой', 'state': {}}).json()['id']
        self.seed_unreadable(self.pid, days_ago=3)
        self.paid.side_effect = main.HTTPException(502, 'REACHED_PROVIDER_STUB')  # заглушка, не реальная сеть
        response = self.media(other, 'beta02-request-other-12345')
        self.assertEqual(response.status_code, 502, response.text)  # дошло до заглушки провайдера, а не до денег
        self.assertIn('REACHED_PROVIDER_STUB', response.text)


if __name__ == '__main__':
    unittest.main()
