"""Сценарный контур для внешнего оркестратора: доступ, MOCK и запрет платного вызова.

Проверяется главное свойство: внешний вызов запускает только бесплатный MOCK,
стоит ноль и не может выбрать провайдера.
"""
import unittest
from unittest.mock import patch

from backend import scenario_dispatch, test_smoke

TOKEN = 'scenario-token-0123456789abcdef0123456789abcdef'
OTHER_TOKEN = 'other-token-0123456789abcdef0123456789abcdef'


class ScenarioDispatchTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def setUp(self):
        test_smoke.StudioSmokeTests.setUp(self)
        created = self.client.post('/api/projects', json={
            'title': 'Сценарий',
            'state': {'characters': [{'id': 'grem', 'name': 'Грэм'}]},
        })
        self.project_id = created.json()['id']
        self.body = {'project_id': self.project_id, 'idea': 'Грэм подъезжает к аэропорту и опаздывает.',
                     'character_ids': ['grem'], 'duration_seconds': 60, 'request_id': 'n8n-1'}

    def env(self, token=TOKEN, scope='*', enabled='1'):
        return {'STUDIO_SERVICE_TOKENS': f'{token}:{scope}', scenario_dispatch.ENABLE_ENV: enabled}

    def call(self, body=None, headers=None, env=None):
        with patch.dict('os.environ', env if env is not None else self.env(), clear=False):
            return self.client.post('/api/scenario/producer', json=body or self.body, headers=headers or {})

    def test_without_machine_token_the_call_is_rejected(self):
        response = self.call()
        self.assertEqual(response.status_code, 401, response.text)

    def test_token_outside_the_project_zone_is_rejected(self):
        response = self.call(headers={'Authorization': f'Bearer {TOKEN}'},
                             env=self.env(scope='другой-проект'))
        self.assertEqual(response.status_code, 403, response.text)

    def test_disabled_contour_is_rejected_with_a_clear_reason(self):
        response = self.call(headers={'Authorization': f'Bearer {TOKEN}'}, env=self.env(enabled=''))
        self.assertEqual(response.status_code, 503, response.text)
        self.assertIn('согласование', response.json()['detail'])

    def test_mock_stage_returns_the_structure_and_costs_nothing(self):
        response = self.call(headers={'Authorization': f'Bearer {TOKEN}'})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['mode'], 'MOCK')
        self.assertEqual(data['status'], 'MOCK_STAGE_COMPLETE')
        self.assertEqual(data['stage'], 'producer.structure')
        self.assertEqual(data['cost_usd'], 0.0)
        self.assertEqual(data['estimated_usd'], 0.0)
        self.assertEqual(data['external_calls'], 0)
        self.assertFalse(data['paid_call_possible'])
        self.assertEqual(data['model']['provider'], 'mock')
        self.assertFalse(data['model']['paid'])
        self.assertEqual(data['request_id'], 'n8n-1')
        self.assertTrue(data['beats'])
        self.assertTrue(data['scenes'])
        self.assertTrue(data['logline'])

    def test_caller_cannot_choose_provider_or_model(self):
        body = dict(self.body, provider='piapi', model='gpt-5.6-luna')
        response = self.call(body=body, headers={'Authorization': f'Bearer {TOKEN}'})
        self.assertEqual(response.status_code, 422, response.text)

    def test_empty_idea_is_rejected(self):
        body = dict(self.body, idea='')
        response = self.call(body=body, headers={'Authorization': f'Bearer {TOKEN}'})
        self.assertEqual(response.status_code, 422, response.text)

    def test_unknown_character_is_rejected(self):
        body = dict(self.body, character_ids=['nobody'])
        response = self.call(body=body, headers={'Authorization': f'Bearer {TOKEN}'})
        self.assertGreaterEqual(response.status_code, 400)
        self.assertLess(response.status_code, 500)

    def test_remote_caller_without_token_is_blocked_by_the_global_gate(self):
        env = {**self.env(), 'STUDIO_REMOTE_HOSTS': 'studio.grem.win', 'STUDIO_ACCESS_PASSWORD': 'пароль-доступа-студии'}
        with patch.dict('os.environ', env, clear=False):
            remote = self.client.__class__(self.client.app, base_url='http://studio.grem.win')
            with remote:
                response = remote.post('/api/scenario/producer', json=self.body)
        self.assertEqual(response.status_code, 401, response.text)

    def test_remote_caller_with_machine_token_reaches_the_stage(self):
        env = {**self.env(), 'STUDIO_REMOTE_HOSTS': 'studio.grem.win', 'STUDIO_ACCESS_PASSWORD': 'пароль-доступа-студии'}
        with patch.dict('os.environ', env, clear=False):
            remote = self.client.__class__(self.client.app, base_url='http://studio.grem.win')
            with remote:
                response = remote.post('/api/scenario/producer', json=self.body,
                                       headers={'Authorization': f'Bearer {TOKEN}'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['cost_usd'], 0.0)


if __name__ == '__main__':
    unittest.main()
