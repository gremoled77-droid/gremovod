"""Независимые пробы ревью GA-01 (голова R3 784ea0c). Вне репозитория, только временные SQLite, без сети.

O1  ремонт на старте стирает исходную сумму и исходный статус денежной строки, бэкапа нет;
O2  бывшая строка 'done' после ремонта снимается сверкой 'failed' как «провайдер не списал»;
O3  у нечитаемой строки нет пути разрешения через API: сверка 409, других маршрутов нет;
O4  сверка перезаписывает заметку: причина ремонта / неизвестного исхода теряется;
O5  'reserved', оставшийся после падения процесса, не сверяется и держит деньги навсегда;
O6  /api/llm/calls отдаёт usd строкой 'unreadable' — тип поля меняется для клиентов.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend import llm_guard, main, test_smoke


def legacy_db(path, rows):
    db = sqlite3.connect(path)
    with db:
        db.execute('CREATE TABLE llm_calls(id TEXT PRIMARY KEY,request_id TEXT UNIQUE,project_id TEXT NOT NULL,'
                   'model TEXT NOT NULL,status TEXT NOT NULL,usd REAL NOT NULL,estimated_usd REAL NOT NULL,'
                   'input_tokens INTEGER,output_tokens INTEGER,created_at TEXT NOT NULL)')
        for rid, status, usd, est in rows:
            db.execute('INSERT INTO llm_calls VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (rid, rid + '-request', 'p-legacy', 'gpt-5.6-luna', status, usd, est, None, None,
                        '2026-10-01T10:00:00+00:00'))
    db.close()


def rows(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    cols = {r['name'] for r in db.execute('PRAGMA table_info(llm_calls)')}
    extra = ',confirmed_usd,note' if 'note' in cols else ''
    out = {r['id']: dict(r) for r in db.execute(f'SELECT id,status,usd,typeof(usd) t{extra} FROM llm_calls')}
    db.close()
    return out


class StartupRepairProbe(unittest.TestCase):
    def start(self, path):
        smoke = test_smoke.StudioSmokeTests('run')
        smoke.setUp()
        self.addCleanup(smoke.tearDown)
        # Перезапуск того же приложения на подготовленной старой базе.
        smoke.client.__exit__(None, None, None)
        p = patch.object(main, 'DB', path)
        p.start()
        self.addCleanup(p.stop)
        smoke.client = TestClient(main.app, base_url='http://127.0.0.1')
        smoke.client.__enter__()
        smoke.client.headers['X-Studio-Session'] = smoke.client.get('/api/session').json()['token']
        return smoke

    def test_O1_O2_O3_O4_O6(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / 'studio.sqlite3'
        legacy_db(path, [('done-neg', 'done', -0.14, 0.1),     # провайдер списал, знак суммы испорчен
                         ('res-neg', 'reserved', -0.2, 0.2),
                         ('done-text', 'done', 'bad', 'bad')])  # ни суммы, ни оценки, ни токенов
        before = rows(path)
        smoke = self.start(path)
        after = rows(path)
        files = sorted(p.name for p in Path(tmp.name).iterdir())
        print('\nBEFORE', before)
        print('AFTER ', after)
        print('FILES ', files)
        # O1: исходные значения нигде не сохранены.
        self.assertEqual(after['done-neg']['status'], 'submission_unknown')
        self.assertNotIn('-0.14', after['done-neg']['note'] or '')
        self.assertNotIn('done', after['done-neg']['note'] or '')  # исходный статус не записан
        self.assertEqual(after['done-text']['usd'], llm_guard.UNREADABLE_AMOUNT)
        self.assertNotIn('bad', after['done-text']['note'] or '')
        self.assertEqual([f for f in files if 'backup' in f or f.endswith('.bak')], [])
        # O6: тип поля usd в API.
        calls = smoke.client.get('/api/llm/calls', params={'project_id': 'p-legacy'}).json()
        print('API   ', [(c['id'], c['usd'], type(c['usd']).__name__) for c in calls])
        # O2: бывший 'done' снимается как «не списано».
        r = smoke.client.post('/api/llm/calls/done-neg/reconcile',
                              json={'outcome': 'failed', 'note': 'провайдер ничего не списал', 'approved': True})
        print('O2    ', r.status_code, r.json())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'failed')
        self.assertEqual(r.json()['released_usd'], 0.1)
        # O4: причина ремонта затёрта заметкой сверки.
        self.assertNotIn('старая запись', rows(path)['done-neg']['note'])
        # O3: нечитаемую строку нельзя разрешить через API.
        for body in ({'outcome': 'done', 'usd': 0.3, 'note': 'сумма по счёту провайдера', 'approved': True},
                     {'outcome': 'failed', 'note': 'провайдер ничего не списал', 'approved': True}):
            r = smoke.client.post('/api/llm/calls/done-text/reconcile', json=body)
            print('O3    ', r.status_code, r.json())
            self.assertEqual(r.status_code, 409)
        routes = sorted({getattr(x, 'path', '') for x in main.app.routes if '/llm/calls' in getattr(x, 'path', '')})
        print('ROUTES', routes)


class OrphanReserveProbe(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def test_O5_reserved_after_crash_is_held_forever(self):
        pid = self.client.post('/api/projects', json={'title': 'P', 'state': {}}).json()['id']
        call_id = llm_guard.reserve_call(main, pid, 'gpt-5.6-luna', 'orphan-request-0001', 0.25)
        # Процесс умер между резервом и ответом провайдера: settle не выполнен. Перезапуск.
        self.client.__exit__(None, None, None)
        self.client = TestClient(main.app, base_url='http://127.0.0.1')
        self.client.__enter__()
        self.client.headers['X-Studio-Session'] = self.client.get('/api/session').json()['token']
        with main.connect() as db:
            row = dict(db.execute('SELECT status,usd FROM llm_calls WHERE id=?', (call_id,)).fetchone())
        budget = self.client.get('/api/budgets/' + pid).json()
        r = self.client.post(f'/api/llm/calls/{call_id}/reconcile',
                             json={'outcome': 'failed', 'note': 'процесс упал до отправки', 'approved': True})
        print('\nO5    ', row, 'llm_reserved_usd=', budget['llm_reserved_usd'], 'unknown_calls=',
              budget['llm_unknown_calls'], 'reconcile=', r.status_code, r.json().get('detail'))
        self.assertEqual(row['status'], 'reserved')
        self.assertEqual(budget['llm_unknown_calls'], 0)  # в «ждут сверки» не попадает
        self.assertEqual(r.status_code, 409)


if __name__ == '__main__':
    unittest.main()
