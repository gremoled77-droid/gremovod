import unittest, traceback
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from backend import main, llm_guard, security, spend_ledger, test_smoke

def attempt(label, fn):
    try:
        r = fn()
        body = getattr(r, 'text', r)
        print('  %-28s -> %s %s' % (label, getattr(r, 'status_code', 'ok'), str(body)[:170].replace('\n', ' ')))
        return r
    except Exception as e:
        print('  %-28s -> EXCEPTION %s: %s' % (label, type(e).__name__, str(e)[:120]))
        return e

class Unreadable(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown
    image_request = test_smoke.StudioSmokeTests.image_request

    def seed(self, day_shift):
        self.A = self.client.post('/api/projects', json={'title': 'A-unreadable', 'state': {}}).json()['id']
        self.B = self.client.post('/api/projects', json={'title': 'B-normal', 'state': {}}).json()['id']
        main.PIAPI_KEY_FILE.write_text('test-key', encoding='utf-8')
        created = (datetime.now(timezone.utc) - timedelta(days=day_shift)).isoformat()
        with main.connect() as db:
            cols = [r[1] for r in db.execute('PRAGMA table_info(llm_calls)')]
            vals = {'id': 'u1', 'request_id': 'u1req0001', 'project_id': self.A, 'model': 'gpt-5.6-luna', 'status': 'submission_unknown',
                    'usd': llm_guard.UNREADABLE_AMOUNT, 'estimated_usd': 0.3, 'input_tokens': None, 'output_tokens': None,
                    'created_at': created, 'note': 'OWNER_DECISION_REQUIRED', 'confirmed_usd': 0.0}
            use = [c for c in cols if c in vals]
            db.execute('INSERT INTO llm_calls(%s) VALUES(%s)' % (','.join(use), ','.join('?' * len(use))), [vals[c] for c in use])

    def agents(self, pid, rid):
        body = {'project_id': pid, 'brief': 'Грэм едет ночью', 'model': 'gpt-5.6-luna', 'provider': '', 'target_models': ['seedream-5-pro']}
        q = self.client.post('/api/agents/estimate', json=body)
        if q.status_code != 200: return q
        main.agent_completion.side_effect = None
        main.agent_completion.return_value = ('ok', {'prompt_tokens': 10, 'completion_tokens': 5})
        return self.client.post('/api/agents/run', json={**body, 'approved': True, 'quote_token': q.json()['quote_token'], 'max_cost_usd': q.json()['estimated_usd'], 'request_id': rid})

    def media(self, pid, rid):
        main.PIAPI_KEY_FILE.write_text('k', encoding='utf-8')
        body = {'project_id': pid, 'model_id': 'seedream-5-lite', 'prompt': 'x', 'request_id': rid, 'approved': True, 'max_cost_usd': 0.052}
        est = self.client.post('/api/model-jobs/estimate', json=body)
        if est.status_code != 200: return est
        body['quote_token'] = est.json()['quote_token']
        main.request_piapi.side_effect = main.HTTPException(502, 'REACHED_PROVIDER')
        return self.client.post('/api/model-jobs', json=body)

    def scenario(self, shift):
        print('\n=== unreadable row created %s ===' % ('TODAY' if shift == 0 else 'yesterday'))
        self.seed(shift)
        for name, pid in (('A(unreadable)', self.A), ('B(normal)', self.B)):
            print(name)
            attempt('GET /api/budgets', lambda: self.client.get('/api/budgets/' + pid))
            attempt('GET /api/economics', lambda: (lambda j: {'llm_usd': j['llm']['usd'], 'unreadable_calls': j['llm'].get('unreadable_calls'), 'costs_complete': j['costs_complete'], 'llm_calls_unpriced': j['llm_calls_unpriced']})(self.client.get('/api/economics', params={'project_id': pid}).json()))
            attempt('agents estimate+run (LLM)', lambda: self.agents(pid, 'agents-' + name[:1] + str(shift) + '-0001'))
            attempt('model-jobs (media)', lambda: self.media(pid, 'request-id-' + name[:1] + str(shift) + '-123456789'))
            def direct():
                with main.connect() as db: security.check_budget(db, pid, 0.01); return 'check_budget passed'
            attempt('security.check_budget', direct)
            def st():
                with main.connect() as db: return spend_ledger.state(db, pid)
            attempt('spend_ledger.state', st)
            def sm():
                with main.connect() as db: s = llm_guard.summary(db, {pid}); return {k: s[k] for k in ('calls','usd','unknown_calls','unreadable_calls')}
            attempt('llm_guard.summary', sm)
        with main.connect() as db:
            s = llm_guard.summary(db)
        print('GLOBAL summary', {k: s[k] for k in ('calls', 'usd', 'today_usd', 'unreadable_calls')})

    def test_today(self): self.scenario(0)
    def test_old(self): self.scenario(3)

if __name__ == '__main__':
    unittest.main()
