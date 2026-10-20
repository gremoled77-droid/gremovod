"""Бюджет LLM: четыре раздельных итога, резерв и неизвестные списания, учёт вызовов агента.

Проверки идут через публичный интерфейс студии: /api/economics, /api/productions/.../economics,
/api/budgets/limits и журнал вызовов llm_calls.
"""
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backend import llm_adapters, llm_gateway, llm_guard, main, native_chat, test_production, test_smoke
from backend.llm_adapters import ProviderResult
from backend.llm_gateway import Usage
from backend.test_llm_gateway import config, rate

KIE = {'provider': 'kie', 'model': 'gpt-6-luna', 'role': 'simple', 'input': 0.03, 'output': 0.15,
       'protocol': 'responses'}
MINIMAX = {'provider': 'minimax', 'model': 'MiniMax-M3.1-Flash', 'role': 'coding', 'input': 0.15, 'output': 0.6}
DEEPSEEK = {'provider': 'deepseek', 'model': 'deepseek-flash', 'role': 'backup', 'input': 0.02, 'output': 0.08}
OPENROUTER = {'provider': 'openrouter', 'model': 'minimax/minimax-m3.1-flash:free', 'role': 'coding',
              'input': 0, 'output': 0, 'free': True, 'opt_in': True}

PAID = ProviderResult(ok=True, text='Ответ студии', usage=Usage(1000, 200), error_kind=None,
                      charged_possible=False, provider_request_id='req-paid')
FREE = ProviderResult(ok=True, text='Бесплатный ответ', usage=Usage(1000, 200), error_kind=None,
                       charged_possible=False, provider_request_id='req-free')
UNKNOWN = ProviderResult(ok=False, text='', usage=Usage(None, None, estimated=True), error_kind='http_5xx',
                         charged_possible=True, provider_request_id=None)
REFUSED = ProviderResult(ok=False, text='', usage=Usage(None, None, estimated=True), error_kind='http_401',
                         charged_possible=False, provider_request_id=None)


class GatewayCase(unittest.TestCase):
    """Общий каркас: временная база студии и реестр с известными тарифами."""

    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def registry(self, *rates, **kwargs):
        payload = config(*rates)
        if 'sample_limits' in kwargs:
            payload['sample_limits_only'] = kwargs['sample_limits']
        tmp = tempfile.mkdtemp(prefix='llm-budget-registry-')
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        path = Path(tmp) / 'llm_gateway.prices.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        return llm_gateway.load_registry(str(path))

    def project(self, title='Бюджет'):
        return self.client.post('/api/projects', json={'title': title, 'state': {}}).json()['id']

    def estimate(self, registry, project_id, **extra):
        body = {'project_id': project_id, 'model': 'MiniMax-M3.1-Flash',
                'messages': [{'role': 'user', 'content': 'Грэм подмигивает'}], 'max_tokens': 500, **extra}
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            return self.client.post('/api/llm/estimate', json=body).json()

    def chat(self, registry, result, project_id, request_id, provider='minimax', **extra):
        """Платный вызов через шлюз: оценка, подпись и сам вызов — по одному реестру."""
        body = {'project_id': project_id, 'model': 'MiniMax-M3.1-Flash',
                'messages': [{'role': 'user', 'content': 'Грэм подмигивает'}], 'max_tokens': 500, **extra}
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            quote = self.client.post('/api/llm/estimate', json=body).json()
            payload = {'provider': provider, 'project_id': project_id, 'model': body['model'],
                       'messages': body['messages'], 'max_tokens': 500, 'approved': True,
                       'quote_token': quote['quote_token'], 'max_cost_usd': quote['estimated_usd'],
                       'request_id': request_id, **extra}
            with patch.object(llm_adapters, 'complete', AsyncMock(return_value=result)):
                return self.client.post('/api/llm/chat', json=payload)

    def llm_block(self, project_id):
        return self.client.get('/api/economics', params={'project_id': project_id}).json()['llm']

    def rows(self, project_id):
        with main.connect() as db:
            return [dict(row) for row in db.execute(
                'SELECT * FROM llm_calls WHERE project_id=? ORDER BY created_at, id', (project_id,)).fetchall()]


