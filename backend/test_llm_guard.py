import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from backend import llm_adapters, llm_gateway, llm_guard, main, test_production, test_smoke
from backend.llm_adapters import ProviderResult
from backend.llm_gateway import Usage

REPLY = {'choices': [{'message': {'role': 'assistant', 'content': 'Slow push-in, one continuous shot.'}}],
         'usage': {'prompt_tokens': 120, 'completion_tokens': 40}}

KIE = {'provider': 'kie', 'model': 'gpt-6-luna', 'role': 'simple', 'input': 0.03, 'output': 0.15, 'protocol': 'responses'}
MINIMAX = {'provider': 'minimax', 'model': 'MiniMax-M3.1-Flash', 'role': 'coding', 'input': 0.15, 'output': 0.6}
DEEPSEEK = {'provider': 'deepseek', 'model': 'deepseek-flash', 'role': 'backup', 'input': 0.02, 'output': 0.08}
OPENROUTER = {'provider': 'openrouter', 'model': 'minimax/minimax-m3.1-flash:free', 'role': 'coding',
              'input': 0, 'output': 0, 'free': True, 'opt_in': True}


def rate(provider, model, **over):
    item = {'provider': provider, 'model': model, 'model_id': model, 'role': 'extra',
            'input': None, 'output': None, 'cached_input_per_mtok': None,
            'source': 'https://example.test/' + model, 'as_of': '2026-10-20', 'protocol': 'openai_chat',
            'base_url': 'https://example.test',
            'capabilities': {'tools': False, 'streaming': False, 'reasoning': False},
            'max_input_tokens': None, 'rate_limit': None, 'upstream_version': None,
            'free': False, 'opt_in': False, 'promotion': False, 'quota_limited': False,
            'requires_dynamic_tier_check': False, 'enabled': True, 'verified_at': '2026-10-20'}
    item.update(over)
    return item


