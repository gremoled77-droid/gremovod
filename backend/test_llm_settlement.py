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
import time
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

    def call_id(self, request_id):
        with main.connect() as db:
            return db.execute('SELECT id FROM llm_calls WHERE request_id=?', (request_id,)).fetchone()['id']

    def test_reconcile_failure_of_plain_call_releases_the_whole_reserve(self):
        """Обычный вызов без подтверждённой части: сверка «не списал» снимает весь резерв.

        Разделение частей не должно ломать старый контракт одиночного вызова.
        """
        self.prepare()
        quote = self.quote()
        body = {'provider': 'piapi', 'project_id': self.pid, 'model': 'gpt-5.6-luna', 'messages': self.messages,
                'max_tokens': 500, 'approved': True, 'quote_token': quote['quote_token'],
                'max_cost_usd': quote['estimated_usd'], 'request_id': 'ga01-recon-single-1'}
        with patch.object(main, 'request_piapi', AsyncMock(side_effect=main.HTTPException(502, 'таймаут'))):
            self.client.post('/api/llm/chat', json=body)
        row = self.call_row('ga01-recon-single-1')
        self.assertEqual(row['status'], 'submission_unknown')
        response = self.client.post(f'/api/llm/calls/{self.call_id("ga01-recon-single-1")}/reconcile',
                                    json={'outcome': 'failed', 'note': 'проверил у провайдера: списания нет', 'approved': True})
        self.assertEqual(response.status_code, 200, response.text)
        after = self.call_row('ga01-recon-single-1')
        self.assertEqual((after['status'], after['usd']), ('failed', 0))
        # Повторная сверка — отказ: исход уже решён.
        self.assertEqual(self.client.post(f'/api/llm/calls/{self.call_id("ga01-recon-single-1")}/reconcile',
                                          json={'outcome': 'done', 'note': 'ещё раз', 'approved': True}).status_code, 409)


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