class FourAmountsTests(GatewayCase):
    """Четыре итога раздельными величинами; «Фактически потрачено» — только подтверждённый факт."""

    def test_budget_shows_four_separate_amounts(self):
        pid = self.project()
        registry = self.registry(rate(**MINIMAX), rate(**KIE))
        ok = self.chat(registry, PAID, pid, 'budget-four-amounts-1')
        self.assertEqual(ok.status_code, 200, ok.text)
        llm = self.llm_block(pid)
        # подтверждённое списание: 1000*0.15 + 200*0.6 за млн по тарифу MiniMax
        self.assertEqual(llm['actual_cost_usd'], 0.00027)
        self.assertEqual(llm['reserved_usd'], 0)
        self.assertEqual(llm['unknown_cost_usd'], 0)
        # ориентир по Kie: 1000*0.03 + 200*0.15 за млн — деньгами не является
        self.assertEqual(llm['reference_cost_usd'], 0.00006)
        self.assertEqual(llm['calls'], 1)
        # старые поля ответа остаются
        for field in ('usd', 'actual_usd', 'estimated_usd', 'today_usd', 'by_model'):
            self.assertIn(field, llm)
        self.assertEqual(llm['by_model']['MiniMax-M3.1-Flash']['calls'], 1)

    def test_free_call_is_zero_actual_with_nonzero_reference(self):
        pid = self.project()
        registry = self.registry(rate(**MINIMAX), rate(**KIE), rate(**OPENROUTER))
        ok = self.chat(registry, FREE, pid, 'budget-free-call-1', provider='openrouter',
                       model='minimax/minimax-m3.1-flash:free', allow_free=True)
        self.assertEqual(ok.status_code, 200, ok.text)
        llm = self.llm_block(pid)
        self.assertEqual(llm['actual_cost_usd'], 0)
        self.assertEqual(llm['reserved_usd'], 0)
        self.assertEqual(llm['unknown_cost_usd'], 0)
        self.assertGreater(llm['reference_cost_usd'], 0)
        self.assertEqual(llm['calls'], 1)

    def test_failed_charge_is_unknown_not_zero(self):
        pid = self.project()
        registry = self.registry(rate(**MINIMAX), rate(**KIE))
        failed = self.chat(registry, UNKNOWN, pid, 'budget-unknown-charge-1')
        self.assertEqual(failed.status_code, 502)
        llm = self.llm_block(pid)
        # подтверждённого списания нет — факта нет
        self.assertEqual(llm['actual_cost_usd'], 0)
        # списание возможно: сумма удерживается до сверки и видна отдельным итогом
        self.assertGreater(llm['unknown_cost_usd'], 0)
        self.assertEqual(llm['reserved_usd'], 0)
        # экспозиция (её проверяет лимит) равна неизвестному списанию
        self.assertEqual(llm['usd'], llm['unknown_cost_usd'])

    def test_reserve_in_flight_is_not_mixed_with_unknown_charge(self):
        pid = self.project()
        registry = self.registry(rate(**MINIMAX), rate(**KIE))
        # вызов в полёте: резерв занят, списания ещё нет
        with main.connect() as db:
            llm_guard.ensure_schema(db)
            db.execute('INSERT INTO llm_calls(id,request_id,project_id,model,status,usd,estimated_usd,created_at,'
                       'execution_provider,execution_model,actual_cost_usd,actual_status,reserved_usd,billing_source)'
                       ' VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       ('row-in-flight', 'budget-in-flight-1', pid, 'MiniMax-M3.1-Flash', 'reserved', 0.0005,
                        0.0005, main.now(), 'minimax', 'MiniMax-M3.1-Flash', None, 'estimated', 0.0005,
                        'route_tariff'))
        llm = self.llm_block(pid)
        # резерв в полёте — зарезервировано, а не неизвестное списание: одна сумма в одном итоге
        self.assertEqual(llm['reserved_usd'], 0.0005)
        self.assertEqual(llm['unknown_cost_usd'], 0)
        self.assertEqual(llm['actual_cost_usd'], 0)

    def test_paid_fallback_after_free_charges_only_paid_provider(self):
        pid = self.project()
        registry = self.registry(rate(**MINIMAX), rate(**KIE), rate(**DEEPSEEK), rate(**OPENROUTER))
        body = {'project_id': pid, 'model': 'minimax/minimax-m3.1-flash:free',
                'messages': [{'role': 'user', 'content': 'Грэм подмигивает'}], 'max_tokens': 500,
                'route_mode': 'auto', 'task': 'coding', 'allow_free': True}
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            quote = self.client.post('/api/llm/estimate', json=body).json()
            payload = {'provider': 'openrouter', 'project_id': pid, 'model': body['model'],
                       'messages': body['messages'], 'max_tokens': 500, 'approved': True,
                       'quote_token': quote['quote_token'], 'max_cost_usd': quote['estimated_usd'],
                       'request_id': 'budget-fallback-1', 'route_mode': 'auto', 'task': 'coding',
                       'allow_free': True}
            with patch.object(llm_adapters, 'complete', AsyncMock(side_effect=[REFUSED, PAID])):
                ok = self.client.post('/api/llm/chat', json=payload)
        self.assertEqual(ok.status_code, 200, ok.text)
        llm = self.llm_block(pid)
        # платёж только платного провайдера, без удвоения
        self.assertEqual(llm['actual_cost_usd'], 0.00027)
        self.assertEqual(llm['unknown_cost_usd'], 0)
        self.assertEqual(llm['calls'], 2)

    def test_sample_limits_do_not_replace_owner_limits(self):
        pid = self.project()
        registry = self.registry(rate(**MINIMAX), rate(**KIE),
                                 sample_limits={'per_call_usd': 0.00001, 'per_day_usd': 0.00002,
                                                'per_month_usd': 0.00003, 'do_not_override_existing_owner_limits': True})
        # лимит владельца выше примерных значений конфигурации: вызов проходит
        self.client.put('/api/budgets/limits', json={'project_usd': 1, 'daily_usd': 2})
        ok = self.chat(registry, PAID, pid, 'budget-owner-limit-1')
        self.assertEqual(ok.status_code, 200, ok.text)
        # лимит владельца ниже: блокирует он, а не пример из конфигурации
        self.client.put('/api/budgets/limits', json={'project_usd': 0.0001, 'daily_usd': 0.0001})
        blocked = self.chat(registry, PAID, pid, 'budget-owner-limit-2')
        self.assertEqual(blocked.status_code, 400)
        self.assertIn('бюджет', blocked.text.lower())
        llm = self.llm_block(pid)
        self.assertEqual(llm['actual_cost_usd'], 0.00027)
        self.assertEqual(llm['calls'], 1)

    def test_not_charged_call_is_in_no_total(self):
        pid = self.project()
        registry = self.registry(rate(**MINIMAX), rate(**KIE))
        # платный маршрут отказал до списания: резерв снимается, списания не было
        refused = self.chat(registry, REFUSED, pid, 'budget-not-charged-1')
        self.assertEqual(refused.status_code, 502)
        rows = self.rows(pid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['actual_status'], 'not_charged')
        self.assertGreater(rows[0]['reserved_usd'], 0)  # резерв в полёте был
        llm = self.llm_block(pid)
        # снятый резерв не попадает ни в зарезервировано, ни в неизвестные списания
        self.assertEqual(llm['reserved_usd'], 0)
        self.assertEqual(llm['unknown_cost_usd'], 0)
        self.assertEqual(llm['actual_cost_usd'], 0)

    def test_unknown_charge_holds_project_limit(self):
        pid = self.project()
        registry = self.registry(rate(**MINIMAX), rate(**KIE))
        # лимит владельца выше оценки одного вызова, но не двух
        self.client.put('/api/budgets/limits', json={'project_usd': 0.0005, 'daily_usd': 0.0005})
        failed = self.chat(registry, UNKNOWN, pid, 'budget-limit-unknown-1')
        self.assertEqual(failed.status_code, 502)
        # резерв удерживается до сверки и занимает лимит проекта
        blocked = self.chat(registry, PAID, pid, 'budget-limit-unknown-2')
        self.assertEqual(blocked.status_code, 400)
        self.assertIn('бюджет', blocked.text.lower())
        llm = self.llm_block(pid)
        self.assertGreater(llm['unknown_cost_usd'], 0)
        self.assertEqual(llm['actual_cost_usd'], 0)


