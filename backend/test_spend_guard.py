"""Платный вызов провайдера — только при резерве в журнале расходов.

Граница живёт в единственной точке выхода к провайдеру (main.request_piapi),
поэтому её нельзя обойти новым маршрутом: без резерва вызов не уходит.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import HTTPException

from backend import main


class SpendReservationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(main, 'DB', Path(self.temp.name) / 'studio.sqlite3')
        self.db_patch.start()
        with main.connect() as db:
            db.execute('''CREATE TABLE llm_calls(id TEXT PRIMARY KEY,request_id TEXT UNIQUE,project_id TEXT NOT NULL,model TEXT NOT NULL,
                status TEXT NOT NULL,usd REAL NOT NULL,estimated_usd REAL NOT NULL,input_tokens INTEGER,output_tokens INTEGER,created_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE jobs(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,kind TEXT NOT NULL,provider TEXT NOT NULL,
                task_id TEXT,status TEXT NOT NULL,request TEXT NOT NULL,response TEXT NOT NULL,created_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE generation_approvals(job_id TEXT PRIMARY KEY,estimated_usd REAL,max_cost_usd REAL,approved_at TEXT,price_basis TEXT)''')

    def tearDown(self):
        self.db_patch.stop()
        self.temp.cleanup()

    def reserve_llm(self, request_id='req-1', model='gpt-5.6-luna', status='reserved'):
        with main.connect() as db:
            db.execute('INSERT INTO llm_calls VALUES(?,?,?,?,?,?,?,?,?,?)',
                       ('call-1', request_id, 'project-1', model, status, 0.1, 0.1, None, None, 'now'))

    async def test_post_without_reservation_never_reaches_provider(self):
        async def fake(self, method, url, headers=None, json=None):
            raise AssertionError('Провайдер не должен вызываться без резерва')
        with patch.object(httpx.AsyncClient, 'request', fake):
            with self.assertRaises(HTTPException) as caught:
                await main.request_piapi('POST', '/v1/chat/completions', 'key', {'model': 'gpt-5.6-luna'})
        self.assertEqual(caught.exception.status_code, 403)

    async def test_post_with_reservation_reaches_provider(self):
        self.reserve_llm()
        seen = []

        async def fake(self, method, url, headers=None, json=None):
            seen.append(url)
            return httpx.Response(200, json={'choices': [{'message': {'content': 'ok'}}]})

        with patch.object(httpx.AsyncClient, 'request', fake):
            value = await main.request_piapi('POST', '/v1/chat/completions', 'key', {'model': 'gpt-5.6-luna'}, spend=('llm', 'req-1'))
        self.assertEqual(len(seen), 1)
        self.assertEqual(value['choices'][0]['message']['content'], 'ok')

    async def test_reservation_of_another_model_is_refused(self):
        self.reserve_llm()
        with self.assertRaises(HTTPException) as caught:
            await main.require_spend_reservation(('llm', 'req-1'), {'model': 'gpt-6-astra'})
        self.assertEqual(caught.exception.status_code, 403)

    async def test_spent_reservation_cannot_be_reused(self):
        self.reserve_llm(status='done')
        with self.assertRaises(HTTPException) as caught:
            await main.require_spend_reservation(('llm', 'req-1'), {'model': 'gpt-5.6-luna'})
        self.assertEqual(caught.exception.status_code, 403)

    async def test_job_reservation_needs_approval_row(self):
        with main.connect() as db:
            db.execute("INSERT INTO jobs VALUES('job-1','project-1','image','piapi',NULL,'submitting','{}','{}','now')")
        with self.assertRaises(HTTPException) as caught:
            main.require_spend_reservation(('job', 'job-1'))
        self.assertEqual(caught.exception.status_code, 403)
        with main.connect() as db:
            db.execute("INSERT INTO generation_approvals VALUES('job-1',0.1,0.2,'now','documentation_estimate')")
        main.require_spend_reservation(('job', 'job-1'))

    async def test_unknown_reservation_kind_is_refused(self):
        with self.assertRaises(HTTPException) as caught:
            main.require_spend_reservation(('manual', 'req-1'))
        self.assertEqual(caught.exception.status_code, 403)


class LegacyPaidRouteTests(unittest.TestCase):
    """Маршруты, у которых не было ни оценки, ни лимита, ни записи в журнал расходов."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(main, 'DB', Path(self.temp.name) / 'studio.sqlite3')
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.addCleanup(self.temp.cleanup)

    def test_direct_chat_is_closed_and_points_to_guarded_route(self):
        from fastapi.testclient import TestClient
        with TestClient(main.app, base_url='http://127.0.0.1') as client:
            client.headers['X-Studio-Session'] = client.get('/api/session').json()['token']
            response = client.post('/api/chat', json={'model': 'gpt-5.6-luna', 'messages': [{'role': 'user', 'content': 'x'}]})
        self.assertEqual(response.status_code, 410)
        self.assertIn('/api/llm/chat', response.json()['detail'])

    def test_agents_config_offers_only_guarded_provider(self):
        from fastapi.testclient import TestClient
        with TestClient(main.app, base_url='http://127.0.0.1') as client:
            client.headers['X-Studio-Session'] = client.get('/api/session').json()['token']
            config = client.get('/api/agents/config').json()
        self.assertEqual(config['providers'], ['piapi'])


if __name__ == '__main__':
    unittest.main()
