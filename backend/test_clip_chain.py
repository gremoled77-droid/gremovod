import json
import subprocess
import unittest
import uuid
from backend import clip_chain, main, test_smoke


class ClipChainTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def make_asset(self, project, kind):
        aid = uuid.uuid4().hex
        main.LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
        name = aid + ('.mp4' if kind == 'video' else '.png')
        path = main.LIBRARY_ROOT / name
        if kind == 'video':
            binary = clip_chain.ffmpeg_path(main)
            subprocess.run([binary, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=160x90:rate=10', '-pix_fmt', 'yuv420p', str(path)], check=True)
        else:
            path.write_bytes(b'x')
        with main.connect() as db:
            db.execute('INSERT INTO library_assets VALUES(?,?,?,?,?,?,?,?)', (aid, 'j-' + aid, project, 0, name, '', json.dumps({'kind': kind}), main.now()))
        return aid

    def test_last_frame_becomes_image_asset_linked_to_clip(self):
        if not clip_chain.ffmpeg_path(main):
            self.skipTest('FFmpeg не установлен')
        project = self.client.post('/api/projects', json={'title': 'Chain', 'state': {}}).json()['id']
        video = self.make_asset(project, 'video')
        response = self.client.post(f'/api/library/{video}/last-frame')
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body['metadata']['kind'], 'image')
        self.assertEqual(body['metadata']['source_asset_id'], video)
        self.assertEqual((body['metadata']['width'], body['metadata']['height']), (160, 90))
        self.assertEqual(self.client.get(body['url']).status_code, 200)
        listed = [a['id'] for a in self.client.get('/api/library', params={'project_id': project}).json()]
        self.assertIn(body['id'], listed)

    def test_only_videos_and_existing_assets(self):
        project = self.client.post('/api/projects', json={'title': 'Chain', 'state': {}}).json()['id']
        image = self.make_asset(project, 'image')
        self.assertEqual(self.client.post(f'/api/library/{image}/last-frame').status_code, 400)
        self.assertEqual(self.client.post('/api/library/missing/last-frame').status_code, 404)


if __name__ == '__main__':
    unittest.main()
