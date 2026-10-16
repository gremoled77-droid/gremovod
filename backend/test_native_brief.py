"""Готовый промпт и референсы из «Кадров» попадают в очередь Codex без изменения сохранённой сцены."""
import json
import unittest

from backend import main, test_smoke


class NativeBriefTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def make_project(self):
        return self.client.post('/api/projects', json={'title': 'Кадры', 'state': {'brief': 'Старое задание', 'scene': {'brief': 'Сцена проекта', 'assets': []}}}).json()['id']

    def make_asset(self, pid):
        aid = 'a' + main.uuid.uuid4().hex[:15]
        name = aid + '.png'
        (main.LIBRARY_ROOT / name).parent.mkdir(parents=True, exist_ok=True)
        (main.LIBRARY_ROOT / name).write_bytes(b'png')
        with main.connect() as db:
            db.execute('INSERT INTO library_assets VALUES(?,?,?,?,?,?,?,?)', (aid, 'j-' + aid, pid, 0, name, '', json.dumps({'kind': 'image'}), main.now()))
        return aid

    def body(self, pid, **extra):
        return {'project_id': pid, 'target': 'gpt-image-2.5', 'operation': 'generate', 'request_id': 'brief_request_' + extra.pop('n', '0001') + '_abcdef', **extra}

    def test_brief_and_references_become_context_without_touching_scene(self):
        pid = self.make_project()
        aid = self.make_asset(pid)
        r = self.client.post('/api/chatgpt/jobs', json=self.body(pid, brief='Грэм у такси ночью', reference_asset_ids=[aid, aid]))
        self.assertEqual(r.status_code, 200, r.text)
        with main.connect() as db:
            request = json.loads(db.execute('SELECT request FROM native_chat_jobs').fetchone()['request'])
        context = request['context']
        self.assertEqual(context['brief'], 'Грэм у такси ночью')
        self.assertEqual([x['asset_id'] for x in context['references']], [aid])
        state = self.client.get('/api/projects/' + pid).json()['state']
        self.assertEqual(state['scene'], {'brief': 'Сцена проекта', 'assets': []})

    def test_brief_without_references_is_allowed(self):
        pid = self.make_project()
        r = self.client.post('/api/chatgpt/jobs', json=self.body(pid, brief='Просто промпт'))
        self.assertEqual(r.status_code, 200, r.text)

    def test_foreign_reference_and_forbidden_combinations_are_rejected(self):
        pid = self.make_project()
        r = self.client.post('/api/chatgpt/jobs', json=self.body(pid, brief='Промпт', reference_asset_ids=['missing']))
        self.assertEqual(r.status_code, 400, r.text)
        r = self.client.post('/api/chatgpt/jobs', json=self.body(pid, brief='Промпт', use_scene=True, n='0002'))
        self.assertEqual(r.status_code, 400, r.text)

    def test_without_brief_old_behaviour_is_unchanged(self):
        pid = self.make_project()
        r = self.client.post('/api/chatgpt/jobs', json=self.body(pid))
        self.assertEqual(r.status_code, 200, r.text)
        with main.connect() as db:
            request = json.loads(db.execute('SELECT request FROM native_chat_jobs').fetchone()['request'])
        self.assertEqual(request['context']['brief'], 'Старое задание')


if __name__ == '__main__':
    unittest.main()
