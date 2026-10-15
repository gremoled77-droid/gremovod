"""Ручной маршрут внешней генерации: задание, текст для копирования, возврат картинки, экономика."""
import io
import json
import unittest

from PIL import Image

from backend import main
from backend import test_smoke


def png(color=(120, 30, 90)):
    buffer = io.BytesIO()
    Image.new('RGB', (64, 48), color).save(buffer, 'PNG')
    return buffer.getvalue()


class ExternalGenerationTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def project(self):
        return self.client.post('/api/projects', json={'state': {'brief': 'x'}}).json()['id']

    def reference(self, pid):
        r = self.client.post('/api/library/import-image', data={'project_id': pid},
                             files={'file': ('ref.png', png((5, 5, 5)), 'image/png')})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()['id']

    def create(self, pid, **extra):
        body = {'project_id': pid, 'request_id': 'external-test-request-0001', 'prompt': 'Grem turns to the guest',
                'target': 'gpt-image-2.5', **extra}
        return self.client.post('/api/external-jobs', json=body)

    def test_create_builds_copy_text_with_reference_order(self):
        pid = self.project()
        a, b = self.reference(pid), self.reference(pid)
        r = self.create(pid, references=[{'asset_id': a, 'role': 'Грэм'}, {'asset_id': b, 'role': 'салон'}])
        self.assertEqual(r.status_code, 200, r.text)
        job = r.json()
        self.assertEqual(job['status'], 'waiting_external')
        self.assertIn('Grem turns to the guest', job['copy_text'])
        self.assertIn('Image 1 — Грэм', job['copy_text'])
        self.assertIn('Image 2 — салон', job['copy_text'])
        self.assertEqual(job['references'][1]['file_url'], f'/api/library/{b}/file')
        self.assertEqual(main.request_piapi.await_count, 0)

    def test_idempotent_and_conflicting_request_id(self):
        pid = self.project()
        first = self.create(pid).json()
        again = self.create(pid).json()
        self.assertTrue(again['duplicate'])
        self.assertEqual(first['id'], again['id'])
        conflict = self.create(pid, prompt='Different prompt')
        self.assertEqual(conflict.status_code, 409)

    def test_rejects_unknown_model_video_model_and_foreign_reference(self):
        pid = self.project()
        self.assertEqual(self.create(pid, target='nope').status_code, 400)
        self.assertEqual(self.create(pid, target='seedance-2.5').status_code, 400)
        other = self.project()
        foreign = self.reference(other)
        r = self.create(pid, references=[{'asset_id': foreign, 'role': 'x'}])
        self.assertEqual(r.status_code, 404)

    def test_result_is_saved_as_separate_attempt_linked_to_job(self):
        pid = self.project()
        job = self.create(pid, node_id='shot-2-3').json()
        r = self.client.post(f'/api/external-jobs/{job["id"]}/result', files={'file': ('chatgpt.png', png(), 'image/png')})
        self.assertEqual(r.status_code, 200, r.text)
        asset = r.json()['asset']
        self.assertEqual(asset['metadata']['provider'], 'external:chatgpt')
        self.assertEqual(asset['metadata']['external_job_id'], job['id'])
        self.assertEqual(asset['metadata']['target'], 'gpt-image-2.5')
        again = self.client.post(f'/api/external-jobs/{job["id"]}/result', files={'file': ('chatgpt.png', png(), 'image/png')})
        self.assertEqual(again.status_code, 409)  # тот же файл повторно
        second = self.client.post(f'/api/external-jobs/{job["id"]}/result', files={'file': ('v2.png', png((9, 9, 200)), 'image/png')})
        self.assertEqual(second.status_code, 200)
        listed = self.client.get(f'/api/external-jobs/{job["id"]}').json()
        self.assertEqual(listed['status'], 'received')
        self.assertEqual(len(listed['results']), 2)
        by_node = self.client.get('/api/external-jobs', params={'project_id': pid, 'node_id': 'shot-2-3'}).json()
        self.assertEqual(len(by_node), 1)
        self.assertEqual(self.client.get(asset['url']).status_code, 200)

    def test_invalid_file_and_cancelled_job(self):
        pid = self.project()
        job = self.create(pid).json()
        bad = self.client.post(f'/api/external-jobs/{job["id"]}/result', files={'file': ('x.png', b'not an image', 'image/png')})
        self.assertEqual(bad.status_code, 422)
        self.assertEqual(self.client.get(f'/api/external-jobs/{job["id"]}').json()['status'], 'waiting_external')
        cancelled = self.client.post(f'/api/external-jobs/{job["id"]}/cancel').json()
        self.assertEqual(cancelled['status'], 'cancelled')
        late = self.client.post(f'/api/external-jobs/{job["id"]}/result', files={'file': ('a.png', png(), 'image/png')})
        self.assertEqual(late.status_code, 409)

    def test_economics_counts_external_attempt_as_free_with_api_equivalent(self):
        pid = self.project()
        job = self.create(pid).json()
        self.client.post(f'/api/external-jobs/{job["id"]}/result', files={'file': ('a.png', png(), 'image/png')})
        report = self.client.get('/api/economics', params={'project_id': pid}).json()
        attempt = next(x for x in report['jobs'] if x['id'] == job['id'])
        self.assertEqual(attempt['provider'], 'external:chatgpt')
        self.assertEqual(attempt['status'], 'completed')
        self.assertTrue(report['media_costs_complete'])
        self.assertEqual(report['unknown_generation_cost_count'], 0)
        self.assertEqual(report['attempts'], 1)
        self.assertIsNotNone(attempt['api_equivalent'])


if __name__ == '__main__':
    unittest.main()
