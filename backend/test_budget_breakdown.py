"""Бюджет проекта: четыре раздельные величины LLM рядом с прежними полями.

Проверка идёт через публичный интерфейс студии: GET /api/budgets/{project_id}.
Раньше ответ отдавал только экспозицию (llm_project_usd), и владелец видел в «Бюджете»
факт вместе с удерживаемыми резервами и неизвестными списаниями одной строкой.
"""
import unittest

from backend import llm_guard, main
from backend.test_llm_cost_display import GatewayCase, KIE, MINIMAX, PAID, UNKNOWN
from backend.test_llm_gateway import rate


class ProjectBudgetBreakdownTests(GatewayCase):
    """Четыре величины LLM в ответе бюджета проекта; прежние поля не исчезают."""

    def budget(self, project_id):
        response = self.client.get('/api/budgets/' + project_id)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_project_budget_returns_four_amounts_next_to_old_fields(self):
        pid = self.project()
        registry = self.registry(rate(**MINIMAX), rate(**KIE))
        ok = self.chat(registry, PAID, pid, 'budget-breakdown-paid-1')
        self.assertEqual(ok.status_code, 200, ok.text)
        data = self.budget(pid)
        # подтверждённый факт: 1000*0.15 + 200*0.6 за млн по тарифу MiniMax
        self.assertEqual(data['actual_cost_usd'], 0.00027)
        self.assertEqual(data['reserved_usd'], 0)
        self.assertEqual(data['unknown_cost_usd'], 0)
        # ориентир по Kie — деньгами не является, но виден отдельной величиной
        self.assertEqual(data['reference_cost_usd'], 0.00006)
        # прежние поля ответа остаются: обратная совместимость
        for field in ('llm_project_usd', 'llm_daily_usd', 'llm_calls_project',
                      'project_limit_usd', 'daily_limit_usd', 'project_reserved_usd', 'daily_reserved_usd'):
            self.assertIn(field, data)
        self.assertEqual(data['llm_calls_project'], 1)
        # экспозиция = факт + резерв + неизвестные списания
        self.assertAlmostEqual(data['llm_project_usd'],
                               data['actual_cost_usd'] + data['reserved_usd'] + data['unknown_cost_usd'],
                               places=6)

    def test_unknown_charge_is_separate_amount_not_actual(self):
        pid = self.project()
        registry = self.registry(rate(**MINIMAX), rate(**KIE))
        failed = self.chat(registry, UNKNOWN, pid, 'budget-breakdown-unknown-1')
        self.assertEqual(failed.status_code, 502)
        data = self.budget(pid)
        # подтверждённого списания нет — факта нет
        self.assertEqual(data['actual_cost_usd'], 0)
        # списание возможно: сумма видна отдельным итогом, а не внутри факта
        self.assertGreater(data['unknown_cost_usd'], 0)
        self.assertEqual(data['reserved_usd'], 0)

    def test_reserved_call_in_flight_is_not_actual(self):
        pid = self.project()
        with main.connect() as db:
            llm_guard.ensure_schema(db)
            db.execute('INSERT INTO llm_calls(id,request_id,project_id,model,status,usd,estimated_usd,created_at,'
                       'execution_provider,execution_model,actual_cost_usd,actual_status,reserved_usd,billing_source)'
                       ' VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       ('row-budget-in-flight', 'budget-breakdown-in-flight-1', pid, 'MiniMax-M3.1-Flash',
                        'reserved', 0.0005, 0.0005, main.now(), 'minimax', 'MiniMax-M3.1-Flash', None,
                        'estimated', 0.0005, 'route_tariff'))
        data = self.budget(pid)
        self.assertEqual(data['reserved_usd'], 0.0005)
        self.assertEqual(data['unknown_cost_usd'], 0)
        self.assertEqual(data['actual_cost_usd'], 0)

    def test_project_without_llm_calls_returns_zero_amounts(self):
        pid = self.project()
        data = self.budget(pid)
        for field in ('actual_cost_usd', 'reserved_usd', 'unknown_cost_usd', 'reference_cost_usd'):
            self.assertEqual(data[field], 0)
        self.assertEqual(data['llm_calls_project'], 0)
        self.assertEqual(data['llm_project_usd'], 0)


if __name__ == '__main__':
    unittest.main()