def registry_config(*rates):
    return {'schema_version': 1, 'as_of': '2026-10-20', 'currency': 'USD',
            'unit': 'USD per 1000000 input or output tokens', 'status': 'test', 'rates': list(rates),
            'comparison_display': {'card_primary': 'kie_piapi_reference_cost',
                                   'budget_primary': 'confirmed_actual_provider_cost',
                                   'reference_provider_allowlist': ['kie', 'piapi'],
                                   'match_priority': 'exact_model_then_named_other_model_baseline',
                                   'default_baseline': {'provider': 'kie', 'model': 'gpt-6-luna', 'kind': 'reference_model'},
                                   'alternative_baseline': {'provider': 'piapi', 'model': 'gpt-5.6-luna', 'kind': 'reference_model'},
                                   'explicit_different_model_label_required': True, 'show_reference_snapshot_date': True,
                                   'free_api_actual_cost_usd': 0, 'paid_approval_must_show_actual_estimate': True,
                                   'unknown_charge_is_not_zero': True, 'pending_and_unknown_reported_separately': True,
                                   'small_amount_precision': 6},
            'sample_limits_only': {'per_call_usd': 0.1, 'per_day_usd': 1, 'per_month_usd': 10,
                                   'do_not_override_existing_owner_limits': True}}


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

    def test_budget_reserved_before_call_and_failed_call_keeps_reserve(self):
        self.prepare()
        self.client.put('/api/budgets/limits', json={'project_usd': 0.00001, 'daily_usd': 0.00001})
        body, quote = self.estimate()
        with patch.object(main, 'request_piapi', AsyncMock(return_value=REPLY)) as call:
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote))
            self.assertEqual(r.status_code, 400)
            self.assertIn('бюджет', r.text.lower())
            self.assertEqual(call.await_count, 0)
        self.client.put('/api/budgets/limits', json={'project_usd': 1, 'daily_usd': 2})
        # 5xx от провайдера: списание возможно, исход неопределён — резерв ждёт сверки
        failing = AsyncMock(side_effect=main.HTTPException(502, 'PiAPI вернул HTTP 500. Проверь доступ и параметры'))
        with patch.object(main, 'request_piapi', failing):
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, request_id='llm-test-request-2'))
            self.assertEqual(r.status_code, 502)
        with main.connect() as db:
            row = db.execute("SELECT status,usd,actual_status,actual_cost_usd FROM llm_calls WHERE request_id='llm-test-request-2'").fetchone()
            self.assertEqual((row['status'], row['usd']), ('failed', 0))
            # отказ провайдера без подтверждения списания: сумма неизвестна, резерв ждёт сверки
            self.assertEqual(row['actual_status'], 'unknown')
            self.assertIsNone(row['actual_cost_usd'])
            self.assertEqual(llm_guard.spent(db, self.pid), (0.000061, 0.000061))

    def test_legacy_success_without_usage_writes_estimate_and_keeps_reserve(self):
        self.prepare()
        body, quote = self.estimate()
        without_usage = {'choices': [{'message': {'role': 'assistant', 'content': 'Ответ без расхода токенов'}}]}
        with patch.object(main, 'request_piapi', AsyncMock(return_value=without_usage)):
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote))
            self.assertEqual(r.status_code, 200, r.text)
            self.assertIsNone(r.json()['cost_usd'])
            self.assertEqual(r.json()['actual']['status'], 'unknown')
        with main.connect() as db:
            row = db.execute('SELECT status,usd,actual_status,actual_cost_usd,reserved_usd FROM llm_calls').fetchone()
            self.assertEqual(row['status'], 'done')
            # факт неизвестен: под done стоит оценка (тот же резерв), а не ноль
            self.assertEqual(row['usd'], quote['estimated_usd'])
            self.assertEqual(row['reserved_usd'], quote['estimated_usd'])
            self.assertIsNone(row['actual_cost_usd'])
            self.assertEqual(row['actual_status'], 'unknown')
            self.assertEqual(llm_guard.spent(db, self.pid), (quote['estimated_usd'], quote['estimated_usd']))

    def test_legacy_provider_error_body_releases_reserve(self):
        self.prepare()
        body, quote = self.estimate()
        # HTTP 200 с телом-ошибкой: провайдер прямо отказал, запрос не обработан.
        # Формулировка сообщения произвольна — решение принимает структурный признак исключения.
        refused = AsyncMock(side_effect=main.ProviderCallFailed(502, 'совершенно новая формулировка отказа', 'bad_body', False))
        with patch.object(main, 'request_piapi', refused):
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote))
            self.assertEqual(r.status_code, 502, r.text)
        with main.connect() as db:
            row = db.execute('SELECT status,usd,actual_status,actual_cost_usd,error_kind FROM llm_calls').fetchone()
            self.assertEqual(row['status'], 'failed')
            self.assertEqual(row['actual_status'], 'not_charged')
            self.assertEqual(row['actual_cost_usd'], 0.0)
            self.assertEqual(llm_guard.spent(db, self.pid), (0.0, 0.0))

    def test_legacy_failure_is_classified_by_structure_not_by_message(self):
        self.prepare()
        body, quote = self.estimate()
        ambiguous = AsyncMock(side_effect=main.ProviderCallFailed(503, 'другая формулировка 5xx', 'http_5xx', True))
        with patch.object(main, 'request_piapi', ambiguous):
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote))
            self.assertEqual(r.status_code, 503, r.text)
        with main.connect() as db:
            row = db.execute('SELECT status,actual_status,actual_cost_usd,error_kind FROM llm_calls').fetchone()
            self.assertEqual(row['status'], 'failed')
            self.assertEqual(row['actual_status'], 'unknown')
            self.assertIsNone(row['actual_cost_usd'])
            self.assertEqual(row['error_kind'], 'http_5xx')
            self.assertEqual(llm_guard.spent(db, self.pid), (quote['estimated_usd'], quote['estimated_usd']))

    def test_legacy_answer_without_text_and_without_usage_is_unknown_charge(self):
        self.prepare()
        body, quote = self.estimate()
        empty = {'choices': [{'message': {'role': 'assistant', 'content': ''}}]}
        with patch.object(main, 'request_piapi', AsyncMock(return_value=empty)):
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote))
            self.assertEqual(r.status_code, 502, r.text)
        with main.connect() as db:
            row = db.execute('SELECT status,usd,actual_status,actual_cost_usd,error_kind FROM llm_calls').fetchone()
            # провайдер ответил, но текста нет: вызов закрыт, факт неизвестен, резерв ждёт сверки
            self.assertEqual(row['status'], 'done')
            self.assertEqual(row['usd'], quote['estimated_usd'])
            self.assertIsNone(row['actual_cost_usd'])
            self.assertEqual(row['actual_status'], 'unknown')
            self.assertEqual(row['error_kind'], 'bad_body')
            self.assertEqual(llm_guard.spent(db, self.pid), (quote['estimated_usd'], quote['estimated_usd']))

    def test_legacy_answer_without_text_but_with_usage_is_confirmed_charge(self):
        self.prepare()
        body, quote = self.estimate()
        empty = {'choices': [{'message': {'role': 'assistant', 'content': ''}}],
                 'usage': {'prompt_tokens': 120, 'completion_tokens': 40}}
        with patch.object(main, 'request_piapi', AsyncMock(return_value=empty)):
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote))
            self.assertEqual(r.status_code, 502, r.text)
        with main.connect() as db:
            row = db.execute('SELECT status,usd,actual_status,actual_cost_usd,error_kind FROM llm_calls').fetchone()
            # провайдер ответил и тарифицировал: факт известен по usage, резерв освобождается
            self.assertEqual(row['status'], 'done')
            self.assertEqual(row['actual_status'], 'confirmed')
            self.assertEqual(row['actual_cost_usd'], 0.000007)
            self.assertEqual(row['usd'], 0.000007)
            self.assertEqual(row['error_kind'], 'bad_body')
            self.assertEqual(llm_guard.spent(db, self.pid), (0.000007, 0.000007))

    def test_confirmed_spend_and_exposure_are_different_numbers(self):
        self.prepare()
        body, quote = self.estimate()
        with patch.object(main, 'request_piapi', AsyncMock(return_value=REPLY)):
            ok = self.client.post('/api/llm/chat', json=self.chat_body(body, quote))
            self.assertEqual(ok.status_code, 200, ok.text)
        unknown = AsyncMock(side_effect=main.HTTPException(502, 'PiAPI вернул HTTP 500. Проверь доступ и параметры'))
        with patch.object(main, 'request_piapi', unknown):
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, request_id='llm-test-request-3'))
            self.assertEqual(r.status_code, 502, r.text)
        confirmed = ok.json()['cost_usd']
        with main.connect() as db:
            summary = llm_guard.summary(db, {self.pid})
            exposure = llm_guard.spent(db, self.pid)[0]
        self.assertGreater(confirmed, 0)
        self.assertEqual(summary['actual_usd'], confirmed)
        self.assertEqual(summary['usd'], exposure)
        self.assertGreater(summary['usd'], summary['actual_usd'])

    def test_other_paid_llm_routes_stay_closed(self):
        for endpoint in ('/api/chat', '/api/compose', '/api/agents/run'):
            self.assertEqual(self.client.post(endpoint, json={'approved': True}).status_code, 503)


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


