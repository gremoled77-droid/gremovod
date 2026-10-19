"""Automation API against temporary production data, with all providers forbidden."""
import os
import uuid
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from backend import main, test_production


class AutomationTests(unittest.TestCase):
    tearDown = test_production.ProductionTests.tearDown
    setup_production = test_production.ProductionTests.setup_production
    new = test_production.ProductionTests.new

    def setUp(self):
        test_production.ProductionTests.setUp(self)
        self.setup_production()
        self.series = self.new('series', 'Sandbox')
        self.scene = self.new('episode', 'Scene', self.series['id'])
        self.shot = self.new('frame', 'Shot', self.scene['id'])
        self.env = patch.dict(os.environ, {'STUDIO_AUTOMATION_TOKEN': 'test-token-' * 4,
                                          'STUDIO_AUTOMATION_PROJECT_ID': self.project})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.service = {'Authorization': 'Bearer ' + 'test-token-' * 4, 'X-Studio-Session': ''}
        self.prefix = '/api/v1/automation'
        self.ctxpath = f'{self.prefix}/contexts/{self.project}/{self.pid}/{self.series["id"]}'
        ctx = self.client.get(self.ctxpath, headers=self.service).json()
        self.body = {k: ctx[k] for k in ('project_id', 'production_id', 'series_id', 'canon_revision', 'base_revision')}
        self.body.update(scene_id=self.scene['id'], shot_id=self.shot['id'],
                         idempotency_key=uuid.uuid4().hex, correlation_id=uuid.uuid4().hex,
                         instruction='Return a storyboard proposal; no model calls.')

    def create(self, **changes):
        return self.client.post(self.prefix + '/jobs', json={**self.body, **changes})

    def claim(self, task, execution='sandbox-execution'):
        return self.client.post(f'{self.prefix}/jobs/{task}/claim', json={'execution_id': execution}, headers=self.service)

    def callback(self, task, **changes):
        body = {'task_id': task, 'event_id': 'callback-0001', 'execution_id': 'sandbox-execution',
                'status': 'review_required', 'proposal': 'Sandbox proposal'}
        return self.client.post(self.prefix + '/callbacks', json={**body, **changes}, headers=self.service)

    def test_roundtrip_review_and_no_canonical_write(self):
        before = self.client.get(self.ctxpath, headers=self.service).json()
        result = self.create()
        self.assertEqual(result.status_code, 200, result.text)
        task = result.json()['task_id']
        self.assertIn(task, self.client.get(self.prefix + '/jobs', headers=self.service).json()['task_ids'])
        self.assertEqual(self.claim(task).json()['status'], 'running')
        self.assertEqual(self.callback(task).json()['status'], 'review_required')
        review = self.client.post(f'{self.prefix}/jobs/{task}/review', json={'decision': 'approved'})
        self.assertEqual(review.json()['status'], 'approved')
        self.assertEqual(len(review.json()['events']), 4)
        self.assertEqual(self.client.get(self.ctxpath, headers=self.service).json(), before)
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM jobs').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT count(*) FROM generation_approvals').fetchone()[0], 0)

    def test_idempotency_conflicting_retries_and_execution_binding(self):
        task = self.create().json()['task_id']
        self.assertEqual(self.create().json()['task_id'], task)
        self.assertEqual(self.create(instruction='Changed input').status_code, 409)
        self.assertEqual(self.claim(task).status_code, 200)
        self.assertEqual(self.claim(task).status_code, 200)
        self.assertEqual(self.claim(task, 'another-execution').status_code, 409)
        self.assertEqual(self.callback(task, execution_id='another-execution').status_code, 409)
        first = self.callback(task).json()
        self.assertEqual(self.callback(task).json(), first)
        self.assertEqual(self.callback(task, proposal='Changed').status_code, 409)
        self.assertEqual(self.callback(task, event_id='callback-0002').status_code, 409)

    def test_concurrent_creation_and_claim(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.create(), range(2)))
        self.assertEqual([r.status_code for r in results], [200, 200])
        task = results[0].json()['task_id']
        self.assertEqual(results[1].json()['task_id'], task)
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(lambda execution: self.claim(task, execution), ['exec-1', 'exec-2']))
        self.assertEqual(sorted(r.status_code for r in claims), [200, 409])

    def test_service_auth_project_isolation_and_owner_only_actions(self):
        task = self.create().json()['task_id']
        self.assertEqual(self.client.get(self.ctxpath, headers={'Authorization': 'Bearer invalid'}).status_code, 401)
        self.assertEqual(self.client.get(self.ctxpath).status_code, 200)
        self.assertEqual(self.client.get(self.ctxpath, headers={'X-Studio-Session': 'invalid'}).status_code, 401)
        self.assertEqual(self.client.post(self.prefix + '/jobs', json=self.body, headers=self.service).status_code, 401)
        self.assertEqual(self.client.post(f'{self.prefix}/jobs/{task}/review', json={'decision': 'approved'}, headers=self.service).status_code, 401)
        self.assertEqual(self.create(project_id='foreign-project').status_code, 404)
        self.assertEqual(self.create(idempotency_key=uuid.uuid4().hex, reference_asset_ids=['foreign-asset']).status_code, 404)
        self.assertEqual(self.create(idempotency_key=uuid.uuid4().hex, shot_id='foreign-shot').status_code, 404)
        with patch.dict(os.environ, {'STUDIO_AUTOMATION_PROJECT_ID': 'foreign-project'}):
            self.assertEqual(self.client.get(f'{self.prefix}/jobs/{task}', headers=self.service).status_code, 404)
            self.assertEqual(self.client.get(self.ctxpath, headers=self.service).status_code, 404)
            self.assertEqual(self.claim(task).status_code, 404)
            self.assertEqual(self.callback(task).status_code, 404)
        with patch.dict(os.environ, {'STUDIO_AUTOMATION_TOKEN': ''}):
            self.assertEqual(self.client.get(self.ctxpath, headers=self.service).status_code, 503)
        # A remote service uses neither browser cookie. Other APIs keep the remote gate.
        with patch.dict(os.environ, {'STUDIO_REMOTE_HOSTS': 'studio.example.test', 'STUDIO_ACCESS_PASSWORD': 'test-password-12345'}):
            headers = {**self.service, 'Host': 'studio.example.test'}
            self.assertEqual(self.client.get(self.ctxpath, headers=headers).status_code, 200)
            self.assertEqual(self.client.get('/api/projects', headers=headers).status_code, 401)

    def test_paid_or_unknown_inputs_rejected(self):
        for change in ({'allowed_paid_media': True}, {'estimated_cost': 1}, {'model_provider': 'kie'},
                       {'model': 'paid-model'}, {'tools': ['http']}, {'approval_state': 'approved'}):
            self.assertEqual(self.create(**change).status_code, 422, change)

    def test_cancel_and_late_callback(self):
        task = self.create().json()['task_id']
        self.claim(task)
        path = f'{self.prefix}/jobs/{task}/cancel'
        self.assertEqual(self.client.post(path).json()['status'], 'cancelled')
        self.assertEqual(self.client.post(path).status_code, 200)
        self.assertEqual(self.callback(task).status_code, 409)
        self.assertEqual(self.claim(task).status_code, 409)

    def test_stale_revision_at_create_claim_callback_and_approval(self):
        self.assertEqual(self.create(base_revision='0' * 64).status_code, 409)
        self.assertEqual(self.create(canon_revision='0' * 64).status_code, 409)
        task = self.create().json()['task_id']
        self.claim(task)
        self.callback(task)
        with main.connect() as db:
            db.execute('UPDATE projects SET title=? WHERE id=?', ('Canon changed', self.project))
        self.assertEqual(self.client.post(f'{self.prefix}/jobs/{task}/review', json={'decision': 'approved'}).status_code, 409)
        # A new task against the refreshed context becomes stale when the scene changes.
        ctx = self.client.get(self.ctxpath, headers=self.service).json()
        self.body.update(canon_revision=ctx['canon_revision'], idempotency_key=uuid.uuid4().hex)
        waiting = self.create().json()['task_id']
        active = self.create(idempotency_key=uuid.uuid4().hex).json()['task_id']
        self.claim(active)
        self.new('frame', 'New shot', self.scene['id'])
        self.assertEqual(self.claim(waiting).status_code, 409)
        self.assertEqual(self.callback(active).status_code, 409)

    def test_vault_changes_invalidate_context_without_project_save(self):
        task = self.create().json()['task_id']
        with main.connect() as db:
            db.execute('INSERT INTO character_assets VALUES(?,?,?,?,?,?,?,?,?,?)',
                       ('vault-ref', self.project, 'grem', 'real_references', '', 'private.png', 'private.png', '', '', main.now()))
        self.assertEqual(self.claim(task).status_code, 409)
        ctx = self.client.get(self.ctxpath, headers=self.service).json()
        self.assertEqual(ctx['vault_references'][0]['id'], 'vault-ref')
        self.assertNotIn('private.png', str(ctx))

    def test_failed_result_and_rejected_review_are_terminal(self):
        task = self.create().json()['task_id']
        self.claim(task)
        self.assertEqual(self.callback(task, status='failed', proposal='').status_code, 400)
        failed = self.callback(task, status='failed', proposal='', error_code='SANDBOX_FAILURE')
        self.assertEqual(failed.json()['status'], 'failed')
        self.assertEqual(self.callback(task, status='failed', proposal='', error_code='SANDBOX_FAILURE').status_code, 200)
        self.assertEqual(self.claim(task).status_code, 409)
        second = self.create(idempotency_key=uuid.uuid4().hex).json()['task_id']
        self.claim(second)
        self.callback(second)
        self.assertEqual(self.client.post(f'{self.prefix}/jobs/{second}/review', json={'decision': 'rejected'}).json()['status'], 'rejected')
        self.assertEqual(self.client.post(f'{self.prefix}/jobs/{second}/review', json={'decision': 'approved'}).status_code, 409)
