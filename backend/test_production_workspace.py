import io
import json
import unittest
from unittest.mock import patch
from PIL import Image
from backend import main, test_production
from backend.production_workspace import promote_workspace


class ProductionWorkspaceTests(unittest.TestCase):
    setUp = test_production.ProductionTests.setUp
    tearDown = test_production.ProductionTests.tearDown
    setup_production = test_production.ProductionTests.setup_production
    setup_frame = test_production.ProductionTests.setup_frame
    new = test_production.ProductionTests.new

    def prepare(self):
        self.setup_production(); self.setup_frame()
        # Reproduce the old shared source also being the working frame.
        with main.connect() as db:
            db.execute('DELETE FROM production_links WHERE project_id=?', (self.frameproject,))
            db.execute('UPDATE production_links SET node_id=? WHERE project_id=?', (self.frame['id'], self.project))
        self.target = self.client.post('/api/projects', json={'title': 'GremoVOD', 'state': {
            'characters': [{'id': 'katya', 'name': 'Катя'}], 'brief': 'Keep my script'}}).json()['id']
        image = io.BytesIO(); Image.new('RGB', (16, 16), 'red').save(image, format='PNG')
        response = self.client.post(f'/api/characters/{self.project}/grem/assets',
                                   files={'file': ('ref.png', image.getvalue(), 'image/png')})
        self.assertEqual(response.status_code, 200, response.text)
        self.ref = response.json()['id']; self.image = image.getvalue()

    def test_promote_preserves_ids_files_jobs_and_shared_character(self):
        self.prepare()
        preview = promote_workspace(main, self.pid, self.target, self.project)
        self.assertEqual(preview['character_files'], 1)
        self.assertEqual(self.client.get('/api/productions/' + self.pid).json()['source_project_id'], self.project)
        with main.connect() as db:
            original = dict(db.execute('SELECT * FROM character_assets WHERE id=?', (self.ref,)).fetchone())
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)', ('old-job', self.project, 'image', 'piapi', 'task', 'completed', '{}', '{}', main.now()))
        old_path = main.char_directory(self.project, 'grem', original['category']) / original['filename']
        result = promote_workspace(main, self.pid, self.target, self.project, apply=True)
        self.assertEqual(result['source_project_id'], self.target)
        self.assertTrue(old_path.is_file())
        self.assertEqual(self.client.get('/api/character-assets/' + self.ref).content, self.image)
        self.assertEqual(self.client.get(f'/api/characters/{self.target}/grem/assets').json()[0]['id'], self.ref)
        state = self.client.get('/api/projects/' + self.target).json()['state']
        self.assertEqual(state['brief'], 'Keep my script')
        self.assertEqual([c['id'] for c in state['characters']], ['grem', 'katya'])
        self.assertEqual(self.client.get('/api/projects/' + self.project + '/workspace-location').json()['source_project_id'], self.target)
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT project_id FROM jobs WHERE id=?', ('old-job',)).fetchone()[0], self.project)
        self.assertTrue(promote_workspace(main, self.pid, self.target, self.project, apply=True)['already_applied'])

    def test_copy_failure_leaves_ownership_unchanged_and_retry_is_safe(self):
        self.prepare()
        with patch('backend.production_workspace.shutil.copyfileobj', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): promote_workspace(main, self.pid, self.target, self.project, apply=True)
        self.assertEqual(self.client.get('/api/productions/' + self.pid).json()['source_project_id'], self.project)
        self.assertEqual(self.client.get('/api/character-assets/' + self.ref).content, self.image)
        self.assertFalse(promote_workspace(main, self.pid, self.target, self.project, apply=True)['already_applied'])

    def test_conflicting_character_or_active_old_job_blocks_changes(self):
        self.prepare()
        with main.connect() as db:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)', ('pending', self.project, 'image', 'piapi', 'task', 'processing', '{}', '{}', main.now()))
        with self.assertRaises(main.HTTPException): promote_workspace(main, self.pid, self.target, self.project, apply=True)
        with main.connect() as db:
            db.execute("UPDATE jobs SET status='completed' WHERE id='pending'")
            db.execute('UPDATE projects SET state=? WHERE id=?', (json.dumps({'characters': [{'id': 'grem', 'name': 'Other'}]}), self.target))
        with self.assertRaises(main.HTTPException): promote_workspace(main, self.pid, self.target, self.project, apply=True)

    def test_archived_test_hidden_from_list_and_board_and_restorable(self):
        self.prepare()
        promote_workspace(main, self.pid, self.target, self.project, apply=True)
        with main.connect() as db:
            db.execute('INSERT INTO project_archives VALUES(?,?,?)', (self.project, 'test', main.now()))
        self.assertNotIn(self.project, [p['id'] for p in self.client.get('/api/projects').json()])
        archived = self.client.get('/api/archived-projects').json()
        self.assertEqual(archived[0]['id'], self.project)
        self.assertEqual(self.client.post(self.framebase + '/open-project').status_code, 409)
        with main.connect() as db:
            sid = db.execute('SELECT parent_id FROM production_nodes WHERE id=?', (self.frame['parent_id'],)).fetchone()[0]
        board = self.client.get(f'/api/productions/{self.pid}/series/{sid}/storyboard').json()
        self.assertFalse(board['scenes'][0]['frames'])
        self.assertEqual(self.client.post('/api/projects/' + self.project + '/restore').status_code, 200)
        self.assertIn(self.project, [p['id'] for p in self.client.get('/api/projects').json()])
        self.assertEqual(self.client.post(self.framebase + '/open-project').json()['project_id'], self.project)
