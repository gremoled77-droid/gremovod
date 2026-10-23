import io
import unittest
from PIL import Image, ImageDraw
from backend import edit_list, test_production


def picture(kind):
    image = Image.new('RGB', (96, 96), (120, 120, 120) if kind == 'flat' else 'white')
    if kind == 'stripes':
        draw = ImageDraw.Draw(image)
        for i in range(0, 96, 12):
            draw.rectangle((i, 0, i + 5, 96), fill='black')
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return stream.getvalue()


class EditListTests(unittest.TestCase):
    setUp = test_production.ProductionTests.setUp
    tearDown = test_production.ProductionTests.tearDown
    setup_production = test_production.ProductionTests.setup_production
    new = test_production.ProductionTests.new

    def build(self):
        self.setup_production()
        series = self.new('series', 'Серия')
        scene = self.new('episode', 'Встреча', series['id'])
        frames = [self.new('frame', t, scene['id']) for t in ('Общий', 'Крупный', 'Реакция')]
        for frame, kind in zip(frames[:2], ('stripes', 'flat')):
            r = self.client.post(f'/api/productions/{self.pid}/nodes/{frame["id"]}/upload', data={'category': '01_Исходники'},
                                 files={'file': (kind + '.png', picture(kind), 'image/png')})
            self.assertEqual(r.status_code, 200, r.text)
        r = self.client.post(f'/api/productions/{self.pid}/nodes/{frames[0]["id"]}/upload', data={'category': '03_Видео'},
                             files={'file': ('clip.mp4', b'not-a-real-video', 'video/mp4')})
        self.assertEqual(r.status_code, 200, r.text)
        put = lambda n, body: self.client.put(f'/api/productions/{self.pid}/nodes/{n["id"]}/visual-plan', json=body)
        put(frames[0], {'sector_end': 3, 'space': 'flat', 'line': 'horizontal'})
        put(frames[1], {'sector_start': 7, 'sector_end': 7, 'space': 'flat', 'line': 'horizontal'})
        put(frames[2], {'sector_start': 7, 'space': 'flat', 'line': 'horizontal'})
        return series, scene, frames

    def test_edit_list_order_cuts_warnings_and_csv(self):
        series, scene, frames = self.build()
        url = f'/api/productions/{self.pid}/series/{series["id"]}/edit-list'
        data = self.client.get(url).json()
        self.assertEqual([r['title'] for r in data['rows']], ['Общий', 'Крупный', 'Реакция'])
        self.assertEqual(data['summary']['shots'], 3)
        self.assertEqual(data['summary']['with_video'], 1)
        first = data['rows'][0]
        self.assertEqual(first['sector_cut'], 'прыжок')
        self.assertTrue(first['video'].endswith('clip.mp4'))
        self.assertIsNotNone(first['image_cut'])
        self.assertGreater(first['image_cut']['score'], 0.2)
        self.assertEqual(data['rows'][1]['sector_cut'], 'гладкая')
        self.assertIsNone(data['rows'][2]['image_cut'])
        self.assertTrue(any('нет видео' in w for w in data['warnings']))
        self.assertTrue(any('повторяют' in w for w in data['warnings']))
        csv_response = self.client.get(url, params={'format': 'csv'})
        self.assertEqual(csv_response.status_code, 200)
        self.assertTrue(csv_response.text.startswith('﻿№;Сцена'))
        self.assertIn('Крупный', csv_response.text)
        self.assertEqual(self.client.get(url, params={'format': 'xml'}).status_code, 400)
        self.assertEqual(self.client.get(f'/api/productions/{self.pid}/series/{scene["id"]}/edit-list').status_code, 404)

    def test_new_candidate_does_not_replace_main_video(self):
        series, scene, frames = self.build()
        url = f'/api/productions/{self.pid}/series/{series["id"]}/edit-list'
        upload = lambda name: self.client.post(f'/api/productions/{self.pid}/nodes/{frames[0]["id"]}/upload', data={'category': '03_Видео'},
                                               files={'file': (name, b'not-a-real-video', 'video/mp4')})
        data = self.client.get(url).json()
        self.assertEqual(data['rows'][0]['video_choice'], 'candidate')
        self.assertEqual(data['rows'][1]['video_choice'], 'none')
        self.assertTrue(any('1.1' in w and 'предварительно' in w for w in data['warnings']))
        self.assertEqual((data['summary']['approved_videos'], data['summary']['ready']), (0, False))
        self.assertIn('предварительно', self.client.get(url, params={'format': 'csv'}).text)
        # Без выбора новый файл подменяет прежний, но лист честно помечает его как предварительный.
        upload('second.mp4')
        data = self.client.get(url).json()
        self.assertTrue(data['rows'][0]['video'].endswith('second.mp4'))
        self.assertEqual(data['rows'][0]['video_choice'], 'candidate')
        editor = self.client.get(f'/api/productions/{self.pid}/nodes/{frames[0]["id"]}/editor').json()
        clip = next(f for f in editor['files'] if f['filename'] == 'clip.mp4')
        saved = self.client.put(f'/api/productions/{self.pid}/nodes/{frames[0]["id"]}/editor',
                                json={**editor['data'], 'base_revision': editor['revision'], 'notes': editor['node']['notes'], 'selected_video_file_id': clip['id']})
        self.assertEqual(saved.status_code, 200, saved.text)
        upload('new-unapproved.mp4')
        data = self.client.get(url).json()
        self.assertTrue(data['rows'][0]['video'].endswith('clip.mp4'))
        self.assertEqual(data['rows'][0]['video_choice'], 'main')
        self.assertEqual(data['summary']['approved_videos'], 1)
        self.assertFalse(any('1.1' in w and 'предварительно' in w for w in data['warnings']))

    def test_vertical_prompt_and_project_rules(self):
        series, scene, frames = self.build()
        self.client.put(f'/api/productions/{self.pid}/nodes/{series["id"]}/visual-rules', json={'palette': 'ochre and teal'})
        got = self.client.get(f'/api/productions/{self.pid}/nodes/{frames[0]["id"]}/vertical-prompt').json()['prompt']
        self.assertIn('do not crop', got)
        self.assertIn('one frontal plane', got)
        self.assertIn('ochre and teal', got)
        self.assertEqual(self.client.get(f'/api/productions/{self.pid}/nodes/{scene["id"]}/vertical-prompt').status_code, 400)
        self.assertEqual(self.client.get(f'/api/productions/{self.pid}/nodes/absent/vertical-prompt').status_code, 404)
        opened = self.client.post(f'/api/productions/{self.pid}/nodes/{frames[0]["id"]}/open-project').json()['project_id']
        rules = self.client.get(f'/api/projects/{opened}/visual-rules-prompt').json()['prompt']
        self.assertIn('ochre and teal', rules)
        alone = self.client.post('/api/projects', json={'title': 'Alone', 'state': {}}).json()['id']
        self.assertEqual(self.client.get(f'/api/projects/{alone}/visual-rules-prompt').json()['prompt'], '')

    def test_label_thresholds(self):
        self.assertEqual([edit_list.label(v) for v in (0.1, 0.3, 0.7)], ['гладкая', 'заметная', 'резкая'])


if __name__ == '__main__':
    unittest.main()
