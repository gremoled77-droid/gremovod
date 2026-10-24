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

    def test_budget_reserved_before_call_and_unknown_failure_keeps_it(self):
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
        request = self.chat_body(body, quote, request_id='llm-test-request-2')
        with patch.object(main, 'request_piapi', failing):
            r = self.client.post('/api/llm/chat', json=request)
            self.assertEqual(r.status_code, 502)
            self.assertEqual(self.client.post('/api/llm/chat', json=request).status_code, 409)
            self.assertEqual(failing.await_count, 1)
        with main.connect() as db:
            row = db.execute("SELECT status,usd FROM llm_calls WHERE request_id='llm-test-request-2'").fetchone()
            self.assertEqual((row['status'], row['usd']), ('submission_unknown', quote['estimated_usd']))
            self.assertEqual(llm_guard.spent(db, self.pid), (quote['estimated_usd'], quote['estimated_usd']))
        self.client.put('/api/budgets/limits', json={'project_usd': quote['estimated_usd'], 'daily_usd': 2})
        with patch.object(main, 'request_piapi', AsyncMock(return_value=REPLY)) as call:
            blocked = self.client.post('/api/llm/chat', json={**request, 'request_id': 'llm-after-unknown'})
            self.assertEqual(blocked.status_code, 400)
            self.assertIn('бюджет', blocked.text.lower())
            call.assert_not_awaited()

    def test_other_paid_llm_routes_stay_closed(self):
        for endpoint in ('/api/chat', '/api/compose', '/api/agents/run'):
            self.assertIn(self.client.post(endpoint, json={'approved': True}).status_code, (400, 422))


