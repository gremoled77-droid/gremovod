"""GA-01 R3 (ревью Claude): нечитаемая сумма не должна ронять барьер и не должна выглядеть как доказанный ноль.

После R2 строка llm_calls с usd='unreadable' останавливает траты, но:
- spend_ledger.state/security.check_budget падают TypeError (HTTP 500), а не контролируемым отказом;
- /api/budgets падает тем же TypeError, владелец не видит строку, ждущую его решения;
- /api/economics показывает llm.usd=0.0 и costs_complete=True.
Без сети и платных вызовов: провайдеры подменены.
"""
import unittest
from datetime import datetime, timedelta, timezone

from backend import llm_guard, main, test_smoke


class UnreadableBarrierTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def seed(self, days_ago):
        self.a = self.client.post('/api/projects', json={'title': 'A', 'state': {}}).json()['id']
        self.b = self.client.post('/api/projects', json={'title': 'B', 'state': {}}).json()['id']
        created = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
        with main.connect() as db:
            db.execute('INSERT INTO llm_calls(id,request_id,project_id,model,status,usd,estimated_usd,created_at,note,confirmed_usd) '
                       'VALUES(?,?,?,?,?,?,?,?,?,?)',
                       ('u1', 'u1request0001', self.a, 'gpt-5.6-luna', 'submission_unknown', llm_guard.UNREADABLE_AMOUNT,
                        0.3, created, 'OWNER_DECISION_REQUIRED', 0.0))

    def media(self, project_id, request_id):
        main.PIAPI_KEY_FILE.write_text('test-key', encoding='utf-8')
        body = {'project_id': project_id, 'model_id': 'seedream-5-lite', 'prompt': 'Ночной Минск',
                'request_id': request_id, 'approved': True, 'max_cost_usd': 0.052}
        estimate = self.client.post('/api/model-jobs/estimate', json=body)
        self.assertEqual(estimate.status_code, 200, estimate.text)
        body['quote_token'] = estimate.json()['quote_token']
        main.request_piapi.side_effect = main.HTTPException(502, 'REACHED_PROVIDER')
        return self.client.post('/api/model-jobs', json=body)

    def test_budget_screen_reports_the_unreadable_row_instead_of_crashing(self):
        self.seed(days_ago=3)
        response = self.client.get('/api/budgets/' + self.a)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['llm_unreadable_project'], 1)

    def test_paid_media_of_the_broken_project_is_refused_with_a_controlled_error(self):
        self.seed(days_ago=3)
        response = self.media(self.a, 'request-id-A-123456789')
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn('повреждён', response.text)
        self.assertNotIn('REACHED_PROVIDER', response.text)

    def test_old_unreadable_row_does_not_stop_the_other_project(self):
        """Старая строка касается только своего проекта: неизвестная сумма в сегодняшний день не попадает."""
        self.seed(days_ago=3)
        self.assertEqual(self.client.get('/api/budgets/' + self.b).status_code, 200)
        self.assertEqual(self.media(self.b, 'request-id-B-123456789').status_code, 502)  # дошло до провайдера

    def test_todays_unreadable_row_stops_everyone_with_a_controlled_error(self):
        """Сегодняшняя нечитаемая сумма могла войти в дневной лимит: траты остановлены везде, но отказом, а не 500."""
        self.seed(days_ago=0)
        response = self.media(self.b, 'request-id-B-223456789')
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn('повреждён', response.text)
        self.assertEqual(self.client.get('/api/budgets/' + self.b).status_code, 200)

    def test_economics_does_not_present_the_unreadable_row_as_a_proven_zero(self):
        self.seed(days_ago=3)
        report = self.client.get('/api/economics', params={'project_id': self.a}).json()
        self.assertFalse(report['costs_complete'])
        self.assertEqual(report['llm_unreadable_calls'], 1)
        clean = self.client.get('/api/economics', params={'project_id': self.b}).json()
        self.assertTrue(clean['costs_complete'])


if __name__ == '__main__':
    unittest.main()
