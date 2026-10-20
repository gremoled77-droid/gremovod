"""Контракт этапа «Продюсер»: идея → сценарная структура.

Сначала проверяется локальный MOCK: сети нет, расходов нет, ключ не нужен.
Затем платный путь с подменённым транспортом: оценка, подпись, строгая проверка
ответа и отсутствие автоматического платного повтора при негодном ответе.
"""
import json
import unittest
import uuid
from unittest.mock import AsyncMock, patch

from backend import main, producer_stage
from backend import model_catalog
from backend import test_smoke

VALID_ANSWER = {
    'logline': 'Грэм берётся за заказ, который грозит ему разорением.',
    'beats': [
        {'id': 'b1', 'stage': 'setup', 'summary': 'Грэм принимает необычный заказ.'},
        {'id': 'b2', 'stage': 'development', 'summary': 'Клиент требует ехать ночью.'},
        {'id': 'b3', 'stage': 'climax', 'summary': 'Грэм понимает, что клиент бежит.'},
        {'id': 'b4', 'stage': 'ending', 'summary': 'Грэм везёт клиента домой и не берёт денег.'},
    ],
    'scenes': [
        {'number': 1, 'title': 'Заказ', 'duration_seconds': 20, 'summary': 'Грэм садится за руль.',
         'character_ids': ['grem'], 'beat_id': 'b1'},
        {'number': 2, 'title': 'Ночь', 'duration_seconds': 25, 'summary': 'Машина едет по городу.',
         'character_ids': ['grem'], 'beat_id': 'b2'},
    ],
    'assumptions': ['Диалоги не написаны.'],
}


def upstream_answer(content):
    return {'choices': [{'message': {'role': 'assistant', 'content': content}}],
            'usage': {'prompt_tokens': 120, 'completion_tokens': 80}}


class ProducerStageTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def make_project(self):
        state = {'characters': [
            {'id': 'grem', 'name': 'Грэм', 'identity': {'face': 'усы', 'costume': 'кедровая куртка'}},
            {'id': 'passenger', 'name': 'Пассажир', 'identity': {'face': 'нервная улыбка'}},
        ], 'style': {'city': 'Минск'}}
        self.pid = self.client.post('/api/projects', json={'title': 'Продюсер', 'state': state}).json()['id']
        return self.pid

    def add_reference(self, asset_id, character_id, category, note):
        with main.connect() as db:
            db.execute('INSERT INTO character_assets VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (asset_id, self.pid, character_id, category, '', 'ref.png', 'ref.png', '', note, main.now()))

    def base_body(self, **extra):
        body = {'project_id': self.pid, 'idea': 'Грэм берёт необычный заказ в Минске.',
                'character_ids': ['grem'], 'duration_seconds': 45, 'language': 'ru',
                'constraints': ['Без говорящих животных'], 'provider': 'mock', 'model': 'mock-producer'}
        body.update(extra)
        return body

    def paid_request(self, body, estimate, request_id=None):
        return {**body, 'approved': True, 'quote_token': estimate['quote_token'],
                'max_cost_usd': estimate['estimated_usd'],
                'request_id': request_id or uuid.uuid4().hex}

    def test_mock_run_returns_the_declared_contract(self):
        self.make_project()
        response = self.client.post('/api/producer/run', json=self.base_body())
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['stage'], 'producer.structure')
        self.assertTrue(data['logline'])
        self.assertTrue(3 <= len(data['beats']) <= 8)
        self.assertTrue(data['scenes'])
        self.assertEqual([scene['number'] for scene in data['scenes']],
                         list(range(1, len(data['scenes']) + 1)))
        self.assertEqual(sum(scene['duration_seconds'] for scene in data['scenes']), 45)
        beat_ids = {beat['id'] for beat in data['beats']}
        self.assertTrue(all(scene['beat_id'] in beat_ids for scene in data['scenes']))
        self.assertEqual(data['cost_usd'], 0.0)
        self.assertEqual(data['external_calls'], 0)
        self.assertFalse(data['model']['paid'])
        self.assertEqual(data['model']['provider'], 'mock')
        self.assertEqual(data['prompt_version']['stage'], 'producer.structure')
        self.assertTrue(data['prompt_version']['revision'])
        self.assertTrue(data['prompt_version']['rules_version'])

    def test_mock_is_deterministic_and_costs_nothing(self):
        self.make_project()
        first = self.client.post('/api/producer/run', json=self.base_body()).json()
        second = self.client.post('/api/producer/run', json=self.base_body()).json()
        self.assertEqual(first['logline'], second['logline'])
        self.assertEqual(first['beats'], second['beats'])
        self.assertEqual(first['scenes'], second['scenes'])
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM llm_calls').fetchone()[0], 0)

    def test_estimate_for_mock_is_free_and_without_quote(self):
        self.make_project()
        response = self.client.post('/api/producer/estimate', json=self.base_body())
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['mode'], 'mock')
        self.assertEqual(data['estimated_usd'], 0.0)
        self.assertEqual(data['quote_token'], '')
        self.assertEqual(data['payload_summary']['character_ids'], ['grem'])

    def test_only_selected_characters_and_approved_references_reach_the_model(self):
        self.make_project()
        self.add_reference('ref-grem', 'grem', 'real_references', 'Фото Грэма')
        self.add_reference('ref-passenger', 'passenger', 'approved_generations', 'Фото пассажира')
        self.add_reference('ref-candidate', 'grem', 'candidate_generations', 'Не утверждён')
        body = producer_stage.ProducerRequest(**self.base_body(reference_ids=['ref-grem']))
        payload, summary = producer_stage.build_payload(main, body)
        self.assertEqual(summary['character_ids'], ['grem'])
        self.assertEqual(summary['reference_ids'], ['ref-grem'])
        text = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn('passenger', text)
        self.assertNotIn('Фото пассажира', text)
        self.assertNotIn('ref.png', text)
        self.assertNotIn('local_path', text)
        for asset_id, reason in (('ref-candidate', 'не утверждён'), ('ref-passenger', 'невыбранному')):
            rejected = producer_stage.ProducerRequest(**self.base_body(reference_ids=[asset_id]))
            with self.assertRaises(main.HTTPException) as caught:
                producer_stage.build_payload(main, rejected)
            self.assertEqual(caught.exception.status_code, 400)
            self.assertIn(reason, caught.exception.detail)

    def test_unknown_character_is_rejected(self):
        self.make_project()
        response = self.client.post('/api/producer/run', json=self.base_body(character_ids=['nobody']))
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn('Персонаж не найден', response.json()['detail'])

    def test_world_is_capped_and_reports_what_was_dropped(self):
        self.make_project()
        body = producer_stage.ProducerRequest(**self.base_body(world={f'key{index}': 'x' * 500 for index in range(12)}))
        payload, summary = producer_stage.build_payload(main, body)
        self.assertLessEqual(len(summary['world_keys']), producer_stage.MAX_WORLD_KEYS)
        self.assertTrue(summary['world_dropped'])
        self.assertTrue(summary['world_truncated'])
        self.assertLessEqual(summary['payload_chars'], producer_stage.MAX_PROMPT_CHARS)

    def test_parse_structure_rejects_a_wrong_shape(self):
        with self.assertRaises(ValueError):
            producer_stage.parse_structure('просто текст')
        with self.assertRaises(ValueError):
            producer_stage.parse_structure(json.dumps({**VALID_ANSWER, 'extra': 1}))
        with self.assertRaises(ValueError):
            producer_stage.parse_structure(json.dumps({key: value for key, value in VALID_ANSWER.items() if key != 'logline'}))
        with self.assertRaises(ValueError):
            producer_stage.parse_structure(json.dumps({**VALID_ANSWER, 'beats': []}))
        with self.assertRaises(ValueError):
            producer_stage.parse_structure(json.dumps({**VALID_ANSWER, 'beats': [{'id': 'b1', 'stage': 'нет', 'summary': 'x'}]}))

    def test_check_references_rejects_unknown_beat_and_character(self):
        payload = {'characters': [{'id': 'grem'}], 'references': [], 'world': {}, 'duration_seconds': 45,
                   'language': 'ru', 'constraints': [], 'idea': 'идея'}
        producer_stage.check_references(producer_stage.parse_structure(json.dumps(VALID_ANSWER)), payload)
        broken_beat = json.loads(json.dumps(VALID_ANSWER))
        broken_beat['scenes'][0]['beat_id'] = 'b9'
        with self.assertRaises(ValueError):
            producer_stage.check_references(producer_stage.parse_structure(json.dumps(broken_beat)), payload)
        broken_actor = json.loads(json.dumps(VALID_ANSWER))
        broken_actor['scenes'][0]['character_ids'] = ['ghost']
        with self.assertRaises(ValueError):
            producer_stage.check_references(producer_stage.parse_structure(json.dumps(broken_actor)), payload)

    def test_paid_run_needs_approval_and_a_valid_quote(self):
        self.make_project()
        body = self.base_body(provider='piapi', model='gpt-5.6-luna')
        estimate = self.client.post('/api/producer/estimate', json=body).json()
        self.assertGreater(estimate['estimated_usd'], 0)
        self.assertEqual(estimate['mode'], 'paid')
        self.client.headers['X-Api-Key'] = 'test-key'
        with patch.object(main, 'request_piapi', AsyncMock()) as upstream:
            unapproved = self.client.post('/api/producer/run', json={**self.paid_request(body, estimate), 'approved': False})
            self.assertEqual(unapproved.status_code, 400, unapproved.text)
            tampered = self.client.post('/api/producer/run', json={**self.paid_request(body, estimate), 'quote_token': 'tampered'})
            self.assertEqual(tampered.status_code, 400, tampered.text)
            self.assertEqual(upstream.await_count, 0)

    def test_paid_run_returns_structure_and_records_the_cost(self):
        self.make_project()
        body = self.base_body(provider='piapi', model='gpt-5.6-luna')
        estimate = self.client.post('/api/producer/estimate', json=body).json()
        self.client.headers['X-Api-Key'] = 'test-key'
        request_id = uuid.uuid4().hex
        upstream = AsyncMock(return_value=upstream_answer(json.dumps(VALID_ANSWER, ensure_ascii=False)))
        with patch.object(main, 'request_piapi', upstream):
            response = self.client.post('/api/producer/run', json=self.paid_request(body, estimate, request_id))
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['logline'], VALID_ANSWER['logline'])
        self.assertEqual(len(data['beats']), 4)
        self.assertEqual(len(data['scenes']), 2)
        self.assertTrue(data['model']['paid'])
        self.assertEqual(data['model']['provider'], 'piapi')
        self.assertEqual(data['model']['id'], 'gpt-5.6-luna')
        self.assertGreater(data['cost_usd'], 0)
        self.assertEqual(data['external_calls'], 1)
        with main.connect() as db:
            row = db.execute('SELECT status,model,usd FROM llm_calls WHERE request_id=?', (request_id,)).fetchone()
            self.assertEqual(row['status'], 'done')
            self.assertEqual(row['model'], 'gpt-5.6-luna')
            self.assertGreater(row['usd'], 0)

    def test_provider_receives_only_the_stage_payload(self):
        self.make_project()
        body = self.base_body(provider='piapi', model='gpt-5.6-luna')
        estimate = self.client.post('/api/producer/estimate', json=body).json()
        self.client.headers['X-Api-Key'] = 'test-key'
        upstream = AsyncMock(return_value=upstream_answer(json.dumps(VALID_ANSWER, ensure_ascii=False)))
        with patch.object(main, 'request_piapi', upstream):
            response = self.client.post('/api/producer/run', json=self.paid_request(body, estimate))
        self.assertEqual(response.status_code, 200, response.text)
        sent = upstream.await_args[0][3]
        self.assertEqual(len(sent['messages']), 2)
        self.assertIn('Сценарные правила проекта', sent['messages'][0]['content'])
        payload = json.loads(sent['messages'][1]['content'])
        self.assertEqual(payload['characters'][0]['id'], 'grem')
        self.assertEqual(payload['duration_seconds'], 45)
        self.assertEqual(payload['language'], 'ru')
        self.assertEqual(payload['constraints'], ['Без говорящих животных'])
        self.assertNotIn('passenger', json.dumps(payload, ensure_ascii=False))
        self.assertNotIn('history', payload)
        self.assertNotIn('messages', payload)
        self.assertNotIn('images', payload)

    def test_invalid_provider_answer_is_reported_without_a_paid_retry(self):
        self.make_project()
        body = self.base_body(provider='piapi', model='gpt-5.6-luna')
        estimate = self.client.post('/api/producer/estimate', json=body).json()
        self.client.headers['X-Api-Key'] = 'test-key'
        request_id = uuid.uuid4().hex
        upstream = AsyncMock(return_value=upstream_answer('это не JSON'))
        with patch.object(main, 'request_piapi', upstream):
            response = self.client.post('/api/producer/run', json=self.paid_request(body, estimate, request_id))
        self.assertEqual(response.status_code, 502, response.text)
        self.assertIn('не соответствует контракту этапа', response.json()['detail'])
        self.assertIn('автоматически не выполняется', response.json()['detail'])
        self.assertEqual(upstream.await_count, 1)
        with main.connect() as db:
            row = db.execute('SELECT status FROM llm_calls WHERE request_id=?', (request_id,)).fetchone()
            self.assertEqual(row['status'], 'done')

    def test_unknown_model_or_provider_is_rejected(self):
        self.make_project()
        unknown_model = self.base_body(provider='piapi', model='gpt-4.1-mini')
        self.assertEqual(self.client.post('/api/producer/estimate', json=unknown_model).status_code, 400)
        foreign_provider = self.base_body(provider='openai', model='gpt-5.6-luna')
        self.assertEqual(self.client.post('/api/producer/estimate', json=foreign_provider).status_code, 400)
        mock_with_paid_model = self.base_body(provider='mock', model='gpt-5.6-luna')
        self.assertEqual(self.client.post('/api/producer/run', json=mock_with_paid_model).status_code, 400)

    def test_empty_idea_is_rejected_before_any_call(self):
        self.make_project()
        response = self.client.post('/api/producer/run', json=self.base_body(idea=''))
        self.assertEqual(response.status_code, 422, response.text)

    def test_full_world_bible_fits_into_the_payload(self):
        """Паспорт мира из 11 полей должен доходить до пакета целиком, включая rules и avoid."""
        self.make_project()
        bible = {'look': 'стилизованная анимация', 'environment': 'Минск, дворики', 'time': 'ночь',
                 'tech': 'современный', 'textures': 'кедр, бетон', 'palette': 'охра и синь',
                 'lighting': 'фонари', 'camera': '35 мм', 'mood': 'тревожно',
                 'rules': 'канон не менять', 'avoid': 'логотипы'}
        body = producer_stage.ProducerRequest(**self.base_body(world=bible))
        payload, summary = producer_stage.build_payload(main, body)
        self.assertEqual(len(summary['world_keys']), 11)
        self.assertEqual(summary['world_dropped'], [])
        self.assertEqual(summary['world_truncated'], [])
        self.assertEqual(payload['world']['rules'], 'канон не менять')
        self.assertEqual(payload['world']['avoid'], 'логотипы')

    def test_provider_is_resolved_from_the_registry(self):
        """Пустой provider — это не «PiAPI», а «возьми провайдера модели из реестра»."""
        self.make_project()
        body = self.base_body(provider='', model='gpt-5.6-luna')
        estimate = self.client.post('/api/producer/estimate', json=body)
        self.assertEqual(estimate.status_code, 200, estimate.text)
        data = estimate.json()
        self.assertEqual(data['mode'], 'paid')
        self.assertGreater(data['estimated_usd'], 0)
        self.assertEqual(data['model']['id'], 'gpt-5.6-luna')
        self.assertEqual(data['model']['provider'], model_catalog.LLM_MODELS['gpt-5.6-luna']['provider'])

    def test_mock_is_selected_by_model_id_and_unknown_model_is_rejected(self):
        self.make_project()
        mock = self.client.post('/api/producer/estimate', json=self.base_body(provider='', model='mock-producer'))
        self.assertEqual(mock.status_code, 200, mock.text)
        self.assertEqual(mock.json()['mode'], 'mock')
        self.assertEqual(mock.json()['estimated_usd'], 0.0)
        unknown = self.client.post('/api/producer/estimate', json=self.base_body(provider='', model='gpt-4.1-mini'))
        self.assertEqual(unknown.status_code, 400, unknown.text)
        self.assertIn('не найдена в реестре', unknown.json()['detail'])


if __name__ == '__main__':
    unittest.main()