class PaidLlmRouteGuardTests(unittest.TestCase):
    """Контроль платных LLM-вызовов на маршрутах /api/chat, /api/compose и /api/agents/run."""
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def prepare(self):
        main.PIAPI_KEY_FILE.write_text('test-key', encoding='utf-8')
        self.pid = self.client.post('/api/projects', json={'title': 'Paid', 'state': {'brief': 'Грэм входит в комнату'}}).json()['id']

    def compose_body(self, **extra):
        return {'project_id': self.pid, 'model': 'gpt-5.6-luna', 'provider': 'piapi', 'target': 'seedream-5-pro', **extra}

    def agents_body(self, **extra):
        return {'project_id': self.pid, 'model': 'gpt-5.6-luna', 'provider': 'piapi', 'brief': 'Грэм входит в комнату',
                'character': {'identity': {'name': 'Грэм'}}, 'style': {}, 'target_models': ['seedream-5-pro'], **extra}

    def reply(self, content='Грэм входит в кадр, статичный кадр'):
        return content, {'prompt_tokens': 100, 'completion_tokens': 20}

    def test_paid_routes_refuse_without_a_signed_estimate(self):
        self.prepare()
        with patch.object(main, 'agent_completion', AsyncMock(return_value=self.reply())) as call, \
             patch.object(main, 'request_piapi', AsyncMock(side_effect=AssertionError('External API forbidden'))) as raw:
            chat = {'provider': 'piapi', 'project_id': self.pid, 'model': 'gpt-5.6-luna',
                    'messages': [{'role': 'user', 'content': 'привет'}], 'max_tokens': 500, 'approved': True,
                    'max_cost_usd': 1, 'request_id': 'paid-no-quote-chat'}
            self.assertEqual(self.client.post('/api/chat', json=chat).status_code, 400)
            # Лимит стоимости подтверждён, но подписанной оценки нет: провайдер вызываться не должен.
            self.assertEqual(self.client.post('/api/compose', json=self.compose_body(approved=True, max_cost_usd=1,
                                                                                     request_id='paid-no-quote-compose')).status_code, 400)
            self.assertEqual(self.client.post('/api/agents/run', json=self.agents_body(approved=True, max_cost_usd=1,
                                                                                       request_id='paid-no-quote-agents')).status_code, 400)
            # Подделанная подпись: цена подтверждена, но оценка не от сервера.
            forged = 'a.b'
            self.assertEqual(self.client.post('/api/compose', json=self.compose_body(approved=True, quote_token=forged,
                                                                                     max_cost_usd=1, request_id='paid-forged-compose')).status_code, 400)
            self.assertEqual(self.client.post('/api/agents/run', json=self.agents_body(approved=True, quote_token=forged,
                                                                                       max_cost_usd=1, request_id='paid-forged-agents')).status_code, 400)
            # Без явного подтверждения владельца — тоже отказ.
            self.assertEqual(self.client.post('/api/compose', json=self.compose_body(request_id='paid-no-approval-compose')).status_code, 400)
            self.assertEqual(self.client.post('/api/agents/run', json=self.agents_body(request_id='paid-no-approval-agents')).status_code, 400)
            self.assertEqual(call.await_count, 0)
            self.assertEqual(raw.await_count, 0)
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM llm_calls').fetchone()[0], 0)

    def test_paid_routes_refuse_when_the_project_budget_is_exceeded(self):
        self.prepare()
        quote = self.client.post('/api/compose/estimate', json=self.compose_body()).json()
        self.assertGreater(quote['estimated_usd'], 0.00001)
        self.client.put('/api/budgets/limits', json={'project_usd': 0.00001, 'daily_usd': 0.00001})
        with patch.object(main, 'agent_completion', AsyncMock(return_value=self.reply())) as call:
            r = self.client.post('/api/compose', json=self.compose_body(approved=True, quote_token=quote['quote_token'],
                                                                        max_cost_usd=quote['estimated_usd'], request_id='paid-budget-compose'))
            self.assertEqual(r.status_code, 400)
            self.assertIn('бюджет', r.text.lower())
            self.assertEqual(call.await_count, 0)

    def test_paid_routes_refuse_when_the_daily_budget_is_exceeded(self):
        self.prepare()
        quote = self.client.post('/api/compose/estimate', json=self.compose_body()).json()
        self.client.put('/api/budgets/limits', json={'project_usd': 100, 'daily_usd': 0.00001})
        with patch.object(main, 'agent_completion', AsyncMock(return_value=self.reply())) as call:
            r = self.client.post('/api/compose', json=self.compose_body(approved=True, quote_token=quote['quote_token'],
                                                                        max_cost_usd=quote['estimated_usd'], request_id='paid-daily-compose'))
            self.assertEqual(r.status_code, 400)
            self.assertIn('суточный', r.text.lower())
            self.assertEqual(call.await_count, 0)

    def test_repeated_request_id_is_refused(self):
        self.prepare()
        quote = self.client.post('/api/compose/estimate', json=self.compose_body()).json()
        body = self.compose_body(approved=True, quote_token=quote['quote_token'], max_cost_usd=quote['estimated_usd'],
                                  request_id='paid-duplicate-compose')
        with patch.object(main, 'agent_completion', AsyncMock(return_value=self.reply())) as call:
            first = self.client.post('/api/compose', json=body)
            self.assertEqual(first.status_code, 200, first.text)
            second = self.client.post('/api/compose', json=body)
            self.assertEqual(second.status_code, 409)
            self.assertEqual(call.await_count, 1)

    def test_repeated_request_id_is_refused_for_the_whole_agent_sequence(self):
        self.prepare()
        quote = self.client.post('/api/agents/estimate', json=self.agents_body()).json()
        body = self.agents_body(approved=True, quote_token=quote['quote_token'], max_cost_usd=quote['estimated_usd'],
                                request_id='paid-duplicate-agents')
        with patch.object(main, 'agent_completion', AsyncMock(return_value=self.reply())) as call:
            first = self.client.post('/api/agents/run', json=body)
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual(call.await_count, 3)
            second = self.client.post('/api/agents/run', json=body)
            self.assertEqual(second.status_code, 409)
            self.assertEqual(call.await_count, 3)

    def test_provider_error_without_charge_evidence_keeps_the_reservation(self):
        self.prepare()
        quote = self.client.post('/api/compose/estimate', json=self.compose_body()).json()
        failing = AsyncMock(side_effect=main.HTTPException(502, 'PiAPI вернул ошибку'))
        with patch.object(main, 'agent_completion', failing):
            r = self.client.post('/api/compose', json=self.compose_body(approved=True, quote_token=quote['quote_token'],
                                                                        max_cost_usd=quote['estimated_usd'], request_id='paid-provider-compose'))
            self.assertEqual(r.status_code, 502)
        with main.connect() as db:
            row = db.execute('SELECT status,usd FROM llm_calls').fetchone()
            self.assertEqual((row['status'], row['usd']), ('submission_unknown', quote['estimated_usd']))
            self.assertEqual(llm_guard.spent(db, self.pid), (quote['estimated_usd'], quote['estimated_usd']))

    def test_partial_agent_failure_keeps_paid_work_accounted(self):
        self.prepare()
        quote = self.client.post('/api/agents/estimate', json=self.agents_body()).json()
        answers = [self.reply('режиссёрский план'), main.HTTPException(502, 'PiAPI вернул ошибку')]

        async def side_effect(*args, **kwargs):
            item = answers.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with patch.object(main, 'agent_completion', AsyncMock(side_effect=side_effect)) as call:
            r = self.client.post('/api/agents/run', json=self.agents_body(approved=True, quote_token=quote['quote_token'],
                                                                         max_cost_usd=quote['estimated_usd'], request_id='paid-partial-agents'))
            self.assertEqual(r.status_code, 502)
            detail = r.json()['detail']
            self.assertEqual(detail['code'], 'AGENT_SEQUENCE_PARTIAL')
            self.assertEqual(detail['completed'], ['director'])
            self.assertEqual(detail['failed_role'], 'continuity')
            self.assertEqual(call.await_count, 2)  # третий агент не запускался
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM llm_calls').fetchone()[0], 2)
            done = db.execute("SELECT usd FROM llm_calls WHERE request_id=? AND status='done'",
                              ('paid-partial-agents#director',)).fetchone()
            unknown = db.execute("SELECT usd,estimated_usd FROM llm_calls WHERE request_id=? AND status='submission_unknown'",
                                 ('paid-partial-agents#continuity',)).fetchone()
            self.assertGreater(done['usd'], 0)
            self.assertIsNotNone(unknown)
            self.assertGreater(unknown['usd'], 0)
            self.assertEqual(unknown['usd'], unknown['estimated_usd'])
            expected = done['usd'] + unknown['usd']
            self.assertEqual(llm_guard.spent(db, self.pid), (expected, expected))

    def test_agent_sequence_checks_the_aggregate_forecast_before_any_call(self):
        self.prepare()
        quote = self.client.post('/api/agents/estimate', json=self.agents_body()).json()
        self.assertEqual(quote['calls'], ['director', 'continuity', 'prompt'])
        calls, forecast = main.agent_plan(main.AgentRunRequest(**self.agents_body()))
        one = calls[0]['cost']
        self.assertLess(one, forecast)  # один агент дешевле всей последовательности
        # Лимит помещается для одного агента, но не для суммарного прогноза.
        self.client.put('/api/budgets/limits', json={'project_usd': one * 1.5, 'daily_usd': forecast * 4})
        with patch.object(main, 'agent_completion', AsyncMock(return_value=self.reply())) as call:
            r = self.client.post('/api/agents/run', json=self.agents_body(approved=True, quote_token=quote['quote_token'],
                                                                         max_cost_usd=quote['estimated_usd'], request_id='paid-forecast-agents'))
            self.assertEqual(r.status_code, 400)
            self.assertIn('бюджет', r.text.lower())
            self.assertEqual(call.await_count, 0)
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM llm_calls').fetchone()[0], 0)

    def test_chat_alias_is_guarded_like_the_main_llm_route(self):
        self.prepare()
        body = {'project_id': self.pid, 'model': 'gpt-5.6-luna', 'messages': [{'role': 'user', 'content': 'привет'}], 'max_tokens': 500}
        quote = self.client.post('/api/llm/estimate', json=body).json()
        with patch.object(main, 'request_piapi', AsyncMock(return_value=REPLY)) as raw:
            without = self.client.post('/api/chat', json={**body, 'provider': 'piapi', 'approved': True,
                                                          'max_cost_usd': quote['estimated_usd'],
                                                          'request_id': 'paid-chat-no-quote'})
            self.assertEqual(without.status_code, 400)
            self.assertEqual(raw.await_count, 0)
            allowed = self.client.post('/api/chat', json={**body, 'provider': 'piapi', 'approved': True,
                                                          'quote_token': quote['quote_token'],
                                                          'max_cost_usd': quote['estimated_usd'], 'request_id': 'paid-chat-with-quote'})
            self.assertEqual(allowed.status_code, 200, allowed.text)
            self.assertEqual(raw.await_count, 1)

    def test_paid_calls_carry_a_token_ceiling(self):
        self.prepare()
        quote = self.client.post('/api/compose/estimate', json=self.compose_body()).json()
        with patch.object(main, 'agent_completion', AsyncMock(return_value=self.reply())) as call:
            r = self.client.post('/api/compose', json=self.compose_body(approved=True, quote_token=quote['quote_token'],
                                                                        max_cost_usd=quote['estimated_usd'], request_id='paid-ceiling-compose'))
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(call.await_args.args[4], main.COMPOSE_MAX_TOKENS)
            self.assertLessEqual(main.COMPOSE_MAX_TOKENS, llm_guard.MAX_OUTPUT_TOKENS)

    def test_estimate_stops_working_when_the_project_context_changes(self):
        self.prepare()
        quote = self.client.post('/api/compose/estimate', json=self.compose_body()).json()
        with main.connect() as db:
            db.execute('UPDATE projects SET state=? WHERE id=?', (json.dumps({'brief': 'Другая сцена'}), self.pid))
        with patch.object(main, 'agent_completion', AsyncMock(return_value=self.reply())) as call:
            r = self.client.post('/api/compose', json=self.compose_body(approved=True, quote_token=quote['quote_token'],
                                                                        max_cost_usd=quote['estimated_usd'], request_id='paid-stale-compose'))
            self.assertEqual(r.status_code, 400)
            self.assertEqual(call.await_count, 0)

    def test_unpriced_model_or_provider_is_refused(self):
        self.prepare()
        for body in (self.compose_body(provider='openai'), self.compose_body(model='gpt-9-unknown')):
            self.assertEqual(self.client.post('/api/compose', json=body).status_code, 400)
        for body in (self.agents_body(provider='openai'), self.agents_body(model='gpt-9-unknown')):
            self.assertEqual(self.client.post('/api/agents/run', json=body).status_code, 400)
        with patch.object(main, 'agent_completion', AsyncMock(return_value=self.reply())) as call:
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
