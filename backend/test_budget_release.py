import json
import unittest
from backend import main, security
from backend import test_smoke

UPSTREAM_FAILED_FREE = {'code': 200, 'data': {'status': 'failed', 'error': {'code': 10003, 'message': 'Invalid input.'},
                                              'meta': {'usage': {'type': 'point', 'frozen': 0, 'consume': 0}}}}
UPSTREAM_FAILED_CHARGED = {'code': 200, 'data': {'status': 'failed', 'meta': {'usage': {'consume': 30000}}}}
UPSTREAM_FAILED_UNKNOWN = {'code': 200, 'data': {'status': 'failed'}}
REJECTED_BEFORE_TASK = {'detail': 'Провайдер отклонил заявку'}


class ReleasedTests(unittest.TestCase):
    def test_free_failures_release_the_reserve(self):
        self.assertTrue(security.released('failed', json.dumps(UPSTREAM_FAILED_FREE)))
        self.assertTrue(security.released('failed', json.dumps(REJECTED_BEFORE_TASK)))
        self.assertTrue(security.released('cancelled', json.dumps(UPSTREAM_FAILED_FREE)))

    def test_charged_or_unclear_jobs_keep_the_reserve(self):
        self.assertFalse(security.released('failed', json.dumps(UPSTREAM_FAILED_CHARGED)))
        self.assertFalse(security.released('failed', json.dumps(UPSTREAM_FAILED_UNKNOWN)))
        self.assertFalse(security.released('failed', '{}'))
        self.assertFalse(security.released('failed', 'not json'))
        self.assertFalse(security.released('failed', json.dumps({'data': {'meta': {'usage': {'consume': True}}}})))

    def test_live_and_finished_jobs_keep_the_reserve(self):
        for status in ('submitting', 'submission_unknown', 'pending', 'processing', 'completed'):
            self.assertFalse(security.released(status, json.dumps(UPSTREAM_FAILED_FREE)), status)


class BudgetReleaseTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def test_failed_free_job_no_longer_blocks_the_project_budget(self):
        with main.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS spending_limits(id INTEGER PRIMARY KEY,project_usd REAL NOT NULL,daily_usd REAL NOT NULL)')
            db.execute('INSERT OR REPLACE INTO spending_limits(id,project_usd,daily_usd) VALUES(1,1,2)')
            project = 'budget-release-project'
            rows = [('free-failed', 'failed', UPSTREAM_FAILED_FREE, 0.6), ('charged-failed', 'failed', UPSTREAM_FAILED_CHARGED, 0.3)]
            for job, status, response, cost in rows:
                db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)', (job, project, 'video', 'piapi', 'task', status, '{}', json.dumps(response), main.now()))
                db.execute('INSERT INTO generation_approvals VALUES(?,?,?,?,?)', (job, cost, cost, main.now(), 'documentation_estimate'))
            try:
                state = security.budget_state(db, project)
                self.assertAlmostEqual(state['project_reserved_usd'], 0.3)
                self.assertAlmostEqual(state['daily_reserved_usd'], 0.3, places=6)
                security.check_budget(db, project, 0.6)
                with self.assertRaises(main.HTTPException):
                    security.check_budget(db, project, 0.8)
            finally:
                for job, *_ in rows:
                    db.execute('DELETE FROM generation_approvals WHERE job_id=?', (job,))
                    db.execute('DELETE FROM jobs WHERE id=?', (job,))


if __name__ == '__main__':
    unittest.main()
