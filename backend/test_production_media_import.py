import unittest
from backend import test_production


class ProductionMediaImportTests(unittest.TestCase):
    setUp = test_production.ProductionTests.setUp
    tearDown = test_production.ProductionTests.tearDown
    setup_production = test_production.ProductionTests.setup_production
    setup_frame = test_production.ProductionTests.setup_frame
    new = test_production.ProductionTests.new

    def test_local_video_and_audio_are_visible_in_own_project_library(self):
        self.setup_production()
        self.setup_frame()
        for kind, ext, category in [('video', 'mp4', '03_Видео'), ('audio', 'wav', '04_Звук')]:
            payload = ('local-' + kind).encode()
            response = self.client.post(self.framebase + '/upload', data={'category': category},
                                        files={'file': ('local.' + ext, payload)})
            self.assertEqual(response.status_code, 200, response.text)
            fid = response.json()['id']
            own = self.client.get('/api/library', params={'project_id': self.frameproject}).json()
            asset = next(a for a in own if a['id'] == fid)
            self.assertEqual(asset['metadata']['kind'], kind)
            self.assertEqual(asset['metadata']['provider'], 'local_import')
            self.assertEqual(self.client.get(asset['url']).content, payload)
            other = self.client.get('/api/library', params={'project_id': self.project}).json()
            self.assertNotIn(fid, [a['id'] for a in other])
