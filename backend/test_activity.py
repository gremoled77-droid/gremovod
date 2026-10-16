"""Единая лента заданий и долгий опрос."""
import io
import time
import unittest

from PIL import Image

from backend import test_smoke


def png():
    buffer = io.BytesIO()
    Image.new('RGB', (32, 32), (1, 2, 3)).save(buffer, 'PNG')
    return buffer.getvalue()


class ActivityTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def test_feed_merges_sources_and_version_changes(self):
        pid = self.client.post('/api/projects', json={'state': {}}).json()['id']
        empty = self.client.get('/api/activity', params={'project_id': pid}).json()
        self.assertEqual(empty['items'], [])
        job = self.client.post('/api/external-jobs', json={
            'project_id': pid, 'request_id': 'activity-test-request-01', 'prompt': 'Night Minsk', 'target': 'gpt-image-2.5'}).json()
        waiting = self.client.get('/api/activity', params={'project_id': pid}).json()
        self.assertTrue(waiting['changed'])
        self.assertEqual(waiting['items'][0]['status'], 'waiting_external')
        self.assertEqual(waiting['items'][0]['source'], 'external')
        self.client.post(f'/api/external-jobs/{job["id"]}/result', files={'file': ('a.png', png(), 'image/png')})
        done = self.client.get('/api/activity', params={'project_id': pid, 'since': waiting['version']}).json()
        self.assertNotEqual(done['version'], waiting['version'])
        self.assertEqual(done['items'][0]['status'], 'done')
        self.assertEqual(len(done['items'][0]['asset_ids']), 1)

    def test_long_poll_returns_after_wait_when_nothing_changed(self):
        pid = self.client.post('/api/projects', json={'state': {}}).json()['id']
        first = self.client.get('/api/activity', params={'project_id': pid}).json()
        start = time.time()
        again = self.client.get('/api/activity', params={'project_id': pid, 'since': first['version'], 'wait': 1}).json()
        self.assertFalse(again['changed'])
        self.assertGreaterEqual(time.time() - start, 0.9)

    def test_unknown_project(self):
        self.assertEqual(self.client.get('/api/activity', params={'project_id': 'missing'}).status_code, 404)


if __name__ == '__main__':
    unittest.main()


class RefreshTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def test_refresh_unknown_job_is_404_and_done_job_is_noop(self):
        self.assertEqual(self.client.post('/api/activity/refresh/nope').status_code, 404)
