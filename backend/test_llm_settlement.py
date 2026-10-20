"""GA-01: достоверный учёт расходов LLM — офлайн-регрессия.

Правило одно на все платные LLM-контуры:
- счётчики провайдера — целые неотрицательные числа, не bool, не выше потолка доверия;
- итоговая сумма конечна и неотрицательна;
- отсутствие или повреждение usage не доказывает $0: резерв остаётся в руках
  (submission_unknown) с причиной, а не превращается в подтверждённый факт;
- подтверждённый факт пишется полностью, без обрезки оценкой;
- в многошаговом прогоне агентов подтверждённая часть учитывается, неопределённая
  удерживается, ложный $0 не пишется.

Тесты офлайн: провайдер подменён mock-ответами, платных вызовов нет.
"""
import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from backend import llm_guard, main, test_smoke


def reply(usage=None, content='Slow push-in, one continuous shot.'):
    """Ответ провайдера: usage опционален — так проверяется его отсутствие."""
    value = {'choices': [{'message': {'role': 'assistant', 'content': content}}]}
    if usage is not None:
        value['usage'] = usage
    return value


class LlmSettlementTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def prepare(self):
        main.PIAPI_KEY_FILE.write_text('test-key', encoding='utf-8')
        self.pid = self.client.post('/api/projects', json={'title': 'GA-01', 'state': {}}).json()['id']
        self.messages = [{'role': 'system', 'content': 'Перепиши в промпт'}, {'role': 'user', 'content': 'Грэм подмигивает'}]

    def quote(self):
        body = {'project_id': self.pid, 'model': 'gpt-5.6-luna', 'messages': self.messages, 'max_tokens': 500}
        r = self.client.post('/api/llm/estimate', json=body)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def chat(self, quote, request_id, usage):
        body = {'provider': 'piapi', 'project_id': self.pid, 'model': 'gpt-5.6-luna', 'messages': self.messages,
                'max_tokens': 500, 'approved': True, 'quote_token': quote['quote_token'],
                'max_cost_usd': quote['estimated_usd'], 'request_id': request_id}
        with patch.object(main, 'request_piapi', AsyncMock(return_value=reply(usage))) as call:
            r = self.client.post('/api/llm/chat', json=body)
        return r, call

    def call_row(self, request_id):
        with main.connect() as db:
            return db.execute('SELECT status,usd,estimated_usd,input_tokens,output_tokens,note FROM llm_calls WHERE request_id=?',
                              (request_id,)).fetchone()

    def test_missing_usage_keeps_reserve_instead_of_pretending_zero(self):
        """Провайдер не отдал usage: это не доказательство $0, резерв держится."""
        self.prepare()
        quote = self.quote()
        r, call = self.chat(quote, 'ga01-missing-1', None)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(call.await_count, 1)
        self.assertGreaterEqual(r.json()['cost_usd'], 0)
        row = self.call_row('ga01-missing-1')
        self.assertEqual(row['status'], 'submission_unknown')
        self.assertEqual(row['usd'], quote['estimated_usd'])
        self.assertGreater(row['usd'], 0)
        self.assertTrue(row['note'], 'причина неопределённости должна быть записана')

    def test_negative_usage_cannot_reduce_the_budget(self):
        """Отрицательные токены не превращают расход в отрицательную сумму."""
        self.prepare()
        quote = self.quote()
        r, call = self.chat(quote, 'ga01-negative-1', {'prompt_tokens': -1000000, 'completion_tokens': -1000000})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(call.await_count, 1)
        self.assertGreaterEqual(r.json()['cost_usd'], 0)
        row = self.call_row('ga01-negative-1')
        self.assertEqual(row['status'], 'submission_unknown')
        self.assertEqual(row['usd'], quote['estimated_usd'])
        with main.connect() as db:
            self.assertGreater(llm_guard.spent(db, self.pid)[0], 0)

    def test_bool_float_and_string_counters_are_not_trusted(self):
        """Счётчик, который нельзя посчитать, usage не доказывает."""
        self.prepare()
        cases = ({'prompt_tokens': True, 'completion_tokens': 40},
                 {'prompt_tokens': 120.0, 'completion_tokens': 40},
                 {'prompt_tokens': '120', 'completion_tokens': 40},
                 {'prompt_tokens': 120, 'completion_tokens': None},
                 {'prompt_tokens': 120})
        for index, usage in enumerate(cases):
            request_id = f'ga01-badusage-{index}'
            quote = self.quote()
            r, _ = self.chat(quote, request_id, usage)
            self.assertEqual(r.status_code, 200, r.text)
            self.assertGreaterEqual(r.json()['cost_usd'], 0, (usage, r.text))
            row = self.call_row(request_id)
            self.assertEqual(row['status'], 'submission_unknown', (usage, dict(row)))
            self.assertEqual(row['usd'], quote['estimated_usd'], (usage, dict(row)))

    def test_absurd_token_count_is_not_a_fact(self):
        """Счётчик за пределом доверия — повреждённый usage, а не гигантский счёт."""
        self.prepare()
        quote = self.quote()
        r, _ = self.chat(quote, 'ga01-absurd-1', {'prompt_tokens': 10 ** 12, 'completion_tokens': 10 ** 12})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertGreaterEqual(r.json()['cost_usd'], 0)
        row = self.call_row('ga01-absurd-1')
        self.assertEqual(row['status'], 'submission_unknown')
        self.assertEqual(row['usd'], quote['estimated_usd'])

    def test_overrun_above_estimate_is_recorded_in_full(self):
        """Факт выше оценки пишется целиком: оценка — потолок резерва, а не факта."""
        self.prepare()
        quote = self.quote()
        usage = {'prompt_tokens': 120000, 'completion_tokens': 90000}
        r, _ = self.chat(quote, 'ga01-overrun-1', usage)
        self.assertEqual(r.status_code, 200, r.text)
        price_in, price_out = llm_guard.price_of('gpt-5.6-luna')
        expected = round((usage['prompt_tokens'] * price_in + usage['completion_tokens'] * price_out) / 1_000_000, 6)
        self.assertGreater(expected, quote['estimated_usd'])
        self.assertEqual(r.json()['cost_usd'], expected)
        row = self.call_row('ga01-overrun-1')
        self.assertEqual(row['status'], 'done')
        self.assertEqual(row['usd'], expected)
        self.assertEqual((row['input_tokens'], row['output_tokens']), (usage['prompt_tokens'], usage['completion_tokens']))

    def test_ordinary_usage_is_a_confirmed_fact(self):
        """Обычный usage — подтверждённый факт, резерв превращается в цену."""
        self.prepare()
        quote = self.quote()
        usage = {'prompt_tokens': 120, 'completion_tokens': 40}
        r, _ = self.chat(quote, 'ga01-ordinary-1', usage)
        self.assertEqual(r.status_code, 200, r.text)
        price_in, price_out = llm_guard.price_of('gpt-5.6-luna')
        expected = round((usage['prompt_tokens'] * price_in + usage['completion_tokens'] * price_out) / 1_000_000, 6)
        row = self.call_row('ga01-ordinary-1')
        self.assertEqual(row['status'], 'done')
        self.assertEqual(row['usd'], expected)
        self.assertEqual((row['input_tokens'], row['output_tokens']), (120, 40))

    def test_unparseable_answer_keeps_reserve_without_no_charge_evidence(self):
        """Провайдер ответил 200, но ответ не разобрать: запрос мог быть исполнен и оплачен."""
        self.prepare()
        quote = self.quote()
        body = {'provider': 'piapi', 'project_id': self.pid, 'model': 'gpt-5.6-luna', 'messages': self.messages,
                'max_tokens': 500, 'approved': True, 'quote_token': quote['quote_token'],
                'max_cost_usd': quote['estimated_usd'], 'request_id': 'ga01-unparseable-1'}
        with patch.object(main, 'request_piapi',
                          AsyncMock(return_value={'usage': {'prompt_tokens': 120, 'completion_tokens': 40}})):
            r = self.client.post('/api/llm/chat', json=body)
        self.assertEqual(r.status_code, 502, r.text)
        row = self.call_row('ga01-unparseable-1')
        self.assertEqual(row['status'], 'submission_unknown')
        self.assertEqual(row['usd'], quote['estimated_usd'])

    def test_duplicate_request_id_does_not_resubmit(self):
        """Повтор того же request_id не отправляет запрос провайдеру снова."""
        self.prepare()
        quote = self.quote()
        with patch.object(main, 'request_piapi', AsyncMock(return_value=reply({'prompt_tokens': 120, 'completion_tokens': 40}))) as call:
            body = {'provider': 'piapi', 'project_id': self.pid, 'model': 'gpt-5.6-luna', 'messages': self.messages,
                    'max_tokens': 500, 'approved': True, 'quote_token': quote['quote_token'],
                    'max_cost_usd': quote['estimated_usd'], 'request_id': 'ga01-duplicate-1'}
            first = self.client.post('/api/llm/chat', json=body)
            second = self.client.post('/api/llm/chat', json=body)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 409, second.text)
        self.assertEqual(call.await_count, 1)


