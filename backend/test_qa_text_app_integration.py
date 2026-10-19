"""QA TEXT sandbox smoke tests against the REAL GremoVOD FastAPI application.

Runs with StudioSmokeTests' temporary SQLite/folders and patched forbidden providers.
Never opens the developer's actual studio.sqlite3, never sends a model request.
"""
import os
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend import main, test_production


class QATextAppIntegrationTests(unittest.TestCase):
    def setUp(self):
        test_production.ProductionTests.setUp(self)
        test_production.ProductionTests.setup_production(self)
        self.series = test_production.ProductionTests.new(self, 'series', 'QA Sandbox Series')
        sid = self.series['id']
        plan_path = f'/api/productions/{self.pid}/series/{sid}/story-plan'
        body = {
            'base_revision': 0,
            'source': 'Грэм встречает гостя у аэропорта.',
            'source_kind': 'idea',
            'cards': [{
                'id': 'qa-card-1', 'scene_id': None, 'title': 'Встреча',
                'summary': 'Грэм подъезжает к аэропорту.',
                'character_ids': [self.char['id']],
                'location_id': None, 'stage': 'setup',
                'change': 'Ожидание → встреча',
            }],
        }
        saved = self.client.put(plan_path, json=body)
        self.assertEqual(saved.status_code, 200, saved.text)
        with main.connect() as db:
            db.execute('UPDATE production_nodes SET notes=? WHERE id=?',
                       ('Грэм подъезжает к аэропорту и выходит из автомобиля.', sid))
        self.env = patch.dict(os.environ, {
            'STUDIO_QA_SANDBOX_TOKEN': 'sandbox-qa-secret-' * 3,
            'STUDIO_QA_SANDBOX_PROJECT_ID': self.project,
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.worker = TestClient(main.app, base_url='http://127.0.0.1')
        self.worker.__enter__()
        self.addCleanup(lambda: self.worker.__exit__(None, None, None))
        self.svc = {'Authorization': 'Bearer ' + 'sandbox-qa-secret-' * 3}
        self.prefix = '/api/v1/qa/text'
        self.context_path = f'{self.prefix}/contexts/{self.project}/{self.pid}/{sid}'

    def tearDown(self):
        test_production.ProductionTests.tearDown(self)

    def prepare(self):
        ctx = self.client.get(self.context_path)
        self.assertEqual(ctx.status_code, 200, ctx.text)
        source = ctx.json()
        self.assertIn('Грэм', source['artifact_text'])
        self.assertIn('Грэм', source['canon'])
        approved = self.client.post(self.prefix + '/approvals', json={
            'project_id': self.project, 'production_id': self.pid,
            'series_id': self.series['id'],
            'artifact_revision': source['artifact_revision'],
            'brief_revision': source['brief_revision'],
            'canon_revision': source['canon_revision'],
            'confirm_source_approval': True,
        })
        self.assertEqual(approved.status_code, 200, approved.text)
        enqueued = self.client.post(self.prefix + '/jobs', json={
            'approval_id': approved.json()['approval_id'],
            'idempotency_key': 'qa-test-' + uuid.uuid4().hex,
        })
        self.assertEqual(enqueued.status_code, 200, enqueued.text)
        return enqueued.json()['task_id'], source

    def claim(self, task):
        claimed = self.worker.post(
            f'{self.prefix}/service/jobs/{task}/claim',
            headers=self.svc, json={'execution_id': 'offline-qa-execution'})
        self.assertEqual(claimed.status_code, 200, claimed.text)

    def verdict(self, task, role, packet):
        text = packet['artifact_text']
        quote = 'Грэм'
        start = text.index(quote)
        payload = {
            'role': role, 'task_id': task, 'project_id': self.project,
            'artifact_id': self.series['id'],
            'artifact_revision': packet['artifact_revision'],
            'review_round': 1,
            'requested_scopes': ['TEXT'], 'checked_scopes': ['TEXT'],
            'scope_results': {'TEXT': 'PASS'}, 'verdict': 'PASS',
            'evidence': [{
                'scope': 'TEXT', 'evidence_type': 'text_quote',
                'source_kind': 'artifact',
                'source_text_revision': packet['text_sha256'],
                'quote': quote, 'start': start, 'end': start + len(quote),
                'observation': 'Synthetic smoke observation; not real QA',
            }],
            'missing_inputs': [], 'biggest_gap': None,
            'model_used': packet['model'],
            'estimated_cost_usd': 0, 'actual_cost_usd': 0,
            'event_id': 'test-event-' + role,
            'execution_id': 'offline-qa-execution',
        }
        return self.worker.post(f'{self.prefix}/service/jobs/{task}/verdict',
                                json=payload, headers=self.svc)

    def test_full_main_app_mock_review_is_not_quality_approval(self):
        task, original = self.prepare()
        self.assertIn(task, self.worker.get(self.prefix + '/service/queue', headers=self.svc).json()['task_ids'])
        self.claim(task)
        packets = {}
        for role in ('REVIEW-REQ', 'REVIEW-SYSTEM'):
            response = self.worker.get(f'{self.prefix}/service/jobs/{task}/packet/{role}', headers=self.svc)
            self.assertEqual(response.status_code, 200, response.text)
            packets[role] = response.json()
        self.assertIn('approved_requirements', packets['REVIEW-REQ'])
        self.assertNotIn('approved_canon', packets['REVIEW-REQ'])
        self.assertIn('approved_canon', packets['REVIEW-SYSTEM'])
        self.assertNotIn('approved_requirements', packets['REVIEW-SYSTEM'])
        for role in ('REVIEW-REQ', 'REVIEW-SYSTEM'):
            r = self.verdict(task, role, packets[role])
            self.assertEqual(r.status_code, 200, r.text)
        final = r.json()
        self.assertEqual(final['status'], 'SANDBOX_TEXT_PRECHECK_PASSED_AWAITING_OWNER')
        for k in ('quality_claim', 'all_passed', 'text_precheck_passed', 'final_release_approved', 'paid_calls_executed'):
            self.assertFalse(final[k], k)
        current = self.client.get(self.context_path).json()
        for k in ('artifact_revision', 'brief_revision', 'canon_revision', 'artifact_text'):
            self.assertEqual(current[k], original[k])
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM generation_approvals').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0], 0)

    def test_real_storyboard_revision_stales_review(self):
        task, _ = self.prepare()
        self.claim(task)
        with main.connect() as db:
            db.execute('UPDATE production_nodes SET notes=? WHERE id=?',
                       ('Сценарий изменён после захвата задачи.', self.series['id']))
        r = self.worker.get(f'{self.prefix}/service/jobs/{task}/packet/REVIEW-REQ', headers=self.svc)
        self.assertEqual(r.status_code, 409, r.text)


    def test_current_scene_editor_wins_over_import_history(self):
        scene = test_production.ProductionTests.new(self, 'episode', 'Сцена у аэропорта', self.series['id'])
        frame = test_production.ProductionTests.new(self, 'frame', 'Реакция героя', scene['id'])
        old_text = 'Грэм подъезжает к аэропорту. Исторический импорт.'
        with main.connect() as db:
            db.execute('INSERT INTO storyboard_imports VALUES(?,?,?,?,?,?)',
                       ('qa-historical-import', self.series['id'], 'historical-hash',
                        old_text, '[]', main.now()))
        saved = self.client.put(f'/api/productions/{self.pid}/nodes/{scene["id"]}/notes',
                                json={'notes': 'Гость уже улетел. Поездка отменена.'})
        self.assertEqual(saved.status_code, 200, saved.text)
        saved = self.client.put(f'/api/productions/{self.pid}/nodes/{frame["id"]}/notes',
                                json={'notes': 'Грэм смотрит на пустую стоянку.'})
        self.assertEqual(saved.status_code, 200, saved.text)
        preview = self.client.get(self.context_path)
        self.assertEqual(preview.status_code, 200, preview.text)
        current = preview.json()
        self.assertIn('Гость уже улетел. Поездка отменена.', current['artifact_text'])
        self.assertIn('Грэм смотрит на пустую стоянку.', current['artifact_text'])
        self.assertNotIn('Исторический импорт.', current['artifact_text'])
        self.assertLess(current['artifact_text'].index(scene['id']),
                        current['artifact_text'].index(frame['id']))
        self.assertEqual(current['source_provenance']['artifact'], 'production_nodes.current_notes')
        task, frozen = self.prepare()
        self.assertEqual(frozen['text_sha256'], current['text_sha256'])
        self.claim(task)
        packet = self.worker.get(f'{self.prefix}/service/jobs/{task}/packet/REVIEW-REQ',
                                 headers=self.svc)
        self.assertEqual(packet.status_code, 200, packet.text)
        self.assertIn('Гость уже улетел', packet.json()['artifact_text'])

    def test_real_story_plan_requirements_and_stale_approval(self):
        task, snapshot = self.prepare()
        self.assertIn('summary: Грэм подъезжает к аэропорту.', snapshot['requirements'])
        self.assertIn('change: Ожидание → встреча', snapshot['requirements'])
        self.assertIn('qa-card-1', snapshot['requirements'])
        self.claim(task)
        plan_path = f'/api/productions/{self.pid}/series/{self.series["id"]}/story-plan'
        changed = {
            'base_revision': 1, 'source': 'Грэм встречает гостя у аэропорта.',
            'source_kind': 'idea',
            'cards': [{
                'id': 'qa-card-1', 'scene_id': None, 'title': 'Встреча',
                'summary': 'Гость уже улетел.', 'character_ids': [self.char['id']],
                'location_id': None, 'stage': 'setup',
                'change': 'Такси больше не нужно',
            }]
        }
        updated = self.client.put(plan_path, json=changed)
        self.assertEqual(updated.status_code, 200, updated.text)
        fresh = self.client.get(self.context_path).json()
        self.assertIn('summary: Гость уже улетел.', fresh['requirements'])
        self.assertIn('change: Такси больше не нужно', fresh['requirements'])
        self.assertNotEqual(fresh['brief_revision'], snapshot['brief_revision'])
        status = self.client.get(f'{self.prefix}/jobs/{task}')
        self.assertEqual(status.status_code, 200, status.text)
        self.assertFalse(status.json()['source_current'])
        self.assertTrue(status.json()['historical_review'])
        packet = self.worker.get(f'{self.prefix}/service/jobs/{task}/packet/REVIEW-REQ',
                                 headers=self.svc)
        self.assertEqual(packet.status_code, 409, packet.text)

    def test_non_ascii_bearer_and_huge_callback_rejected(self):
        task, _ = self.prepare()
        bad = self.worker.get(self.prefix+'/service/queue',
                              headers={b'authorization': b'Bearer \xff'})
        self.assertEqual(bad.status_code, 401, bad.text)
        self.claim(task)
        packet = self.worker.get(f'{self.prefix}/service/jobs/{task}/packet/REVIEW-REQ',
                                 headers=self.svc).json()
        body = {
            'role':'REVIEW-REQ','task_id':task,'project_id':self.project,
            'artifact_id':self.series['id'],'artifact_revision':packet['artifact_revision'],
            'checked_scopes':[], 'scope_results':{'TEXT':'BLOCKED'},
            'verdict':'BLOCKED','evidence':[],'missing_inputs':['x'*100000],
            'model_used':packet['model'],'event_id':'huge-test-event',
            'execution_id':'offline-qa-execution'
        }
        attempt = self.worker.post(f'{self.prefix}/service/jobs/{task}/verdict',
                                   json=body,headers=self.svc)
        self.assertEqual(attempt.status_code, 413, attempt.text)
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM qa_text_verdicts').fetchone()[0],0)

    def test_auth_remote_and_paid_fields_fail_closed(self):
        task, _ = self.prepare()
        r = self.worker.get(self.prefix + '/service/queue')
        self.assertEqual(r.status_code, 401, r.text)
        self.assertEqual(self.worker.post(self.prefix + '/jobs', headers=self.svc,
                                         json={'approval_id': 'forged', 'idempotency_key': 'forged-key'}).status_code, 401)
        self.assertEqual(self.worker.post(f'{self.prefix}/service/jobs/{task}/claim', headers=self.svc,
            json={'execution_id': 'x', 'approved_expert_model': True}).status_code, 422)
        with TestClient(main.app, base_url='http://example.net') as remote:
            self.assertEqual(remote.get(self.prefix + '/service/queue', headers=self.svc).status_code, 403)


if __name__ == '__main__':
    unittest.main()