class AgentsReconcileTests(unittest.TestCase):
    """P1 ревью Codex: сверка неопределённой части не обнуляет подтверждённые расходы.

    Прогон агентов — один платный вызов на три роли. Роли с достоверным usage дают факт,
    проблемная роль оставляет резерв. Сверка освобождает резерв, но подтверждённое
    остаётся в счёте: иначе сверка одной неоплаченной роли стирает оплату остальных.
    """

    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def prepare(self):
        main.PIAPI_KEY_FILE.write_text('test-key', encoding='utf-8')
        self.pid = self.client.post('/api/projects', json={'title': 'GA-01 reconcile', 'state': {}}).json()['id']
        self.body = {'project_id': self.pid, 'brief': 'Грэм едет ночью', 'model': 'gpt-5.6-luna', 'provider': '',
                     'target_models': ['seedream-5-pro']}

    def run_agents(self, request_id, outcomes):
        """outcomes: список (content, usage) по ролям."""
        quote = self.client.post('/api/agents/estimate', json=self.body).json()
        with patch.object(main, 'agent_completion', AsyncMock(side_effect=outcomes)):
            r = self.client.post('/api/agents/run', json={**self.body, 'approved': True, 'quote_token': quote['quote_token'],
                                                          'max_cost_usd': quote['estimated_usd'], 'request_id': request_id})
        return r, quote

    def spend_row(self):
        """Только поля, которые были в журнале до разделения: регресс падает и на старой схеме."""
        with main.connect() as db:
            return db.execute('SELECT id,status,usd FROM llm_calls').fetchone()

    def split_row(self):
        with main.connect() as db:
            return db.execute('SELECT id,status,usd,confirmed_usd,input_tokens,output_tokens,note FROM llm_calls').fetchone()

    def confirmed_for(self, tokens_in, tokens_out):
        price_in, price_out = llm_guard.price_of('gpt-5.6-luna')
        return round((tokens_in * price_in + tokens_out * price_out) / 1_000_000, 6)

    def reconcile(self, call_id, body):
        return self.client.post(f'/api/llm/calls/{call_id}/reconcile', json={**body, 'approved': True})

    def test_reconcile_failure_keeps_confirmed_spend_of_the_other_roles(self):
        """Сверка «провайдер не списал» по одной роли не стирает оплату подтверждённых ролей."""
        self.prepare()
        good = {'prompt_tokens': 120, 'completion_tokens': 40}
        r, _ = self.run_agents('ga01-recon-1', [('Сцена.', good), ('Континуитет.', {}), ('Промпты.', good)])
        self.assertEqual(r.status_code, 200, r.text)
        confirmed = self.confirmed_for(240, 80)
        before = self.spend_row()
        self.assertEqual(before['status'], 'submission_unknown')
        self.assertGreater(before['usd'], confirmed, 'резерв неопределённой роли должен удерживаться')
        response = self.reconcile(before['id'], {'outcome': 'failed', 'note': 'у провайдера по второй роли списания нет'})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload['confirmed_usd'], confirmed)
        self.assertEqual(payload['usd'], confirmed)
        after = self.spend_row()
        self.assertEqual(after['usd'], confirmed, 'подтверждённые расходы остальных ролей не должны обнуляться')
        self.assertGreaterEqual(after['usd'], 0)
        self.assertEqual(self.split_row()['confirmed_usd'], confirmed)
        with main.connect() as db:
            self.assertAlmostEqual(llm_guard.spent(db, self.pid)[0], confirmed, places=6)

    def test_confirmed_part_counts_each_role_with_its_own_usage(self):
        """Подтверждённая часть — сумма по каждой роли со своим usage, а не по первой попавшейся."""
        self.prepare()
        first = {'prompt_tokens': 100, 'completion_tokens': 50}
        third = {'prompt_tokens': 200, 'completion_tokens': 60}
        r, _ = self.run_agents('ga01-recon-2', [('Сцена.', first), ('Континуитет.', {'prompt_tokens': -5, 'completion_tokens': 10}),
                                                   ('Промпты.', third)])
        self.assertEqual(r.status_code, 200, r.text)
        row = self.split_row()
        self.assertEqual(row['confirmed_usd'], self.confirmed_for(300, 110))
        self.assertEqual((row['input_tokens'], row['output_tokens']), (300, 110))

    def test_repeat_reconcile_is_rejected_and_changes_nothing(self):
        """Повторная сверка отклоняется: сумма не может списаться второй раз."""
        self.prepare()
        good = {'prompt_tokens': 120, 'completion_tokens': 40}
        r, _ = self.run_agents('ga01-recon-3', [('Сцена.', good), ('Континуитет.', {}), ('Промпты.', good)])
        self.assertEqual(r.status_code, 200, r.text)
        confirmed = self.confirmed_for(240, 80)
        row = self.spend_row()
        first = self.reconcile(row['id'], {'outcome': 'failed', 'note': 'списания по второй роли нет'})
        self.assertEqual(first.status_code, 200, first.text)
        amount = self.spend_row()['usd']
        self.assertEqual(amount, confirmed)
        again = self.reconcile(row['id'], {'outcome': 'done', 'usd': 0.5, 'note': 'повторная сверка'})
        self.assertEqual(again.status_code, 409, again.text)
        self.assertEqual(self.spend_row()['usd'], amount, 'повторная сверка не должна менять сумму')

    def test_reconcile_zero_never_zeroes_confirmed_part(self):
        """Ноль в сверке не обнуляет подтверждённое и не даёт отрицательной суммы."""
        self.prepare()
        good = {'prompt_tokens': 120, 'completion_tokens': 40}
        r, _ = self.run_agents('ga01-recon-4', [('Сцена.', good), ('Континуитет.', {}), ('Промпты.', good)])
        self.assertEqual(r.status_code, 200, r.text)
        confirmed = self.confirmed_for(240, 80)
        response = self.reconcile(self.spend_row()['id'], {'outcome': 'done', 'usd': 0, 'note': 'проверил, провайдер не списал'})
        self.assertEqual(response.status_code, 200, response.text)
        after = self.spend_row()
        self.assertEqual(after['usd'], confirmed)
        self.assertGreaterEqual(after['usd'], 0)

    def test_reconcile_total_cost_never_goes_below_confirmed(self):
        """Названная стоимость вызова ниже подтверждённого не уменьшает доказанный факт."""
        self.prepare()
        good = {'prompt_tokens': 120, 'completion_tokens': 40}
        r, _ = self.run_agents('ga01-recon-5', [('Сцена.', good), ('Континуитет.', {}), ('Промпты.', good)])
        self.assertEqual(r.status_code, 200, r.text)
        confirmed = self.confirmed_for(240, 80)
        response = self.reconcile(self.spend_row()['id'], {'outcome': 'done', 'usd': round(confirmed / 2, 6),
                                                           'note': 'назвал сумму меньше подтверждённого'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.spend_row()['usd'], confirmed)

    def test_reconcile_unconfirmed_amount_adds_to_confirmed(self):
        """Стоимость неопределённой части добавляется к подтверждённой, а не заменяет её."""
        self.prepare()
        good = {'prompt_tokens': 120, 'completion_tokens': 40}
        r, _ = self.run_agents('ga01-recon-6', [('Сцена.', good), ('Континуитет.', {}), ('Промпты.', good)])
        self.assertEqual(r.status_code, 200, r.text)
        confirmed = self.confirmed_for(240, 80)
        response = self.reconcile(self.spend_row()['id'], {'outcome': 'done', 'unconfirmed_usd': 0.001,
                                                           'note': 'у провайдера по второй роли 0.001'})
        self.assertEqual(response.status_code, 200, response.text)
        after = self.spend_row()
        self.assertEqual(after['usd'], round(confirmed + 0.001, 6))
        self.assertEqual(self.split_row()['confirmed_usd'], confirmed)

    def test_usd_and_unconfirmed_usd_together_are_rejected(self):
        """Две суммы сразу — неоднозначно: такой запрос не принимается."""
        self.prepare()
        good = {'prompt_tokens': 120, 'completion_tokens': 40}
        r, _ = self.run_agents('ga01-recon-7', [('Сцена.', good), ('Континуитет.', {}), ('Промпты.', good)])
        self.assertEqual(r.status_code, 200, r.text)
        response = self.reconcile(self.spend_row()['id'], {'outcome': 'done', 'usd': 0.01, 'unconfirmed_usd': 0.01,
                                                           'note': 'две суммы сразу'})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.spend_row()['status'], 'submission_unknown')

    def test_unknown_part_is_reported_separately(self):
        """В отчёте и журнале подтверждённое и неопределённое видны раздельно."""
        self.prepare()
        good = {'prompt_tokens': 120, 'completion_tokens': 40}
        r, _ = self.run_agents('ga01-recon-8', [('Сцена.', good), ('Континуитет.', {}), ('Промпты.', good)])
        self.assertEqual(r.status_code, 200, r.text)
        confirmed = self.confirmed_for(240, 80)
        row = self.split_row()
        with main.connect() as db:
            report = llm_guard.summary(db, {self.pid})
        self.assertEqual(report['confirmed_usd'], confirmed)
        self.assertAlmostEqual(report['unknown_usd'], row['usd'] - confirmed, places=6)
        self.assertEqual(report['unknown_calls'], 1)
        calls = self.client.get('/api/llm/calls').json()
        self.assertEqual(calls[0]['confirmed_usd'], confirmed)


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

    def test_task_reserve_writes_a_row_the_current_schema_accepts(self):
        """Резерв задания пишется в текущую схему журнала, подтверждённая часть — 0.

        Журнал разделён на подтверждённое и неопределённое: запись резерва обязана
        попадать в колонки, которые сейчас есть, иначе задание падает на записи.
        """
        self.prepare()
        with main.connect() as db:
            db.execute('INSERT INTO llm_tasks(id,project_id,revision,model,spec,estimated_usd,status,permit_expires,result,valid,created_at,expires_at)'
                       ' VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                       (self.TASK_ID, self.pid, 'rev-1', 'minimax-m2.1', json.dumps({}), self.ESTIMATED_USD, 'permitted',
                        int(time.time()) + 600, None, None, main.now(), int(time.time()) + 3600))
        with patch.object(llm_guard, 'task_request_id', lambda row: self.REQUEST_ID, create=True):
            call_id = llm_guard.reserve_minimax_task(main, self.row, 'rev-1')
        with main.connect() as db:
            row = db.execute('SELECT status,usd,confirmed_usd FROM llm_calls WHERE id=?', (call_id,)).fetchone()
        self.assertEqual(row['status'], 'reserved')
        self.assertEqual(row['usd'], self.ESTIMATED_USD)
        self.assertEqual(row['confirmed_usd'], 0)

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
