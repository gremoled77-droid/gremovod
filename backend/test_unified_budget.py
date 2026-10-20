"""Единый счётчик денег студии: медиа + платные LLM-вызовы + P0-конверты + перерасход.

Дефект, который закрывает файл: у каждой стороны был свой «единый счётчик».
Медиа-контур считал одобрения Studio и платные LLM-вызовы, P0-контур — одобрения
Studio и конверты. Ни одна сторона не считала всё, поэтому лимит проекта можно было
превышить дважды: один раз мимо LLM, второй раз мимо конвертов.

Каждый тест называет свой счётчик и проверяет, что в общей сумме он виден.
"""
import json
import unittest
from datetime import datetime, timedelta, timezone

from backend import llm_guard, p0_authz, security, spend_ledger
from backend import test_p0_control as fixtures

MOSCOW = timezone(timedelta(hours=3))


class UnifiedBudgetTests(unittest.TestCase):
    """Общий счётчик: media + LLM + P0-конверты + перерасход считаются вместе."""

    def setUp(self):
        p0_authz.allow_ephemeral_key()
        self.fixture = fixtures.P0SafetyTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db = self.fixture.db
        self.db.execute('UPDATE spending_limits SET project_usd=10,daily_usd=10')
        self._legacy_tables()
        self._llm_table()

    # ------------------------------------------------------------- helpers

    def _legacy_tables(self):
        """Форма настоящей таблицы jobs студии: одобрение медиа держит бюджет."""
        self.db.execute('DROP TABLE IF EXISTS jobs')
        self.db.execute('CREATE TABLE jobs(id TEXT PRIMARY KEY, project_id TEXT, kind TEXT,'
                        ' provider TEXT, task_id TEXT, status TEXT, request TEXT, response TEXT, created_at TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS generation_approvals(job_id TEXT PRIMARY KEY,'
                        ' estimated_usd REAL, actual_usd REAL, created_at TEXT, note TEXT)')

    def _media(self, project, usd, name='media-1', status='completed', created=None):
        created = created or datetime.now(MOSCOW).isoformat()
        self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',
                        (name, project, 'video', 'piapi', 'task', status, '{}', json.dumps({}), created))
        self.db.execute('INSERT INTO generation_approvals VALUES(?,?,?,?,?)',
                        (name, usd, usd, created, 'documentation_estimate'))

    def _llm_table(self):
        self.db.execute('''CREATE TABLE IF NOT EXISTS llm_calls(id TEXT PRIMARY KEY,request_id TEXT UNIQUE,
            project_id TEXT NOT NULL,model TEXT NOT NULL,status TEXT NOT NULL,usd REAL NOT NULL,
            estimated_usd REAL NOT NULL,input_tokens INTEGER,output_tokens INTEGER,created_at TEXT NOT NULL)''')

    def _llm(self, project, usd, status='done', name='call-1', created=None):
        created = created or datetime.now(MOSCOW).isoformat()
        self.db.execute('INSERT INTO llm_calls(id,request_id,project_id,model,status,usd,estimated_usd,created_at)'
                        ' VALUES(?,?,?,?,?,?,?,?)',
                        (name, name, project, 'gpt-5.6-luna', status, usd, usd, created))

    # --------------------------------------------------------------- tests

    def test_llm_spend_is_counted_next_to_media_and_p0_envelopes(self):
        """LLM-расход должен попадать в тот же счётчик, что медиа и конверты."""
        self._media('proj', 0.25)
        self._llm('proj', 0.02)
        self.fixture.intent()
        self.fixture.auth(cents=100)
        state = spend_ledger.state(self.db, 'proj')
        self.assertAlmostEqual(state['media_reserved_usd'], 0.25)
        self.assertAlmostEqual(state['llm_reserved_usd'], 0.02)
        self.assertAlmostEqual(state['p0_reserved_usd'], 1.0)
        self.assertAlmostEqual(state['project_reserved_usd'], 1.27)

    def test_security_budget_state_is_the_same_counter_as_the_ledger(self):
        """Два ответа на вопрос «сколько занято» — это два источника истины."""
        self._media('proj', 0.25)
        self._llm('proj', 0.02)
        state = security.budget_state(self.db, 'proj')
        self.assertAlmostEqual(state['project_reserved_usd'], 0.27)
        self.assertAlmostEqual(state['llm_reserved_usd'], 0.02)

    def test_failed_llm_call_does_not_hold_the_budget(self):
        """Провайдер отклонил вызов и ничего не списал — резерв снят."""
        self._llm('proj', 0.02, status='failed', name='call-failed')
        state = spend_ledger.state(self.db, 'proj')
        self.assertAlmostEqual(state['llm_reserved_usd'], 0.0)

    def test_unknown_llm_call_keeps_holding_the_budget(self):
        """Неопределённый исход держит резерв до сверки."""
        self._llm('proj', 0.02, status='submission_unknown', name='call-unknown')
        state = spend_ledger.state(self.db, 'proj')
        self.assertAlmostEqual(state['llm_reserved_usd'], 0.02)

    def test_missing_llm_calls_table_does_not_break_the_counter(self):
        """База, в которой таблицы llm_calls ещё нет, — не ошибка, а ноль."""
        self.db.execute('DROP TABLE IF EXISTS llm_calls')
        state = spend_ledger.state(self.db, 'proj')
        self.assertAlmostEqual(state['llm_reserved_usd'], 0.0)
        self.assertAlmostEqual(state['project_reserved_usd'], 0.0)

    def test_llm_money_from_yesterday_is_not_counted_today(self):
        """Дневной лимит считает московский день, проектный — все дни."""
        yesterday = (datetime.now(MOSCOW) - timedelta(days=1)).isoformat()
        self._llm('proj', 0.02, name='call-yesterday', created=yesterday)
        state = spend_ledger.state(self.db, 'proj')
        self.assertAlmostEqual(state['project_reserved_usd'], 0.02)
        self.assertAlmostEqual(state['daily_reserved_usd'], 0.0)

    def test_budget_barrier_counts_llm_money_too(self):
        """Лимит проекта нельзя обойти, потратив деньги на LLM."""
        self.db.execute('UPDATE spending_limits SET project_usd=0.05,daily_usd=0.05')
        self._media('proj', 0.04)
        self._llm('proj', 0.02)
        with self.assertRaises(Exception):
            spend_ledger.check(self.db, 'proj', 0.01)

    def test_timestamp_without_timezone_is_counted_as_studio_time(self):
        """Метка без часового пояса — это время студии, а не время машины."""
        naive = datetime.now(MOSCOW).replace(tzinfo=None).isoformat()
        self._llm('proj', 0.02, name='call-naive', created=naive)
        state = spend_ledger.state(self.db, 'proj')
        self.assertAlmostEqual(state['daily_reserved_usd'], 0.02)

    def test_llm_holding_statuses_have_one_source(self):
        """Статусы, удерживающие резерв, не должны расходиться в двух местах."""
        self.assertEqual(llm_guard.HOLDING_STATUSES, spend_ledger.LLM_HOLDING_STATUSES)


if __name__ == '__main__':
    unittest.main()
