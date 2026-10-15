"""Кнопка «В референсы»: копия результата в папку персонажа."""
import io
import unittest

from PIL import Image

from backend import test_smoke


def png(color=(8, 80, 8)):
    buffer = io.BytesIO()
    Image.new('RGB', (40, 40), color).save(buffer, 'PNG')
    return buffer.getvalue()


class SendToReferenceTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def make(self):
        pid = self.client.post('/api/projects', json={'state': {'characters': [{'id': 'grem', 'name': 'Грэм'}]}}).json()['id']
        asset = self.client.post('/api/library/import-image', data={'project_id': pid},
                                 files={'file': ('r.png', png(), 'image/png')}).json()['id']
        return pid, asset

    def test_copies_result_and_lists_it(self):
        pid, asset = self.make()
        r = self.client.post(f'/api/library/{asset}/to-character',
                             json={'project_id': pid, 'character_id': 'grem', 'category': 'approved_generations'})
        self.assertEqual(r.status_code, 200, r.text)
        listed = self.client.get(f'/api/characters/{pid}/grem/assets').json()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]['category'], 'approved_generations')
        self.assertEqual(self.client.get(r.json()['url']).status_code, 200)
        self.assertEqual(self.client.get(f'/api/library/{asset}/file').status_code, 200)  # оригинал на месте

    def test_duplicate_category_and_model_reference_validation(self):
        pid, asset = self.make()
        body = {'project_id': pid, 'character_id': 'grem', 'category': 'real_references'}
        self.assertEqual(self.client.post(f'/api/library/{asset}/to-character', json=body).status_code, 200)
        self.assertEqual(self.client.post(f'/api/library/{asset}/to-character', json=body).status_code, 409)
        bad = {**body, 'category': 'model_references', 'model_id': 'nope'}
        self.assertEqual(self.client.post(f'/api/library/{asset}/to-character', json=bad).status_code, 400)
        ok = {**body, 'category': 'model_references', 'model_id': 'seedream-5-lite'}
        self.assertEqual(self.client.post(f'/api/library/{asset}/to-character', json=ok).status_code, 200)

    def test_foreign_asset_and_bad_category(self):
        pid, asset = self.make()
        other = self.client.post('/api/projects', json={'state': {}}).json()['id']
        r = self.client.post(f'/api/library/{asset}/to-character',
                             json={'project_id': other, 'character_id': 'grem', 'category': 'approved_generations'})
        self.assertEqual(r.status_code, 404)
        r = self.client.post(f'/api/library/{asset}/to-character',
                             json={'project_id': pid, 'character_id': 'grem', 'category': 'hack'})
        self.assertEqual(r.status_code, 400)


if __name__ == '__main__':
    unittest.main()