class AgentsSettlementTests(unittest.TestCase):
    """Прогон агентов: три роли — один резерв, факт по каждой роли считается отдельно."""

    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def prepare(self):
        main.PIAPI_KEY_FILE.write_text('test-key', encoding='utf-8')
        self.pid = self.client.post('/api/projects', json={'title': 'GA-01 agents', 'state': {}}).json()['id']
        self.body = {'project_id': self.pid, 'brief': 'Грэм едет ночью', 'model': 'gpt-5.6-luna', 'provider': '',
                     'target_models': ['seedream-5-pro']}

    def run_agents(self, request_id, outcomes):
        """outcomes: список (content, usage) по ролям либо исключение вместо пары."""
        quote = self.client.post('/api/agents/estimate', json=self.body).json()
        with patch.object(main, 'agent_completion', AsyncMock(side_effect=outcomes)) as call:
            r = self.client.post('/api/agents/run', json={**self.body, 'approved': True, 'quote_token': quote['quote_token'],
                                                          'max_cost_usd': quote['estimated_usd'], 'request_id': request_id})
        return r, call, quote

    def call_row(self):
        with main.connect() as db:
            return db.execute('SELECT status,usd,estimated_usd,input_tokens,output_tokens,note FROM llm_calls').fetchone()

    def test_agents_without_usage_keeps_the_reserve(self):
        """Три роли без usage: провайдер ничего не подтвердил — $0 не пишется."""
        self.prepare()
        r, call, quote = self.run_agents('ga01-agents-1', [('Сцена: Грэм едет ночью.', {})] * 3)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(call.await_count, 3)
        payload = r.json()
        self.assertEqual(payload['confirmed_usd'], 0)
        self.assertFalse(payload['cost_confirmed'])
        self.assertGreater(payload['unconfirmed_usd'], 0)
        self.assertEqual(payload['cost_usd'], quote['estimated_usd'])
        row = self.call_row()
        self.assertEqual(row['status'], 'submission_unknown')
        self.assertEqual(row['usd'], quote['estimated_usd'])
        self.assertNotEqual(row['usd'], 0)

    def test_agents_partial_roles_keep_confirmed_and_unknown_parts(self):
        """Три роли, у второй нет usage: подтверждённое считается, неопределённое удерживается."""
        self.prepare()
        good = {'prompt_tokens': 120, 'completion_tokens': 40}
        r, call, quote = self.run_agents('ga01-agents-2', [('Сцена.', good), ('Континуитет.', {}), ('Промпты.', good)])
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(call.await_count, 3)
        price_in, price_out = llm_guard.price_of('gpt-5.6-luna')
        confirmed = round((240 * price_in + 80 * price_out) / 1_000_000, 6)
        payload = r.json()
        self.assertEqual(payload['confirmed_usd'], confirmed)
        self.assertGreater(payload['unconfirmed_usd'], 0)
        self.assertFalse(payload['cost_confirmed'])
        self.assertEqual(payload['cost_usd'], round(confirmed + payload['unconfirmed_usd'], 6))
        row = self.call_row()
        self.assertEqual(row['status'], 'submission_unknown')
        self.assertEqual(row['usd'], round(confirmed + payload['unconfirmed_usd'], 6))
        self.assertGreater(row['usd'], confirmed)
        self.assertEqual((row['input_tokens'], row['output_tokens']), (240, 80))

    def test_agents_interrupted_keeps_confirmed_part_and_holds_the_rest(self):
        """Обрыв на второй роли: оплаченная первая роль учтена, остальное удерживается."""
        self.prepare()
        good = {'prompt_tokens': 120, 'completion_tokens': 40}
        r, call, quote = self.run_agents('ga01-agents-3', [('Сцена.', good), main.HTTPException(502, 'PiAPI вернул ошибку')])
        self.assertEqual(r.status_code, 502, r.text)
        self.assertEqual(call.await_count, 2)
        row = self.call_row()
        self.assertEqual(row['status'], 'submission_unknown')
        self.assertGreater(row['usd'], 0)
        self.assertNotEqual(row['usd'], 0)
        self.assertLessEqual(row['usd'], quote['estimated_usd'])
        self.assertTrue(row['note'])

    def test_agents_negative_usage_never_lowers_spend(self):
        """Отрицательные токены в роли агента не уменьшают занятый бюджет."""
        self.prepare()
        bad = {'prompt_tokens': -1000000, 'completion_tokens': -1000000}
        r, call, quote = self.run_agents('ga01-agents-4', [('Сцена.', bad)] * 3)
        self.assertEqual(r.status_code, 200, r.text)
        row = self.call_row()
        self.assertEqual(row['status'], 'submission_unknown')
        self.assertEqual(row['usd'], quote['estimated_usd'])
        self.assertGreaterEqual(r.json()['cost_usd'], 0)

    def test_agents_ordinary_usage_is_a_confirmed_fact(self):
        """Все роли с достоверным usage — подтверждённый факт, удержания не остаётся."""
        self.prepare()
        good = {'prompt_tokens': 120, 'completion_tokens': 40}
        r, call, quote = self.run_agents('ga01-agents-5', [('Сцена.', good)] * 3)
        self.assertEqual(r.status_code, 200, r.text)
        price_in, price_out = llm_guard.price_of('gpt-5.6-luna')
        confirmed = round((360 * price_in + 120 * price_out) / 1_000_000, 6)
        payload = r.json()
        self.assertEqual(payload['confirmed_usd'], confirmed)
        self.assertEqual(payload['unconfirmed_usd'], 0)
        self.assertTrue(payload['cost_confirmed'])
        self.assertEqual(payload['cost_usd'], confirmed)
        row = self.call_row()
        self.assertEqual(row['status'], 'done')
        self.assertEqual(row['usd'], confirmed)
        self.assertEqual((row['input_tokens'], row['output_tokens']), (360, 120))


