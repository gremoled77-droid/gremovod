import unittest
from unittest.mock import AsyncMock, patch
from backend import llm_guard, main, test_smoke

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
                           {'provider': 'openai'}, {'project_id': None}, {'model': 'gpt-6-astra'}):
                r = self.client.post('/api/llm/chat', json={**ok, **change})
                self.assertEqual(r.status_code, 400, (change, r.text))
            self.assertEqual(self.client.post('/api/llm/chat', json={**ok, 'max_tokens': None}).status_code, 400)
            self.assertEqual(call.await_count, 0)

    def test_limits_on_tokens_models_and_input_size(self):
        self.prepare()
        base = {'project_id': self.pid, 'model': 'gpt-5.6-luna', 'messages': self.messages}
        self.assertEqual(self.client.post('/api/llm/estimate', json={**base, 'max_tokens': 4000}).status_code, 422)
        self.assertEqual(self.client.post('/api/llm/estimate', json={**base, 'model': 'gpt-6-astra'}).status_code, 400)
        huge = [{'role': 'user', 'content': 'x' * (llm_guard.MAX_INPUT_CHARS + 1)}]
        self.assertEqual(self.client.post('/api/llm/estimate', json={**base, 'messages': huge}).status_code, 400)
        self.assertEqual(self.client.post('/api/llm/estimate', json={**base, 'project_id': 'absent'}).status_code, 404)
        self.assertEqual(self.client.post('/api/llm/estimate', json={**base, 'messages': [{'role': 'user', 'content': '  '}]}).status_code, 400)

    def test_budget_reserved_before_call_and_failed_call_frees_it(self):
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
            self.assertEqual(db.execute("SELECT status,usd FROM llm_calls WHERE request_id='llm-test-request-2'").fetchone()['usd'], 0)
            self.assertEqual(llm_guard.spent(db, self.pid), (0.0, 0.0))

    def test_other_paid_llm_routes_stay_closed(self):
        for endpoint in ('/api/chat', '/api/compose', '/api/agents/run'):
            self.assertEqual(self.client.post(endpoint, json={'approved': True}).status_code, 503)


if __name__ == '__main__':
    unittest.main()
