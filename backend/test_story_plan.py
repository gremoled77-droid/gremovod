"""Planning and mocked paid text calls, isolated SQLite and real temporary folders."""
import json
import uuid
import unittest
from unittest.mock import AsyncMock, patch
from backend import main, story_plan
from backend import test_production as production_tests


class StoryPlanTests(unittest.TestCase):
    setUp = production_tests.ProductionTests.setUp
    tearDown = production_tests.ProductionTests.tearDown
    setup_production = production_tests.ProductionTests.setup_production
    new = production_tests.ProductionTests.new
    def prepare_plan(self):
        self.setup_production()
        self.series = self.new('series', 'План серии')
        self.url = f'/api/productions/{self.pid}/series/{self.series["id"]}/story-plan'
        self.board_url = self.url.replace('story-plan', 'storyboard')
        self.card = {'id': 'card-1', 'scene_id': None, 'title': 'Встреча', 'summary': 'Герой замечает гостя.',
                     'character_ids': [self.char['id']], 'location_id': None, 'stage': 'setup', 'change': 'Спокойствие → интерес'}
        self.body = {'base_revision': 0, 'source': 'Таксист встречает необычного гостя.', 'source_kind': 'idea', 'cards': [self.card]}

    def save_plan(self):
        r = self.client.put(self.url, json=self.body)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_plan_is_separate_and_stale_or_foreign_links_rejected(self):
        self.prepare_plan()
        saved = self.save_plan()
        self.assertEqual(saved['revision'], 1)
        self.assertFalse(self.client.get(self.board_url).json()['scenes'])
        self.assertEqual(self.client.get(self.url).json()['source'], self.body['source'])
        self.assertEqual(self.client.put(self.url, json=self.body).status_code, 409)
        self.body['base_revision'] = 1
        for bad in [{'scene_id': 'foreign'}, {'character_ids': ['foreign']}, {'location_id': self.char['id']}]:
            r = self.client.put(self.url, json={**self.body, 'cards': [{**self.card, **bad}]})
            self.assertEqual(r.status_code, 400, r.text)
        self.assertEqual(self.client.put(self.url, json={**self.body, 'cards': [self.card, self.card]}).status_code, 400)

    def test_apply_new_and_existing_preserves_text_cast_frames_and_unplanned_scenes(self):
        self.prepare_plan()
        old = self.new('episode', 'Авторское название', self.series['id'])
        other = self.new('episode', 'Вне плана', self.series['id'])
        frame = self.new('frame', 'Рабочий кадр', old['id'])
        self.client.put(f'/api/productions/{self.pid}/nodes/{old["id"]}/notes', json={'notes': 'Полный авторский текст.'})
        self.body['cards'].append({**self.card, 'id': 'card-2', 'scene_id': old['id'], 'title': 'Название плана', 'summary': 'Краткая выжимка.'})
        saved = self.save_plan()
        preview = self.client.post(self.url + '/preview', json={'plan_revision': saved['revision'], 'board_revision': ''}).json()
        self.assertEqual(preview['remaining'][0]['id'], other['id'])
        self.assertEqual(self.client.post(self.url + '/apply', json=preview).status_code, 400)
        r = self.client.post(self.url + '/apply', json={**preview, 'keep_unplanned': True})
        self.assertEqual(r.status_code, 200, r.text)
        current = self.client.get(self.board_url).json()
        self.assertEqual([n['number'] for n in current['scenes']], [1, 2, 3])
        self.assertEqual(current['scenes'][1]['id'], old['id'])
        self.assertEqual(current['scenes'][1]['title'], old['title'])
        self.assertEqual(current['scenes'][1]['notes'], 'Полный авторский текст.')
        self.assertEqual(current['scenes'][1]['frames'][0]['id'], frame['id'])
        self.assertEqual(current['scenes'][0]['selection']['character_node_ids'], [self.char['id']])
        self.assertEqual(self.client.post(self.url + '/apply', json={**preview, 'keep_unplanned': True}).status_code, 409)
        self.assertEqual(len(self.client.get(self.board_url).json()['scenes']), 3)

    def test_changed_scene_blocks_apply_and_disk_failure_rolls_back(self):
        self.prepare_plan(); self.save_plan()
        view = self.client.post(self.url + '/preview', json={'plan_revision': 1, 'board_revision': ''}).json()
        self.new('episode', 'Параллельная сцена', self.series['id'])
        self.assertEqual(self.client.post(self.url + '/apply', json={**view, 'keep_unplanned': True}).status_code, 409)
        view = self.client.post(self.url + '/preview', json={'plan_revision': 1, 'board_revision': ''}).json()
        with patch.object(story_plan.Path, 'write_text', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.client.post(self.url + '/apply', json={**view, 'keep_unplanned': True})
        self.assertEqual(len(self.client.get(self.board_url).json()['scenes']), 1)
        self.assertEqual(self.client.get(self.url).json()['revision'], 1)

    def estimate_request(self):
        base = {'plan_revision': 1, 'model': 'gpt-5.6-luna'}
        estimate = self.client.post(self.url + '/estimate', json=base)
        self.assertEqual(estimate.status_code, 200, estimate.text)
        return {**base, **estimate.json(), 'request_id': uuid.uuid4().hex,
                'approved': True, 'max_cost_usd': estimate.json()['estimated_usd']}

    def test_paid_suggestion_needs_quote_and_approval_persists_and_does_not_apply(self):
        self.prepare_plan(); self.save_plan()
        req = self.estimate_request()
        output = json.dumps({'cards': [{'title': 'Гость', 'summary': 'Встреча', 'character_ids': [self.char['id']]}]}, ensure_ascii=False)
        upstream = AsyncMock(return_value={'choices': [{'message': {'content': output}}], 'usage': {'prompt_tokens': 20, 'completion_tokens': 40}})
        with patch.object(main, 'get_key', return_value='test-key'), patch.object(main, 'request_piapi', upstream):
            self.assertEqual(self.client.post(self.url + '/suggest', json={**req, 'approved': False}).status_code, 400)
            self.assertEqual(self.client.post(self.url + '/suggest', json={**req, 'quote_token': 'tampered'}).status_code, 400)
            self.assertEqual(upstream.await_count, 0)
            response = self.client.post(self.url + '/suggest', json=req)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['status'], 'done')
            self.assertEqual(self.client.post(self.url + '/suggest', json=req).status_code, 409)
            self.assertEqual(upstream.await_count, 1)
        saved = self.client.get(self.url).json()
        self.assertEqual(saved['suggestions'][0]['data']['cards'][0]['title'], 'Гость')
        self.assertEqual(len(saved['cards']), 1)
        self.assertFalse(self.client.get(self.board_url).json()['scenes'])
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM llm_calls').fetchone()[0], 1)

    def test_invalid_response_saved_and_long_input_rejected_before_payment(self):
        self.prepare_plan(); self.save_plan(); req = self.estimate_request()
        with patch.object(main, 'get_key', return_value='test-key'), patch.object(main, 'request_piapi', AsyncMock(return_value={'choices': [{'message': {'content': '{"cards":['}}]})) as upstream:
            response = self.client.post(self.url + '/suggest', json=req)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['status'], 'invalid')
            self.assertEqual(self.client.get(self.url).json()['suggestions'][0]['data']['raw'], '{"cards":[')
            self.assertEqual(upstream.await_count, 1)
        self.body['base_revision'] = 1; self.body['source'] = 'А' * 31000
        self.save_plan()
        self.assertEqual(self.client.post(self.url + '/estimate', json={'plan_revision': 2}).status_code, 400)

    def test_quote_does_not_allow_changed_model_or_changed_plan_and_budget_still_applies(self):
        self.prepare_plan(); self.save_plan(); req = self.estimate_request()
        with patch.object(main, 'get_key', return_value='test-key'), patch.object(main, 'request_piapi', AsyncMock()) as upstream:
            self.assertEqual(self.client.post(self.url + '/suggest', json={**req, 'model': 'gpt-5.6-sol'}).status_code, 400)
            self.body['base_revision'] = 1
            self.body['source'] = 'Другой замысел'
            self.save_plan()
            self.assertEqual(self.client.post(self.url + '/suggest', json=req).status_code, 409)
            req = {**req, 'plan_revision': 2}
            estimate = self.client.post(self.url + '/estimate', json=req).json()
            req.update(quote_token=estimate['quote_token'], max_cost_usd=estimate['estimated_usd'])
            with main.connect() as db:
                db.execute('UPDATE spending_limits SET project_usd=0,daily_usd=0 WHERE id=1')
            self.assertEqual(self.client.post(self.url + '/suggest', json=req).status_code, 400)
            self.assertEqual(upstream.await_count, 0)
        self.assertEqual(self.client.get(self.url).json()['suggestions'][0]['status'], 'failed')
