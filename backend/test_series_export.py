"""Export real temporary files; no providers, working databases, or external uploads."""
import csv
import io
import json
import unittest
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from backend import main, series_export, test_production


class SeriesExportTests(unittest.TestCase):
    setUp = test_production.ProductionTests.setUp
    tearDown = test_production.ProductionTests.tearDown
    setup_production = test_production.ProductionTests.setup_production
    new = test_production.ProductionTests.new

    def prepare(self):
        self.setup_production()
        self.series = self.new('series', 'Экспорт')
        self.scene = self.new('episode', 'Сцена', self.series['id'])
        self.frames = [self.new('frame', title, self.scene['id']) for title in ('Первый', 'Второй')]
        app = FastAPI()
        series_export.register(app, main)
        self.export_client = TestClient(app)
        self.addCleanup(self.export_client.close)
        self.url = f'/api/productions/{self.pid}/series/{self.series["id"]}/export.zip'

    def upload(self, node, filename, content, category='03_Видео'):
        response = self.client.post(f'/api/productions/{self.pid}/nodes/{node["id"]}/upload',
                                    data={'category': category}, files={'file': (filename, content)})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_selected_ordered_media_and_sound_inside_zip(self):
        self.prepare()
        selected = self.upload(self.frames[0], 'chosen.mp4', b'chosen-video')
        self.upload(self.frames[0], 'other.mp4', b'unselected-video')
        self.upload(self.frames[1], 'next.mp4', b'next-video')
        picture = io.BytesIO()
        Image.new('RGB', (8, 8), 'blue').save(picture, format='PNG')
        self.upload(self.frames[1], 'frame.png', picture.getvalue(), '02_Изображения')
        audio = self.upload(self.frames[1], 'sound.wav', b'frame-sound', '04_Звук')
        self.upload(self.series, 'music.mp3', b'series-music', '03_Монтаж')
        with main.connect() as db:
            db.execute('INSERT INTO production_entity_state(node_id,data,updated_at) VALUES(?,?,CURRENT_TIMESTAMP)',
                       (self.frames[0]['id'], json.dumps({'selected_video_file_id': selected['id']})))
        cue = self.client.post(f'/api/productions/{self.pid}/nodes/{self.frames[1]["id"]}/sound',
                               json={'kind': 'sfx', 'text': 'Дверь', 'start_s': 1.25}).json()
        with main.connect() as db:
            db.execute('UPDATE frame_sound_cues SET file_id=? WHERE id=?', (audio['id'], cue['id']))
        response = self.export_client.get(self.url)
        self.assertEqual(response.status_code, 200, response.text if response.status_code != 200 else '')
        self.assertEqual(response.headers['content-type'], 'application/zip')
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            names = z.namelist()
            self.assertFalse(any('other.mp4' in name for name in names))
            self.assertEqual(z.read('01_Видео/0001_chosen.mp4'), b'chosen-video')
            self.assertEqual(z.read('01_Видео/0002_next.mp4'), b'next-video')
            self.assertEqual(z.read('02_Кадры/0002_frame.png'), picture.getvalue())
            self.assertEqual(sum(z.read(n) == b'frame-sound' for n in names), 1)
            self.assertEqual(sum(z.read(n) == b'series-music' for n in names), 1)
            rows = list(csv.reader(io.StringIO(z.read('edit-list.csv').decode('utf-8-sig')), delimiter=';'))
            self.assertEqual([r[3] for r in rows[1:]], ['Первый', 'Второй'])
            self.assertIn('главный дубль', rows[1][-1])
            self.assertIn('последний дубль', rows[2][-1])
            sounds = z.read('sound-list.csv').decode('utf-8-sig')
            self.assertIn('1.25', sounds)
            self.assertIn('03_Звук/', sounds)
            self.assertIn('не нативный проект', z.read('README.txt').decode('utf-8-sig'))
            self.assertTrue(all('..' not in n and not n.startswith('/') for n in names))

    def test_empty_series_is_a_valid_package_and_stale_selection_is_not_replaced(self):
        self.prepare()
        empty = self.new('series', 'Пустая')
        with series_export.package(main, self.pid, empty['id']) as stream, zipfile.ZipFile(stream) as z:
            self.assertEqual(set(z.namelist()), {'edit-list.csv', 'sound-list.csv', 'audio-files.csv', 'README.txt'})
        other = self.upload(self.frames[1], 'foreign-take.mp4', b'other-frame')
        self.upload(self.frames[0], 'fallback.mp4', b'wrong-fallback')
        with main.connect() as db:
            db.execute('INSERT INTO production_entity_state(node_id,data,updated_at) VALUES(?,?,CURRENT_TIMESTAMP)',
                       (self.frames[0]['id'], json.dumps({'selected_video_file_id': other['id']})))
        with series_export.package(main, self.pid, self.series['id']) as stream, zipfile.ZipFile(stream) as z:
            self.assertFalse(any('fallback' in n for n in z.namelist()))
            self.assertIn('другой дубль не подставлен', z.read('README.txt').decode('utf-8-sig'))

    def test_missing_files_and_invalid_selection_do_not_substitute_other_take(self):
        self.prepare()
        selected = self.upload(self.frames[0], 'missing.mp4', b'gone')
        self.upload(self.frames[0], 'other.mp4', b'not-approved')
        with main.connect() as db:
            row = db.execute('SELECT relative_path FROM production_files WHERE id=?', (selected['id'],)).fetchone()
            db.execute('INSERT INTO production_entity_state(node_id,data,updated_at) VALUES(?,?,CURRENT_TIMESTAMP)',
                       (self.frames[0]['id'], json.dumps({'selected_video_file_id': selected['id']})))
        (main.PRODUCTIONS_ROOT / row['relative_path']).unlink()
        with series_export.package(main, self.pid, self.series['id']) as stream, zipfile.ZipFile(stream) as z:
            self.assertFalse(any(n.endswith('.mp4') for n in z.namelist()))
            self.assertIn('Файл отсутствует', z.read('README.txt').decode('utf-8-sig'))

    def test_series_scope_and_path_escape_are_rejected(self):
        self.prepare()
        self.assertEqual(self.export_client.get(self.url.replace(self.pid, 'foreign')).status_code, 404)
        self.assertEqual(self.export_client.get(self.url.replace(self.series['id'], self.scene['id'])).status_code, 404)
        uploaded = self.upload(self.frames[0], 'clip.mp4', b'safe')
        # A registered file must stay inside the requested series, even if another series shares the production.
        other = self.new('series', 'Другая серия')
        foreign = self.upload(other, 'foreign.mp4', b'private', '03_Монтаж')
        with main.connect() as db:
            path = db.execute('SELECT relative_path FROM production_files WHERE id=?', (foreign['id'],)).fetchone()[0]
            db.execute('UPDATE production_files SET relative_path=? WHERE id=?', (path, uploaded['id']))
        self.assertEqual(self.export_client.get(self.url).status_code, 400)
        with main.connect() as db:
            db.execute('UPDATE production_files SET relative_path=? WHERE id=?', ('../../outside.mp4', uploaded['id']))
        self.assertEqual(self.export_client.get(self.url).status_code, 400)


if __name__ == '__main__':
    unittest.main()
