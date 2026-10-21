"""Денежная граница студии: единый лимит для LLM и генераций, резерв при неопределённом исходе, честный факт.

Проверки воспроизводят поведение учёта. Реальные платные вызовы не выполняются."""
import unittest
from unittest.mock import AsyncMock, patch

from backend import llm_guard, main, security, test_smoke

REPLY = {'choices': [{'message': {'role': 'assistant', 'content': 'Готово.'}}],
         'usage': {'prompt_tokens': 120, 'completion_tokens': 40}}
# Провайдер сообщил нулевое потребление полным набором счётчиков: доказательство есть.
EMPTY_BUT_PAID = {'choices': [{'message': {'role': 'assistant', 'content': ''}}],
                  'usage': {'total_tokens': 0, 'prompt_tokens': 0, 'completion_tokens': 0}}
# Провайдер прислал только total_tokens=0: остальных счётчиков нет, доказательства нет.
ZERO_UNPROVEN = {'choices': [{'message': {'role': 'assistant', 'content': ''}}],
                 'usage': {'total_tokens': 0}}


class MoneyBoundaryTests(unittest.TestCase):
    """Общий лимит проекта и дня одинаков для платных LLM-вызовов и генераций."""

    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def prepare(self):
        main.PIAPI_KEY_FILE.write_text('test-key', encoding='utf-8')
        self.pid = self.client.post('/api/projects', json={'title': 'Money', 'state': {}}).json()['id']

    def quote(self):
        body = {'project_id': self.pid, 'model': 'gpt-5.6-luna',
                'messages': [{'role': 'user', 'content': 'Грэм подмигивает'}], 'max_tokens': 500}
        r = self.client.post('/api/llm/estimate', json=body)
        self.assertEqual(r.status_code, 200, r.text)
        return body, r.json()

    def chat(self, body, quote, request_id, reply=REPLY, error=None):
        payload = {'provider': 'piapi', 'project_id': self.pid, 'model': body['model'], 'messages': body['messages'],
                   'max_tokens': body['max_tokens'], 'approved': True, 'quote_token': quote['quote_token'],
                   'max_cost_usd': quote['estimated_usd'], 'request_id': request_id}
        if error is not None:
            with patch.object(main, 'request_piapi', AsyncMock(side_effect=error)) as call:
                response = self.client.post('/api/llm/chat', json=payload)
                return response, call
        with patch.object(main, 'request_piapi', AsyncMock(return_value=reply)) as call:
            response = self.client.post('/api/llm/chat', json=payload)
            return response, call

    def media_reserve(self, job_id, cost):
        """Симуляция одобренной генерации: деньги удерживаются."""
        with main.connect() as db:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',
                       (job_id, self.pid, 'video', 'piapi', 'task', 'completed', '{}', '{}', main.now()))
            db.execute('INSERT INTO generation_approvals VALUES(?,?,?,?,?)',
                       (job_id, cost, cost, main.now(), 'documentation_estimate'))

    def llm_reserve(self, call_id, usd):
        """Симуляция LLM-вызова в полёте: резерв удерживается."""
        with main.connect() as db:
            db.execute('INSERT INTO llm_calls(id,request_id,project_id,model,status,usd,estimated_usd,input_tokens,output_tokens,created_at)'
                       ' VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (call_id, call_id, self.pid, 'gpt-5.6-luna', 'reserved', usd, usd, None, None, main.now()))

    def call_row(self, request_id):
        with main.connect() as db:
            return db.execute('SELECT * FROM llm_calls WHERE request_id=?', (request_id,)).fetchone()

    def test_media_and_llm_share_one_cap_in_any_order(self):
        self.prepare()
        body, quote = self.quote()
        estimate = quote['estimated_usd']
        self.client.put('/api/budgets/limits', json={'project_usd': 0.0001, 'daily_usd': 1})
        # Сначала генерация заняла часть лимита, затем LLM упирается в тот же лимит.
        self.media_reserve('media-first', 0.00005)
        response, call = self.chat(body, quote, 'money-order-media-first')
        self.assertEqual(response.status_code, 400, response.text)
        self.assertIn('бюджет', response.text.lower())
        self.assertEqual(call.await_count, 0)
        # Обратный порядок: LLM занял часть лимита, теперь генерация упирается в тот же лимит.
        with main.connect() as db:
            db.execute('DELETE FROM generation_approvals WHERE job_id=?', ('media-first',))
            db.execute('DELETE FROM jobs WHERE id=?', ('media-first',))
        self.llm_reserve('llm-first', estimate)
        with main.connect() as db:
            with self.assertRaises(main.HTTPException):
                security.check_budget(db, self.pid, 0.00005)
            with self.assertRaises(main.HTTPException):
                security.check_budget(db, self.pid, 0.00005)
            # а вот столько проходит
            security.check_budget(db, self.pid, 0.00001)

    def test_unknown_outcome_keeps_reserve_and_blocks_paid_retry(self):
        self.prepare()
        body, quote = self.quote()
        response, _ = self.chat(body, quote, 'money-unknown-1', error=main.HTTPException(502, 'PiAPI вернул ошибку'))
        self.assertEqual(response.status_code, 502)
        row = self.call_row('money-unknown-1')
        self.assertEqual(row['status'], 'submission_unknown')
        self.assertEqual(row['usd'], quote['estimated_usd'])
        with main.connect() as db:
            self.assertGreater(llm_guard.spent(db, self.pid)[0], 0)
        # Тот же request_id: повтор не выполняется.
        again, call = self.chat(body, quote, 'money-unknown-1', error=main.HTTPException(502, 'PiAPI вернул ошибку'))
        self.assertEqual(again.status_code, 409)
        self.assertEqual(call.await_count, 0)
        # Новый request_id: резерв неизвестного вызова всё ещё держит лимит.
        self.client.put('/api/budgets/limits', json={'project_usd': quote['estimated_usd'] + 1e-9, 'daily_usd': 1})
        retry, call = self.chat(body, quote, 'money-unknown-2')
        self.assertEqual(retry.status_code, 400)
        self.assertIn('бюджет', retry.text.lower())
        self.assertEqual(call.await_count, 0)

    def test_provider_rejection_releases_the_reserve(self):
        self.prepare()
        body, quote = self.quote()
        response, _ = self.chat(body, quote, 'money-rejected-1', error=main.HTTPException(400, 'PiAPI отклонил запрос'))
        self.assertEqual(response.status_code, 400)
        row = self.call_row('money-rejected-1')
        self.assertEqual((row['status'], row['usd']), ('failed', 0))
        with main.connect() as db:
            self.assertEqual(llm_guard.spent(db, self.pid), (0.0, 0.0))

    def test_actual_cost_above_estimate_is_recorded_and_visible(self):
        self.prepare()
        body, quote = self.quote()
        heavy = {'choices': [{'message': {'role': 'assistant', 'content': 'Готово.'}}],
                 'usage': {'prompt_tokens': 120000, 'completion_tokens': 90000}}
        response, _ = self.chat(body, quote, 'money-heavy-1', reply=heavy)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertGreater(data['cost_usd'], data['estimated_usd'])
        self.assertTrue(data['over_estimate'])
        self.assertAlmostEqual(data['cost_usd'], 0.0132, places=6)
        row = self.call_row('money-heavy-1')
        self.assertEqual(row['status'], 'done')
        self.assertEqual(row['usd'], data['cost_usd'])
        self.assertGreater(row['usd'], row['estimated_usd'])

    def test_unreadable_answer_keeps_reserve_unless_provider_says_zero(self):
        self.prepare()
        body, quote = self.quote()
        response, _ = self.chat(body, quote, 'money-broken-1', reply={'code': 200, 'message': 'модель недоступна'})
        self.assertEqual(response.status_code, 502)
        row = self.call_row('money-broken-1')
        self.assertEqual(row['status'], 'submission_unknown')
        self.assertEqual(row['usd'], quote['estimated_usd'])
        # Провайдер явно сообщил нулевое потребление полным набором счётчиков: резерв освобождается.
        body2, quote2 = self.quote()
        response2, _ = self.chat(body2, quote2, 'money-zero-1', reply=EMPTY_BUT_PAID)
        self.assertEqual(response2.status_code, 502)
        row2 = self.call_row('money-zero-1')
        self.assertEqual((row2['status'], row2['usd']), ('failed', 0))
        # Одного total_tokens=0 недостаточно: обязательных счётчиков нет, нулевое
        # потребление не доказано — резерв удерживается до ручной сверки.
        body3, quote3 = self.quote()
        response3, _ = self.chat(body3, quote3, 'money-zero-unproven-1', reply=ZERO_UNPROVEN)
        self.assertEqual(response3.status_code, 502)
        row3 = self.call_row('money-zero-unproven-1')
        self.assertEqual(row3['status'], 'submission_unknown')
        self.assertEqual(row3['usd'], quote3['estimated_usd'])

    def test_reconcile_releases_or_confirms_unknown_call(self):
        self.prepare()
        body, quote = self.quote()
        self.chat(body, quote, 'money-recon-1', error=main.HTTPException(502, 'таймаут'))
        row = self.call_row('money-recon-1')
        body = {'outcome': 'failed', 'note': 'проверил у провайдера: списания нет'}
        # Без подтверждения — отказ.
        self.assertEqual(self.client.post(f'/api/llm/calls/{row["id"]}/reconcile', json=body).status_code, 400)
        confirmed = self.client.post(f'/api/llm/calls/{row["id"]}/reconcile', json={**body, 'approved': True})
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        after = self.call_row('money-recon-1')
        self.assertEqual((after['status'], after['usd']), ('failed', 0))
        self.assertIn('проверил', after['note'])
        # Повторная сверка — отказ: исход уже не неопределённый.
        self.assertEqual(self.client.post(f'/api/llm/calls/{row["id"]}/reconcile',
                                          json={'outcome': 'done', 'note': 'ещё раз', 'approved': True}).status_code, 409)

    def test_reconcile_can_confirm_the_real_charge(self):
        self.prepare()
        body, quote = self.quote()
        self.chat(body, quote, 'money-recon-2', error=main.HTTPException(502, 'таймаут'))
        row = self.call_row('money-recon-2')
        confirmed = self.client.post(f'/api/llm/calls/{row["id"]}/reconcile',
                                     json={'outcome': 'done', 'usd': 0.0042, 'note': 'нашёл в кабинете провайдера', 'approved': True})
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        after = self.call_row('money-recon-2')
        self.assertEqual((after['status'], after['usd']), ('done', 0.0042))

    def test_budget_report_shows_llm_inside_the_total(self):
        self.prepare()
        body, quote = self.quote()
        response, _ = self.chat(body, quote, 'money-report-1')
        self.assertEqual(response.status_code, 200, response.text)
        spent = response.json()['cost_usd']
        budget = self.client.get(f'/api/budgets/{self.pid}').json()
        self.assertAlmostEqual(budget['llm_reserved_usd'], spent, places=6)
        self.assertAlmostEqual(budget['project_reserved_usd'], spent, places=6)
        self.assertAlmostEqual(budget['llm_project_usd'], spent, places=6)
        self.assertEqual(budget['llm_unknown_calls'], 0)

    def test_unknown_call_is_visible_in_the_report(self):
        self.prepare()
        body, quote = self.quote()
        self.chat(body, quote, 'money-report-2', error=main.HTTPException(502, 'таймаут'))
        budget = self.client.get(f'/api/budgets/{self.pid}').json()
        self.assertEqual(budget['llm_unknown_calls'], 1)
        self.assertAlmostEqual(budget['llm_unknown_usd'], quote['estimated_usd'], places=6)
        self.assertAlmostEqual(budget['project_reserved_usd'], quote['estimated_usd'], places=6)
        calls = self.client.get('/api/llm/calls', params={'project_id': self.pid}).json()
        self.assertEqual(calls[0]['status'], 'submission_unknown')
        self.assertEqual(calls[0]['request_id'], 'money-report-2')


if __name__ == '__main__':
    unittest.main()