class SeriesBudgetTests(GatewayCase):
    """Лимит серии считает и удерживаемый резерв, и неизвестные списания."""

    setUp = test_production.ProductionTests.setUp
    tearDown = test_production.ProductionTests.tearDown
    setup_production = test_production.ProductionTests.setup_production
    new = test_production.ProductionTests.new

    def test_series_limit_counts_unknown_charge(self):
        self.setup_production()
        series = self.new('series', 'Серия')
        scene = self.new('episode', 'Встреча', series['id'])
        frame = self.new('frame', 'Крупный план', scene['id'])
        frame_project = self.client.post(f'/api/productions/{self.pid}/nodes/{frame["id"]}/open-project').json()['project_id']
        registry = self.registry(rate(**MINIMAX), rate(**KIE))
        failed = self.chat(registry, UNKNOWN, frame_project, 'series-unknown-charge-1')
        self.assertEqual(failed.status_code, 502)
        report = self.client.get(f'/api/productions/{self.pid}/series/{series["id"]}/economics').json()
        self.assertGreater(report['llm']['unknown_cost_usd'], 0)
        self.assertEqual(report['llm']['actual_cost_usd'], 0)
        self.assertEqual(report['llm']['calls'], 1)
        # лимит серии меньше удерживаемого резерва: следующий вызов не проходит
        self.client.put(f'/api/productions/{self.pid}/series/{series["id"]}/budget', json={'limit_usd': 0.000001})
        blocked = self.chat(registry, PAID, frame_project, 'series-unknown-charge-2')
        self.assertEqual(blocked.status_code, 400)
        self.assertIn('серии', blocked.text)


