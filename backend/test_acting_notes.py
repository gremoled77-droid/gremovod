"""Acting notes on temporary SQLite, with provider calls forbidden by the fixture."""
import copy
from concurrent.futures import ThreadPoolExecutor
from backend import main, test_production
import unittest


class ActingNotesTests(unittest.TestCase):
    setUp = test_production.ProductionTests.setUp
    tearDown = test_production.ProductionTests.tearDown
    setup_production = test_production.ProductionTests.setup_production
    new = test_production.ProductionTests.new

    def prepare(self):
        self.setup_production()
        self.series = self.new('series', 'Тест')
        self.scene = self.new('episode', 'Встреча', self.series['id'])
        self.shot = self.new('frame', 'Реакция', self.scene['id'])
        self.url = f"/api/productions/{self.pid}/series/{self.series['id']}/scenes/{self.scene['id']}/acting-notes"
        with main.connect() as db:
            import json
            db.execute('INSERT INTO production_entity_state VALUES(?,?,?)',
                       (self.scene['id'], json.dumps({'character_node_ids': [self.char['id']]}), 'test'))
        saved = self.client.get(self.url).json()
        self.body = {'base_revision': saved['revision'], 'source_revision': saved['source_revision'],
                     'status': 'draft', 'beats': [{'id': 'beat-one', 'actor_id': self.char['id'],
                     'shot_ids': [self.shot['id']], 'objective': 'Убедить', 'tactic': 'Объяснить',
                     'visible_action': 'Останавливает жест и смотрит на партнёра', 'camera': 'Статично'}]}
        return saved

    def test_save_reopen_export_and_canon_unchanged(self):
        saved = self.prepare()
        self.assertEqual(saved['revision'], 0)
        self.assertEqual(saved['beats'], [])
        board_url = f"/api/productions/{self.pid}/series/{self.series['id']}/storyboard"
        board = self.client.get(board_url).json()
        project = self.client.get('/api/projects/' + self.project).json()
        response = self.client.put(self.url, json={**self.body, 'status': 'approved'})
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.client.get(self.url).json()
        self.assertEqual(saved['revision'], 1)
        self.assertEqual(saved['status'], 'approved')
        version = {'base_revision': 1, 'source_revision': saved['source_revision']}
        first = self.client.post(self.url + '/export', json=version)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertIn('Видимое действие: Останавливает жест', first.json()['text'])
        self.assertIn('Камера (отдельно от действия): Статично', first.json()['text'])
        self.assertEqual(first.json(), self.client.post(self.url + '/export', json=version).json())
        self.assertEqual(board, self.client.get(board_url).json())
        self.assertEqual(project, self.client.get('/api/projects/' + self.project).json())
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0], 0)

    def test_two_editors_and_concurrent_writes(self):
        self.prepare()
        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = sorted(pool.map(lambda _: self.client.put(self.url, json=self.body).status_code, range(2)))
        self.assertEqual(codes, [200, 409])
        self.assertEqual(self.client.get(self.url).json()['revision'], 1)
        self.assertEqual(self.client.put(self.url, json=self.body).status_code, 409)

    def test_scene_change_marks_stale_and_blocks_export_and_stale_save(self):
        self.prepare()
        saved = self.client.put(self.url, json=self.body).json()
        with main.connect() as db:
            db.execute('UPDATE production_nodes SET notes=? WHERE id=?', ('Новая реплика', self.scene['id']))
        latest = self.client.get(self.url).json()
        self.assertTrue(latest['stale'])
        version = {'base_revision': saved['revision'], 'source_revision': saved['source_revision']}
        self.assertEqual(self.client.put(self.url, json={**self.body, **version}).status_code, 409)
        self.assertEqual(self.client.post(self.url + '/export', json={**version,
                         'source_revision': latest['source_revision']}).status_code, 409)
        self.assertEqual(self.client.put(self.url, json={**self.body, 'base_revision': 1,
                         'source_revision': latest['source_revision']}).status_code, 200)

    def test_foreign_actor_shot_scene_and_duplicate_ids_rejected(self):
        self.prepare()
        other = self.new('episode', 'Другая сцена', self.series['id'])
        foreign_shot = self.new('frame', 'Чужой план', other['id'])
        absent_actor = self.new('character', 'Не в сцене')
        for update in ({'actor_id': absent_actor['id']}, {'partner_id': absent_actor['id']},
                       {'partner_id': self.char['id']}, {'shot_ids': [foreign_shot['id']]},
                       {'shot_ids': [self.shot['id'], self.shot['id']]}):
            body = copy.deepcopy(self.body)
            body['beats'][0].update(update)
            # Adding frames/characters may update the scene snapshot.
            body['source_revision'] = self.client.get(self.url).json()['source_revision']
            self.assertEqual(self.client.put(self.url, json=body).status_code, 400, update)
        body = copy.deepcopy(self.body)
        body['beats'] *= 2
        body['source_revision'] = self.client.get(self.url).json()['source_revision']
        self.assertEqual(self.client.put(self.url, json=body).status_code, 400)
        self.assertEqual(self.client.get(self.url.replace(self.pid, 'foreign')).status_code, 404)
        wrong_series = self.new('series', 'Другая серия')
        self.assertEqual(self.client.get(self.url.replace(self.series['id'], wrong_series['id'])).status_code, 404)

    def test_schema_approval_session_and_deleted_cast(self):
        self.prepare()
        for extra in ({'unknown': True}, {'base_revision': True}, {'status': 'canon'}):
            self.assertEqual(self.client.put(self.url, json={**self.body, **extra}).status_code, 422)
        empty = copy.deepcopy(self.body)
        empty['beats'][0]['visible_action'] = ' '
        self.assertEqual(self.client.put(self.url, json={**empty, 'status': 'approved'}).status_code, 400)
        self.assertEqual(self.client.put(self.url, json=empty).status_code, 200)
        self.client.headers.pop('X-Studio-Session')
        self.client.cookies.clear()
        self.assertEqual(self.client.put(self.url, json=self.body).status_code, 401)
        self.client.headers['X-Studio-Session'] = self.client.get('/api/session').json()['token']
        with main.connect() as db:
            db.execute('UPDATE production_entity_state SET data=? WHERE node_id=?',
                       ('{"character_node_ids":[]}', self.scene['id']))
        saved = self.client.get(self.url).json()
        self.assertTrue(saved['stale'])
        self.assertEqual(self.client.put(self.url, json={**self.body, 'base_revision': 1,
                         'source_revision': saved['source_revision']}).status_code, 400)

    def test_approval_requires_action_and_trigger_and_schema_limits(self):
        self.prepare()
        for beats in ([], [{**self.body['beats'][0], 'next_tactic': 'Отложить ответ'}]):
            self.assertEqual(self.client.put(self.url, json={**self.body, 'status': 'approved', 'beats': beats}).status_code, 400)
        body = copy.deepcopy(self.body)
        body['beats'][0].update(next_tactic='Отложить ответ', trigger='Уточнение гостя')
        self.assertEqual(self.client.put(self.url, json={**body, 'status': 'approved'}).status_code, 200)
        self.assertEqual(self.client.put(self.url, json={**body, 'beats': body['beats'] * 51}).status_code, 422)
        body['beats'][0]['sound'] = 'x' * 2001
        self.assertEqual(self.client.put(self.url, json=body).status_code, 422)
        self.assertEqual(self.client.get(self.url).json()['status'], 'approved')

    def test_real_other_production_isolation_and_scene_delete_cleanup(self):
        self.prepare()
        other_project = self.client.post('/api/projects', json={'title': 'Other', 'state': {
            'characters': [{'id': 'other', 'name': 'Другой герой'}]}}).json()['id']
        other_pid = self.client.post('/api/productions', json={'title': 'Other', 'source_project_id': other_project}).json()['id']
        other_actor = self.client.get('/api/productions/' + other_pid).json()['nodes'][0]['id']
        body = copy.deepcopy(self.body)
        body['beats'][0]['actor_id'] = other_actor
        self.assertEqual(self.client.put(self.url, json=body).status_code, 400)
        self.assertEqual(self.client.get(self.url.replace(self.pid, other_pid)).status_code, 404)
        self.assertEqual(self.client.put(self.url, json=self.body).status_code, 200)
        with main.connect() as db:
            db.execute('DELETE FROM production_nodes WHERE id=?', (self.scene['id'],))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM acting_notes').fetchone()[0], 0)
        self.assertEqual(self.client.get(self.url).status_code, 404)
