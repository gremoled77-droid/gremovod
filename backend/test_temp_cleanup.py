"""Временная папка: сердечко, срок 7 дней, мягкое удаление и восстановление."""
import io
import json
import unittest
import sqlite3
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
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

    def test_cleanup_rechecks_favorite_keep_age_and_usage_after_scan(self):
        for change in ['favorite', 'keep', 'fresh', 'reference']:
            with self.subTest(change=change):
                pid, aid = self.make()
                studio = self.age(aid, 8)
                original = temp_cleanup.candidates
                def changed_after_scan(*args, **kwargs):
                    scanned = original(*args, **kwargs)
                    if change == 'fresh':
                        self.age(aid, 1)
                    elif change == 'reference':
                        with studio.connect() as db:
                            db.execute('UPDATE projects SET state=? WHERE id=?', (json.dumps({'ref': aid}), pid))
                    else:
                        with studio.connect() as db:
                            row = db.execute('SELECT metadata FROM library_assets WHERE id=?', (aid,)).fetchone()
                            meta = json.loads(row['metadata']); meta[change] = True
                            db.execute('UPDATE library_assets SET metadata=? WHERE id=?', (json.dumps(meta), aid))
                    return scanned
                with patch.object(temp_cleanup, 'candidates', side_effect=changed_after_scan):
                    self.assertEqual(temp_cleanup.run_cleanup(studio, pid), [])
                self.assertEqual(self.client.get(f'/api/library/{aid}/file').status_code, 200)

    def test_manual_trash_rejects_used_asset_and_duplicate_deletion(self):
        pid, aid = self.make()
        studio = self.age(aid, 1)
        with studio.connect() as db:
            db.execute('UPDATE projects SET state=? WHERE id=?', (json.dumps({'ref': aid}), pid))
        self.assertEqual(self.client.post(f'/api/library/{aid}/trash').status_code, 409)
        self.assertEqual(self.client.get(f'/api/library/{aid}/file').status_code, 200)
        with studio.connect() as db:
            db.execute('UPDATE projects SET state=? WHERE id=?', ('{}', pid))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.client.post(f'/api/library/{aid}/trash').status_code, range(2)))
        self.assertEqual(sorted(results), [200, 404])
        journal = self.client.get('/api/library/cleanup/journal', params={'project_id': pid}).json()
        self.assertEqual(len(journal), 1)
        self.assertEqual(self.client.post(f'/api/library/cleanup/restore/{journal[0]["id"]}').status_code, 200)
        self.assertEqual(self.client.get(f'/api/library/{aid}/file').content, png())

    def test_protection_check_holds_writer_lock(self):
        pid, aid = self.make(); studio = self.age(aid, 1)
        original = temp_cleanup.used_reason
        blocked = []
        def concurrent_assignment(db, row, state_texts):
            other = sqlite3.connect(studio.DB, timeout=.05)
            try:
                with self.assertRaises(sqlite3.OperationalError):
                    other.execute('UPDATE projects SET state=? WHERE id=?', (json.dumps({'ref': aid}), pid))
                blocked.append(True)
            finally:
                other.close()
            return original(db, row, state_texts)
        with patch.object(temp_cleanup, 'used_reason', side_effect=concurrent_assignment):
            self.assertEqual(self.client.post(f'/api/library/{aid}/trash').status_code, 200)
        self.assertEqual(blocked, [True])

    def test_database_error_restores_original_file_and_row(self):
        pid, aid = self.make(); studio = self.age(aid, 1)
        original_connect = studio.connect
        @contextmanager
        def fail_delete():
            with original_connect() as db:
                db.set_authorizer(lambda action, table, *_: sqlite3.SQLITE_DENY
                                  if action == sqlite3.SQLITE_DELETE and table == 'library_assets'
                                  else sqlite3.SQLITE_OK)
                yield db
        with patch.object(studio, 'connect', fail_delete):
            with self.assertRaises(sqlite3.DatabaseError):
                temp_cleanup.move_to_trash(studio, aid, datetime.now(timezone.utc))
        self.assertEqual(self.client.get(f'/api/library/{aid}/file').content, png())
        self.assertEqual(self.client.get('/api/library/cleanup/journal', params={'project_id': pid}).json(), [])



if __name__ == '__main__':
    unittest.main()
