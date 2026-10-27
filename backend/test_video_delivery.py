import asyncio
import json
import subprocess
import unittest
from unittest.mock import AsyncMock, patch
from backend import clip_chain, job_delivery, main, test_smoke


class VideoDeliveryTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def mp4(self):
        import tempfile
        from pathlib import Path
        binary = clip_chain.ffmpeg_path(main)
        if not binary:
            self.skipTest('FFmpeg не установлен')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'clip.mp4'
            subprocess.run([binary, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc=duration=1:size=160x90:rate=10', '-pix_fmt', 'yuv420p', str(path)], check=True)
            return path.read_bytes()

    def test_monitor_saves_finished_video_by_itself_once(self):
        project = self.client.post('/api/projects', json={'title': 'Video', 'state': {}}).json()['id']
        response = {'data': {'task_id': 'video-task', 'status': 'completed', 'output': {'video_url': 'https://cdn.example.test/clip.mp4'}}}
        with main.connect() as db:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',
                       ('video-job', project, 'video', 'piapi', 'video-task', 'completed', json.dumps({'model_id': 'minimax-h3'}), json.dumps(response), main.now()))
        content = self.mp4()
        with patch.object(main, 'download_video', AsyncMock(return_value=content)) as download:
            asyncio.run(job_delivery.cycle(main))
            asyncio.run(job_delivery.cycle(main))
            download.assert_awaited_once()
        assets = self.client.get('/api/library', params={'project_id': project}).json()
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]['metadata']['kind'], 'video')
        self.assertEqual((assets[0]['metadata']['width'], assets[0]['metadata']['height']), (160, 90))
        self.assertEqual(self.client.get('/api/jobs').json()[0]['delivery']['state'], 'saved')
        activity = self.client.get('/api/activity', params={'project_id': project}).json()['items']
        self.assertEqual(activity[0]['asset_ids'], [assets[0]['id']])

    def test_manual_save_after_automatic_one_does_not_duplicate(self):
        project = self.client.post('/api/projects', json={'title': 'Video', 'state': {}}).json()['id']
        response = {'data': {'task_id': 'video-task', 'status': 'completed', 'output': {'video_url': 'https://cdn.example.test/clip.mp4'}}}
        with main.connect() as db:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',
                       ('video-job', project, 'video', 'piapi', 'video-task', 'completed', '{}', json.dumps(response), main.now()))
        with patch.object(main, 'download_video', AsyncMock(return_value=self.mp4())) as download:
            asyncio.run(job_delivery.cycle(main))
            saved = self.client.post('/api/jobs/video-job/outputs/0/save')
            self.assertEqual(saved.status_code, 200, saved.text)
            download.assert_awaited_once()
        self.assertEqual(len(self.client.get('/api/library', params={'project_id': project}).json()), 1)


if __name__ == '__main__':
    unittest.main()