class TaskSettlementTests(unittest.TestCase):
    """Денежная часть задания MiniMax.

    Сам lifecycle задания (prepare → permit → execute) восстанавливается в GA-02
    и здесь намеренно не проверяется: тест достаёт до денежной ветки, подменяя
    только отсутствующие в этой базе помощники (task_identity/task_request_id).
    """

    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    TASK_ID = 'ga01-task-1'
    REQUEST_ID = 'ga01-task-request-1'
    CALL_ID = 'ga01-task-call-1'
    ESTIMATED_USD = 0.1

    def prepare(self):
        main.PIAPI_KEY_FILE.write_text('test-key', encoding='utf-8')
        self.pid = self.client.post('/api/projects', json={'title': 'GA-01 task', 'state': {}}).json()['id']
        spec = {'project_id': self.pid, 'stage': {'id': 'story', 'revision': 'r1', 'instruction': 'Напиши сцену'},
                'model': 'minimax-m2.1', 'inputs': [{'id': 'brief', 'content': 'Грэм едет ночью', 'approved': True}],
                'skills': [], 'max_tokens': 500, 'response_format': 'text', 'request_id': self.REQUEST_ID}
        self.row = {'id': self.TASK_ID, 'project_id': self.pid, 'revision': 'rev-1', 'model': 'minimax-m2.1',
                    'estimated_usd': self.ESTIMATED_USD, 'status': 'permitted', 'spec': json.dumps(spec), 'result': None}

    def reserve(self, studio, row, revision):
        with studio.connect() as db:
            db.execute('INSERT INTO llm_calls(id,request_id,project_id,model,status,usd,estimated_usd,input_tokens,output_tokens,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (self.CALL_ID, f'llm:{self.REQUEST_ID}:{revision}', row['project_id'], row['model'], 'reserved',
                        row['estimated_usd'], row['estimated_usd'], None, None, studio.now()))
        return self.CALL_ID

    def execute(self, provider):
        body = llm_guard.TaskExecution(revision='rev-1', permit_token='signed-permit')
        with patch.object(llm_guard, 'load_task', lambda studio, task_id: self.row), \
                patch.object(llm_guard, 'task_request_id', lambda row: self.REQUEST_ID, create=True), \
                patch.object(llm_guard, 'task_identity', lambda row: {'task_id': row['id'], 'request_id': self.REQUEST_ID,
                                                                      'revision': row['revision']}, create=True), \
                patch.object(llm_guard, 'reserve_minimax_task', self.reserve), \
                patch('backend.security.verify_execution_permit', lambda *args, **kwargs: True), \
                patch.object(main, 'request_piapi', provider):
            return asyncio.run(llm_guard.execute_minimax_task(main, self.TASK_ID, body, 'test-key'))

    def call_row(self):
        with main.connect() as db:
            return db.execute('SELECT status,usd,estimated_usd,note FROM llm_calls WHERE id=?', (self.CALL_ID,)).fetchone()

    def test_task_timeout_keeps_reserve_without_no_charge_evidence(self):
        """Таймаут после отправки не доказывает, что деньги не списаны: резерв держится."""
        self.prepare()
        with self.assertRaises(Exception):
            self.execute(AsyncMock(side_effect=TimeoutError('read timeout')))
        row = self.call_row()
        self.assertEqual(row['status'], 'submission_unknown')
        self.assertEqual(row['usd'], self.ESTIMATED_USD)
        self.assertTrue(row['note'])

    def test_task_provider_refusal_releases_reserve(self):
        """Отказ провайдера до исполнения: деньги не списаны, резерв освобождается."""
        self.prepare()
        with self.assertRaises(Exception):
            self.execute(AsyncMock(side_effect=main.HTTPException(400, 'PiAPI отклонил запрос')))
        row = self.call_row()
        self.assertEqual(row['status'], 'failed')
        self.assertEqual(row['usd'], 0)

    def test_task_explicit_zero_consumption_releases_reserve(self):
        """Провайдер сам сообщил нулевое потребление — это доказательство «не списал»."""
        self.prepare()
        with self.assertRaises(Exception):
            self.execute(AsyncMock(return_value={'usage': {'prompt_tokens': 0, 'completion_tokens': 0}}))
        row = self.call_row()
        self.assertEqual(row['status'], 'failed')
        self.assertEqual(row['usd'], 0)

    def test_task_missing_usage_keeps_reserve(self):
        """Задание выполнено, но usage нет: факт не подтверждён, резерв удерживается."""
        self.prepare()
        result = self.execute(AsyncMock(return_value=reply(None, 'Сцена готова')))
        self.assertEqual(result.content, 'Сцена готова')
        row = self.call_row()
        self.assertEqual(row['status'], 'submission_unknown')
        self.assertEqual(row['usd'], self.ESTIMATED_USD)

    def test_task_valid_usage_is_recorded_in_full(self):
        """Достоверный usage — подтверждённый факт по цене провайдера."""
        self.prepare()
        usage = {'prompt_tokens': 4000, 'completion_tokens': 500}
        result = self.execute(AsyncMock(return_value=reply(usage, 'Сцена готова')))
        price_in, price_out = llm_guard.minimax_price_of('minimax-m2.1')
        expected = round((usage['prompt_tokens'] * price_in + usage['completion_tokens'] * price_out) / 1_000_000, 6)
        row = self.call_row()
        self.assertEqual(row['status'], 'done')
        self.assertEqual(row['usd'], expected)
        self.assertEqual(result.cost_usd, expected)


