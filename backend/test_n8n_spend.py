"""Учёт расходов n8n-агентов в бюджете студии.

Дефект, который закрывает файл: расходы n8n-агентов не попадали в бюджет студии.
У n8n был только его собственный cap (`sessionCostCapUsd`) — консервативная оценка,
не доказанный стоп на уровне провайдера. Проект мог потратить сверх общего лимита:
медиа, LLM-вызовы студии и агенты n8n считались разными счётчиками.

Каждый тест называет свой случай: что должно произойти с деньгами.
"""
import json
import os
import unittest
from pathlib import Path

from backend import main, security, spend_ledger, test_smoke

TOKEN_ALL = 'n8n-token-all'
TOKEN_OTHER = 'n8n-token-other'


class N8nSpendTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def setUp(self):
        test_smoke.StudioSmokeTests.setUp(self)
        # Переменные окружения правим сами: patch.dict кладёт в восстановление всю
        # копию окружения и затирает чужие переменные (например, ключи провайдеров)
        # для тестов, которые идут после. Здесь нужен ровно один ключ.
        self._tokens_before = os.environ.get('STUDIO_SERVICE_TOKENS')
        os.environ['STUDIO_SERVICE_TOKENS'] = f'{TOKEN_ALL}:*;{TOKEN_OTHER}:other-project'
        self.project = self.client.post('/api/projects', json={'title': 'n8n spend', 'state': {'brief': 'x'}}).json()['id']

    def tearDown(self):
        test_smoke.StudioSmokeTests.tearDown(self)
        if self._tokens_before is None:
            os.environ.pop('STUDIO_SERVICE_TOKENS', None)
        else:
            os.environ['STUDIO_SERVICE_TOKENS'] = self._tokens_before

    # ------------------------------------------------------------- helpers

    def machine(self, path, payload=None, token=TOKEN_ALL, method='post'):
        # Машинный вызов идёт без браузерной сессии: cookie сбрасываем, чтобы
        # проверить именно права машинного токена.
        self.client.cookies.clear()
        headers = {'Authorization': f'Bearer {token}', 'X-Studio-Session': ''}
        call = getattr(self.client, method)
        if method == 'get':
            return call(path, headers=headers)
        return call(path, headers=headers, json=payload)

    def allowance(self, role='A1', cap=0.05, token=None):
        headers = {'X-Studio-Session': self.client.headers['X-Studio-Session']}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return self.client.put(f'/api/n8n/allowances/{role}', headers=headers,
                               json={'cap_usd': cap, 'model': 'anthropic/claude-sonnet-5-5'})

    def reserve(self, request_id='req-1', role='A1', project=None, token=TOKEN_ALL):
        return self.machine('/api/n8n/spend/reserve',
                            {'project_id': project or self.project, 'request_id': request_id, 'role': role,
                             'stage': 'idea', 'model': 'anthropic/claude-sonnet-5-5'}, token=token)

    def settle(self, permit_id, status='done', usd=0.004, token=TOKEN_ALL):
        return self.machine('/api/n8n/spend/settle',
                            {'permit_id': permit_id, 'status': status, 'usd': usd}, token=token)

    def budget(self, project=None):
        with main.connect() as db:
            return spend_ledger.state(db, project or self.project)

    def limits(self, project_usd=1, daily_usd=2):
        self.client.put('/api/budgets/limits', json={'project_usd': project_usd, 'daily_usd': daily_usd})

    # --------------------------------------------------------------- tests

    def test_reserve_holds_money_in_the_one_counter(self):
        """Резерв n8n-агента виден в том же счётчике, что медиа и LLM."""
        self.allowance(cap=0.05)
        response = self.reserve()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['status'], 'reserved')
        state = self.budget()
        self.assertAlmostEqual(state['n8n_reserved_usd'], 0.05)
        self.assertAlmostEqual(state['project_reserved_usd'], 0.05)

    def test_reserve_without_allowance_is_refused(self):
        """Нет потолка роли — платить нельзя: fail-closed, а не «разрешено по умолчанию»."""
        response = self.reserve(role='A9')
        self.assertEqual(response.status_code, 400, response.text)
        self.assertAlmostEqual(self.budget()['project_reserved_usd'], 0.0)

    def test_reserve_over_the_project_budget_is_refused(self):
        """Потолок роли не влезает в остаток бюджета — шаг не запускается."""
        self.allowance(cap=0.5)
        self.limits(project_usd=0.1, daily_usd=0.1)
        response = self.reserve()
        self.assertEqual(response.status_code, 400, response.text)
        self.assertAlmostEqual(self.budget()['project_reserved_usd'], 0.0)

    def test_reserve_is_idempotent_by_request_id(self):
        """Повтор того же запроса не бронирует деньги дважды."""
        self.allowance(cap=0.05)
        first = self.reserve(request_id='req-dup')
        second = self.reserve(request_id='req-dup')
        self.assertEqual(first.json()['permit_id'], second.json()['permit_id'])
        self.assertAlmostEqual(self.budget()['n8n_reserved_usd'], 0.05)

    def test_closed_request_cannot_be_reserved_again(self):
        """Закрытый резерв повторно не открывает деньги."""
        self.allowance(cap=0.05)
        permit = self.reserve(request_id='req-closed').json()
        self.settle(permit['permit_id'])
        again = self.reserve(request_id='req-closed')
        self.assertEqual(again.status_code, 409, again.text)

    def test_settle_releases_the_difference(self):
        """Подтверждённый факт меньше резерва — в бюджете остаётся только факт."""
        self.allowance(cap=0.05)
        permit = self.reserve().json()
        response = self.settle(permit['permit_id'], status='done', usd=0.004)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertAlmostEqual(response.json()['held_usd'], 0.004)
        self.assertAlmostEqual(self.budget()['n8n_reserved_usd'], 0.004)

    def test_settle_over_the_reserve_shows_the_overrun(self):
        """Факт больше потолка: перерасход виден в счётчике, а не спрятан."""
        self.allowance(cap=0.05)
        permit = self.reserve().json()
        self.settle(permit['permit_id'], status='done', usd=0.07)
        self.assertAlmostEqual(self.budget()['n8n_reserved_usd'], 0.07)

    def test_failed_settle_releases_the_whole_reserve(self):
        """Провайдер ничего не списал — резерв освобождается полностью."""
        self.allowance(cap=0.05)
        permit = self.reserve().json()
        self.settle(permit['permit_id'], status='failed', usd=0)
        self.assertAlmostEqual(self.budget()['n8n_reserved_usd'], 0.0)

    def test_unknown_settle_keeps_holding_the_money(self):
        """Агент не отчитался: резерв держится и блокирует новые траты."""
        self.allowance(cap=0.05)
        permit = self.reserve().json()
        self.settle(permit['permit_id'], status='unknown', usd=None)
        self.assertAlmostEqual(self.budget()['n8n_reserved_usd'], 0.05)

    def test_double_settle_is_refused(self):
        """Закрытый резерв нельзя закрыть повторно: двойного списания быть не должно."""
        self.allowance(cap=0.05)
        permit = self.reserve().json()
        self.settle(permit['permit_id'], status='done', usd=0.004)
        again = self.settle(permit['permit_id'], status='done', usd=0.004)
        self.assertEqual(again.status_code, 409, again.text)
        self.assertAlmostEqual(self.budget()['n8n_reserved_usd'], 0.004)

    def test_settle_without_a_fact_keeps_the_reserve(self):
        """Статус done без суммы — не подтверждённый факт, резерв остаётся."""
        self.allowance(cap=0.05)
        permit = self.reserve().json()
        response = self.settle(permit['permit_id'], status='done', usd=None)
        self.assertEqual(response.status_code, 400, response.text)
        self.assertAlmostEqual(self.budget()['n8n_reserved_usd'], 0.05)

    def test_unknown_permit_is_not_found(self):
        response = self.settle('n8n_missing')
        self.assertEqual(response.status_code, 404, response.text)

    def test_machine_token_outside_the_project_zone_is_refused(self):
        """Токен чужого проекта не может двигать деньги этого проекта."""
        self.allowance(cap=0.05)
        response = self.reserve(token=TOKEN_OTHER)
        self.assertEqual(response.status_code, 403, response.text)
        self.assertAlmostEqual(self.budget()['project_reserved_usd'], 0.0)

    def test_without_a_token_the_reserve_is_refused(self):
        """Без машинного токена резерва нет."""
        self.allowance(cap=0.05)
        response = self.client.post('/api/n8n/spend/reserve',
                                    headers={'X-Studio-Session': ''},
                                    json={'project_id': self.project, 'request_id': 'req-no-token', 'role': 'A1'})
        self.assertEqual(response.status_code, 401, response.text)

    def test_machine_token_cannot_set_allowances(self):
        """Потолок роли задаёт владелец, не агент."""
        self.allowance(cap=0.05)
        response = self.machine('/api/n8n/allowances/A2', {'cap_usd': 10}, token=TOKEN_ALL, method='put')
        self.assertEqual(response.status_code, 401, response.text)

    def test_n8n_money_is_visible_in_the_budget_endpoint(self):
        """Панель бюджета студии показывает расход n8n-агентов."""
        self.allowance(cap=0.05)
        self.reserve()
        data = self.client.get('/api/budgets/' + self.project).json()
        self.assertAlmostEqual(data['n8n_reserved_usd'], 0.05)

    def test_n8n_money_blocks_media_spend(self):
        """Общий лимит: деньги n8n-агента занимают тот же лимит, что и генерации."""
        self.allowance(cap=0.08)
        self.limits(project_usd=0.1, daily_usd=0.1)
        self.reserve()
        with main.connect() as db:
            with self.assertRaises(main.HTTPException):
                security.check_budget(db, self.project, 0.05)

    def test_missing_table_does_not_break_the_counter(self):
        """База без таблицы n8n_spend — ноль расходов, а не ошибка."""
        with main.connect() as db:
            db.execute('DROP TABLE IF EXISTS n8n_spend')
        state = self.budget()
        self.assertAlmostEqual(state['n8n_reserved_usd'], 0.0)
        self.assertAlmostEqual(state['project_reserved_usd'], 0.0)

    def test_allowance_can_be_raised_and_lowered_by_the_owner(self):
        """Владелец управляет потолком роли."""
        self.assertEqual(self.allowance(role='A3', cap=0.02).status_code, 200)
        self.assertEqual(self.allowance(role='A3', cap=0.08).status_code, 200)
        data = self.client.get('/api/n8n/allowances').json()['allowances']
        self.assertAlmostEqual([row for row in data if row['role'] == 'A3'][0]['cap_usd'], 0.08)

    def test_n8n_fragment_speaks_the_same_addresses_as_the_studio(self):
        """Фрагмент для n8n и реальные маршруты студии не должны разъехаться."""
        root = Path(__file__).resolve().parent.parent
        fragment = json.loads((root / 'integrations' / 'n8n' / 'workflows' / 'n8n-spend-gate.fragment.json')
                              .read_text(encoding='utf-8'))
        endpoints = fragment['meta']['studioEndpoints']
        routes = {route.path for route in main.app.routes if hasattr(route, 'path')}
        self.assertIn(endpoints['reserve'], routes)
        self.assertIn(endpoints['settle'], routes)
        urls = ' '.join(node['parameters']['url'] for node in fragment['nodes'])
        self.assertIn(endpoints['reserve'], urls)
        self.assertIn(endpoints['settle'], urls)
        reserve_node = [node for node in fragment['nodes'] if node['name'] == 'Резерв расхода'][0]
        self.assertEqual(reserve_node['onError'], 'stopWorkflow')


if __name__ == '__main__':
    unittest.main()