class AgentCallTests(GatewayCase):
    """Работа, порученная агенту, видна в бюджете наравне с вызовами через шлюз."""

    def worker_headers(self):
        return test_smoke.StudioSmokeTests.worker_headers(self)

    def agent_project(self):
        return self.client.post('/api/projects', json={'title': 'Агент', 'state': {'brief': 'A quiet empty courtyard',
                                                                                     'scene': {'brief': 'An empty courtyard at dusk',
                                                                                               'assets': []}}}).json()['id']

    def agent_body(self, project_id, request_id):
        return {'project_id': project_id, 'target': 'gpt-image-2.5', 'request_id': request_id, 'use_scene': True}

    def agent_job(self, request_id, operation='generate'):
        pid = self.agent_project()
        body = self.agent_body(pid, request_id)
        body['operation'] = operation
        created = self.client.post('/api/chatgpt/jobs', json=body)
        self.assertEqual(created.status_code, 200, created.text)
        claim = self.client.post('/api/chatgpt/worker/claim', headers=self.worker_headers()).json()
        self.assertIsNotNone(claim.get('job'))
        return pid, claim['job']['id']

    def worker_has_no_job(self):
        claim = self.client.post('/api/chatgpt/worker/claim', headers=self.worker_headers()).json()
        self.assertIsNone(claim.get('job'))

    def test_agent_job_is_refused_without_a_tariff(self):
        pid = self.agent_project()
        # в реестре нет тарифа ни у модели агента, ни у базовой линии: цену работы посчитать нечем
        registry = self.registry()
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            created = self.client.post('/api/chatgpt/jobs', json=self.agent_body(pid, 'agent-no-tariff-0001'))
        self.assertEqual(created.status_code, 400)
        self.assertIn('тариф', created.text.lower())
        # работа не уходит воркеру
        self.worker_has_no_job()
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM native_chat_jobs WHERE id=?',
                                        ('agent-no-tariff-0001',)).fetchone()[0], 0)

    def test_agent_job_is_refused_when_the_registry_has_only_a_zero_tariff(self):
        pid = self.agent_project()
        # в реестре только подтверждённо бесплатный маршрут 0/0: держать резерв под
        # неподтверждённое списание нечем, поэтому работа агента не ставится (fail-closed)
        priceless = {'provider': 'kie', 'model': 'gpt-6-luna', 'role': 'simple', 'input': None, 'output': None}
        registry = self.registry(rate(**priceless), rate(**OPENROUTER))
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            created = self.client.post('/api/chatgpt/jobs', json=self.agent_body(pid, 'agent-zero-only-0001'))
        self.assertEqual(created.status_code, 400)
        self.assertIn('тариф', created.text.lower())
        # работа не уходит воркеру и в журнале не остаётся
        self.worker_has_no_job()
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM native_chat_jobs WHERE id=?',
                                        ('agent-zero-only-0001',)).fetchone()[0], 0)

    def test_agent_reserve_falls_back_to_a_paid_route_and_holds_the_unknown_charge(self):
        pid = self.agent_project()
        # базовая линия без цены, в реестре бесплатный 0/0 и платный маршрут:
        # резерв держит платный маршрут, а не нулевой тариф
        priceless = {'provider': 'kie', 'model': 'gpt-6-luna', 'role': 'simple', 'input': None, 'output': None}
        registry = self.registry(rate(**priceless), rate(**OPENROUTER), rate(**MINIMAX))
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            created = self.client.post('/api/chatgpt/jobs', json=self.agent_body(pid, 'agent-paid-fallback-0001'))
        self.assertEqual(created.status_code, 200, created.text)
        reserve = llm_gateway.agent_reserve(registry, None, None, llm_gateway.agent_estimate_usage('{}', ''))
        self.assertGreater(reserve, 0)
        # агент не назвал расход: списание неизвестно, но резерв ненулевой
        claim = self.client.post('/api/chatgpt/worker/claim', headers=self.worker_headers()).json()
        job = claim['job']['id']
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            ready = self.client.post(f'/api/chatgpt/worker/jobs/{job}/progress', headers=self.worker_headers(),
                                     json={'status': 'prompt_ready', 'prompt': 'A wide view of an empty courtyard at dusk.'})
        self.assertEqual(ready.status_code, 200, ready.text)
        unknown = [row for row in self.rows(pid) if row['actual_status'] == 'unknown']
        self.assertEqual(len(unknown), 1)
        self.assertGreater(unknown[0]['reserved_usd'], 0)
        llm = self.llm_block(pid)
        self.assertGreater(llm['unknown_cost_usd'], 0)
        self.assertEqual(llm['actual_cost_usd'], 0)
        # и неизвестное списание занимает лимит проекта
        self.client.put('/api/budgets/limits', json={'project_usd': 0.000001, 'daily_usd': 2})
        blocked = self.chat(registry, PAID, pid, 'agent-paid-fallback-0002')
        self.assertEqual(blocked.status_code, 400)
        self.assertIn('бюджет', blocked.text.lower())

    def test_agent_job_is_refused_when_the_limit_is_exhausted_and_the_fallback_is_free(self):
        pid = self.agent_project()
        # лимит проекта исчерпан, а единственный нулевой тариф резерв не держит:
        # работа агента не должна проходить с нулевым резервом
        priceless = {'provider': 'kie', 'model': 'gpt-6-luna', 'role': 'simple', 'input': None, 'output': None}
        registry = self.registry(rate(**priceless), rate(**OPENROUTER), rate(**MINIMAX))
        self.client.put('/api/budgets/limits', json={'project_usd': 0.0000001, 'daily_usd': 2})
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            created = self.client.post('/api/chatgpt/jobs', json=self.agent_body(pid, 'agent-limit-free-0001'))
        self.assertEqual(created.status_code, 400)
        self.assertIn('бюджет', created.text.lower())
        self.worker_has_no_job()

    def test_agent_job_is_refused_when_the_project_limit_is_exhausted(self):
        pid = self.agent_project()
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        self.client.put('/api/budgets/limits', json={'project_usd': 0.0000001, 'daily_usd': 2})
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            created = self.client.post('/api/chatgpt/jobs', json=self.agent_body(pid, 'agent-limit-project-0001'))
        self.assertEqual(created.status_code, 400)
        self.assertIn('бюджет', created.text.lower())
        self.worker_has_no_job()

    def test_agent_job_is_refused_when_the_daily_limit_is_exhausted(self):
        pid = self.agent_project()
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        self.client.put('/api/budgets/limits', json={'project_usd': 1, 'daily_usd': 0.0000001})
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            created = self.client.post('/api/chatgpt/jobs', json=self.agent_body(pid, 'agent-limit-day-0001'))
        self.assertEqual(created.status_code, 400)
        self.assertIn('лимит', created.text.lower())
        self.worker_has_no_job()

    def test_agent_job_is_not_completed_when_the_spend_row_fails(self):
        pid, job = self.agent_job('agent-spend-fail-0001')
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        with patch.object(llm_guard, 'current_registry', return_value=registry), \
             patch.object(native_chat, 'insert_agent_call',
                          side_effect=sqlite3.IntegrityError('UNIQUE constraint failed: llm_calls.request_id')):
            with self.assertRaises(sqlite3.IntegrityError):
                self.client.post(f'/api/chatgpt/worker/jobs/{job}/progress', headers=self.worker_headers(),
                                 json={'status': 'prompt_ready', 'prompt': 'A wide view of an empty courtyard at dusk.'})
        # задание не помечено выполненным: расход агента не потерян,
        # но и не остаётся в невынимаемом состоянии 'preparing'
        with main.connect() as db:
            item = db.execute('SELECT status FROM native_chat_jobs WHERE id=?', (job,)).fetchone()
            rows = db.execute('SELECT COUNT(*) FROM llm_calls WHERE project_id=?', (pid,)).fetchone()[0]
        self.assertEqual(item['status'], 'failed')
        self.assertEqual(rows, 0)

    def test_rejected_report_does_not_block_the_agent_queue(self):
        pid, job = self.agent_job('agent-invalid-transition-0001')
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            # обычный отчёт с пустым промптом: переход этапа недопустим
            rejected = self.client.post(f'/api/chatgpt/worker/jobs/{job}/progress', headers=self.worker_headers(),
                                        json={'status': 'prompt_ready', 'prompt': ''})
        self.assertEqual(rejected.status_code, 409)
        with main.connect() as db:
            item = db.execute('SELECT status FROM native_chat_jobs WHERE id=?', (job,)).fetchone()
        # задание не остаётся в невынимаемом состоянии 'preparing'
        self.assertEqual(item['status'], 'failed')
        # очередь агента по всей студии не заблокирована: задание заводится заново и уходит воркеру
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            again = self.client.post('/api/chatgpt/jobs', json=self.agent_body(pid, 'agent-after-reject-0001'))
        self.assertEqual(again.status_code, 200, again.text)
        claim = self.client.post('/api/chatgpt/worker/claim', headers=self.worker_headers()).json()
        self.assertIsNotNone(claim.get('job'))

    def test_agent_call_is_journaled_once_per_request_id(self):
        pid = self.agent_project()
        body = self.agent_body(pid, 'agent-once-00001')
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        report = {'status': 'prompt_ready', 'prompt': 'A wide view of an empty courtyard at dusk.',
                  'provider': 'kie', 'model': 'gpt-6-luna', 'usage': {'input_tokens': 1000, 'output_tokens': 200}}
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            first = self.client.post('/api/chatgpt/jobs', json=body)
            self.assertEqual(first.status_code, 200, first.text)
            # повторная постановка того же задания возвращает то же задание, а не вторую работу
            again = self.client.post('/api/chatgpt/jobs', json=body)
            self.assertEqual(again.status_code, 200, again.text)
            self.assertEqual(again.json()['id'], first.json()['id'])
            job = first.json()['id']
            claim = self.client.post('/api/chatgpt/worker/claim', headers=self.worker_headers()).json()
            self.assertEqual(claim['job']['id'], job)
            ready = self.client.post(f'/api/chatgpt/worker/jobs/{job}/progress', headers=self.worker_headers(),
                                     json=report)
            self.assertEqual(ready.status_code, 200, ready.text)
            # повторный отчёт о той же работе не создаёт второй строки расхода
            repeat = self.client.post(f'/api/chatgpt/worker/jobs/{job}/progress', headers=self.worker_headers(), json=report)
            self.assertNotEqual(repeat.status_code, 200)
        self.assertEqual(len(self.rows(pid)), 1)

    def test_agent_unknown_charge_occupies_the_project_and_day_limits(self):
        pid, job = self.agent_job('agent-limit-hold-0001')
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            ready = self.client.post(f'/api/chatgpt/worker/jobs/{job}/progress', headers=self.worker_headers(),
                                     json={'status': 'prompt_ready', 'prompt': 'A wide view of an empty courtyard at dusk.'})
        self.assertEqual(ready.status_code, 200, ready.text)
        llm = self.llm_block(pid)
        self.assertGreater(llm['unknown_cost_usd'], 0)
        # неизвестное списание агента занимает лимит проекта
        self.client.put('/api/budgets/limits', json={'project_usd': 0.000001, 'daily_usd': 2})
        blocked = self.chat(registry, PAID, pid, 'agent-limit-hold-0002')
        self.assertEqual(blocked.status_code, 400)
        self.assertIn('бюджет', blocked.text.lower())
        # и лимит дня
        self.client.put('/api/budgets/limits', json={'project_usd': 1, 'daily_usd': 0.000001})
        blocked_day = self.chat(registry, PAID, pid, 'agent-limit-hold-0003')
        self.assertEqual(blocked_day.status_code, 400)
        self.assertIn('лимит', blocked_day.text.lower())

    def test_free_agent_model_is_not_refused(self):
        pid, job = self.agent_job('agent-free-model-0001', operation='prompt')
        registry = self.registry(rate(**KIE), rate(**MINIMAX), rate(**OPENROUTER))
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            ready = self.client.post(f'/api/chatgpt/worker/jobs/{job}/progress', headers=self.worker_headers(),
                                     json={'status': 'prompt_ready', 'prompt': 'A wide view of an empty courtyard at dusk.',
                                           'provider': 'openrouter', 'model': 'minimax/minimax-m3.1-flash:free',
                                           'usage': {'input_tokens': 1000, 'output_tokens': 200}})
        # нулевой тариф — это тариф: отказа нет
        self.assertEqual(ready.status_code, 200, ready.text)
        rows = self.rows(pid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['actual_status'], 'free')
        self.assertEqual(rows[0]['actual_cost_usd'], 0)
        self.assertEqual(rows[0]['reserved_usd'], 0)
        llm = self.llm_block(pid)
        self.assertEqual(llm['actual_cost_usd'], 0)
        self.assertEqual(llm['unknown_cost_usd'], 0)
        with main.connect() as db:
            item = db.execute('SELECT status FROM native_chat_jobs WHERE id=?', (job,)).fetchone()
        self.assertEqual(item['status'], 'completed')

    def test_refused_report_leaves_the_job_recoverable(self):
        pid, job = self.agent_job('agent-refused-report-0001')
        # тарифа нет вовсе: отчёт отвергнут по существу
        with patch.object(llm_guard, 'current_registry', return_value=self.registry()):
            refused = self.client.post(f'/api/chatgpt/worker/jobs/{job}/progress', headers=self.worker_headers(),
                                       json={'status': 'prompt_ready', 'prompt': 'A wide view of an empty courtyard at dusk.'})
        self.assertEqual(refused.status_code, 400)
        with main.connect() as db:
            item = db.execute('SELECT status,message FROM native_chat_jobs WHERE id=?', (job,)).fetchone()
        # задание не остаётся в невынимаемом состоянии
        self.assertEqual(item['status'], 'failed')
        self.assertIn('тариф', item['message'])
        # очередь агента по всей студии не заблокирована
        self.worker_has_no_job()
        # и в проекте можно завести новое задание
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            again = self.client.post('/api/chatgpt/jobs', json=self.agent_body(pid, 'agent-after-refusal-0001'))
        self.assertEqual(again.status_code, 200, again.text)

    def test_failed_report_with_named_spend_is_confirmed(self):
        pid, job = self.agent_job('agent-failed-named-0001')
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            failed = self.client.post(f'/api/chatgpt/worker/jobs/{job}/progress', headers=self.worker_headers(),
                                      json={'status': 'failed', 'message': 'Не получилось собрать промпт',
                                            'provider': 'kie', 'model': 'gpt-6-luna',
                                            'usage': {'input_tokens': 1000, 'output_tokens': 200}})
        self.assertEqual(failed.status_code, 200, failed.text)
        rows = self.rows(pid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'failed')
        self.assertEqual(rows[0]['actual_status'], 'confirmed')
        # тариф Kie: 1000*0.03 + 200*0.15 за млн
        self.assertEqual(rows[0]['actual_cost_usd'], 0.00006)
        llm = self.llm_block(pid)
        self.assertEqual(llm['actual_cost_usd'], 0.00006)
        self.assertEqual(llm['unknown_cost_usd'], 0)

    def test_failed_report_without_spend_is_unknown_with_reserve(self):
        pid, job = self.agent_job('agent-failed-unknown-0001')
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            failed = self.client.post(f'/api/chatgpt/worker/jobs/{job}/progress', headers=self.worker_headers(),
                                      json={'status': 'failed', 'message': 'Не получилось собрать промпт'})
        self.assertEqual(failed.status_code, 200, failed.text)
        rows = self.rows(pid)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['status'], 'failed')
        self.assertEqual(rows[0]['actual_status'], 'unknown')
        self.assertIsNone(rows[0]['actual_cost_usd'])
        self.assertGreater(rows[0]['reserved_usd'], 0)
        llm = self.llm_block(pid)
        self.assertEqual(llm['actual_cost_usd'], 0)
        self.assertGreater(llm['unknown_cost_usd'], 0)

    def test_report_uses_the_agents_own_tariff_and_records_over_limit_spend(self):
        pid, job = self.agent_job('agent-real-tariff-0001')
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        # лимит исчерпан к моменту отчёта: расход всё равно записывается
        self.client.put('/api/budgets/limits', json={'project_usd': 0.0000001, 'daily_usd': 2})
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            ready = self.client.post(f'/api/chatgpt/worker/jobs/{job}/progress', headers=self.worker_headers(),
                                     json={'status': 'prompt_ready', 'prompt': 'A wide view of an empty courtyard at dusk.',
                                           'provider': 'minimax', 'model': 'MiniMax-M3.1-Flash',
                                           'usage': {'input_tokens': 1000, 'output_tokens': 200}})
        self.assertEqual(ready.status_code, 200, ready.text)
        rows = self.rows(pid)
        self.assertEqual(len(rows), 1)
        # тариф — реальный, по модели агента, а не по дешёвой базовой линии
        self.assertEqual(rows[0]['execution_provider'], 'minimax')
        self.assertEqual(rows[0]['price_snapshot_id'], 'minimax/MiniMax-M3.1-Flash@2026-10-20')
        # тариф MiniMax: 1000*0.15 + 200*0.6 за млн
        self.assertEqual(rows[0]['actual_cost_usd'], 0.00027)
        # лимит при отчёте проверяется по реальному тарифу, но перерасход запись не отменяет
        with main.connect() as db:
            item = db.execute('SELECT status,message FROM native_chat_jobs WHERE id=?', (job,)).fetchone()
        self.assertIn('Лимит превышен', item['message'])
        llm = self.llm_block(pid)
        self.assertEqual(llm['actual_cost_usd'], 0.00027)
        self.assertEqual(llm['unknown_cost_usd'], 0)

    def test_agent_call_is_journaled_with_reported_provider_and_model(self):
        pid, job = self.agent_job('agent-budget-report-0001')
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            ready = self.client.post(f'/api/chatgpt/worker/jobs/{job}/progress', headers=self.worker_headers(),
                                     json={'status': 'prompt_ready', 'prompt': 'A wide view of an empty courtyard at dusk.',
                                           'provider': 'kie', 'model': 'gpt-6-luna',
                                           'usage': {'input_tokens': 1000, 'output_tokens': 200}})
        self.assertEqual(ready.status_code, 200, ready.text)
        rows = self.rows(pid)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row['execution_provider'], row['execution_model']), ('kie', 'gpt-6-luna'))
        self.assertEqual(row['actual_status'], 'confirmed')
        # тариф Kie: 1000*0.03 + 200*0.15 за млн
        self.assertEqual(row['actual_cost_usd'], 0.00006)
        self.assertEqual((row['input_tokens'], row['output_tokens']), (1000, 200))
        llm = self.llm_block(pid)
        # codex_chat больше не исключён из «Фактически потрачено»
        self.assertEqual(llm['actual_cost_usd'], 0.00006)
        self.assertEqual(llm['unknown_cost_usd'], 0)
        self.assertEqual(llm['calls'], 1)
        with main.connect() as db:
            version = db.execute('SELECT model,usage FROM prompt_versions WHERE project_id=?', (pid,)).fetchone()
        self.assertEqual(version['model'], 'gpt-6-luna')
        self.assertEqual(json.loads(version['usage'])['usage']['input_tokens'], 1000)

    def test_agent_call_without_spend_is_unknown_charge_not_zero(self):
        pid, job = self.agent_job('agent-budget-unknown-0001')
        registry = self.registry(rate(**KIE), rate(**MINIMAX))
        with patch.object(llm_guard, 'current_registry', return_value=registry):
            ready = self.client.post(f'/api/chatgpt/worker/jobs/{job}/progress', headers=self.worker_headers(),
                                     json={'status': 'prompt_ready', 'prompt': 'A wide view of an empty courtyard at dusk.'})
        self.assertEqual(ready.status_code, 200, ready.text)
        rows = self.rows(pid)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        # провайдер и модель не названы — записываются как неизвестные, не как константа
        self.assertEqual((row['execution_provider'], row['execution_model']), ('unknown', 'unknown'))
        self.assertEqual(row['actual_status'], 'unknown')
        self.assertIsNone(row['actual_cost_usd'])
        llm = self.llm_block(pid)
        self.assertEqual(llm['actual_cost_usd'], 0)
        # работа агента стоила денег: сумма неизвестна и ждёт сверки
        self.assertGreater(llm['unknown_cost_usd'], 0)
        self.assertEqual(llm['calls'], 1)


if __name__ == '__main__':
    unittest.main()