class UsageValidatorTests(unittest.TestCase):
    """Сам валидатор: только целые неотрицательные числа, не bool, в границах доверия."""

    def test_only_plain_non_negative_ints_are_trusted(self):
        self.assertIsNone(llm_guard.valid_tokens({}))
        self.assertIsNone(llm_guard.valid_tokens({'prompt_tokens': 10}))
        self.assertIsNone(llm_guard.valid_tokens({'prompt_tokens': 10, 'completion_tokens': None}))
        self.assertIsNone(llm_guard.valid_tokens({'prompt_tokens': -1, 'completion_tokens': 1}))
        self.assertIsNone(llm_guard.valid_tokens({'prompt_tokens': True, 'completion_tokens': 1}))
        self.assertIsNone(llm_guard.valid_tokens({'prompt_tokens': 1.5, 'completion_tokens': 1}))
        self.assertIsNone(llm_guard.valid_tokens({'prompt_tokens': '10', 'completion_tokens': 1}))
        self.assertIsNone(llm_guard.valid_tokens({'prompt_tokens': 10 ** 12, 'completion_tokens': 1}))
        self.assertIsNone(llm_guard.valid_tokens('120'))
        self.assertEqual(llm_guard.valid_tokens({'prompt_tokens': 120, 'completion_tokens': 40}), (120, 40))
        self.assertEqual(llm_guard.valid_tokens({'prompt_tokens': 0, 'completion_tokens': 0}), (0, 0))

    def test_cost_is_never_negative_or_nonfinite(self):
        price_in, price_out = llm_guard.price_of('gpt-5.6-luna')
        usd, tokens_in, tokens_out = llm_guard.actual_cost(price_in, price_out, {'prompt_tokens': -100, 'completion_tokens': -100})
        self.assertIsNone(usd)
        self.assertIsNone(tokens_in)
        self.assertIsNone(tokens_out)
        usd, _, _ = llm_guard.actual_cost(price_in, price_out, {'prompt_tokens': 120, 'completion_tokens': 40})
        self.assertGreater(usd, 0)


if __name__ == '__main__':
    unittest.main()