class PiapiTransportTests(unittest.IsolatedAsyncioTestCase):
    """Транспорт PiAPI различает исходы структурно: признак «списания не было» едет на исключении,
    а не в тексте сообщения — смена формулировки исход не меняет."""

    async def call(self, response):
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response)) as client:
            with self.assertRaises(main.ProviderCallFailed) as ctx:
                await main.request_piapi('POST', '/v1/chat/completions', 'test-key',
                                         {'model': 'gpt-5.6-luna', 'messages': [{'role': 'user', 'content': 'x'}]},
                                         client=client)
        return ctx.exception

    async def test_error_body_in_200_means_not_charged(self):
        exc = await self.call(httpx.Response(200, json={'error': {'message': 'model is unavailable'}}))
        self.assertFalse(exc.charged_possible)
        self.assertEqual(exc.error_kind, 'bad_body')

    async def test_401_means_not_charged(self):
        exc = await self.call(httpx.Response(401, json={'error': {'message': 'invalid api key'}}))
        self.assertFalse(exc.charged_possible)
        self.assertEqual(exc.error_kind, 'http_401')

    async def test_5xx_means_charge_is_possible(self):
        exc = await self.call(httpx.Response(503, text='upstream unavailable'))
        self.assertTrue(exc.charged_possible)
        self.assertEqual(exc.error_kind, 'http_5xx')

    async def test_cloudflare_1010_means_charge_is_possible(self):
        exc = await self.call(httpx.Response(403, text='browser_signature_banned Error 1010'))
        self.assertTrue(exc.charged_possible)
        self.assertEqual(exc.error_kind, 'cloudflare_1010')


