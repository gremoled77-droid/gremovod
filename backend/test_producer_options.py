"""Каталог выбора модели этапа «Продюсер»: честная доступность и состав моделей.

Проверяется, что в каталоге нет обещаний: провайдер без ключа приходит
недоступным, ключ в ответ не попадает, а модели берутся из реестра.
"""
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from backend import connections, test_smoke


class ProducerOptionsTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def options(self):
        response = self.client.get('/api/producer/options')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_mock_is_first_and_free_by_default(self):
        data = self.options()
        self.assertEqual(data['providers'][0]['id'], 'mock')
        self.assertTrue(data['providers'][0]['available'])
        self.assertEqual(data['providers'][0]['models'], ['mock-producer'])
        self.assertEqual(data['default'], {'provider': 'mock', 'model': 'mock-producer'})
        mock = [model for model in data['models'] if model['id'] == 'mock-producer'][0]
        self.assertEqual(mock['price_in'], 0.0)
        self.assertEqual(mock['price_out'], 0.0)

    def test_models_come_from_the_registry_and_carry_prices(self):
        data = self.options()
        ids = {model['id'] for model in data['models']}
        self.assertIn('gpt-5.6-luna', ids)
        for model in data['models']:
            self.assertIn('idea', model['scopes'])
            self.assertGreaterEqual(model['price_in'], 0)
            self.assertGreaterEqual(model['price_out'], 0)
        luna = [model for model in data['models'] if model['id'] == 'gpt-5.6-luna'][0]
        self.assertEqual(luna['provider'], 'piapi')
        self.assertGreater(luna['price_in'], 0)

    def test_provider_without_key_is_unavailable_without_promises(self):
        with patch.object(connections, 'credential',
                          side_effect=HTTPException(400, 'Ключ не настроен: PIAPI_API_KEY.txt')):
            data = self.options()
        piapi = [item for item in data['providers'] if item['id'] == 'piapi']
        self.assertEqual(len(piapi), 1)
        self.assertFalse(piapi[0]['available'])
        self.assertIn('Ключ не настроен', piapi[0]['message'])
        self.assertTrue(piapi[0]['models'])

    def test_provider_without_llm_models_is_not_offered(self):
        data = self.options()
        ids = {item['id'] for item in data['providers']}
        for without_llm in ('elevenlabs', 'fish'):
            self.assertNotIn(without_llm, ids)

    def test_no_key_material_in_the_answer(self):
        data = self.options()
        for provider in data['providers']:
            self.assertNotIn('key', provider)
            self.assertNotIn('secret', provider)
            self.assertNotIn('digest', provider)


class ProducerProjectStateTests(unittest.TestCase):
    """Выбор модели живёт в состоянии проекта и уважает ревизию."""

    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def test_choice_is_saved_and_loaded_with_the_project(self):
        created = self.client.post('/api/projects', json={
            'title': 'Продюсер',
            'state': {'producer': {'provider': 'piapi', 'model': 'gpt-5.6-luna'}},
        }).json()
        loaded = self.client.get('/api/projects/' + created['id']).json()
        self.assertEqual(loaded['state']['producer'], {'provider': 'piapi', 'model': 'gpt-5.6-luna'})
        self.assertGreaterEqual(loaded['revision'], 0)
        saved = self.client.post('/api/projects', json={
            'id': created['id'], 'title': 'Продюсер',
            'state': {'producer': {'provider': 'mock', 'model': 'mock-producer'}},
            'base_revision': loaded['revision'],
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertGreater(saved.json()['revision'], loaded['revision'])
        again = self.client.get('/api/projects/' + created['id']).json()
        self.assertEqual(again['state']['producer'], {'provider': 'mock', 'model': 'mock-producer'})

    def test_stale_revision_with_a_new_choice_is_a_conflict(self):
        created = self.client.post('/api/projects', json={
            'title': 'Продюсер',
            'state': {'producer': {'provider': 'mock', 'model': 'mock-producer'}},
        }).json()
        pid = created['id']
        updated = self.client.post('/api/projects', json={
            'id': pid, 'title': 'Продюсер', 'state': {'brief': 'правка другого окна'},
            'base_revision': created['revision'],
        })
        self.assertEqual(updated.status_code, 200, updated.text)
        stale = self.client.post('/api/projects', json={
            'id': pid, 'title': 'Продюсер',
            'state': {'producer': {'provider': 'piapi', 'model': 'gpt-5.6-luna'}},
            'base_revision': created['revision'],
        })
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()['detail']['code'], 'PROJECT_CONFLICT')
        latest = self.client.get('/api/projects/' + pid).json()
        self.assertEqual(latest['state']['brief'], 'правка другого окна')
