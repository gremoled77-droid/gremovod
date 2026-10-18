"""Long Windows production paths: real files, API roundtrip and import rollback."""
import sys
import shutil
import unittest
import uuid
from pathlib import Path

from backend import main, production_folders as folders
from backend import test_production


class ProductionPathTests(unittest.TestCase):
    setUp = test_production.ProductionTests.setUp
    new = test_production.ProductionTests.new

    def tearDown(self):
        # tempfile's normal Win32 cleanup cannot traverse the paths under test.
        self.assertTrue(main.PRODUCTIONS_ROOT.resolve().is_relative_to(Path(self.temp.name).resolve()))
        root = folders.checked_path(main, '.')
        if root.exists():
            shutil.rmtree(root)
        test_production.ProductionTests.tearDown(self)

    def prepare_long_series(self):
        result = self.client.post('/api/productions', json={'title': 'Производство' * 6})
        self.assertEqual(result.status_code, 200, result.text)
        self.pid = result.json()['id']
        response = self.client.post(f'/api/productions/{self.pid}/nodes', json={
            'kind': 'series', 'title': 'Длинное название серии ' * 3, 'guest': 'Имя гостя ' * 7})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_deep_frame_upload_roundtrip_preserves_stored_paths(self):
        series = self.prepare_long_series()
        scene = self.new('episode', 'Длинное название сцены ' * 3, series['id'])
        frame = self.new('frame', 'Длинное название кадра ' * 3, scene['id'])
        original = frame['relative_dir']
        self.assertGreater(len(str(main.PRODUCTIONS_ROOT / original)), 260)
        self.assertFalse(Path(original).is_absolute())
        path = folders.checked_path(main, original)
        if sys.platform == 'win32':
            self.assertTrue(str(path).startswith('\\\\?\\'))
        self.assertTrue((path / 'КАДР.md').is_file())
        payload = b'Local production document on a long path'
        response = self.client.post(f'/api/productions/{self.pid}/nodes/{frame["id"]}/upload',
            data={'category': '01_Исходники'}, files={'file': ('note.txt', payload, 'text/plain')})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get(response.json()['url']).content, payload)
        self.assertEqual(folders.node(main, self.pid, frame['id'])['relative_dir'], original)
        with self.assertRaises(main.HTTPException):
            folders.checked_path(main, '../../escape')

    def test_long_import_conflict_rolls_back_created_files_and_keeps_existing(self):
        series = self.prepare_long_series()
        url = f'/api/productions/{self.pid}/series/{series["id"]}/storyboard'
        board = self.client.get(url).json()
        parent = folders.checked_path(main, Path(series['relative_dir']) / '02_Эпизоды')
        existing = parent / '002_Занято'
        existing.mkdir()
        (existing / 'keep.txt').write_text('existing', encoding='utf-8')
        response = self.client.post(url + '/import', json={
            'base_revision': board['revision'], 'request_id': uuid.uuid4().hex,
            'script': 'Сцена 1 — Новая\nТекст.\nСцена 2 — Занято\nТекст.'})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertFalse((parent / '001_Новая').exists())
        self.assertEqual((existing / 'keep.txt').read_text(encoding='utf-8'), 'existing')
        self.assertFalse(self.client.get(url).json()['scenes'])
