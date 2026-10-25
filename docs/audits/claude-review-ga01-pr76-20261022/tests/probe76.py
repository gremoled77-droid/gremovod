import sqlite3, tempfile, unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from fastapi import FastAPI
from backend import llm_guard, main, spend_ledger, test_llm_settlement as t

class P1A(unittest.TestCase):
    """Сверка done без суммы: резерв по оценке становится подтверждённым фактом?"""
    def test_done_without_amount(self):
        f = t.AgentsReconcileTests(); f.setUp(); self.addCleanup(f.tearDown); f.prepare()
        good = {'prompt_tokens': 120, 'completion_tokens': 40}
        r, _ = f.run_agents('review-p1a-nosum-1', [('a', good), ('b', {}), ('c', good)])
        print('run', r.status_code, r.text[:300])
        row = f.split_row()
        before = (row['usd'], row['confirmed_usd'])
        res = f.reconcile(row['id'], {'outcome': 'done', 'note': 'без суммы'})
        print('P1A status', r.status_code, r.text[:300]); print('P1A before(usd,confirmed)=%s response=%s %s' % (before, res.status_code, res.json()))
        self.assertNotEqual(res.json().get('confirmed_usd'), before[0], 'весь резерв стал подтверждённым без названной суммы')

class Legacy(unittest.TestCase):
    def mk(self, rows, col=False):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / 'l.sqlite3'
        @contextmanager
        def connect():
            db = sqlite3.connect(path); db.row_factory = sqlite3.Row
            try:
                with db: yield db
            finally: db.close()
        self.connect = connect
        with connect() as db:
            db.execute('CREATE TABLE llm_calls(id TEXT PRIMARY KEY,request_id TEXT UNIQUE,project_id TEXT NOT NULL,model TEXT NOT NULL,status TEXT NOT NULL,usd REAL NOT NULL,estimated_usd,input_tokens,output_tokens,created_at TEXT NOT NULL,note TEXT'+(',confirmed_usd REAL' if col else '')+')')
            for r in (tuple(x)+(None,)*(7-len(x)) for x in rows): db.execute('INSERT INTO llm_calls VALUES(?,?,?,?,?,?,?,?,?,?,?'+(',?' if col else '')+')', (r[0], r[0], 'p', 'gpt-5.6-luna', *r[1:6], main.now(), None) + ((r[6],) if col else ()))
        app = FastAPI(); llm_guard.register(app, SimpleNamespace(connect=connect))
        self.start = app.router.on_startup[-1]
    def rows(self):
        with self.connect() as db: return {r['id']: dict(r) for r in db.execute('SELECT * FROM llm_calls')}

    def test_B_bad_estimated(self):
        # (id,status,usd,estimated,tin,tout)
        for bad in ('bad', None, -5, float('inf'), 'nan'):
            with self.subTest(est=repr(bad)):
                self.mk([('neg', 'reserved', -.1, bad, None, None), ('negdone', 'done', -.1, bad, None, None),
                         ('cneg', 'done', .1, bad, None, None, -1.0), ('cneg2', 'reserved', .2, bad, None, None, -1.0)], col=True)
                try:
                    self.start(); self.start()
                except Exception as e:
                    self.fail('startup crash: %r' % e)
                print('B', repr(bad), {k: (v['status'], v['usd'], v['confirmed_usd']) for k, v in self.rows().items()})

    def test_B_bad_usd_text(self):
        self.mk([('x', 'reserved', .1, .1, None, None)])
        with self.connect() as db: db.execute("UPDATE llm_calls SET usd='bad' WHERE id='x'")
        try: self.start()
        except Exception as e: self.fail('startup crash on usd=bad: %r' % e)

    def test_B_nan_usd(self):
        self.skipTest('sqlite stores NaN as NULL')
        try: self.start()
        except Exception as e: self.fail('startup crash on usd=nan: %r' % e)
        print('nan usd ->', self.rows())

    def test_R3_all_statuses(self):
        sts = ['reserved', 'submission_unknown', 'done', 'failed', 'released', 'cancelled', 'weird']
        self.mk([(s, s, -.5, .2, 100, 100) for s in sts])
        self.start(); self.start()
        rows = self.rows()
        for s, r in rows.items():
            print('R3', s, r['usd'], r['confirmed_usd'])
            self.assertGreaterEqual(r['usd'], 0); self.assertGreaterEqual(r['confirmed_usd'], 0)
        with self.connect() as db:
            self.assertGreaterEqual(llm_guard.spent(db, 'p')[0], 0)

    def test_C_done_usd_gt_confirmed(self):
        self.mk([('d', 'done', .5, .5, None, None, .1)], col=True)
        self.start(); self.start()
        r = self.rows()['d']
        with self.connect() as db: s = llm_guard.summary(db, {'p'})
        print('C row', r['usd'], r['confirmed_usd'], 'summary', s['usd'], s['confirmed_usd'], s['unknown_usd'], s['unknown_calls'])
        self.assertAlmostEqual(s['usd'], s['confirmed_usd'] + s['unknown_usd'], places=6)

    def test_P2A_tokens(self):
        for v in (1.5, 1e30, float('inf'), float('nan'), -1, True, '12', 120.0):
            print('token_count', repr(v), '->', llm_guard.token_count(v), 'confirmed', llm_guard.confirmed_from_tokens('gpt-5.6-luna', v, 10))
        self.mk([('f', 'submission_unknown', .5, .5, 1.5, 1e30)])
        self.start()
        print('P2A', self.rows()['f'])

class P2ABlast(Legacy):
    def test_huge_legacy_tokens_then_failed_reconcile(self):
        self.mk([('f', 'submission_unknown', .5, .5, 1.5, 1e30)])
        self.start()
        with self.connect() as db:
            row = db.execute('SELECT usd,confirmed_usd FROM llm_calls').fetchone()
            c, u = llm_guard.split_held(row['usd'], row['confirmed_usd'])
        print('P2A blast: confirmed part', c, 'unknown', u, '-> failed-reconcile would set usd =', c)
        self.assertLessEqual(row['confirmed_usd'], row['usd'])
