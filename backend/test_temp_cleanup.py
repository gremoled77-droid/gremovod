"""Временная папка: сердечко, срок 7 дней, мягкое удаление и восстановление."""
import io
import json
import unittest
from datetime import datetime, timedelta, timezone

from PIL import Image

from backend import temp_cleanup, test_smoke


def png():
    b = io.BytesIO()
    Image.new('RGB', (30, 30), (5, 50, 5)).save(b, 'PNG')
    return b.getvalue()


class TempCleanupTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def make(self):
        pid = self.client.post('/api/projects', json={'state': {}}).json()['id']
        aid = self.client.post('/api/library/import-image', data={'project_id': pid},
                               files={'file': ('r.png', png(), 'image/png')}).json()['id']
        return pid, aid

    def age(self, aid, days, provider='piapi'):
        from backend import main as studio
        old = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with studio.connect() as db:
            row = db.execute('SELECT metadata FROM library_assets WHERE id=?', (aid,)).fetchone()
            meta = json.loads(row['metadata'])
            meta['provider'] = provider
            db.execute('UPDATE library_assets SET created_at=?,metadata=? WHERE id=?', (old, json.dumps(meta), aid))
        return studio

    def test_expired_is_listed_and_removed_softly_then_restored(self):
        pid, aid = self.make()
        studio = self.age(aid, 8)
        listed = self.client.get('/api/library/temp', params={'project_id': pid}).json()['items']
        self.assertTrue(listed[0]['expired'])
        dry = self.client.post('/api/library/cleanup', json={'project_id': pid}).json()
        self.assertEqual(dry['would_remove'], [aid])
        self.assertEqual(self.client.get(f'/api/library/{aid}/file').status_code, 200)
        done = self.client.post('/api/library/cleanup', json={'project_id': pid, 'approved': True}).json()
        self.assertEqual(done['removed'], [aid])
        self.assertEqual(self.client.get(f'/api/library/{aid}/file').status_code, 404)
        entry = self.client.get('/api/library/cleanup/journal', params={'project_id': pid}).json()[0]
        self.assertEqual(self.client.post(f'/api/library/cleanup/restore/{entry["id"]}').status_code, 200)
        self.assertEqual(self.client.get(f'/api/library/{aid}/file').status_code, 200)
        # восстановленный файл больше не кандидат
        self.assertEqual(self.client.post('/api/library/cleanup', json={'project_id': pid, 'approved': True}).json()['removed'], [])

    def test_favorite_and_fresh_and_used_are_kept(self):
        pid, aid = self.make()
        self.age(aid, 8)
        self.client.post(f'/api/library/{aid}/favorite', json={'favorite': True})
        self.assertEqual(self.client.post('/api/library/cleanup', json={'project_id': pid, 'approved': True}).json()['removed'], [])
        self.client.post(f'/api/library/{aid}/favorite', json={'favorite': False})
        self.age(aid, 2)
        self.assertEqual(self.client.post('/api/library/cleanup', json={'project_id': pid, 'approved': True}).json()['removed'], [])
        self.age(aid, 9)
        with __import__('backend.main', fromlist=['x']).connect() as db:
            db.execute('UPDATE projects SET state=? WHERE id=?', (json.dumps({'ref': aid}), pid))
        item = self.client.get('/api/library/temp', params={'project_id': pid}).json()['items'][0]
        self.assertTrue(item['protected'])
        self.assertEqual(self.client.post('/api/library/cleanup', json={'project_id': pid, 'approved': True}).json()['removed'], [])


if __name__ == '__main__':
    unittest.main()