class LlmJournalTests(unittest.TestCase):
    """Журнал вызовов: исполнение, тарифный ориентир и токены хранятся раздельно;
    исход вызова различается по правилу денег (неизвестное списание не равно нулю)."""

    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def prepare(self):
        self.pid = self.client.post('/api/projects', json={'title': 'LLM', 'state': {}}).json()['id']
        self.messages = [{'role': 'system', 'content': 'Перепиши в промпт'}, {'role': 'user', 'content': 'Грэм подмигивает'}]

    def registry(self, *rates):
        tmp = tempfile.mkdtemp(prefix='llm-guard-registry-')
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        path = Path(tmp) / 'llm_gateway.prices.json'
        path.write_text(json.dumps(registry_config(*rates)), encoding='utf-8')
        return llm_gateway.load_registry(str(path))

    def estimate(self, model, **extra):
        body = {'project_id': self.pid, 'model': model, 'messages': self.messages, 'max_tokens': 500, **extra}
        r = self.client.post('/api/llm/estimate', json=body)
        self.assertEqual(r.status_code, 200, r.text)
        return body, r.json()

    def chat_body(self, body, quote, request_id, **extra):
        return {'provider': 'piapi', 'project_id': self.pid, 'model': body['model'], 'messages': self.messages,
                'max_tokens': body['max_tokens'], 'approved': True, 'quote_token': quote['quote_token'],
                'max_cost_usd': quote['estimated_usd'], 'request_id': request_id, **extra}

    def rows(self):
        with main.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM llm_calls ORDER BY created_at, id').fetchall()]

    def spent(self):
        with main.connect() as db:
            return llm_guard.spent(db, self.pid)

    def test_migration_adds_columns_and_keeps_old_rows(self):
        tmp = tempfile.mkdtemp(prefix='llm-guard-migration-')
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        db = sqlite3.connect(Path(tmp) / 'old.sqlite3')
        self.addCleanup(db.close)
        db.row_factory = sqlite3.Row
        db.execute('CREATE TABLE llm_calls(id TEXT PRIMARY KEY,request_id TEXT UNIQUE,project_id TEXT NOT NULL,'
                   'model TEXT NOT NULL,status TEXT NOT NULL,usd REAL NOT NULL,estimated_usd REAL NOT NULL,'
                   'input_tokens INTEGER,output_tokens INTEGER,created_at TEXT NOT NULL)')
        db.execute('INSERT INTO llm_calls VALUES(?,?,?,?,?,?,?,?,?,?)',
                   ('id-1', 'req-1', 'p-1', 'gpt-5.6-luna', 'done', 0.000007, 0.000061, 120, 40, '2026-10-20T10:00:00+00:00'))
        db.commit()
        llm_guard.ensure_schema(db)
        columns = {row['name'] for row in db.execute('PRAGMA table_info(llm_calls)')}
        for name, _kind in llm_guard.CALL_COLUMNS:
            self.assertIn(name, columns)
        old = db.execute('SELECT * FROM llm_calls WHERE id=?', ('id-1',)).fetchone()
        self.assertEqual((old['status'], old['usd'], old['input_tokens'], old['output_tokens']),
                         ('done', 0.000007, 120, 40))
        self.assertIsNone(old['actual_status'])

    def test_journal_keeps_execution_reference_and_tokens_apart(self):
        self.prepare()
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        result = ProviderResult(ok=True, text='Ответ студии', usage=Usage(1000, 200), error_kind=None,
                                charged_possible=False, provider_request_id='req-4711')
        with patch.object(llm_guard, 'current_registry', return_value=registry), \
                patch.object(llm_adapters, 'complete', AsyncMock(return_value=result)) as call:
            body, quote = self.estimate('MiniMax-M3.1-Flash')
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, 'journal-1'))
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(call.await_count, 1)
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row['execution_provider'], row['execution_model']), ('minimax', 'MiniMax-M3.1-Flash'))
        self.assertEqual(row['actual_status'], 'confirmed')
        self.assertEqual(row['actual_cost_usd'], 0.00027)      # 1000*0.15 + 200*0.6 за млн по тарифу MiniMax
        self.assertEqual(row['reserved_usd'], 0.000309)        # резерв по тарифу маршрута, не по ориентиру
        self.assertEqual(row['billing_source'], 'provider_usage')
        self.assertEqual((row['reference_provider'], row['reference_model']), ('kie', 'gpt-6-luna'))
        self.assertEqual(row['reference_kind'], 'reference_model')
        self.assertEqual(row['reference_cost_usd'], 0.00006)    # 1000*0.03 + 200*0.15 по тарифу Kie
        self.assertEqual(row['reference_cost_status'], 'confirmed')
        self.assertEqual((row['input_tokens'], row['output_tokens']), (1000, 200))
        self.assertEqual((row['status'], row['usd']), ('done', 0.00027))
        self.assertEqual(row['route_mode'], 'manual')

    def test_unknown_outcome_keeps_reserve_and_writes_no_amount(self):
        self.prepare()
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        result = ProviderResult(ok=False, text='', usage=Usage(None, None, estimated=True), error_kind='http_5xx',
                                charged_possible=True, provider_request_id=None)
        with patch.object(llm_guard, 'current_registry', return_value=registry), \
                patch.object(llm_adapters, 'complete', AsyncMock(return_value=result)):
            body, quote = self.estimate('MiniMax-M3.1-Flash')
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, 'journal-unknown'))
            self.assertEqual(r.status_code, 502, r.text)
        row = self.rows()[0]
        self.assertEqual(row['actual_status'], 'unknown')
        self.assertIsNone(row['actual_cost_usd'])
        self.assertEqual(row['error_kind'], 'http_5xx')
        self.assertEqual(row['reserved_usd'], 0.000309)
        self.assertEqual(self.spent(), (0.000309, 0.000309))

    def test_provider_refusal_releases_reserve(self):
        self.prepare()
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        result = ProviderResult(ok=False, text='', usage=Usage(None, None, estimated=True), error_kind='http_401',
                                charged_possible=False, provider_request_id=None)
        with patch.object(llm_guard, 'current_registry', return_value=registry), \
                patch.object(llm_adapters, 'complete', AsyncMock(return_value=result)):
            body, quote = self.estimate('MiniMax-M3.1-Flash')
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, 'journal-refused'))
            self.assertEqual(r.status_code, 502, r.text)
        row = self.rows()[0]
        self.assertEqual(row['actual_status'], 'not_charged')
        self.assertEqual(row['actual_cost_usd'], 0.0)
        self.assertEqual(row['error_kind'], 'http_401')
        self.assertEqual(self.spent(), (0.0, 0.0))

    def test_route_refused_before_network_is_not_charged(self):
        self.prepare()
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        refused = AsyncMock(side_effect=main.HTTPException(400, 'Маршрут выключен владельцем: minimax/MiniMax-M3.1-Flash'))
        with patch.object(llm_guard, 'current_registry', return_value=registry), \
                patch.object(llm_adapters, 'complete', refused):
            body, quote = self.estimate('MiniMax-M3.1-Flash')
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, 'journal-gate'))
            self.assertEqual(r.status_code, 400, r.text)
        row = self.rows()[0]
        self.assertEqual(row['actual_status'], 'not_charged')
        self.assertEqual(row['actual_cost_usd'], 0.0)
        self.assertEqual(row['error_kind'], 'route_rejected')
        self.assertEqual(self.spent(), (0.0, 0.0))

    def test_free_route_is_journaled_with_zero_actual_and_nonzero_reference(self):
        self.prepare()
        registry = self.registry(rate(**KIE), rate(**MINIMAX), rate(**OPENROUTER))
        result = ProviderResult(ok=True, text='Бесплатный ответ', usage=Usage(1000, 200), error_kind=None,
                                charged_possible=False, provider_request_id='req-free')
        with patch.object(llm_guard, 'current_registry', return_value=registry), \
                patch.object(llm_adapters, 'complete', AsyncMock(return_value=result)):
            body, quote = self.estimate('minimax/minimax-m3.1-flash:free', allow_free=True)
            self.assertEqual(quote['estimated_usd'], 0)
            self.assertGreater(quote['reference']['cost_usd'], 0)
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, 'journal-free', allow_free=True))
            self.assertEqual(r.status_code, 200, r.text)
        row = self.rows()[0]
        self.assertEqual(row['execution_provider'], 'openrouter')
        self.assertEqual(row['actual_status'], 'free')
        self.assertEqual(row['actual_cost_usd'], 0.0)
        self.assertEqual(row['reserved_usd'], 0.0)
        self.assertGreater(row['reference_cost_usd'], 0)
        self.assertEqual(self.spent(), (0.0, 0.0))

    def test_fallback_chain_makes_at_most_one_paid_attempt(self):
        self.prepare()
        registry = self.registry(rate(**KIE), rate(**MINIMAX), rate(**DEEPSEEK), rate(**OPENROUTER))
        free_result = ProviderResult(ok=False, text='', usage=Usage(None, None, estimated=True), error_kind='http_401',
                                     charged_possible=False, provider_request_id=None)
        paid_result = ProviderResult(ok=True, text='Платный ответ', usage=Usage(1000, 200), error_kind=None,
                                     charged_possible=False, provider_request_id='req-paid')
        with patch.object(llm_guard, 'current_registry', return_value=registry), \
                patch.object(llm_adapters, 'complete', AsyncMock(side_effect=[free_result, paid_result])) as call:
            body, quote = self.estimate('minimax/minimax-m3.1-flash:free', route_mode='auto', task='coding', allow_free=True)
            self.assertEqual(quote['estimated_usd'], 0.000309)
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, 'journal-chain',
                                                                      route_mode='auto', task='coding', allow_free=True))
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(call.await_count, 2)
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        free_row, paid_row = rows
        self.assertEqual((free_row['execution_provider'], free_row['actual_status']), ('openrouter', 'not_charged'))
        self.assertEqual(free_row['reserved_usd'], 0.0)
        self.assertEqual((paid_row['execution_provider'], paid_row['actual_status']), ('minimax', 'confirmed'))
        self.assertEqual(paid_row['fallback_from'], 'openrouter/minimax/minimax-m3.1-flash:free')
        self.assertEqual(paid_row['actual_cost_usd'], 0.00027)
        self.assertEqual(self.spent(), (0.00027, 0.00027))

    def test_paid_opt_in_route_takes_the_only_paid_slot(self):
        registry = self.registry(rate(**KIE),
                                 rate('kie', 'gpt-6-luna-optin', role='coding', input=0.03, output=0.15, opt_in=True),
                                 rate(**MINIMAX), rate(**DEEPSEEK))
        # платный маршрут по оптину — платный: он занимает единственное платное место цепочки,
        # а не встаёт перед ним вторым платным маршрутом (две платные попытки на один запрос)
        chain = llm_guard.plan_chain(registry, 'coding', allow_free=True)
        self.assertEqual([(r.provider, r.model) for r in chain], [('kie', 'gpt-6-luna-optin')])
        self.assertLessEqual(len([r for r in chain if not r.free]), 1)
        # без разрешения владельца маршрут по оптину в цепочку не попадает
        chain_without = llm_guard.plan_chain(registry, 'coding', allow_free=False)
        self.assertEqual([(r.provider, r.model) for r in chain_without], [('minimax', 'MiniMax-M3.1-Flash')])

    def test_zero_tariff_route_without_free_flag_is_free_not_confirmed_zero(self):
        self.prepare()
        # тариф 0/0 без флага free: маршрут бесплатный, поэтому подтверждённого нуля у него быть не может
        registry = self.registry(rate(**KIE), rate(**MINIMAX),
                                 rate('openrouter', 'minimax/minimax-m3.1-flash:free', role='coding',
                                      input=0, output=0, free=False, opt_in=False))
        result = ProviderResult(ok=True, text='Бесплатный ответ', usage=Usage(1000, 200), error_kind=None,
                                charged_possible=False, provider_request_id='req-zero')
        with patch.object(llm_guard, 'current_registry', return_value=registry), \
                patch.object(llm_adapters, 'complete', AsyncMock(return_value=result)):
            body, quote = self.estimate('minimax/minimax-m3.1-flash:free')
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, 'journal-zero'))
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.json()['execution']['status'], 'free')
        row = self.rows()[0]
        self.assertEqual(row['actual_status'], 'free')
        self.assertEqual(row['actual_cost_usd'], 0.0)
        self.assertEqual(self.spent(), (0.0, 0.0))

    def test_adapter_path_keeps_usage_when_the_answer_is_unusable(self):
        self.prepare()
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        answered = {'choices': [{'message': {'role': 'assistant', 'content': ''}}],
                    'usage': {'prompt_tokens': 1000, 'completion_tokens': 200}}
        real_complete = llm_adapters.complete

        async def fake_complete(route, messages, max_tokens, **kwargs):
            transport = httpx.MockTransport(lambda request: httpx.Response(200, json=answered))
            async with httpx.AsyncClient(transport=transport) as client:
                return await real_complete(route, messages, max_tokens, client=client, **kwargs)

        with patch.object(llm_guard, 'current_registry', return_value=registry), \
                patch.object(llm_adapters.connections, 'provider_key', return_value='test-key'), \
                patch.object(llm_adapters, 'complete', fake_complete):
            body, quote = self.estimate('MiniMax-M3.1-Flash')
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, 'journal-adapter'))
            self.assertEqual(r.status_code, 502, r.text)
        row = self.rows()[0]
        # провайдер ответил и тарифицировал: факт известен по usage, а не «списание неизвестно»
        self.assertEqual(row['actual_status'], 'confirmed')
        self.assertEqual(row['actual_cost_usd'], 0.00027)
        self.assertEqual(row['input_tokens'], 1000)
        self.assertEqual(row['output_tokens'], 200)
        self.assertEqual(self.spent(), (0.00027, 0.00027))

    def test_chain_stops_when_limit_does_not_cover_paid_route(self):
        self.prepare()
        self.client.put('/api/budgets/limits', json={'project_usd': 0.00001, 'daily_usd': 0.00001})
        registry = self.registry(rate(**KIE), rate(**MINIMAX), rate(**DEEPSEEK), rate(**OPENROUTER))
        free_result = ProviderResult(ok=False, text='', usage=Usage(None, None, estimated=True), error_kind='http_401',
                                     charged_possible=False, provider_request_id=None)
        with patch.object(llm_guard, 'current_registry', return_value=registry), \
                patch.object(llm_adapters, 'complete', AsyncMock(side_effect=[free_result])) as call:
            body, quote = self.estimate('minimax/minimax-m3.1-flash:free', route_mode='auto', task='coding', allow_free=True)
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, 'journal-limit',
                                                                      route_mode='auto', task='coding', allow_free=True))
            self.assertEqual(r.status_code, 400, r.text)
            self.assertIn('бюджет', r.text.lower())
            self.assertEqual(call.await_count, 1)
        rows = self.rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['execution_provider'], 'openrouter')

    def test_repeat_request_id_does_not_charge_again(self):
        self.prepare()
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        result = ProviderResult(ok=True, text='Ответ студии', usage=Usage(1000, 200), error_kind=None,
                                charged_possible=False, provider_request_id='req-1')
        with patch.object(llm_guard, 'current_registry', return_value=registry), \
                patch.object(llm_adapters, 'complete', AsyncMock(return_value=result)) as call:
            body, quote = self.estimate('MiniMax-M3.1-Flash')
            first = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, 'journal-repeat'))
            self.assertEqual(first.status_code, 200, first.text)
            again = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, 'journal-repeat'))
            self.assertEqual(again.status_code, 409)
            self.assertEqual(call.await_count, 1)
        self.assertEqual(len(self.rows()), 1)
        self.assertEqual(self.spent(), (0.00027, 0.00027))

    def test_estimate_and_chat_responses_keep_old_fields_and_add_card(self):
        self.prepare()
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        result = ProviderResult(ok=True, text='Ответ студии', usage=Usage(1000, 200), error_kind=None,
                                charged_possible=False, provider_request_id='req-1')
        with patch.object(llm_guard, 'current_registry', return_value=registry), \
                patch.object(llm_adapters, 'complete', AsyncMock(return_value=result)):
            body, quote = self.estimate('MiniMax-M3.1-Flash')
            for field in ('estimated_usd', 'quote_token', 'max_tokens', 'model'):
                self.assertIn(field, quote)
            self.assertEqual(quote['max_tokens'], 500)
            self.assertEqual(quote['execution'], {'provider': 'minimax', 'model': 'MiniMax-M3.1-Flash', 'status': 'paid'})
            self.assertEqual(quote['reference']['provider'], 'kie')
            self.assertEqual(quote['reference']['kind'], 'reference_model')
            self.assertEqual(quote['actual'], {'cost_usd': None, 'status': 'estimated', 'max_cost_usd': 0.000309})
            r = self.client.post('/api/llm/chat', json=self.chat_body(body, quote, 'journal-card'))
            self.assertEqual(r.status_code, 200, r.text)
            answer = r.json()
        for field in ('choices', 'usage', 'provider', 'model', 'cost_usd', 'estimated_usd'):
            self.assertIn(field, answer)
        self.assertEqual(answer['provider'], 'minimax')
        self.assertEqual(answer['cost_usd'], 0.00027)
        self.assertEqual(answer['estimated_usd'], 0.000309)
        self.assertEqual(answer['actual'], {'cost_usd': 0.00027, 'status': 'confirmed', 'max_cost_usd': 0.000309})
        self.assertEqual(answer['reference']['cost_usd'], 0.00006)
        self.assertEqual(answer['execution'], {'provider': 'minimax', 'model': 'MiniMax-M3.1-Flash', 'status': 'paid'})


if __name__ == '__main__':
    unittest.main()
