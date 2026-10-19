"""Isolated SQLite/TestClient regression tests for the QA sandbox adapter."""
import json
import os
import sqlite3
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import qa_text_precheck as qa
from backend import security


class Studio:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()


class QAReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.studio = Studio(str(Path(self.temp.name) / 'qa.sqlite'))
        with self.studio.connect() as db:
            db.executescript('''
                CREATE TABLE projects(id TEXT PRIMARY KEY,state TEXT,revision INTEGER);
                CREATE TABLE productions(id TEXT PRIMARY KEY,source_project_id TEXT);
                CREATE TABLE production_nodes(id TEXT PRIMARY KEY,production_id TEXT,kind TEXT,parent_id TEXT,number INTEGER,notes TEXT);
                CREATE TABLE storyboard_imports(request_id TEXT PRIMARY KEY,series_id TEXT,script TEXT);
                CREATE TABLE production_entity_state(node_id TEXT,data TEXT);
                CREATE TABLE story_plans(series_id TEXT PRIMARY KEY,revision INTEGER,data TEXT);
                CREATE TABLE character_assets(id TEXT,project_id TEXT,character_id TEXT,category TEXT,model_id TEXT,note TEXT,created_at TEXT);
                INSERT INTO productions VALUES('prod','project');
                INSERT INTO production_nodes VALUES('series','prod','series',NULL,1,'A series');
                INSERT INTO storyboard_imports VALUES('imp','series','Грэм подъезжает к аэропорту.');
            ''')
            db.execute('INSERT INTO projects VALUES(?,?,?)', ('project', json.dumps({'characters':[
                {'id':'grem','name':'Грэм','identity':{'hair':'black','hat':'blue'}}]}), 1))
            db.execute('INSERT INTO story_plans VALUES(?,?,?)', ('series',1,json.dumps({
                'source':'Грэм должен встретить гостя.', 'cards':[{'title':'Встреча', 'description':'У аэропорта'}]})))
        self.app = FastAPI()
        qa.register(self.app, self.studio)
        self.ctx = TestClient(self.app, base_url='http://localhost')
        self.ctx.__enter__()
        self.addCleanup(lambda: self.ctx.__exit__(None,None,None))
        self.env = patch.dict(os.environ, {'STUDIO_QA_SANDBOX_TOKEN': 'dev-secret-'*4,
                                           'STUDIO_QA_SANDBOX_PROJECT_ID':'project'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.owners = {'X-Studio-Session': security.LAUNCH_TOKEN}
        self.svc = {'Authorization':'Bearer ' + 'dev-secret-'*4}
        self.url = qa.PREFIX

    def approve(self):
        c=self.ctx.get(self.url+'/contexts/project/prod/series',headers=self.owners)
        self.assertEqual(c.status_code,200,c.text)
        snap=c.json()
        r=self.ctx.post(self.url+'/approvals',json={
            'project_id':'project', 'production_id':'prod', 'series_id':'series',
            'artifact_revision':snap['artifact_revision'], 'brief_revision':snap['brief_revision'],
            'canon_revision':snap['canon_revision'], 'confirm_source_approval':True},headers=self.owners)
        self.assertEqual(r.status_code,200,r.text)
        return r.json()['approval_id']

    def job(self, approval_id=None, key='idempotent-001'):
        approval_id=approval_id or self.approve()
        r=self.ctx.post(self.url+'/jobs',json={'approval_id':approval_id,'idempotency_key':key},headers=self.owners)
        self.assertEqual(r.status_code,200,r.text)
        return r.json()['task_id']

    def claim(self,task_id):
        r=self.ctx.post(self.url+f'/service/jobs/{task_id}/claim',json={'execution_id':'execute-123'},headers=self.svc)
        self.assertEqual(r.status_code,200,r.text)

    def verdict(self,task,role,outcome='PASS',dry_run=False,**changes):
        p=self.ctx.get(self.url+f'/service/jobs/{task}/packet/{role}',headers=self.svc).json()
        text=p['artifact_text']; quote=text[0:4]
        evidence=[{'scope':'TEXT','evidence_type':'text_quote','source_kind':'artifact',
                   'source_text_revision':p['text_sha256'],'quote':quote,
                   'start':0,'end':4,'observation':'Verified excerpt'}]
        body={'role':role,'task_id':task,'project_id':'project','artifact_id':'series',
              'artifact_revision':p['artifact_revision'],'review_round':1,
              'requested_scopes':['TEXT'], 'checked_scopes':['TEXT'] if outcome!='BLOCKED' else [],
              'scope_results':{'TEXT':outcome}, 'verdict':outcome,
              'evidence':evidence if outcome!='BLOCKED' else [],
              'missing_inputs':['source unavailable'] if outcome=='BLOCKED' else [],
              'biggest_gap':'Wrong specification' if outcome=='FAIL' else None,
              'model_used':qa.ROLE_MODELS[role], 'estimated_cost_usd':0,
              'actual_cost_usd':0,'event_id':'evt-'+role,'execution_id':'execute-123',**changes}
        return body if dry_run else self.ctx.post(self.url+f'/service/jobs/{task}/verdict',json=body,headers=self.svc)

    def test_approval_not_from_service_or_untrusted_flag(self):
        p=self.ctx.get(self.url+'/contexts/project/prod/series')
        self.assertEqual(p.status_code,401)
        p=self.ctx.get(self.url+'/contexts/project/prod/series',headers=self.owners)
        self.assertFalse(p.json()['approved'])
        b=p.json()
        data={'project_id':'project','production_id':'prod','series_id':'series',
              'artifact_revision':b['artifact_revision'], 'brief_revision':b['brief_revision'],
              'canon_revision':b['canon_revision'], 'confirm_source_approval':True}
        self.assertEqual(self.ctx.post(self.url+'/approvals',json=data,headers=self.svc).status_code,401)
        self.assertEqual(self.ctx.post(self.url+'/approvals',json={**data,'approved_expert_model':True},headers=self.owners).status_code,422)
        self.assertEqual(self.ctx.post(self.url+'/approvals',json=data,headers=self.owners).status_code,200)

    def test_independent_role_packages_and_mock_pass(self):
        task=self.job();self.claim(task)
        a=self.ctx.get(self.url+f'/service/jobs/{task}/packet/REVIEW-REQ',headers=self.svc).json()
        b=self.ctx.get(self.url+f'/service/jobs/{task}/packet/REVIEW-SYSTEM',headers=self.svc).json()
        self.assertIn('approved_requirements',a);self.assertNotIn('approved_canon',a)
        self.assertIn('approved_canon',b);self.assertNotIn('approved_requirements',b)
        self.assertEqual(self.verdict(task,'REVIEW-REQ').status_code,200)
        done=self.verdict(task,'REVIEW-SYSTEM');self.assertEqual(done.status_code,200,done.text)
        self.assertEqual(done.json()['status'],'SANDBOX_TEXT_PRECHECK_PASSED_AWAITING_OWNER')
        self.assertFalse(done.json()['text_precheck_passed'])
        self.assertFalse(done.json()['all_passed'])
        self.assertFalse(done.json()['final_release_approved'])

    def test_fail_and_blocked_status(self):
        task=self.job();self.claim(task)
        self.assertEqual(self.verdict(task,'REVIEW-REQ','FAIL').status_code,200)
        self.assertEqual(self.verdict(task,'REVIEW-SYSTEM').json()['status'],'CHANGES_REQUESTED')
        task=self.job(key='another-job-123');self.claim(task)
        self.assertEqual(self.verdict(task,'REVIEW-REQ','BLOCKED').status_code,200)
        self.assertEqual(self.verdict(task,'REVIEW-SYSTEM').json()['status'],'BLOCKED')

    def test_forged_citations_and_media_scope_rejected(self):
        task=self.job();self.claim(task)
        self.assertEqual(self.verdict(task,'REVIEW-REQ', evidence=[{'scope':'TEXT','evidence_type':'text_quote',
          'source_kind':'artifact', 'source_text_revision':'0'*64,'quote':'Подлог',
          'start':0,'end':6,'observation':'fake'}]).status_code,422)
        self.assertEqual(self.verdict(task,'REVIEW-REQ', requested_scopes=['TEXT','IMAGE']).status_code,422)
        self.assertEqual(self.verdict(task,'REVIEW-REQ', checked_scopes=['IMAGE']).status_code,422)
        self.assertEqual(self.verdict(task,'REVIEW-REQ').status_code,200)

    def test_stale_revisions_and_idempotency(self):
        approval=self.approve()
        task=self.job(approval)
        self.assertEqual(self.job(approval),task)
        other=self.approve()
        self.assertEqual(self.ctx.post(self.url+'/jobs',json={'approval_id':other,'idempotency_key':'idempotent-001'},headers=self.owners).status_code,409)
        self.claim(task)
        self.assertEqual(self.verdict(task,'REVIEW-REQ').status_code,200)
        self.assertEqual(self.verdict(task,'REVIEW-REQ').status_code,200)
        self.assertEqual(self.verdict(task,'REVIEW-REQ',event_id='changed-event-1').status_code,409)
        stale_payload=self.verdict(task,'REVIEW-SYSTEM',dry_run=True)
        with self.studio.connect() as db:
            db.execute("UPDATE storyboard_imports SET script='Новая редакция' WHERE series_id='series'")
        self.assertEqual(self.ctx.post(self.url+f'/service/jobs/{task}/verdict',json=stale_payload,headers=self.svc).status_code,409)
        with self.studio.connect() as db:
            db.execute('SELECT COUNT(*) FROM qa_text_verdicts').fetchone()
            self.assertEqual(db.execute('SELECT count(*) FROM qa_text_verdicts').fetchone()[0],1)

    def test_missing_approved_sources_and_project_isolation(self):
        with self.studio.connect() as db:
            db.execute('DELETE FROM story_plans')
        self.assertEqual(self.ctx.get(self.url+'/contexts/project/prod/series',headers=self.owners).status_code,409)
        with self.studio.connect() as db:
            db.execute('INSERT INTO story_plans VALUES(?,?,?)',('series',1,json.dumps({'source':'brief'})))
        task=self.job()
        self.assertEqual(self.ctx.get(self.url+'/service/queue',headers={'Authorization':'Bearer wrong'}).status_code,401)
        with patch.dict(os.environ,{'STUDIO_QA_SANDBOX_PROJECT_ID':'other'}):
            self.assertEqual(self.ctx.post(self.url+f'/service/jobs/{task}/claim',json={'execution_id':'x'},headers=self.svc).status_code,404)
        self.assertEqual(self.ctx.post(self.url+'/jobs',json={'approval_id':'no-such-id','idempotency_key':'another-key-123'},headers=self.owners).status_code,404)

    def test_sandbox_service_is_local_only_and_fails_closed(self):
        task=self.job()
        with patch.dict(os.environ, {'STUDIO_QA_SANDBOX_TOKEN':''}):
            self.assertEqual(self.ctx.get(self.url+'/service/queue',headers=self.svc).status_code,503)
        with TestClient(self.app, base_url='http://example.com') as remote:
            self.assertEqual(remote.get(self.url+'/service/queue',headers=self.svc).status_code,403)
        self.claim(task)
        blocked=self.ctx.post(self.url+f'/service/jobs/{task}/block',headers=self.svc,
            json={'execution_id':'execute-123','error_code':'REVIEWER_UNAVAILABLE'})
        self.assertEqual(blocked.status_code,200,blocked.text)
        self.assertEqual(blocked.json()['status'],'BLOCKED')
        self.assertEqual(blocked.json()['error_code'],'REVIEWER_UNAVAILABLE')
        self.assertEqual(self.ctx.post(self.url+f'/service/jobs/{task}/block',headers=self.svc,
            json={'execution_id':'execute-123','error_code':'REVIEWER_UNAVAILABLE'}).status_code,200)
        self.assertNotIn(task,self.ctx.get(self.url+'/service/queue',headers=self.svc).json()['task_ids'])

    def test_owner_cancel_and_no_claim_after_cancel(self):
        task=self.job()
        c=self.ctx.post(self.url+f'/jobs/{task}/cancel',headers=self.owners)
        self.assertEqual(c.status_code,200,c.text)
        self.assertEqual(c.json()['status'],'CANCELLED')
        self.assertEqual(self.ctx.post(self.url+f'/service/jobs/{task}/claim',headers=self.svc,
            json={'execution_id':'execute-123'}).status_code,409)

    def test_concurrent_claim_and_injection_rejection(self):
        task=self.job()
        def attempt(execution):
            return self.ctx.post(self.url+f'/service/jobs/{task}/claim',headers=self.svc,
                                 json={'execution_id':execution}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(attempt,['execute-a','execute-b']))
        self.assertEqual(sorted(results),[200,409])
        self.assertEqual(self.ctx.post(self.url+f'/jobs/{task}/cancel',headers=self.svc).status_code,401)
        self.assertEqual(self.ctx.post(self.url+'/jobs',headers=self.owners,json={
            'approval_id':self.approve(),'idempotency_key':'idempotent-002',
            'review_phase':'FINAL_MEDIA'}).status_code,422)
        self.assertEqual(self.ctx.post(self.url+'/jobs',headers=self.owners,json={
            'approval_id':self.approve(),'idempotency_key':'idempotent-003',
            'requested_scopes':['TEXT','IMAGE']}).status_code,422)

    def test_no_generation_or_canon_write(self):
        self.job();self.job(key='second-job-123')
        with self.studio.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM qa_text_jobs').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT revision FROM projects WHERE id=?',('project',)).fetchone()[0],1)
            self.assertEqual(db.execute('SELECT script FROM storyboard_imports').fetchone()[0],'Грэм подъезжает к аэропорту.')


if __name__=='__main__':
    unittest.main()