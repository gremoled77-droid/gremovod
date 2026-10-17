import io
import unittest
from PIL import Image
from backend import test_smoke


class MediaDetailsTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def make(self):
        pid = self.client.post('/api/projects', json={'state': {}}).json()['id']
        image = io.BytesIO(); Image.new('RGB', (30, 40), 'blue').save(image, format='PNG')
        result = self.client.post('/api/library/import-image', data={'project_id': pid},
                                  files={'file': ('ref.png', image.getvalue(), 'image/png')})
        self.assertEqual(result.status_code, 200, result.text)
        return pid, result.json()['id']

    def test_details_match_library_and_track_favorite_and_soft_trash(self):
        pid, aid = self.make()
        path = '/api/library/' + aid
        before = self.client.get('/api/library', params={'project_id': pid}).json()[0]
        detail = self.client.get(path + '/details')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json(), before)
        self.assertEqual(self.client.post(path + '/favorite', json={'favorite': True}).status_code, 200)
        self.assertTrue(self.client.get(path + '/details').json()['metadata']['favorite'])
        self.assertEqual(self.client.post(path + '/trash').status_code, 200)
        self.assertEqual(self.client.get(path + '/details').status_code, 404)
        journal = self.client.get('/api/library/cleanup/journal', params={'project_id': pid}).json()
        self.assertEqual(self.client.post('/api/library/cleanup/restore/' + str(journal[0]['id'])).status_code, 200)
        self.assertEqual(self.client.get(path + '/details').json()['id'], aid)

    def test_used_file_stays_available_after_refused_trash(self):
        pid, aid = self.make()
        project = self.client.get('/api/projects/' + pid).json()
        self.client.post('/api/projects', json={'id': pid, 'title': 'Used', 'state': {'scene': {'asset_id': aid}}, 'base_revision': project['revision']})
        result = self.client.post('/api/library/' + aid + '/trash')
        self.assertEqual(result.status_code, 409)
        self.assertEqual(self.client.get('/api/library/' + aid + '/details').status_code, 200)
        self.assertEqual(self.client.get('/api/library/not-found/details').status_code, 404)
