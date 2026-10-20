import json
import unittest
from unittest.mock import AsyncMock, patch
from backend import llm_guard, main, test_production, test_smoke

REPLY = {'choices': [{'message': {'role': 'assistant', 'content': 'Slow push-in, one continuous shot.'}}],
         'usage': {'prompt_tokens': 120, 'completion_tokens': 40}}


class LlmGuardTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def prepare(self):
        main.PIAPI_KEY_FILE.write_text('test-key', encoding='utf-8')
        self.pid = self.client.post('/api/projects', json={'title': 'LLM', 'state': {}}).json()['id']
        self.messages = [{'role': 'system', 'content': 'Перепиши в промпт'}, {'role': 'user', 'content': 'Грэм подмигивает'}]

    def estimate(self, **extra):
        body = {'project_id': self.pid, 'model': 'gpt-5.6-luna', 'messages': self.messages, 'max_tokens': 500, **extra}
        r = self.client.post('/api/llm/estimate', json=body)
        self.assertEqual(r.status_code, 200, r.text)
        return body, r.json()

    def chat_body(self, body, quote, **extra):
        return {'provider': 'piapi', 'project_id': self.pid, 'model': body['model'], 'messages': self.messages, 'max_tokens': body['max_tokens'],
                'approved': True, 'quote_token': quote['quote_token'], 'max_cost_usd': quote['estimated_usd'],
                'request_id': 'llm-test-request-1', **extra}

    def test_signed_estimate_then_call_records_actual_cost(self):
        self.prepare()
        body, quote = self.estimate()
        self.assertLess(quote['estimated_usd'], 0.001)
        with patch.object(main, 'request_piapi', AsyncMock(return_value=REPLY)) as call:
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote))
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json()['choices'][0]['message']['content'], 'Slow push-in, one continuous shot.')
            self.assertLessEqual(r.json()['cost_usd'], quote['estimated_usd'])
            self.assertEqual(call.await_count, 1)
            self.assertEqual(call.await_args.args[3]['max_tokens'], 500)
            again = self.client.post('/api/llm/chat', json=self.chat_body(body, quote))
            self.assertEqual(again.status_code, 409)
            self.assertEqual(call.await_count, 1)
        with main.connect() as db:
            row = db.execute('SELECT status,input_tokens,output_tokens FROM llm_calls').fetchone()
        self.assertEqual((row['status'], row['input_tokens'], row['output_tokens']), ('done', 120, 40))

    def test_refuses_without_quote_changes_or_confirmation(self):
        self.prepare()
        body, quote = self.estimate()
        with patch.object(main, 'request_piapi', AsyncMock(return_value=REPLY)) as call:
            ok = self.chat_body(body, quote)
            for change in ({'quote_token': ''}, {'quote_token': quote['quote_token'] + 'x'}, {'approved': False}, {'max_tokens': 501},
                           {'messages': [{'role': 'user', 'content': 'другой текст'}]}, {'max_cost_usd': 0}, {'max_cost_usd': None},
                           {'provider': 'openai'}, {'project_id': None}, {'model': 'gpt-9-unknown'}):
                r = self.client.post('/api/llm/chat', json={**ok, **change})
                self.assertEqual(r.status_code, 400, (change, r.text))
            self.assertEqual(self.client.post('/api/llm/chat', json={**ok, 'max_tokens': None}).status_code, 400)
            self.assertEqual(call.await_count, 0)

    def test_limits_on_tokens_models_and_input_size(self):
        self.prepare()
        base = {'project_id': self.pid, 'model': 'gpt-5.6-luna', 'messages': self.messages}
        self.assertEqual(self.client.post('/api/llm/estimate', json={**base, 'max_tokens': 4000}).status_code, 422)
        self.assertEqual(self.client.post('/api/llm/estimate', json={**base, 'model': 'gpt-9-unknown'}).status_code, 400)
        self.assertEqual(self.client.post('/api/llm/estimate', json={**base, 'model': 'gpt-6-astra'}).status_code, 200)
        huge = [{'role': 'user', 'content': 'x' * (llm_guard.MAX_INPUT_CHARS + 1)}]
        self.assertEqual(self.client.post('/api/llm/estimate', json={**base, 'messages': huge}).status_code, 400)
        self.assertEqual(self.client.post('/api/llm/estimate', json={**base, 'project_id': 'absent'}).status_code, 404)
        self.assertEqual(self.client.post('/api/llm/estimate', json={**base, 'messages': [{'role': 'user', 'content': '  '}]}).status_code, 400)

    def test_budget_reserved_before_call_and_reserve_survives_unknown_outcome(self):
        self.prepare()
        self.client.put('/api/budgets/limits', json={'project_usd': 0.00001, 'daily_usd': 0.00001})
        body, quote = self.estimate()
        with patch.object(main, 'request_piapi', AsyncMock(return_value=REPLY)) as call:
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote))
            self.assertEqual(r.status_code, 400)
            self.assertIn('бюджет', r.text.lower())
            self.assertEqual(call.await_count, 0)
        self.client.put('/api/budgets/limits', json={'project_usd': 1, 'daily_usd': 2})
        failing = AsyncMock(side_effect=main.HTTPException(502, 'PiAPI вернул ошибку'))
        with patch.object(main, 'request_piapi', failing):
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, request_id='llm-test-request-2'))
            self.assertEqual(r.status_code, 502)
        with main.connect() as db:
            row = db.execute("SELECT status,usd,estimated_usd FROM llm_calls WHERE request_id='llm-test-request-2'").fetchone()
            # Исход неизвестен: резерв держится до сверки, деньги не возвращаются в лимит.
            self.assertEqual(row['status'], 'submission_unknown')
            self.assertEqual(row['usd'], quote['estimated_usd'])
            self.assertGreater(llm_guard.spent(db, self.pid)[0], 0)
        rejected = AsyncMock(side_effect=main.HTTPException(400, 'PiAPI отклонил запрос'))
        with patch.object(main, 'request_piapi', rejected):
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, request_id='llm-test-request-3'))
            self.assertEqual(r.status_code, 400)
        with main.connect() as db:
            row = db.execute("SELECT status,usd FROM llm_calls WHERE request_id='llm-test-request-3'").fetchone()
            # Отказ провайдера до исполнения: резерв освобождается.
            self.assertEqual((row['status'], row['usd']), ('failed', 0))

    def test_paid_llm_routes_share_the_same_protocol(self):
        """Оценка, подтверждение и лимит теперь есть на всех платных маршрутах.

        Заморозка снята не «на словах»: без подписи и подтверждения запрос
        отклоняется, а провайдер не зовётся.
        """
        self.prepare()
        for endpoint, body in (('/api/compose', {'project_id': self.pid, 'target': 'seedream-5-pro'}),
                               ('/api/agents/run', {'project_id': self.pid, 'brief': 'Грэм едет ночью'})):
            for change in ({'approved': False}, {'quote_token': 'x'}, {'max_cost_usd': 0}):
                r = self.client.post(endpoint, json={**body, **change})
                self.assertIn(r.status_code, (400, 404, 422), (endpoint, change, r.text))
        # Прямой чат закрыт: провайдер не вызывается, ответ ведёт на защищённый маршрут.
        closed = self.client.post('/api/chat', json={'model': 'gpt-5.6-luna', 'messages': [{'role': 'user', 'content': 'x'}]})
        self.assertEqual(closed.status_code, 410)
        self.assertIn('/api/llm/chat', closed.json()['detail'])

    def test_compose_estimates_then_runs_and_records_the_cost(self):
        self.prepare()
        with main.connect() as db:
            db.execute("UPDATE projects SET state=? WHERE id=?", (json.dumps({'brief': 'Грэм едет ночью по Минску.'}, ensure_ascii=False), self.pid))
        body = {'project_id': self.pid, 'target': 'seedream-5-pro', 'model': 'gpt-5.6-luna', 'provider': ''}
        preview = self.client.post('/api/compose/preview', json=body)
        self.assertEqual(preview.status_code, 200, preview.text)
        quote = preview.json()
        self.assertGreater(quote['estimated_usd'], 0)
        self.assertTrue(quote['quote_token'])
        with patch.object(main, 'request_piapi', AsyncMock(return_value=REPLY)) as call:
            r = self.client.post('/api/compose', json={**body, 'approved': True, 'quote_token': quote['quote_token'],
                                                      'max_cost_usd': quote['estimated_usd'], 'request_id': 'compose-test-1'})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(call.await_count, 1)
            again = self.client.post('/api/compose', json={**body, 'approved': True, 'quote_token': quote['quote_token'],
                                                          'max_cost_usd': quote['estimated_usd'], 'request_id': 'compose-test-1'})
            self.assertEqual(again.status_code, 409)
            self.assertEqual(call.await_count, 1)
        with main.connect() as db:
            row = db.execute("SELECT status,usd FROM llm_calls WHERE request_id='compose-test-1'").fetchone()
        self.assertEqual(row['status'], 'done')
        self.assertGreater(row['usd'], 0)

    def test_agents_estimate_covers_every_role_and_one_reservation_holds_them(self):
        self.prepare()
        body = {'project_id': self.pid, 'brief': 'Грэм едет ночью', 'model': 'gpt-5.6-luna', 'provider': '',
                'target_models': ['seedream-5-pro']}
        estimate = self.client.post('/api/agents/estimate', json=body)
        self.assertEqual(estimate.status_code, 200, estimate.text)
        quote = estimate.json()
        self.assertEqual(quote['calls'], 3)
        self.assertGreater(quote['estimated_usd'], 0)
        with patch.object(main, 'agent_completion', AsyncMock(return_value=('Сцена: Грэм едет ночью.', {'prompt_tokens': 120, 'completion_tokens': 40}))) as call:
            r = self.client.post('/api/agents/run', json={**body, 'approved': True, 'quote_token': quote['quote_token'],
                                                        'max_cost_usd': quote['estimated_usd'], 'request_id': 'agents-test-1'})
            self.assertEqual(r.status_code, 200, r.text)
            # Три роли — три вызова провайдера, но резерв в журнале один.
            self.assertEqual(call.await_count, 3)
        with main.connect() as db:
            rows = db.execute('SELECT status,usd FROM llm_calls').fetchall()
        # Три роли — три вызова провайдера, но резерв в журнале один.
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'done')

    def test_agents_run_without_approval_or_quote_never_calls_the_provider(self):
        self.prepare()
        body = {'project_id': self.pid, 'brief': 'Грэм едет ночью', 'model': 'gpt-5.6-luna', 'target_models': ['seedream-5-pro']}
        with patch.object(main, 'request_piapi', AsyncMock(return_value=REPLY)) as call:
            self.assertEqual(self.client.post('/api/agents/run', json=body).status_code, 400)
            self.assertEqual(self.client.post('/api/agents/run', json={**body, 'approved': True}).status_code, 400)
            self.assertEqual(call.await_count, 0)


