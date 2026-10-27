import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from backend import motion, test_production


class MotionTests(unittest.TestCase):
    setUp = test_production.ProductionTests.setUp
    tearDown = test_production.ProductionTests.tearDown
    setup_production = test_production.ProductionTests.setup_production
    new = test_production.ProductionTests.new

    def test_prepare_sets_portrait_canvas(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            html = (motion.prepare('intro', '9:16', tmp) / 'index.html').read_text(encoding='utf-8')
            self.assertIn('data-width="1080" data-height="1920"', html)
            self.assertIn('width=1080, height=1920', html)
            self.assertTrue((Path(tmp) / 'project' / 'assets' / 'gsap.min.js').is_file())

    def test_render_saves_into_series_montage_folder(self):
        self.setup_production()
        series = self.new('series', 'Серия 1')
        seen = {}

        def fake_run(command, **kwargs):
            seen['command'] = command
            seen['values'] = json.loads(Path(command[command.index('--variables-file') + 1]).read_text(encoding='utf-8'))
            Path(command[command.index('-o') + 1]).write_bytes(b'mov-bytes')
            return subprocess.CompletedProcess(command, 0, '', '')

        url = f'/api/productions/{self.pid}/series/{series["id"]}/motion'
        with mock.patch.object(motion.shutil, 'which', return_value='npx'), mock.patch.object(motion.subprocess, 'run', fake_run):
            r = self.client.post(url, json={'template': 'lower-third', 'aspect': '9:16', 'values': {'name': ' Грэм ', 'role': ''}})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(seen['values'], {'name': 'Грэм'})
        self.assertIn('mov', seen['command'])
        self.assertTrue(r.json()['filename'].endswith('_9x16.mov'))
        files = self.client.get(f'/api/productions/{self.pid}/nodes/{series["id"]}').json()['files']
        self.assertIn('03_Монтаж', files[0]['relative_path'])
        self.assertEqual(self.client.get(r.json()['url']).content, b'mov-bytes')

    def test_render_rejects_unknown_fields_and_non_series(self):
        self.setup_production()
        series = self.new('series', 'Серия 1')
        episode = self.new('episode', 'Сцена', series['id'])
        with mock.patch.object(motion.shutil, 'which', return_value='npx'):
            r = self.client.post(f'/api/productions/{self.pid}/series/{series["id"]}/motion', json={'template': 'intro', 'values': {'evil': 'x'}})
            self.assertEqual(r.status_code, 400)
            r = self.client.post(f'/api/productions/{self.pid}/series/{episode["id"]}/motion', json={'template': 'intro'})
            self.assertEqual(r.status_code, 404)
