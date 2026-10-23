"""Local integration checks: temporary SQLite/media, forbidden external calls."""
import tempfile
import unittest
import shutil
import wave
import io
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from backend import main
from backend import connections, image_assets, native_chat, job_delivery, reference_upload, kie
import httpx
from PIL import Image


class StudioSmokeTests(unittest.TestCase):
    def setUp(self):
        self.free_upload_impl=reference_upload.upload_free
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = [patch.object(main, 'DB', root/'studio.sqlite3'),
                        patch.object(main,'PRODUCTIONS_ROOT',root/'projects'),
                        patch.object(job_delivery,'ENABLED',False),
                        patch.object(main,'OUTPUT_LOCKS',{}),
                        patch.object(reference_upload,'LOCKS',{}),
                        patch.object(reference_upload,'upload',AsyncMock(side_effect=AssertionError('External upload forbidden'))),
                        patch.object(reference_upload,'upload_free',AsyncMock(side_effect=AssertionError('External free upload forbidden'))),
                        patch.object(native_chat, 'RUNTIME', root/'prompt-chat'),
                        patch.object(main, 'PIAPI_KEY_FILE', root/'PIAPI_API_KEY.txt'),
                        patch.object(main, 'CHAR_ROOT', root/'characters'),
                        patch.object(main, 'MEDIA', root/'media'),
                        patch.object(main, 'LIBRARY_ROOT', root/'library'),
                        patch.object(connections, 'ROOT', root),
                        patch.object(connections, 'ELEVENLABS_LEGACY_FILE', root/'legacy-key.txt'),
                        patch.object(connections, 'KIE_DPAPI_FILES', []),
                        patch.object(kie, 'request', AsyncMock(side_effect=AssertionError('External KIE forbidden'))),
                        patch.object(connections, 'CHECKS', {}),
                        patch.dict(main.os.environ, {p['env']:'' for p in connections.PROVIDERS.values()}),
                        patch.object(main, 'request_piapi', AsyncMock(side_effect=AssertionError('External API forbidden'))),
                        patch.object(main, 'agent_completion', AsyncMock(side_effect=AssertionError('External API forbidden')))]
        for item in self.patches: item.start()
        self.client = TestClient(main.app,base_url="http://127.0.0.1")
        self.client.__enter__()
        self.client.headers["X-Studio-Session"]=self.client.get("/api/session").json()["token"]

    def tearDown(self):
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches): item.stop()
        self.temp.cleanup()

    def test_health_and_diagnostics(self):
        self.assertTrue(self.client.get('/api/health').json()['ok'])
        self.assertIn('sqlite', self.client.get('/api/diagnostics').json())

    def test_stale_project_save_preserves_server_prompt_and_character_version(self):
        initial=self.client.post('/api/projects',json={'title':'Original','state':{'prompts':{},'characters':[]}}).json()
        pid=initial['id']
        with main.connect() as db:
            db.execute('UPDATE projects SET state=? WHERE id=?',(json.dumps({'prompts':{'gpt-image-2.5':'New server prompt'},'characters':[{'id':'grem','working_asset_id':'new-image'}]}),pid))
        stale=self.client.post('/api/projects',json={'id':pid,'title':'Stale','state':{'prompts':{}},'base_revision':initial['revision']})
        self.assertEqual(stale.status_code,409)
        self.assertEqual(stale.json()['detail']['code'],'PROJECT_CONFLICT')
        latest=self.client.get('/api/projects/'+pid).json()
        self.assertEqual(latest['title'],'Original')
        self.assertEqual(latest['state']['prompts']['gpt-image-2.5'],'New server prompt')
        self.assertEqual(latest['state']['characters'][0]['working_asset_id'],'new-image')
        self.assertGreater(latest['revision'],initial['revision'])
        self.assertEqual(self.client.post('/api/projects',json={'id':pid,'state':{}}).status_code,409)
        good=self.client.post('/api/projects',json={'id':pid,'title':'Updated','state':latest['state'],'base_revision':latest['revision']})
        self.assertEqual(good.status_code,200)
        self.assertGreater(good.json()['revision'],latest['revision'])

    def test_hardening_host_parsing_and_sqlite_settings(self):
        for value in ('evil.example','127.0.0.1@evil.example','localhost:bad','localhost/extra','localhost:70000','[::1'):
            self.assertEqual(self.client.get('/api/health',headers={'Host':value}).status_code,403,value)
        for value in ('127.0.0.1:8000','localhost:5173','[::1]:8000'):
            self.assertEqual(self.client.get('/api/health',headers={'Host':value}).status_code,200,value)
        with main.connect() as db:
            self.assertEqual(db.execute('PRAGMA foreign_keys').fetchone()[0],1)
            self.assertEqual(db.execute('PRAGMA busy_timeout').fetchone()[0],10000)

    def test_economics_separates_unpriced_prompts_without_claiming_full_total(self):
        pid=self.client.post('/api/projects',json={'state':{}}).json()['id']
        prompt_id='offline-priced-prompt'
        with main.connect() as db:
            db.execute('INSERT INTO prompt_versions VALUES(?,?,?,?,?,?,?,?,?,?)',(prompt_id,pid,'seedream-5-lite','A portrait','{}','piapi','test-model','{}',main.RULES_VERSION,main.now()))
        report=self.client.get('/api/economics',params={'project_id':pid}).json()
        self.assertTrue(report['media_costs_complete'])
        self.assertFalse(report['costs_complete'])
        self.assertEqual(report['llm_calls_unpriced'],1)
        self.assertEqual(report['unknown_generation_cost_count'],0)
        self.client.put('/api/economics/jobs/'+prompt_id,json={'actual_usd':0.012,'note':'Offline test price'})
        report=self.client.get('/api/economics',params={'project_id':pid}).json()
        self.assertTrue(report['costs_complete'])
        self.assertEqual(report['llm_calls_unpriced'],0)
        self.assertAlmostEqual(report['actual_usd_known'],0.012)

    def test_recover_unknown_submission_only_reads_and_never_pays_twice(self):
        body=self.image_request()
        main.request_piapi.side_effect=main.HTTPException(502,'Response lost')
        self.assertEqual(self.client.post('/api/model-jobs',json=body).status_code,502)
        payload=main.image_payload(main.ModelJobRequest(**body))
        result={'data':{'task_id':'existing-task','model':payload['model'],'task_type':payload['task_type'],'input':payload['input'],'status':'completed','output':{'image_url':'https://cdn.example.test/recovered.png'}}}
        main.request_piapi.side_effect=None;main.request_piapi.return_value=result
        route='/api/jobs/'+body['request_id']+'/recover'
        preview=self.client.post(route,json={'task_id':'existing-task'})
        self.assertEqual(preview.status_code,200,preview.text)
        self.assertFalse(preview.json()['attached'])
        self.assertEqual(self.client.get('/api/jobs').json()[0]['status'],'submission_unknown')
        attached=self.client.post(route,json={'task_id':'existing-task','approved':True})
        self.assertEqual(attached.status_code,200,attached.text)
        self.assertTrue(attached.json()['attached'])
        calls=main.request_piapi.await_count
        self.assertTrue(self.client.post(route,json={'task_id':'existing-task','approved':True}).json()['attached'])
        self.assertEqual(main.request_piapi.await_count,calls)
        self.assertEqual([c.args[0] for c in main.request_piapi.await_args_list],['POST','GET','GET'])
        self.assertTrue(self.client.post('/api/model-jobs',json=body).json()['duplicate'])
        self.assertEqual(main.request_piapi.await_count,calls)
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM generation_approvals').fetchone()[0],1)

    def test_same_request_waits_for_answer_and_owner_can_stop_waiting(self):
        first=self.image_request()
        again=lambda request_id,**changes:self.requote(first,request_id=request_id,**changes)
        main.request_piapi.side_effect=None
        main.request_piapi.return_value={'data':{'task_id':'hung-task','status':'pending'}}
        self.assertEqual(self.client.post('/api/model-jobs',json=first).status_code,200)
        calls=main.request_piapi.await_count
        blocked=self.client.post('/api/model-jobs',json=again('request-id-second-0001',node_id='other-node'))
        self.assertEqual(blocked.status_code,409)
        self.assertIn(first['request_id'],blocked.json()['detail'])
        self.assertEqual(main.request_piapi.await_count,calls)
        self.assertTrue(self.client.post('/api/model-jobs',json=first).json()['duplicate'])
        main.request_piapi.return_value={'data':{'task_id':'other-task','status':'pending'}}
        self.assertEqual(self.client.post('/api/model-jobs',json=again('request-id-other-model',model_id='nano-banana-2.1')).status_code,200)
        self.assertEqual(self.client.post('/api/model-jobs',json=again('request-id-other-prompt',prompt='Дневной Минск')).status_code,200)
        with main.connect() as db: reserved=main.security.budget_state(db,first['project_id'])['project_reserved_usd']
        self.assertEqual(self.client.post('/api/jobs/'+first['request_id']+'/stop-waiting').status_code,200)
        with main.connect() as db:
            self.assertAlmostEqual(main.security.budget_state(db,first['project_id'])['project_reserved_usd'],reserved-0.052)
        self.assertEqual(self.client.post('/api/jobs/'+first['request_id']+'/stop-waiting').status_code,409)
        main.request_piapi.return_value={'data':{'task_id':'second-task','status':'pending'}}
        second=again('request-id-second-0001')
        self.assertEqual(self.client.post('/api/model-jobs',json=second).status_code,200)
        main.request_piapi.return_value={'data':{'task_id':'second-task','status':'completed','output':{}}}
        self.client.get('/api/jobs/'+second['request_id'])
        main.request_piapi.side_effect=main.HTTPException(400,'Rejected')
        self.assertIn('Rejected',self.client.post('/api/model-jobs',json=again('request-id-third-00001')).text)
        main.request_piapi.side_effect=main.HTTPException(502,'Response lost')
        self.assertEqual(self.client.post('/api/model-jobs',json=again('request-id-fourth-0001')).status_code,502)
        self.assertEqual(self.client.post('/api/model-jobs',json=again('request-id-fifth-00001')).status_code,409)

    def test_recovery_rejects_unrelated_provider_task(self):
        body=self.image_request()
        main.request_piapi.side_effect=main.HTTPException(502,'Unknown')
        self.client.post('/api/model-jobs',json=body)
        main.request_piapi.side_effect=None
        main.request_piapi.return_value={'data':{'task_id':'wrong-task','model':'other','task_type':'other','input':{'prompt':'Another prompt'},'status':'completed'}}
        response=self.client.post('/api/jobs/'+body['request_id']+'/recover',json={'task_id':'wrong-task','approved':True})
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.client.get('/api/jobs').json()[0]['status'],'submission_unknown')

    def test_delivery_monitor_polls_then_saves_original_without_new_generation(self):
        body=self.image_request()
        main.request_piapi.side_effect=None
        main.request_piapi.return_value={'data':{'task_id':'auto-save-task','status':'pending'}}
        self.client.post('/api/model-jobs',json=body)
        main.request_piapi.return_value={'data':{'task_id':'auto-save-task','status':'completed','output':{'image_url':'https://cdn.example.test/auto.png'}}}
        image=io.BytesIO();Image.new('RGB',(1200,800),'orange').save(image,format='PNG');content=image.getvalue()
        with patch.object(main,'download_image',AsyncMock(return_value=content)) as download:
            asyncio.run(job_delivery.cycle(main))
            asyncio.run(job_delivery.cycle(main))
            download.assert_awaited_once()
        self.assertEqual([c.args[0] for c in main.request_piapi.await_args_list],['POST','GET'])
        job=self.client.get('/api/jobs').json()[0]
        self.assertEqual(job['delivery']['state'],'saved')
        assets=self.client.get('/api/library',params={'project_id':body['project_id']}).json()
        self.assertEqual(len(assets),1)
        self.assertEqual(self.client.get(assets[0]['url']).content,content)
        thumbnail=self.client.get(assets[0]['thumbnail_url'])
        self.assertEqual(thumbnail.status_code,200)
        with Image.open(io.BytesIO(thumbnail.content)) as preview:
            self.assertLessEqual(max(preview.size),512)
        self.assertLess(len(thumbnail.content),len(content))

    def test_kie_job_uses_kie_key_quote_budget_and_delivers_without_piapi(self):
        pid=self.client.post('/api/projects',json={'title':'KIE','state':{}}).json()['id']
        body={'project_id':pid,'model_id':'kie-seedream-5-pro','prompt':'Ночной Минск','reference_urls':['https://cdn.example.test/a.png','https://cdn.example.test/b.png'],
              'options':{'quality':'high'},'request_id':'kie-request-123456789','approved':True}
        self.assertEqual(self.client.post('/api/model-jobs/estimate',json=body).status_code,400)  # high (2K) ещё не проверен вживую
        body['options']={'quality':'basic'}
        estimate=self.client.post('/api/model-jobs/estimate',json=body).json()
        self.assertEqual(estimate['estimated_usd'],0.0375)
        body.update(quote_token=estimate['quote_token'],max_cost_usd=0.0375)
        missing=self.client.post('/api/model-jobs',json=body)
        self.assertEqual(missing.status_code,400)
        self.assertIn('KIE_API_KEY.txt',missing.text)
        kie.request.assert_not_awaited()
        (connections.ROOT/'KIE_API_KEY.txt').write_text('test-kie-key',encoding='utf-8')
        kie.request.side_effect=None
        kie.request.return_value={'code':200,'msg':'success','data':{'taskId':'kie-task-1'}}
        created=self.client.post('/api/model-jobs',json={**body,'request_id':'kie-request-987654321'})
        self.assertEqual(created.status_code,200,created.text)
        method,path,key,wire=kie.request.await_args.args
        self.assertEqual((method,path,key),('POST','/api/v1/jobs/createTask','test-kie-key'))
        self.assertEqual(wire,{'model':'seedream/5-pro-image-to-image','input':{'prompt':'Ночной Минск','image_urls':body['reference_urls'],
                               'quality':'basic','aspect_ratio':'16:9','output_format':'png','nsfw_checker':True}})
        kie.request.return_value={'code':200,'msg':'success','data':{'taskId':'kie-task-1','state':'success','creditsConsumed':14.5,
                                  'resultJson':json.dumps({'resultUrls':['https://cdn.example.test/kie.png']})}}
        image=io.BytesIO();Image.new('RGB',(640,360),'teal').save(image,format='PNG')
        with patch.object(main,'download_image',AsyncMock(return_value=image.getvalue())):
            asyncio.run(job_delivery.cycle(main))
        self.assertEqual(kie.request.await_args.args[:2],('GET','/api/v1/jobs/recordInfo?taskId=kie-task-1'))
        main.request_piapi.assert_not_awaited()
        job=self.client.get('/api/jobs').json()[0]
        self.assertEqual((job['provider'],job['status'],job['delivery']['state']),('kie','completed','saved'))
        self.assertEqual(len(self.client.get('/api/library',params={'project_id':pid}).json()),1)
        self.assertEqual(self.client.post(f"/api/jobs/{job['id']}/recover",json={'task_id':'kie-task-1'}).status_code,409)

    def test_reference_upload_requires_approval_caches_and_feeds_scene(self):
        pid=self.client.post('/api/projects',json={'state':{}}).json()['id']
        main.PIAPI_KEY_FILE.write_text('fake-key')
        image=io.BytesIO();Image.new('RGB',(64,64),'blue').save(image,format='PNG')
        asset=self.client.post('/api/library/import-image',data={'project_id':pid},files={'file':('reference.png',image.getvalue(),'image/png')}).json()
        route='/api/library/'+asset['id']+'/upload-reference'
        self.assertEqual(self.client.post(route,json={}).status_code,400)
        reference_upload.upload.assert_not_awaited()
        reference_upload.upload.side_effect=None
        reference_upload.upload.return_value='https://cdn.example.test/uploaded.png'
        first=self.client.post(route,json={'approved':True,'provider':'piapi'})
        self.assertEqual(first.status_code,200,first.text)
        self.assertTrue(self.client.post(route,json={'approved':True,'provider':'piapi'}).json()['cached'])
        reference_upload.upload.assert_awaited_once()
        project=self.client.get('/api/projects/'+pid).json()
        self.client.post('/api/projects',json={'id':pid,'base_revision':project['revision'],'state':{'scene':{'brief':'Character on a street','assets':[{'asset_id':asset['id'],'role':'character'}]}}})
        context=self.client.post('/api/compose/preview',json={'project_id':pid,'target':'seedance-2.5','use_scene':True}).json()['context']
        self.assertEqual(context['references'][0]['url'],'https://cdn.example.test/uploaded.png')
        self.assertEqual(self.client.get(asset['url']).content,image.getvalue())
        main.request_piapi.assert_not_awaited()

    def test_free_reference_upload_needs_no_piapi_key_and_caches_direct_link(self):
        pid=self.client.post('/api/projects',json={'state':{}}).json()['id']
        image=io.BytesIO();Image.new('RGB',(64,64),'green').save(image,format='PNG')
        asset=self.client.post('/api/library/import-image',data={'project_id':pid},files={'file':('reference.png',image.getvalue(),'image/png')}).json()
        reference_upload.upload_free.side_effect=None
        reference_upload.upload_free.return_value={'url':'https://tempfile.org/free-file/download','expires_at':__import__('time').time()+82800}
        route='/api/library/'+asset['id']+'/upload-reference'
        with patch.object(main,'get_key',side_effect=AssertionError('Free storage must not read provider credentials')):
            first=self.client.post(route,json={'approved':True})
            self.assertEqual(first.status_code,200,first.text)
            self.assertEqual(first.json()['provider'],'tempfile')
            self.assertTrue(self.client.post(route,json={'approved':True}).json()['cached'])
        reference_upload.upload_free.assert_awaited_once()
        reference_upload.upload.assert_not_awaited()
        self.assertEqual(self.client.get('/api/library',params={'project_id':pid}).json()[0]['provider_reference_url'],'https://tempfile.org/free-file/download')
        self.assertEqual(self.client.get(asset['url']).content,image.getvalue())
        main.request_piapi.assert_not_awaited()

    def test_free_upload_transport_uses_documented_form_and_no_credentials(self):
        real_client=httpx.AsyncClient
        def handler(request):
            self.assertEqual(str(request.url),'https://tempfile.org/api/upload/local')
            self.assertEqual(request.method,'POST')
            self.assertNotIn('x-api-key',request.headers)
            self.assertNotIn('authorization',request.headers)
            self.assertIn(b'name="expiryHours"',request.content)
            self.assertIn(b'name="files"; filename="test.png"',request.content)
            return httpx.Response(200,json={'success':True,'files':[{'id':'free123','expiryTime':(__import__('time').time()+86400)*1000}]})
        with patch.object(reference_upload.httpx,'AsyncClient',side_effect=lambda **kw:real_client(transport=httpx.MockTransport(handler),**kw)):
            result=asyncio.run(self.free_upload_impl('test.png',b'bytes'))
        self.assertEqual(result['url'],'https://tempfile.org/free123/download')

    def test_download_failure_keeps_completed_status_and_retries_only_download(self):
        body=self.image_request()
        main.request_piapi.side_effect=None
        main.request_piapi.return_value={'data':{'task_id':'completed-task','status':'completed','output':{'image_url':'https://cdn.example.test/expired.png'}}}
        self.client.post('/api/model-jobs',json=body)
        with patch.object(main,'download_image',AsyncMock(side_effect=main.HTTPException(502,'Expired URL'))):
            for attempt in range(5):asyncio.run(job_delivery.deliver(main,body['request_id']))
        job=self.client.get('/api/jobs').json()[0]
        self.assertEqual(job['status'],'completed')
        self.assertEqual(job['delivery']['state'],'attention')
        self.assertEqual(job['delivery']['attempts'],5)
        asyncio.run(job_delivery.cycle(main))
        self.assertEqual(main.request_piapi.await_count,1)

    def test_legacy_project_database_migrates_without_losing_content(self):
        import sqlite3
        legacy=Path(self.temp.name)/'legacy.sqlite3'
        with sqlite3.connect(legacy) as db:
            db.execute('CREATE TABLE projects(id TEXT PRIMARY KEY,title TEXT,state TEXT,updated_at TEXT)')
            db.execute('INSERT INTO projects VALUES(?,?,?,?)',('old','Existing','{"brief":"Preserve me"}',main.now()))
        db.close()
        with patch.object(main,'DB',legacy):
            main.init()
            loaded=self.client.get('/api/projects/old').json()
            self.assertEqual(loaded['revision'],0)
            self.assertEqual(loaded['state']['brief'],'Preserve me')
            self.assertEqual(self.client.post('/api/projects',json={'id':'old','base_revision':0,'title':'Existing','state':loaded['state']}).json()['revision'],1)

    def test_local_session_rejects_foreign_hosts_origins_and_missing_token(self):
        self.assertEqual(self.client.get('/api/projects',headers={'Host':'evil.example'}).status_code,403)
        self.assertEqual(self.client.get('/api/session',headers={'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/library/import-image',headers={'Origin':'https://evil.example'},data={'project_id':'x'},files={'file':('x.png',b'x','image/png')}).status_code,403)
        self.assertEqual(self.client.get('/api/projects',headers={'Sec-Fetch-Site':'cross-site'}).status_code,403)
        with TestClient(main.app,base_url='http://127.0.0.1') as stranger:
            self.assertEqual(stranger.get('/api/projects').status_code,401)
            self.assertEqual(stranger.get('/api/session').status_code,200)
            self.assertEqual(stranger.get('/api/projects').status_code,200)

    def test_paid_llm_routes_fail_closed_without_verified_prices(self):
        for endpoint in ('/api/chat','/api/compose','/api/agents/run'):
            self.assertIn(self.client.post(endpoint,json={'approved':True}).status_code,(400,422))
        main.request_piapi.assert_not_awaited()
        main.agent_completion.assert_not_awaited()

    def test_signed_quote_cannot_be_omitted_modified_or_expired(self):
        body=self.image_request()
        for change in ({'quote_token':''},{'quote_token':body['quote_token']+'x'},{'prompt':'Changed prompt'},{'options':{'aspect_ratio':'16:9'}}):
            self.assertEqual(self.client.post('/api/model-jobs',json={**body,**change}).status_code,400)
        from backend import security
        with patch.object(security.time,'time',return_value=__import__('time').time()+601):
            self.assertEqual(self.client.post('/api/model-jobs',json=body).status_code,400)
        other=self.client.post('/api/projects',json={}).json()['id']
        self.assertEqual(self.client.post('/api/model-jobs',json={**body,'project_id':other}).status_code,400)
        main.request_piapi.assert_not_awaited()

    def test_server_budgets_keep_uncertain_reservations_and_daily_total(self):
        body=self.image_request()
        self.assertEqual(self.client.put('/api/budgets/limits',json={'project_usd':0.06,'daily_usd':0.07}).status_code,200)
        main.request_piapi.side_effect=main.HTTPException(502,'Uncertain')
        self.assertEqual(self.client.post('/api/model-jobs',json=body).status_code,502)
        self.assertEqual(self.client.post('/api/model-jobs',json=self.requote(body,request_id='second-budget-request-01',prompt='Дневной Минск')).status_code,400)
        other=self.image_request(request_id='other-project-request-01')
        self.assertEqual(self.client.post('/api/model-jobs',json=other).status_code,400)
        self.assertEqual(main.request_piapi.await_count,1)
        budget=self.client.get('/api/budgets/'+body['project_id']).json()
        self.assertEqual(budget['project_reserved_usd'],0.052)
        self.assertEqual(budget['daily_reserved_usd'],0.052)

    def test_disabled_video_models_reject_duration_before_schema_access(self):
        for model in ('wan-3.0','ltx-2.5','kling-3.0'):
            response=self.client.post('/api/model-jobs/estimate',json={'model_id':model,'prompt':'A street','options':{'duration':5}})
            self.assertEqual(response.status_code,400,response.text)

    def test_simultaneous_submissions_cannot_overrun_project_budget(self):
        from concurrent.futures import ThreadPoolExecutor
        body=self.image_request()
        self.client.put('/api/budgets/limits',json={'project_usd':0.06,'daily_usd':2})
        main.request_piapi.side_effect=None
        main.request_piapi.return_value={'data':{'task_id':'budget-concurrent-task','status':'pending'}}
        bodies=[self.requote(body,request_id=f'concurrent-budget-{index:04d}',prompt=f'Минск {index}') for index in range(2)]
        def send(index):
            return self.client.post('/api/model-jobs',json=bodies[index]).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            codes=list(pool.map(send,range(2)))
        self.assertEqual(sorted(codes),[200,400])
        self.assertEqual(main.request_piapi.await_count,1)

    def test_hunyuan_image_adapter_budget_and_single_reference(self):
        pid=self.client.post('/api/projects',json={'state':{'brief':'Empty street'}}).json()['id']
        body={'project_id':pid,'model_id':'hunyuan-i2v','prompt':'The camera moves slowly forward. Keep the street empty.',
              'reference_urls':['https://cdn.example.test/source.png'],'request_id':'hunyuan-mock-test-0001','max_cost_usd':0.09}
        estimate=self.client.post('/api/model-jobs/estimate',json=body)
        self.assertEqual(estimate.status_code,200,estimate.text)
        self.assertEqual(estimate.json()['estimated_usd'],0.09)
        payload=estimate.json()['payload']
        self.assertEqual(payload['task_type'],'img2video-replace')
        self.assertEqual(payload['input']['image'],body['reference_urls'][0])
        self.assertNotIn('duration',payload['input'])
        self.assertEqual(self.client.post('/api/model-jobs/estimate',json={**body,'reference_urls':[]}).status_code,400)
        self.assertEqual(self.client.post('/api/model-jobs/estimate',json={**body,'options':{'duration':5}}).status_code,400)
        self.assertEqual(self.client.post('/api/model-jobs/estimate',json={**body,'prompt':'Use @image1'}).status_code,400)
        self.assertEqual(self.client.post('/api/model-jobs',json=body).status_code,400)
        self.assertEqual(self.client.post('/api/model-jobs',json={**body,'approved':True,'max_cost_usd':0.08}).status_code,400)
        self.assertEqual(main.request_piapi.await_count,0)

    def worker_headers(self):
        return {'X-Studio-Worker':(native_chat.RUNTIME/'worker-token.txt').read_text().strip()}

    def description_fixture(self):
        identity={key:'' for key in ('species','face','hair','eyes','costume','negative')}
        state={'brief':'Do not use this unrelated scene','prompts':{'gpt-image-2.5':'Keep original prompt'},'characters':[{'id':'hero','name':'Герой','identity':identity,'profiles':{}}]}
        pid=self.client.post('/api/projects',json={'state':state}).json()['id']
        image=io.BytesIO();Image.new('RGB',(32,32),'blue').save(image,format='PNG')
        endpoint=f'/api/characters/{pid}/hero/assets'
        asset=self.client.post(endpoint,files={'file':('reference.png',image.getvalue(),'image/png')}).json()
        body={'project_id':pid,'operation':'describe_character','character_id':'hero','request_id':'character-description-test-0001'}
        return pid,asset,body

    def test_character_description_uses_owned_references_and_saves_identity_without_generation(self):
        pid,asset,body=self.description_fixture()
        first=self.client.post('/api/chatgpt/jobs',json=body);self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.client.post('/api/chatgpt/jobs',json=body).json()['id'],first.json()['id'])
        claim=self.client.post('/api/chatgpt/worker/claim',headers=self.worker_headers()).json()
        self.assertEqual(claim['request']['context']['references'][0]['asset_id'],asset['id'])
        self.assertNotIn('brief',claim['request']['context'])
        self.assertIn('Never call imagegen',claim['request']['rules'])
        self.assertEqual(self.client.post('/api/chatgpt/worker/jobs/'+first.json()['id']+'/progress',headers=self.worker_headers(),json={'status':'prompt_ready','prompt':'wrong operation'}).status_code,409)
        identity={'species':'Человек','face':'Круглое лицо','hair':'Закрыты кепкой','eyes':'Цвет неразличим','costume':'Красная кепка','negative':'Сохранить форму лица и кепку'}
        done=self.client.post('/api/chatgpt/worker/jobs/'+first.json()['id']+'/progress',headers=self.worker_headers(),json={'status':'identity_ready','identity':identity})
        self.assertEqual(done.status_code,200,done.text);self.assertEqual(done.json()['status'],'completed')
        self.assertEqual(done.json()['description_result']['identity'],identity)
        state=self.client.get('/api/projects/'+pid).json()['state']
        self.assertEqual(state['characters'][0]['identity'],identity)
        self.assertEqual(state['prompts']['gpt-image-2.5'],'Keep original prompt')
        with main.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM library_assets').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT count(*) FROM prompt_versions').fetchone()[0],0)
        self.assertFalse(self.client.get('/api/economics',params={'project_id':pid}).json()['attempts'])
        self.assertEqual(main.request_piapi.await_count,0)
        self.assertEqual(main.agent_completion.await_count,0)

    def test_new_reference_batch_replaces_unclaimed_description(self):
        pid,asset,body=self.description_fixture()
        first=self.client.post('/api/chatgpt/jobs',json=body);self.assertEqual(first.status_code,200,first.text)
        image=io.BytesIO();Image.new('RGB',(32,32),'red').save(image,format='PNG')
        self.client.post(f'/api/characters/{pid}/hero/assets',files={'file':('second.png',image.getvalue(),'image/png')})
        second=self.client.post('/api/chatgpt/jobs',json={**body,'request_id':'character-description-test-0002'})
        self.assertEqual(second.status_code,200,second.text)
        jobs=self.client.get('/api/chatgpt/jobs',params={'project_id':pid}).json()
        self.assertEqual(next(j for j in jobs if j['id']==body['request_id'])['status'],'cancelled')
        claim=self.client.post('/api/chatgpt/worker/claim',headers=self.worker_headers()).json()
        self.assertEqual(claim['job']['id'],second.json()['id'])
        self.assertEqual(len(claim['request']['context']['references']),2)

    def test_character_description_preserves_intervening_manual_changes(self):
        pid,asset,body=self.description_fixture()
        self.client.post('/api/chatgpt/jobs',json=body)
        self.client.post('/api/chatgpt/worker/claim',headers=self.worker_headers())
        current=self.client.get('/api/projects/'+pid).json();current['state']['characters'][0]['identity']['costume']='Ручная правка костюма'
        self.client.post('/api/projects',json={'id':pid,'state':current['state'],'base_revision':current['revision']})
        identity={key:'Распознанное значение' for key in ('species','face','hair','eyes','costume','negative')}
        done=self.client.post('/api/chatgpt/worker/jobs/'+body['request_id']+'/progress',headers=self.worker_headers(),json={'status':'identity_ready','identity':identity})
        self.assertEqual(done.status_code,200,done.text)
        self.assertEqual(done.json()['description_result']['skipped_fields'],['costume'])
        self.assertEqual(done.json()['description_result']['identity']['costume'],'Ручная правка костюма')

    def test_character_description_rejects_missing_foreign_and_invalid_references(self):
        pid,asset,body=self.description_fixture()
        other=self.client.post('/api/projects',json={'state':{'characters':[{'id':'hero','identity':{}}]}}).json()['id']
        self.assertEqual(self.client.post('/api/chatgpt/jobs',json={**body,'project_id':other}).status_code,400)
        self.assertEqual(self.client.post('/api/chatgpt/jobs',json={**body,'character_id':'missing'}).status_code,404)
        self.assertEqual(self.client.post(f'/api/characters/{pid}/hero/assets',files={'file':('fake.png',b'not an image','image/png')}).status_code,422)
        self.client.post('/api/chatgpt/jobs',json=body);self.client.post('/api/chatgpt/worker/claim',headers=self.worker_headers())
        self.client.delete('/api/character-assets/'+asset['id'])
        result=self.client.post('/api/chatgpt/worker/jobs/'+body['request_id']+'/progress',headers=self.worker_headers(),json={'status':'identity_ready','identity':{key:'value' for key in ('species','face','hair','eyes','costume','negative')}})
        self.assertEqual(result.status_code,409,result.text)

    def test_replace_character_archives_history_and_changes_prompt_reference(self):
        state={'brief':'Portrait','selectedCharacter':'grem','characters':[{'id':'grem','name':'Грэм','identity':{},'profiles':{}}]}
        pid=self.client.post('/api/projects',json={'state':state}).json()['id']
        png=io.BytesIO();Image.new('RGB',(32,32),'blue').save(png,format='PNG');content=png.getvalue()
        def upload():
            return self.client.post('/api/library/import-image',data={'project_id':pid},files={'file':('grem.png',content,'image/png')}).json()['id']
        first,second=upload(),upload()
        endpoint=f'/api/characters/{pid}/grem/replace'
        for aid in (first,second,second):
            result=self.client.post(endpoint,json={'asset_id':aid})
            self.assertEqual(result.status_code,200,result.text)
        character=result.json()['character']
        self.assertEqual(character['working_asset_id'],second)
        self.assertEqual(character['version_history'],[first])
        vault=self.client.get(f'/api/characters/{pid}/grem/assets').json()
        self.assertEqual(sorted(a['category'] for a in vault),['approved_generations','archived_generations'])
        for asset in vault:self.assertEqual(self.client.get(asset['url']).content,content)
        context=main.compose_context(main.ComposeRequest(project_id=pid,target='gpt-image-2.5',provider='codex_chat'))
        self.assertEqual([r['asset_id'] for r in context['references']],[second])
        library=self.client.get('/api/library',params={'project_id':pid}).json()
        self.assertEqual(next(a for a in library if a['id']==first)['metadata']['character_status'],'archived')
        self.assertEqual(self.client.get(f'/api/library/{first}/file').content,content)
        other=self.client.post('/api/projects',json={'state':state}).json()['id']
        self.assertEqual(self.client.post(f'/api/characters/{other}/grem/replace',json={'asset_id':second}).status_code,404)
        self.assertEqual(self.client.post(f'/api/characters/{pid}/missing/replace',json={'asset_id':second}).status_code,404)

    def test_refinement_import_and_edit_keep_original_and_context_isolated(self):
        pid=self.client.post('/api/projects',json={'state':{'brief':'Do not replace the edit with this unrelated brief','prompts':{'gpt-image-2.5':'Existing scene prompt'}}}).json()['id']
        image=io.BytesIO();Image.new('RGB',(1024,1024),'gray').save(image,format='PNG');original=image.getvalue()
        def upload(name):
            r=self.client.post('/api/library/import-image',data={'project_id':pid},files={'file':(name,original,'image/png')});self.assertEqual(r.status_code,200,r.text);return r.json()
        source,reference=upload('source.png'),upload('shoe-reference.png')
        body={'project_id':pid,'operation':'edit','request_id':'refinement-local-test-0001','source_asset_id':source['id'],'reference_asset_id':reference['id'],'edit_instruction':'Change only the shoes to match Image 2.'}
        first=self.client.post('/api/chatgpt/jobs',json=body);self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.client.post('/api/chatgpt/jobs',json=body).json()['id'],first.json()['id'])
        claim=self.client.post('/api/chatgpt/worker/claim',headers=self.worker_headers()).json();context=claim['request']['context']
        self.assertEqual([x['role'] for x in context['references']],['edit_target','detail_reference'])
        self.assertNotIn('world_bible',context)
        self.assertEqual(context['brief'],body['edit_instruction'])
        ready=self.client.post('/api/chatgpt/worker/jobs/'+first.json()['id']+'/progress',headers=self.worker_headers(),json={'status':'prompt_ready','prompt':'Change only the shoes to match Image 2.'})
        self.assertEqual(ready.json()['status'],'generating',ready.text)
        self.assertIn('Preserve all unrelated features',ready.json()['prompt'])
        done=self.client.post('/api/chatgpt/worker/jobs/'+first.json()['id']+'/image',headers=self.worker_headers(),files={'file':('edited.png',original,'image/png')})
        self.assertEqual(done.status_code,200,done.text)
        self.assertNotEqual(done.json()['asset_id'],source['id'])
        self.assertEqual(self.client.get(source['url']).content,original)
        assets=self.client.get('/api/library',params={'project_id':pid}).json();edited=next(x for x in assets if x['id']==done.json()['asset_id'])
        self.assertEqual(edited['metadata']['edit_source_asset_id'],source['id'])
        self.assertEqual(edited['metadata']['detail_reference_asset_id'],reference['id'])
        state=self.client.get('/api/projects/'+pid).json()['state'];self.assertEqual(state['prompts']['gpt-image-2.5'],'Existing scene prompt')
        econ=self.client.get('/api/economics',params={'project_id':pid}).json()
        self.assertEqual(econ['chat_image_count'],1)
        self.assertEqual(econ['attempts'],1) # Imported references are not generation attempts.
        self.assertEqual(main.request_piapi.await_count,0)

    def test_refinement_rejects_foreign_or_invalid_input(self):
        one=self.client.post('/api/projects',json={'state':{}}).json()['id'];two=self.client.post('/api/projects',json={'state':{}}).json()['id']
        bad=self.client.post('/api/library/import-image',data={'project_id':one},files={'file':('fake.png',b'not an image','image/png')})
        self.assertEqual(bad.status_code,422)
        image=io.BytesIO();Image.new('RGB',(16,16)).save(image,format='PNG')
        source=self.client.post('/api/library/import-image',data={'project_id':one},files={'file':('ref.png',image.getvalue(),'image/png')}).json()
        body={'project_id':two,'operation':'edit','request_id':'refinement-foreign-test-01','source_asset_id':source['id'],'edit_instruction':'Change only shoes'}
        self.assertEqual(self.client.post('/api/chatgpt/jobs',json=body).status_code,404)
        self.assertEqual(self.client.post('/api/chatgpt/jobs',json={**body,'project_id':one,'edit_instruction':'  '}).status_code,400)
        self.assertEqual(self.client.post('/api/chatgpt/jobs',json={**body,'project_id':one,'reference_asset_id':source['id']}).status_code,400)

    def test_native_character_references_exclude_candidates_and_rejections(self):
        pid=self.client.post('/api/projects',json={'state':{'brief':'Full-body character on gray','selectedCharacter':'hero','characters':[{'id':'hero','identity':{'costume':'red cap'},'profiles':{}}]}}).json()['id']
        endpoint=f'/api/characters/{pid}/hero/assets'
        png=io.BytesIO();Image.new('RGB',(32,32),'blue').save(png,format='PNG')
        for category in ('real_references','approved_generations','candidate_generations','rejected_generations','model_references'):
            response=self.client.post(endpoint,data={'category':category,'model_id':'seedance-2.5','note':category},files={'file':('ref.png',png.getvalue(),'image/png')})
            self.assertEqual(response.status_code,200,response.text)
        native=self.client.post('/api/chatgpt/jobs',json={'project_id':pid,'target':'gpt-image-2.5','request_id':'character-reference-test-0001','operation':'prompt'})
        self.assertEqual(native.status_code,200,native.text)
        job=self.client.post('/api/chatgpt/worker/claim',headers=self.worker_headers()).json()
        refs=job['request']['context']['references']
        self.assertEqual(len(refs),2)
        self.assertEqual({x['role'] for x in refs},{'character_identity','approved_character_reference'})
        self.assertEqual({x['note'] for x in refs},{'real_references','approved_generations'})
        self.assertTrue(Path(refs[0]['local_path']).is_file())
        api_context=self.client.post('/api/compose/preview',json={'project_id':pid,'target':'gpt-image-2.5'}).json()['context']
        self.assertEqual(api_context['references'],[])

    def test_native_pipeline_scene_and_economics_without_paid_api(self):
        pid=self.client.post('/api/projects',json={'title':'Clip test','state':{'brief':'A quiet empty courtyard','scene':{'brief':'An empty courtyard at dusk','assets':[]}}}).json()['id']
        body={'project_id':pid,'target':'gpt-image-2.5','request_id':'native-generation-test-0001','use_scene':True}
        first=self.client.post('/api/chatgpt/jobs',json=body)
        self.assertEqual(first.status_code,200,first.text)
        self.assertEqual(self.client.post('/api/chatgpt/jobs',json=body).json()['id'],first.json()['id'])
        self.assertEqual(self.client.post('/api/chatgpt/worker/claim').status_code,403)
        claim=self.client.post('/api/chatgpt/worker/claim',headers=self.worker_headers()).json()
        self.assertEqual(claim['request']['context']['brief'],'An empty courtyard at dusk')
        job=claim['job']['id']
        # No second worker may claim already-running image generation.
        self.assertIsNone(self.client.post('/api/chatgpt/worker/claim',headers=self.worker_headers()).json()['job'])
        ready=self.client.post(f'/api/chatgpt/worker/jobs/{job}/progress',headers=self.worker_headers(),json={'status':'prompt_ready','prompt':'A wide view of an empty courtyard at dusk.'})
        self.assertEqual(ready.json()['status'],'generating',ready.text)
        loaded=self.client.get('/api/projects/'+pid).json()['state']
        self.assertEqual(loaded['scene']['prompts']['gpt-image-2.5'],ready.json()['prompt'])
        image=io.BytesIO();Image.new('RGB',(1536,1024),'navy').save(image,format='PNG')
        result=self.client.post(f'/api/chatgpt/worker/jobs/{job}/image',headers=self.worker_headers(),files={'file':('test.png',image.getvalue(),'image/png')})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['status'],'completed')
        aid=result.json()['asset_id']
        self.assertEqual(self.client.get(result.json()['image_url']).status_code,200)
        # Callback retry reuses the result; never another asset.
        again=self.client.post(f'/api/chatgpt/worker/jobs/{job}/image',headers=self.worker_headers(),files={'file':('test.png',image.getvalue(),'image/png')})
        self.assertEqual(again.json()['asset_id'],aid)
        self.assertEqual(self.client.post('/api/chatgpt/jobs',json=body).json()['id'],job)
        self.assertEqual(self.client.put('/api/economics/assets/'+aid,json={'decision':'used'}).status_code,200)
        economics=self.client.get('/api/economics',params={'project_id':pid}).json()
        self.assertEqual(economics['chat_image_count'],1)
        self.assertEqual(economics['success_percent'],100)
        self.assertEqual(economics['actual_usd_known'],0)
        self.assertEqual(economics['unknown_cost_count'],0)
        self.assertAlmostEqual(economics['chat_api_equivalent_usd'],0.16464,places=5)
        self.assertEqual(main.request_piapi.await_count,0)
        self.assertEqual(main.agent_completion.await_count,0)

    def test_scene_asset_roles_and_project_isolation(self):
        pid=self.client.post('/api/projects',json={'state':{'brief':'base','scene':{'brief':'Character in a location','assets':[{'asset_id':'missing','role':'character'}]}}}).json()['id']
        r=self.client.post('/api/compose/preview',json={'project_id':pid,'target':'gpt-image-2.5','use_scene':True})
        self.assertEqual(r.status_code,400)
        self.client.post('/api/projects',json={'id':pid,'base_revision':self.client.get('/api/projects/'+pid).json()['revision'],'state':{'brief':'base','referenceUrls':'https://example.test/a.png'}})
        for target in main.MODEL_SPECS:
            if main.MODEL_SPECS[target]['kind']=='video':continue
            preview=self.client.post('/api/compose/preview',json={'project_id':pid,'target':target})
            self.assertEqual(preview.status_code,200,preview.text)
            self.assertEqual(preview.json()['context']['references'][0]['label'],'Image 1')
        self.assertNotIn('For a still image',main.system_rules(main.MODEL_SPECS['ltx-2.5']))

    def test_native_queue_cancel_and_no_automatic_retry(self):
        pid=self.client.post('/api/projects',json={'state':{'brief':'Empty square'}}).json()['id']
        body={'project_id':pid,'request_id':'native-cancel-test-0001'}
        job=self.client.post('/api/chatgpt/jobs',json=body).json()['id']
        second=self.client.post('/api/chatgpt/jobs',json={**body,'request_id':'native-cancel-test-0002'})
        self.assertEqual(second.status_code,409)
        self.assertEqual(self.client.post(f'/api/chatgpt/jobs/{job}/cancel').status_code,200)
        self.assertIsNone(self.client.post('/api/chatgpt/worker/claim',headers=self.worker_headers()).json()['job'])
        self.assertFalse(self.client.get('/api/chatgpt/status').json()['automatic_wake'])

    def test_gpt_equivalent_calculator_is_not_actual_charge(self):
        from backend.image_pricing import api_equivalent
        self.assertEqual(api_equivalent(1024,1024)['output_tokens_estimate'],7024)
        self.assertAlmostEqual(api_equivalent(1024,1024)['usd'],0.21072)
        self.assertTrue(api_equivalent(None,None)['assumed_size'])
        self.assertFalse(api_equivalent(3840,2160)['assumed_size'])

    def test_piapi_key_file_and_priority(self):
        with patch.dict(main.os.environ, {'PIAPI_API_KEY':''}):
            main.PIAPI_KEY_FILE.write_text('\ufefftest-local-key\n',encoding='utf-8')
            self.assertEqual(main.get_key(None),'test-local-key')
            self.assertEqual(main.get_key(''),'test-local-key')
            self.assertEqual(main.get_key('header-test-key'),'header-test-key')
            with patch.dict(main.os.environ, {'PIAPI_API_KEY':'environment-test-key'}):
                self.assertEqual(main.get_key(None),'environment-test-key')
            main.PIAPI_KEY_FILE.write_text('',encoding='utf-8')
            with self.assertRaises(main.HTTPException): main.get_key(None)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg/FFprobe unavailable')
    def test_audio_import_analyze_cut_wav(self):
        # Synthetic tone: no user media and no external API.
        source=Path(self.temp.name)/'tone.wav'
        main.cmd(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i',
                  'sine=frequency=440:duration=3','-y',str(source)])
        main.MEDIA.mkdir(parents=True,exist_ok=True)
        upload=self.client.post('/api/media/upload',files={'file':('tone.wav',source.read_bytes(),'audio/wav')})
        self.assertEqual(upload.status_code,200,upload.text)
        filename=upload.json()['url'].rsplit('/',1)[1]
        analysis=self.client.get('/api/audio/analyze/'+filename)
        self.assertEqual(analysis.status_code,200,analysis.text)
        self.assertAlmostEqual(analysis.json()['duration'],3,places=1)
        payload={'filename':filename,'start':0.2,'end':1.2,'denoise':True,'normalize':True}
        self.assertEqual(self.client.post('/api/audio/cut',json=payload).status_code,400)
        result=self.client.post('/api/audio/cut',json={**payload,'consent_confirmed':True})
        self.assertEqual(result.status_code,200,result.text)
        audio=self.client.get(result.json()['url'])
        self.assertEqual(audio.status_code,200)
        with wave.open(io.BytesIO(audio.content),'rb') as wav:
            self.assertEqual(wav.getnchannels(),1)
            self.assertEqual(wav.getframerate(),44100)
            self.assertAlmostEqual(wav.getnframes()/wav.getframerate(),1,places=1)

    def test_project_character_style_graph_roundtrip(self):
        state = {'characters':[{'id':'graham','name':'Грэм','identity':{'eyes':'карие'},
                               'profiles':{'one':{'prompt_notes':'Профиль 1'},'two':{'prompt_notes':'Профиль 2'}}}],
                 'style':{'palette':'баклажан'}, 'prompts':{'one':'Кадр','two':'Движение'},
                 'videoReference':'https://example.test/frame.png',
                 'nodes':[{'id':'brief','position':{'x':10,'y':20}}], 'edges':[]}
        pid = self.client.post('/api/projects', json={'title':'Проверка','state':state}).json()['id']
        self.assertIn(pid, [p['id'] for p in self.client.get('/api/projects').json()])
        self.assertEqual(self.client.get('/api/projects/'+pid).json()['state'], state)
        state['characters'][0]['profiles']['one']['prompt_notes'] = 'Обновление'
        self.client.post('/api/projects', json={'id':pid,'base_revision':self.client.get('/api/projects/'+pid).json()['revision'],'title':'Изменён','state':state})
        # Reopen through another client and another SQLite connection.
        with TestClient(main.app,base_url="http://127.0.0.1") as reopened:
            reopened.get("/api/session")
            loaded = reopened.get('/api/projects/'+pid).json()
        self.assertEqual(loaded['state'], state)
        self.assertEqual(loaded['state']['characters'][0]['profiles']['two']['prompt_notes'], 'Профиль 2')
        state['characters'] = []
        state['style'] = {}
        self.client.post('/api/projects', json={'id':pid,'base_revision':self.client.get('/api/projects/'+pid).json()['revision'],'state':state})
        self.assertEqual(self.client.get('/api/projects/'+pid).json()['state'], state)
        self.assertEqual(self.client.get('/api/projects/missing').status_code, 404)

    def test_reference_categories_upload_read_delete(self):
        pid = self.client.post('/api/projects', json={'state':{'characters':[{'id':'graham'}]}}).json()['id']
        endpoint = f'/api/characters/{pid}/graham/assets'
        for category in main.CHAR_CATEGORIES:
            image=io.BytesIO();Image.new('RGB',(32,32),'blue').save(image,format='PNG');content=image.getvalue()
            response = self.client.post(endpoint, data={'category':category,'model_id':'seedream-5-pro','note':'Причина'},
                                        files={'file':('reference.png',content,'image/png')})
            self.assertEqual(response.status_code, 200, response.text)
            url = response.json()['url']
            self.assertEqual(self.client.get(url).content, content)
            self.assertEqual(self.client.delete(url).status_code, 200)
            self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(endpoint).json(), [])
        invalid = self.client.post(endpoint, data={'category':'unknown'}, files={'file':('x.png',b'x','image/png')})
        self.assertEqual(invalid.status_code, 400)

    def test_local_prompts_isolate_model_profiles_and_keep_canon(self):
        body = {'brief':'Ночной Минск','target':'seedream-5-pro',
                'character':{'identity':{'eyes':'карие'}, 'profiles':{
                    'seedream-5-pro':{'prompt_notes':'ТОЛЬКО ЭТОТ ПРОФИЛЬ'},
                    'seedance-2.5':{'prompt_notes':'ЧУЖОЙ ПРОФИЛЬ'}}},'style':{'palette':'баклажан'}}
        result = self.client.post('/api/prompt-drafts', json=body)
        self.assertEqual(result.status_code, 200, result.text)
        draft = result.json()
        for text in ['Ночной Минск','карие','баклажан','ТОЛЬКО ЭТОТ ПРОФИЛЬ']:
            self.assertIn(text, draft['prompt'])
        self.assertNotIn('ЧУЖОЙ ПРОФИЛЬ', draft['prompt'])
        self.assertEqual(draft['external_calls'], 0)
        body['target'] = 'unknown'
        self.assertEqual(self.client.post('/api/prompt-drafts',json=body).status_code,400)

    def test_invalid_jobs_rejected_before_external_request(self):
        for overrides in [{'model_id':'unknown'}, {'options':{'size':'100K'}},
                          {'reference_urls':['file:///private.png']},
                          {'reference_urls':['https://example.test/a.png']*11}]:
            body = {'model_id':'seedream-5-pro','prompt':'Кадр',**overrides}
            self.assertEqual(self.client.post('/api/model-jobs',json=body).status_code,400)
        main.request_piapi.assert_not_awaited()

    def image_request(self,**overrides):
        pid=self.client.post('/api/projects',json={'title':'Image workflow','state':{}}).json()['id']
        main.PIAPI_KEY_FILE.write_text('test-piapi-key',encoding='utf-8')
        body={'project_id':pid,'model_id':'seedream-5-lite','prompt':'Ночной Минск','request_id':'request-id-123456789','approved':True,'max_cost_usd':0.052,**overrides}
        estimate=self.client.post('/api/model-jobs/estimate',json=body)
        if estimate.status_code==200:body['quote_token']=estimate.json()['quote_token']
        return body

    def requote(self,body,**changes):
        body={**body,**changes}
        estimate=self.client.post('/api/model-jobs/estimate',json=body).json()
        return {**body,'quote_token':estimate['quote_token'],'max_cost_usd':estimate['estimated_usd']}

    def test_image_approval_limit_and_legacy_bypass(self):
        body=self.image_request()
        estimate=self.client.post('/api/model-jobs/estimate',json=body)
        self.assertEqual(estimate.status_code,200,estimate.text)
        self.assertEqual(estimate.json()['estimated_usd'],0.052)
        self.assertEqual(estimate.json()['payload']['input']['size'],'2K')
        for patch_body in [{'approved':False},{'max_cost_usd':0.051},{'request_id':None}, {'options':{'max_images':15}}, {'options':{'size':'100K'}}, {'reference_urls':['http://localhost/a.png']}]:
            self.assertEqual(self.client.post('/api/model-jobs',json={**body,**patch_body}).status_code,400)
        self.assertEqual(self.client.post('/api/tasks',json={'payload':{}}).status_code,410)
        main.request_piapi.assert_not_awaited()

    def test_image_submit_is_idempotent_and_saved_before_upstream(self):
        body=self.image_request()
        async def upstream(*args):
            with main.connect() as db:
                self.assertEqual(db.execute('SELECT status FROM jobs WHERE id=?',(body['request_id'],)).fetchone()['status'],'submitting')
            return {'data':{'task_id':'provider-task','status':'completed','output':{'image_urls':['https://cdn.example.test/a.png']}}}
        main.request_piapi.side_effect=upstream
        first=self.client.post('/api/model-jobs',json=body)
        self.assertEqual(first.status_code,200,first.text)
        second=self.client.post('/api/model-jobs',json=body)
        self.assertTrue(second.json()['duplicate'])
        self.assertEqual(main.request_piapi.await_count,1)
        self.assertEqual(self.client.post('/api/model-jobs',json={**body,'prompt':'Other'}).status_code,409)
        self.assertEqual(self.client.get('/api/jobs/'+body['request_id']).status_code,200)
        self.assertEqual(main.request_piapi.await_count,1) # No polling completed tasks.
        with main.connect() as db:
            approval=dict(db.execute('SELECT * FROM generation_approvals').fetchone())
        self.assertEqual(approval['max_cost_usd'],0.052)

    def test_uncertain_submission_never_retries(self):
        body=self.image_request()
        main.request_piapi.side_effect=main.HTTPException(502,'Соединение потеряно')
        result=self.client.post('/api/model-jobs',json=body)
        self.assertEqual(result.status_code,502)
        self.assertEqual(result.json()['detail']['status'],'submission_unknown')
        self.assertTrue(self.client.post('/api/model-jobs',json=body).json()['duplicate'])
        self.assertEqual(main.request_piapi.await_count,1)

    def test_generated_image_library_download_metadata_and_reopen(self):
        body=self.image_request()
        main.request_piapi.side_effect=None
        main.request_piapi.return_value={'data':{'task_id':'provider-task','status':'completed','output':{'image_urls':['https://cdn.example.test/a.png']}}}
        job=self.client.post('/api/model-jobs',json=body).json()['job_id']
        content=io.BytesIO();Image.new('RGB',(16,12),'purple').save(content,format='PNG')
        with patch.object(main,'download_image',AsyncMock(return_value=content.getvalue())) as download:
            endpoint=f'/api/jobs/{job}/images/0/save'
            saved=self.client.post(endpoint)
            self.assertEqual(saved.status_code,200,saved.text)
            self.assertEqual(self.client.post(endpoint).json()['id'],saved.json()['id'])
            download.assert_awaited_once()
            (main.LIBRARY_ROOT/saved.json()['filename']).unlink()
            restored=self.client.post(endpoint)
            self.assertEqual(restored.json()['id'],saved.json()['id'])
        self.assertEqual(self.client.get(saved.json()['url']).content,content.getvalue())
        with TestClient(main.app,base_url="http://127.0.0.1") as reopened:
            reopened.get("/api/session")
            library=reopened.get('/api/library',params={'project_id':body['project_id']}).json()
        self.assertEqual(library[0]['metadata']['request']['payload']['input']['prompt'],body['prompt'])
        self.assertEqual(library[0]['metadata']['width'],16)
        self.assertEqual(library[0]['source_url'],'https://cdn.example.test/a.png')
        self.assertEqual(self.client.post(f'/api/jobs/{job}/images/9/save').status_code,400)

    def test_connections_hide_keys_and_require_explicit_check(self):
        sentinel='private-test-key-do-not-expose'
        for spec in connections.PROVIDERS.values():
            (connections.ROOT/spec['file']).write_text(sentinel,encoding='utf-8')
        result=self.client.get('/api/connections')
        self.assertNotIn(sentinel,result.text)
        self.assertTrue(all(x['status']=='unverified' for x in result.json()))
        real_client=httpx.AsyncClient
        def handler(request):
            self.assertEqual(request.method,'GET')
            return httpx.Response(200,json={'data':[],'secret_reflection':sentinel},request=request)
        with patch.object(connections.httpx,'AsyncClient',side_effect=lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs)):
            for provider in connections.PROVIDERS:
                r=self.client.post(f'/api/connections/{provider}/check')
                self.assertEqual(r.json()['status'],'connected',r.text)
                self.assertNotIn(sentinel,r.text)
        self.assertNotIn(sentinel,self.client.get('/api/connections').text)
        (connections.ROOT/'PIAPI_API_KEY.txt').write_text('changed-test-key',encoding='utf-8')
        self.assertEqual(connections.connection_info('piapi')['status'],'unverified')

    def test_connection_blocking_and_non_json_errors(self):
        (connections.ROOT/'PIAPI_API_KEY.txt').write_text('fake-key',encoding='utf-8')
        real_client=httpx.AsyncClient
        for code,text,status in [(403,'browser_signature_banned Error 1010','blocked'),(401,'private response','denied'),(200,'not JSON','error')]:
            transport=httpx.MockTransport(lambda request:httpx.Response(code,text=text,request=request))
            with patch.object(connections.httpx,'AsyncClient',side_effect=lambda **kwargs:real_client(transport=transport,**kwargs)):
                r=self.client.post('/api/connections/piapi/check')
            self.assertEqual(r.json()['status'],status,r.text)
            self.assertNotIn('private response',r.text)

    def test_downloads_reject_private_network_and_invalid_images(self):
        for url in ['http://example.test/a.png','https://127.0.0.1/a.png','https://[::1]/a.png','https://user:password@example.test/a.png']:
            with self.assertRaises(main.HTTPException): image_assets.check_public_url(url)
        with self.assertRaises(main.HTTPException): image_assets.inspect_image(b'<html>not an image</html>')

    def test_image_downloader_checks_redirects_and_forwards_no_keys(self):
        real_client=httpx.AsyncClient
        def handler(request):
            self.assertNotIn('authorization',request.headers)
            self.assertNotIn('x-api-key',request.headers)
            if request.url.path=='/start': return httpx.Response(302,headers={'location':'https://other.example.test/image'},request=request)
            return httpx.Response(200,content=b'image bytes',request=request)
        with patch.object(image_assets,'check_public_url') as guard, patch.object(image_assets.httpx,'AsyncClient',side_effect=lambda **kwargs:real_client(transport=httpx.MockTransport(handler),**kwargs)):
            self.assertEqual(asyncio.run(image_assets.download_image('https://cdn.example.test/start')),b'image bytes')
        self.assertEqual([c.args[0] for c in guard.call_args_list],['https://cdn.example.test/start','https://other.example.test/image'])

    @patch.dict(main.MODEL_SPECS['seedance-2.5'], {'launch_enabled': True})  # конвейер, не проверка модели
    def test_seedance_schema_estimate_approval_and_submission(self):
        body=self.image_request(model_id='seedance-2.5',prompt='Slow forward dolly in @image1',
                                reference_urls=['https://cdn.example.test/frame.png'],
                                options={'resolution':'480p','duration':5,'aspect_ratio':'16:9'},max_cost_usd=0.75)
        estimate=self.client.post('/api/model-jobs/estimate',json=body)
        self.assertEqual(estimate.status_code,200,estimate.text)
        self.assertEqual(estimate.json()['estimated_usd'],0.75)
        inp=estimate.json()['payload']['input']
        self.assertEqual(inp['mode'],'omni_reference')
        self.assertEqual(inp['omni_reference_task_type'],'reference')
        self.assertNotIn('generate_audio',inp)
        for patch_body in [{'max_cost_usd':0.06},{'approved':False},{'reference_urls':[]},
                           {'prompt':'Move @video1'},
                           {'options':{'duration':5.5}}, {'options':{'duration':31}},
                           {'options':{'resolution':'4K'}}, {'options':{'draft':True}}]:
            self.assertEqual(self.client.post('/api/model-jobs',json={**body,**patch_body}).status_code,400)
        main.request_piapi.assert_not_awaited()
        main.request_piapi.side_effect=None
        main.request_piapi.return_value={'data':{'task_id':'seedance-test','status':'pending'}}
        submitted=self.client.post('/api/model-jobs',json=body)
        self.assertEqual(submitted.status_code,200,submitted.text)
        self.assertEqual(self.client.get('/api/jobs').json()[0]['kind'],'video')
        self.assertEqual(self.client.post('/api/model-jobs',json=body).json()['duplicate'],True)
        main.request_piapi.assert_awaited_once()

    @patch.dict(main.MODEL_SPECS['seedance-2.5'], {'launch_enabled': True})  # конвейер, не проверка модели
    def test_seedance_draft_then_final_uses_project_queue(self):
        draft_body=self.image_request(model_id='seedance-2.5',prompt='Slow forward dolly',options={'draft':True,'duration':4},
                                      max_cost_usd=0.6,request_id='draft-request-1234567')
        main.request_piapi.side_effect=None
        main.request_piapi.return_value={'data':{'task_id':'draft-task-1','status':'pending'}}
        self.assertEqual(self.client.post('/api/model-jobs',json=draft_body).status_code,200)
        wire=main.request_piapi.await_args.args[3]
        self.assertTrue(wire['input']['draft'])
        self.assertNotIn('billing',wire)
        final={k:v for k,v in draft_body.items() if k!='quote_token'}
        final['options']={'draft_task_id':'draft-task-1'}
        estimate=self.client.post('/api/model-jobs/estimate',json=final)
        self.assertEqual(estimate.status_code,200,estimate.text)
        self.assertEqual(estimate.json()['estimated_usd'],3.2)
        self.assertEqual(estimate.json()['payload']['input'],{'draft_task_id':'draft-task-1','resolution':'1080p'})
        self.assertTrue(any('Финал 1080p' in line for line in estimate.json()['lines']))
        preview=self.client.post('/api/model-jobs/preview',json=final)
        self.assertEqual(preview.status_code,200,preview.text)
        self.assertEqual(preview.json()['wire_body']['input'],{'draft_task_id':'draft-task-1','resolution':'1080p'})
        for bad in ({'draft_task_id':'unknown-task'},{'draft_task_id':'draft-task-1','duration':4}):
            self.assertEqual(self.client.post('/api/model-jobs/estimate',json={**final,'options':bad}).status_code,400)
        main.request_piapi.assert_awaited_once()

    def test_prompt_api_uses_project_rules_profiles_references_and_history(self):
        state={'brief':'Ночная улица','motionBrief':'Медленный проезд вперёд','style':{'palette':'синий и янтарный'},
               'selectedCharacter':'hero','characters':[{'id':'hero','identity':{'costume':'красная кепка'},'profiles':{
                   'seedance-2.5':{'prompt_notes':'Сохранить кепку','reference_urls':''},
                   'other':{'prompt_notes':'DO_NOT_LEAK_OTHER_PROFILE'}}}],
               'videoReference':'https://cdn.example.test/frame.png',
               'parameters':{'seedance-2.5':{'resolution':'480p','duration':5}},
               'prompts':{'seedream-5-lite':'Keep image prompt'}}
        pid=self.client.post('/api/projects',json={'state':state}).json()['id']
        main.PIAPI_KEY_FILE.write_text('fake-key',encoding='utf-8')
        body={'project_id':pid,'target':'seedance-2.5','provider':'piapi','model':'gpt-5.6-luna'}
        preview=self.client.post('/api/compose/preview',json=body)
        self.assertEqual(preview.status_code,200,preview.text)
        self.assertEqual(preview.json()['external_calls'],0)
        self.assertIn('Seedance 2.5',preview.json()['system_rules'])
        self.assertEqual(preview.json()['context']['references'][0]['label'],'@image1')
        self.assertNotIn('DO_NOT_LEAK_OTHER_PROFILE',preview.text)
        self.assertEqual(self.client.post('/api/compose',json={**body,'approved':True}).status_code,400)
        main.agent_completion.assert_not_awaited()
        main.request_piapi.assert_not_awaited()

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg unavailable')
    @patch.dict(main.MODEL_SPECS['seedance-2.5'], {'launch_enabled': True})  # конвейер, не проверка модели
    def test_video_download_validate_library_and_reopen(self):
        body=self.image_request(model_id='seedance-2.5',options={'resolution':'480p','duration':5},max_cost_usd=0.75)
        main.request_piapi.side_effect=None
        main.request_piapi.return_value={'data':{'task_id':'video-test','status':'completed','output':{'video_url':'https://cdn.example.test/result.mp4'}}}
        job=self.client.post('/api/model-jobs',json=body).json()['job_id']
        video=Path(self.temp.name)/'sample.mp4'
        main.cmd(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=blue:s=64x48:d=1','-c:v','libx264','-pix_fmt','yuv420p','-y',str(video)])
        with patch.object(main,'download_video',AsyncMock(return_value=video.read_bytes())) as download:
            result=self.client.post(f'/api/jobs/{job}/outputs/0/save')
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(result.json()['metadata']['kind'],'video')
            self.assertEqual(result.json()['metadata']['width'],64)
            self.assertEqual(self.client.get(result.json()['url']).content,video.read_bytes())
            self.assertEqual(self.client.post(f'/api/jobs/{job}/outputs/0/save').json()['id'],result.json()['id'])
            download.assert_awaited_once()
        with TestClient(main.app,base_url="http://127.0.0.1") as reopened:
            reopened.get("/api/session")
            library=reopened.get('/api/library',params={'project_id':body['project_id']}).json()
        self.assertEqual(library[0]['metadata']['format'],'MP4')


if __name__ == '__main__': unittest.main()
