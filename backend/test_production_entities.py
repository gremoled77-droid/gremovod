"""Рабочее место кадра: один ответ для инструментов, без переключения проекта приложения."""
import io
import json
import unittest

from PIL import Image

from backend import main, test_production, test_smoke


def png():
    image = io.BytesIO()
    Image.new('RGB', (32, 20), 'red').save(image, format='PNG')
    return image.getvalue()


class FrameWorkspaceTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown
    setup_production = test_production.ProductionTests.setup_production
    new = test_production.ProductionTests.new

    def upload(self, nid, category, name, data, ctype):
        r = self.client.post(f'/api/productions/{self.pid}/nodes/{nid}/upload', data={'category': category}, files={'file': (name, data, ctype)})
        self.assertEqual(r.status_code, 200, r.text)

    def test_workspace_reports_place_choice_sound_jobs_and_project(self):
        self.setup_production()
        series = self.new('series', 'Серия')
        scene = self.new('episode', 'Вокзал', series['id'])
        frame = self.new('frame', 'Крупный', scene['id'])
        url = f'/api/productions/{self.pid}/nodes/{frame["id"]}/workspace'
        empty = self.client.get(url).json()
        self.assertIsNone(empty['project_id'])
        self.assertEqual((empty['series']['id'], empty['scene']['id'], empty['frame']['title']), (series['id'], scene['id'], 'Крупный'))
        self.assertEqual((empty['image_choice'], empty['video_choice'], empty['files'], empty['jobs']), ('none', 'none', [], []))
        self.upload(frame['id'], '02_Изображения', 'a.png', png(), 'image/png')
        self.upload(frame['id'], '03_Видео', 'take.mp4', b'not-a-real-video', 'video/mp4')
        cue = self.client.post(f'/api/productions/{self.pid}/nodes/{frame["id"]}/sound', json={
            'kind': 'ambience', 'text': 'вокзал', 'hero_node_id': None, 'level_db': -20, 'start_s': 0, 'duration_s': None})
        self.assertEqual(cue.status_code, 200, cue.text)
        got = self.client.get(url).json()
        self.assertEqual((got['image_choice'], got['video_choice']), ('candidate', 'candidate'))
        self.assertEqual([c['text'] for c in got['cues']], ['вокзал'])
        video = got['video']['id']
        saved = self.client.put(f'/api/productions/{self.pid}/nodes/{frame["id"]}/editor', json={
            **got['selection'], 'base_revision': got['revision'], 'notes': got['frame']['notes'], 'selected_video_file_id': video})
        self.assertEqual(saved.status_code, 200, saved.text)
        # Проект кадра открывается на сервере; приложение его не переключает, но инструменты берут его из ответа.
        project = self.client.post(f'/api/productions/{self.pid}/nodes/{frame["id"]}/open-project').json()['project_id']
        with main.connect() as db:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)', ('job-1', project, 'video', 'piapi', None, 'processing',
                                                                    json.dumps({'model_id': 'minimax-h3'}), '{}', main.now()))
        got = self.client.get(url).json()
        self.assertEqual(got['project_id'], project)
        self.assertEqual((got['video_choice'], got['video']['id']), ('main', video))
        self.assertEqual([(j['id'], j['status']) for j in got['jobs']], [('job-1', 'running')])
        self.assertEqual(self.client.get(f'/api/productions/{self.pid}/nodes/{scene["id"]}/workspace').status_code, 400)
        self.assertEqual(self.client.get(f'/api/productions/missing/nodes/{frame["id"]}/workspace').status_code, 404)


if __name__ == '__main__':
    unittest.main()
