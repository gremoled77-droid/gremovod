"""O7: барьер R3 fail-closed и без repair_legacy_money на старте (ремонт отключён)."""
import unittest
from unittest.mock import patch
from backend import llm_guard, main, test_smoke


class BarrierWithoutRepair(unittest.TestCase):
    def setUp(self):
        self.p = patch.object(llm_guard, 'repair_legacy_money', lambda db: 0)
        self.p.start()
        test_smoke.StudioSmokeTests.setUp(self)

    def tearDown(self):
        test_smoke.StudioSmokeTests.tearDown(self)
        self.p.stop()

    def test_negative_and_text_amounts_block_without_repair(self):
        for usd in (-0.14, 'bad', float('inf')):
            pid = self.client.post('/api/projects', json={'title': 'P', 'state': {}}).json()['id']
            with main.connect() as db:
                db.execute("INSERT INTO llm_calls(id,request_id,project_id,model,status,usd,estimated_usd,created_at,confirmed_usd) "
                           "VALUES(?,?,?,?,?,?,?,?,0)", ('x' + pid, 'r' + pid, pid, 'gpt-5.6-luna', 'done', usd, 0.1,
                                                        '2026-10-01T10:00:00+00:00'))
                with self.assertRaises(main.HTTPException) as caught:
                    llm_guard.check_budget(db, pid, 0.01)
                with self.assertRaises(main.HTTPException) as caught2:
                    main.security.check_budget(db, pid, 0.01)
            eco = self.client.get('/api/economics', params={'project_id': pid}).json()
            print(repr(usd), caught.exception.status_code, caught2.exception.status_code,
                  'costs_complete=', eco['costs_complete'], 'unreadable=', eco['llm_unreadable_calls'])
            self.assertFalse(eco['costs_complete'])


if __name__ == '__main__':
    unittest.main()
