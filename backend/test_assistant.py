"""Помощник постановки: карточки по состоянию кадра и история со ссылками на объекты."""
import json
import unittest

from backend import main, test_production, test_smoke
from backend.test_production_entities import png


class AssistantTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown
    setup_production = test_production.ProductionTests.setup_production
    new = test_production.ProductionTests.new

    def say(self, text, node_id=None):
        r = self.client.post(f'/api/productions/{self.pid}/assistant', json={'text': text, 'node_id': node_id})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def actions(self, frame):
        return [c['action'] for c in self.say('что дальше?', frame['id'])[1]['cards']]

    def test_cards_follow_frame_state_and_history_keeps_only_links(self):
        self.setup_production()
        scene = self.new('episode', 'Вокзал', self.new('series', 'Серия')['id'])
        frame = self.new('frame', 'Крупный', scene['id'])
        base = f'/api/productions/{self.pid}/nodes/{frame["id"]}'
        self.assertEqual(self.actions(frame), ['open_create', 'open_sound'])
        self.client.post(base + '/upload', data={'category': '02_Изображения'}, files={'file': ('a.png', png(), 'image/png')})
        self.assertEqual(self.actions(frame), ['pick_photo', 'open_sound'])
        ed = self.client.get(base + '/editor').json()
        image = next(f for f in ed['files'] if f['kind'] == 'image')
        self.client.put(base + '/editor', json={**ed['data'], 'base_revision': ed['revision'], 'notes': '', 'selected_image_file_id': image['id']})
        cards = self.say('оживи', frame['id'])[1]['cards']
        animate = next(c for c in cards if c['action'] == 'animate')
        self.assertEqual((animate['node_id'], animate['paid']), (frame['id'], True))
        project = self.client.post(base + '/open-project').json()['project_id']
        with main.connect() as db:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)', ('v1', project, 'video', 'piapi', None, 'processing',
                                                                    json.dumps({'node_id': frame['id']}), '{}', main.now()))
        self.assertEqual(self.actions(frame), ['watch', 'open_sound'])
        # Без кадра — подсказка выбрать кадр, без карточек.
        free = self.say('привет')
        self.assertEqual((free[1]['cards'], free[1]['node_id']), ([], None))
        # Подпись кадра читается при выдаче: переименование видно в старых сообщениях.
        self.client.put(base + '/notes', json={'notes': ''})
        with main.connect() as db:
            db.execute("UPDATE production_nodes SET title='Реакция' WHERE id=?", (frame['id'],))
        history = self.client.get(f'/api/productions/{self.pid}/assistant').json()
        self.assertEqual(len(history), 10)
        self.assertEqual(history[0]['node_title'], 'Кадр 1.1 · Реакция')
        self.assertEqual([m['role'] for m in history[:2]], ['user', 'assistant'])
        only = self.client.get(f'/api/productions/{self.pid}/assistant', params={'node_id': frame['id']}).json()
        self.assertEqual(len(only), 8)
        with main.connect() as db:
            stored = db.execute("SELECT * FROM assistant_messages WHERE role='user' AND node_id IS NOT NULL LIMIT 1").fetchone()
        self.assertNotIn('Крупный', json.dumps(dict(stored), ensure_ascii=False))
        self.assertEqual(self.client.post('/api/productions/missing/assistant', json={'text': 'x'}).status_code, 404)
        self.assertEqual(self.client.post(f'/api/productions/{self.pid}/assistant', json={'text': 'x', 'node_id': scene['id']}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
