import json
import sqlite3
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from backend import llm_guard, main, test_llm_settlement

def emit(case, **data):
    print(json.dumps({"case": case, **data}, ensure_ascii=False))

test = test_llm_settlement.LlmSettlementTests()
test.setUp()
try:
    test.prepare()
    spec = {'project_id':test.pid, 'stage':{'id':'story','revision':'r1','instruction':'Write scene'},
            'model':'minimax-m2.1','inputs':[{'id':'brief','content':'Synthetic brief','approved':True}],
            'skills':[],'max_tokens':500,'response_format':'text','request_id':'review-task-lifecycle-1'}
    with patch.object(main, 'request_piapi', AsyncMock()) as provider:
        try:
            test.client.post('/api/llm/tasks', json=spec)
            raise AssertionError('Unexpected functional Task API')
        except NameError as exc:
            emit('unpatched_task_prepare', error=type(exc).__name__, message=str(exc), submits=provider.await_count)
            assert 'task_identity' in str(exc) and provider.await_count == 0
    q = test.quote()
    body = dict(provider='piapi', project_id=test.pid, model='gpt-5.6-luna', messages=test.messages,
                max_tokens=500, approved=True, quote_token=q['quote_token'], max_cost_usd=q['estimated_usd'],
                request_id='review-contradiction-1')
    value = {'usage': {'prompt_tokens': 120, 'completion_tokens': 40, 'total_tokens': 0}}
    with patch.object(main, 'request_piapi', AsyncMock(return_value=value)) as provider:
        result = test.client.post('/api/llm/chat', json=body)
    row = dict(test.call_row(body['request_id']))
    emit('contradictory_usage_parse_failure', http=result.status_code, ledger=row, submits=provider.await_count)
    assert row['status'] == 'failed' and row['usd'] == 0
finally:
    test.tearDown()

test = test_llm_settlement.AgentsReconcileTests()
test.setUp()
try:
    test.prepare()
    good = {'prompt_tokens': 120, 'completion_tokens': 40}
    result, _ = test.run_agents('review-reconcile-1', [('a', good), ('b', {}), ('c', good)])
    before = dict(test.split_row())
    response = test.reconcile(before['id'], {'outcome': 'done', 'unconfirmed_usd': 0.001, 'note': 'review manual fact'})
    with main.connect() as db:
        report = llm_guard.summary(db, {test.pid})
    emit('manual_reconcile_confirmed_report', before=before, response=response.json(), summary=report)
    assert response.json()['usd'] > response.json()['confirmed_usd'] and report['unknown_calls'] == 0
finally:
    test.tearDown()

for malformed in (False, True, 'fault'):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / 'old.sqlite3'
        @contextmanager
        def connect():
            db = sqlite3.connect(path)
            db.row_factory = sqlite3.Row
            try:
                with db:
                    yield db
            finally:
                db.close()
        with connect() as db:
            db.execute('CREATE TABLE llm_calls(id TEXT PRIMARY KEY,request_id TEXT UNIQUE,project_id TEXT NOT NULL,model TEXT NOT NULL,status TEXT NOT NULL,usd REAL NOT NULL,estimated_usd REAL NOT NULL,input_tokens INTEGER,output_tokens INTEGER,created_at TEXT NOT NULL,note TEXT)')
            for row in [('done', 'done', 0.03, 120, 40), ('unknown', 'submission_unknown', 0.1, 'bad' if malformed is True else 240, 80), ('reserved', 'reserved', 0.1, None, None), ('failed', 'failed', 0.0, None, None), ('legacy-negative', 'done', -0.14, -1000000, -1000000)]:
                ident, status, usd, ti, to = row
                db.execute('INSERT INTO llm_calls VALUES(?,?,?,?,?,?,?,?,?,?,?)', (ident, ident, 'p', 'gpt-5.6-luna', status, usd, .1, ti, to, main.now(), None))
        app = FastAPI()
        llm_guard.register(app, SimpleNamespace(connect=connect))
        setup = app.router.on_startup[-1]
        error = None
        try:
            if malformed == 'fault':
                with patch.object(llm_guard, 'confirmed_from_tokens', side_effect=sqlite3.OperationalError('injected migration interruption')):
                    setup()
            else:
                setup()
        except Exception as exc:
            error = type(exc).__name__
        setup()  # Reopen/startup must not silently leave a partial migration.
        with connect() as db:
            rows = [dict(r) for r in db.execute('SELECT id,status,usd,confirmed_usd FROM llm_calls')]
        emit('legacy_migration_' + ('fault' if malformed == 'fault' else 'invalid' if malformed else 'normal'), first_error=error, after_second_startup=rows)
        if malformed:
            assert error == ('OperationalError' if malformed == 'fault' else 'TypeError') and all(r['confirmed_usd'] is None for r in rows)
        else:
            assert rows[0]['confirmed_usd'] == .03 and rows[1]['confirmed_usd'] > 0
            with connect() as db:
                ledger = llm_guard.spent(db, 'p')
            emit('legacy_negative_budget_after_upgrade', spent=ledger)
            assert rows[-1]['confirmed_usd'] == -.14 and ledger[0] < .23

try:
    llm_guard.settle_from_usage(float('nan'), 1, {'prompt_tokens': 1, 'completion_tokens': 1}, .1)
except Exception as exc:
    emit('nonfinite_price', error=type(exc).__name__, message=str(exc))
    assert isinstance(exc, TypeError)
