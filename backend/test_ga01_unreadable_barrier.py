"""GA-01 R3: нечитаемая сумма останавливает траты контролируемым отказом и не выглядит доказанным нулём.

Строка llm_calls с usd='unreadable' (llm_guard.UNREADABLE_AMOUNT) — сумма неизвестна:
- платная операция её проекта получает понятный отказ, а не TypeError и HTTP 500;
- сегодняшняя такая строка могла войти в дневной лимит, поэтому траты останавливаются везде;
- старая строка другого проекта траты не останавливает;
- /api/budgets отвечает и показывает строку, /api/economics не пишет «все суммы известны»;
- лимит серии с такой строкой не считается и не пропускает соседний проект.
Без сети и платных вызовов: провайдеры подменены.
"""
import unittest
from datetime import datetime, timedelta, timezone

from backend import llm_guard, main, test_smoke
from backend import test_production as production_tests


def seed_unreadable(project_id, days_ago):
    created = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    with main.connect() as db:
        db.execute('INSERT INTO llm_calls(id,request_id,project_id,model,status,usd,estimated_usd,created_at,note,confirmed_usd) '
                   'VALUES(?,?,?,?,?,?,?,?,?,?)',
                   ('u1', 'u1request0001', project_id, 'gpt-5.6-luna', 'submission_unknown', llm_guard.UNREADABLE_AMOUNT,
                    0.3, created, 'OWNER_DECISION_REQUIRED', 0.0))


class UnreadableBarrierTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def seed(self, days_ago):
        self.a = self.client.post('/api/projects', json={'title': 'A', 'state': {}}).json()['id']
        self.b = self.client.post('/api/projects', json={'title': 'B', 'state': {}}).json()['id']
        seed_unreadable(self.a, days_ago)

    def media(self, project_id, request_id):
        main.PIAPI_KEY_FILE.write_text('test-key', encoding='utf-8')
        body = {'project_id': project_id, 'model_id': 'seedream-5-lite', 'prompt': 'Ночной Минск',
                'request_id': request_id, 'approved': True, 'max_cost_usd': 0.052}
        estimate = self.client.post('/api/model-jobs/estimate', json=body)
        self.assertEqual(estimate.status_code, 200, estimate.text)
        body['quote_token'] = estimate.json()['quote_token']
        main.request_piapi.side_effect = main.HTTPException(502, 'REACHED_PROVIDER')
        return self.client.post('/api/model-jobs', json=body)

    def llm_chat(self, project_id, request_id):
        main.PIAPI_KEY_FILE.write_text('test-key', encoding='utf-8')
        body = {'project_id': project_id, 'model': 'gpt-5.6-luna', 'max_tokens': 500,
                'messages': [{'role': 'user', 'content': 'Грэм подмигивает'}]}
        quote = self.client.post('/api/llm/estimate', json=body)
        if quote.status_code != 200:
            return quote
        main.request_piapi.side_effect = main.HTTPException(502, 'REACHED_PROVIDER')
        return self.client.post('/api/llm/chat', json={**body, 'provider': 'piapi', 'approved': True, 'request_id': request_id,
                                                       'quote_token': quote.json()['quote_token'],
                                                       'max_cost_usd': quote.json()['estimated_usd']})

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
        llm = self.llm_chat(self.b, 'request-id-B-llm-23456789')
        self.assertEqual(llm.status_code, 400, llm.text)
        self.assertIn('повреждён', llm.text)
        main.request_piapi.assert_not_awaited()
        self.assertEqual(self.client.get('/api/budgets/' + self.b).status_code, 200)

    def test_economics_does_not_present_the_unreadable_row_as_a_proven_zero(self):
        self.seed(days_ago=3)
        report = self.client.get('/api/economics', params={'project_id': self.a}).json()
        self.assertFalse(report['costs_complete'])
        self.assertEqual(report['llm_unreadable_calls'], 1)
        clean = self.client.get('/api/economics', params={'project_id': self.b}).json()
        self.assertTrue(clean['costs_complete'])


class UnreadableSeriesBudgetTests(unittest.TestCase):
    setUp = production_tests.ProductionTests.setUp
    tearDown = production_tests.ProductionTests.tearDown
    setup_production = production_tests.ProductionTests.setup_production
    new = production_tests.ProductionTests.new

    def test_series_limit_is_not_computed_over_an_unreadable_row(self):
        """Старая нечитаемая строка одного кадра серии: соседний кадр не тратит из лимита серии вслепую."""
        self.setup_production()
        series = self.new('series', 'Серия')
        scene = self.new('episode', 'Сцена', series['id'])
        projects = [self.client.post(f'/api/productions/{self.pid}/nodes/{self.new("frame", name, scene["id"])["id"]}/open-project')
                    .json()['project_id'] for name in ('Первый', 'Второй')]
        path = f'/api/productions/{self.pid}/series/{series["id"]}/budget'
        self.assertEqual(self.client.put(path, json={'limit_usd': 1.0}).status_code, 200)
        seed_unreadable(projects[0], days_ago=3)
        with main.connect() as db:
            with self.assertRaises(main.HTTPException) as caught:
                main.security.check_budget(db, projects[1], 0.01)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertIn('серии', caught.exception.detail)
        self.assertEqual(self.client.put(path, json={'limit_usd': None}).status_code, 200)
        with main.connect() as db:
            main.security.check_budget(db, projects[1], 0.01)  # без лимита серии старая строка соседа не мешает


if __name__ == '__main__':
    unittest.main()