class LlmEconomicsTests(unittest.TestCase):
    setUp = test_production.ProductionTests.setUp
    tearDown = test_production.ProductionTests.tearDown
    setup_production = test_production.ProductionTests.setup_production
    new = test_production.ProductionTests.new

    def call_llm(self, project_id, request_id):
        messages = [{'role': 'user', 'content': 'Грэм подмигивает'}]
        body = {'project_id': project_id, 'model': 'gpt-5.6-luna', 'messages': messages, 'max_tokens': 500}
        quote = self.client.post('/api/llm/estimate', json=body).json()
        with patch.object(main, 'request_piapi', AsyncMock(return_value=REPLY)):
            return self.client.post('/api/llm/chat', json={**body, 'provider': 'piapi', 'approved': True, 'quote_token': quote['quote_token'],
                                                           'max_cost_usd': quote['estimated_usd'], 'request_id': request_id}), quote

    def test_llm_spend_shows_in_budget_project_and_series_reports(self):
        main.PIAPI_KEY_FILE.write_text('test-key', encoding='utf-8')
        self.setup_production()
        series = self.new('series', 'Серия')
        scene = self.new('episode', 'Встреча', series['id'])
        frame = self.new('frame', 'Крупный план', scene['id'])
        frame_project = self.client.post(f'/api/productions/{self.pid}/nodes/{frame["id"]}/open-project').json()['project_id']
        empty = self.client.get(f'/api/budgets/{frame_project}').json()
        self.assertEqual((empty['llm_project_usd'], empty['llm_daily_usd'], empty['llm_calls_project']), (0, 0, 0))
        reply, quote = self.call_llm(frame_project, 'llm-economics-1')
        self.assertEqual(reply.status_code, 200, reply.text)
        spent = reply.json()['cost_usd']
        self.assertGreater(spent, 0)
        budget = self.client.get(f'/api/budgets/{frame_project}').json()
        self.assertEqual((budget['llm_project_usd'], budget['llm_daily_usd'], budget['llm_calls_project']), (spent, spent, 1))
        project = self.client.get('/api/economics', params={'project_id': frame_project}).json()['llm']
        self.assertEqual((project['calls'], project['usd']), (1, spent))
        self.assertEqual(project['by_model']['gpt-5.6-luna']['calls'], 1)
        other = self.client.get('/api/economics', params={'project_id': self.project}).json()['llm']
        self.assertEqual(other['calls'], 0)
        report = self.client.get(f'/api/productions/{self.pid}/series/{series["id"]}/economics').json()
        self.assertEqual((report['llm']['calls'], report['llm']['usd']), (1, spent))

    def test_series_limit_counts_llm_spend(self):
        main.PIAPI_KEY_FILE.write_text('test-key', encoding='utf-8')
        self.setup_production()
        series = self.new('series', 'Серия')
        scene = self.new('episode', 'Встреча', series['id'])
        frame = self.new('frame', 'Крупный план', scene['id'])
        frame_project = self.client.post(f'/api/productions/{self.pid}/nodes/{frame["id"]}/open-project').json()['project_id']
        first, _ = self.call_llm(frame_project, 'llm-economics-2')
        self.assertEqual(first.status_code, 200, first.text)
        spent = first.json()['cost_usd']
        self.client.put(f'/api/productions/{self.pid}/series/{series["id"]}/budget', json={'limit_usd': spent + 0.00001})
        second, _ = self.call_llm(frame_project, 'llm-economics-3')
        self.assertEqual(second.status_code, 400)
        self.assertIn('серии', second.text)


if __name__ == '__main__':
    unittest.main()
