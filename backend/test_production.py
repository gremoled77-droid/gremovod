"""Production tree, shared references and voice generation without provider calls."""
import io
import json
import unittest
import asyncio
import httpx
from unittest.mock import AsyncMock, patch
from PIL import Image
from backend import test_smoke
from backend import main, character_voice, production_folders


class ProductionTests(unittest.TestCase):
    setUp=test_smoke.StudioSmokeTests.setUp
    tearDown=test_smoke.StudioSmokeTests.tearDown

    def setup_production(self):
        self.project=self.client.post('/api/projects',json={'title':'Source','state':{'characters':[{'id':'grem','name':'Грэм','identity':{'costume':'red cap'}}]}}).json()['id']
        r=self.client.post('/api/productions',json={'title':'GremoVOD','source_project_id':self.project});self.assertEqual(r.status_code,200,r.text)
        self.pid=r.json()['id'];tree=self.client.get('/api/productions/'+self.pid).json();self.char=tree['nodes'][0]
        self.base=f'/api/productions/{self.pid}/nodes/{self.char["id"]}'

    def new(self,kind,title,parent=None):
        r=self.client.post(f'/api/productions/{self.pid}/nodes',json={'kind':kind,'title':title,'parent_id':parent});self.assertEqual(r.status_code,200,r.text);return r.json()

    def setup_frame(self):
        series=self.new('series','Проверка');episode=self.new('episode','Встреча',series['id']);frame=self.new('frame','Крупный план',episode['id'])
        self.frame=frame;self.framebase=f'/api/productions/{self.pid}/nodes/{frame["id"]}'
        r=self.client.post(self.framebase+'/open-project');self.assertEqual(r.status_code,200,r.text);self.frameproject=r.json()['project_id']

    def test_tree_real_folders_shared_character_and_reference_upload(self):
        self.setup_production();self.setup_frame()
        self.assertTrue((main.PRODUCTIONS_ROOT/'GremoVOD'/'01_Персонажи'/'Грэм'/'РЕФЕРЕНС_КАРТА.md').is_file())
        self.assertTrue((main.PRODUCTIONS_ROOT/self.frame['relative_dir']/'04_Звук').is_dir())
        self.assertEqual(self.client.get('/api/projects/'+self.frameproject).json()['state']['characters'][0]['id'],'grem')
        image=io.BytesIO();Image.new('RGB',(32,48),'red').save(image,format='PNG')
        upload=self.client.post(self.base+'/upload',data={'category':'02_Референсы'},files={'file':('cap.png',image.getvalue(),'image/png')})
        self.assertEqual(upload.status_code,200,upload.text)
        assets=self.client.get('/api/library',params={'project_id':self.frameproject}).json()
        self.assertEqual(len(assets),1)
        self.assertEqual(self.client.get(upload.json()['url']).content,image.getvalue())
        self.assertEqual(self.client.post(self.framebase+'/open-project').json()['project_id'],self.frameproject)
        for _ in range(2):self.assertEqual(self.client.post('/api/productions/'+self.pid+'/sync').status_code,200)
        self.assertEqual(len(self.client.get('/api/library',params={'project_id':self.frameproject}).json()),1)

    def test_invalid_hierarchy_and_escaped_path(self):
        self.setup_production()
        self.assertEqual(self.client.post('/api/productions/'+self.pid+'/nodes',json={'kind':'frame','title':'Wrong'}).status_code,400)
        self.assertEqual(self.client.post('/api/productions/'+self.pid+'/nodes',json={'kind':'location','title':'CON.txt'}).status_code,400)
        self.assertEqual(self.client.post('/api/productions/'+self.pid+'/nodes',json={'kind':'character','title':'Bad','character_id':'absent'}).status_code,400)
        with self.assertRaises(main.HTTPException):production_folders.checked_path(main,'../../escape')
        self.assertEqual(self.client.post(self.base+'/upload',data={'category':'../../escape'},files={'file':('a.txt',b'test','text/plain')}).status_code,400)

    def save_voice(self,provider='fish'):
        profile={'provider':provider,'name':'Test Voice','voice_id':'test_voice_123','url':'https://fish.audio/m/test_voice_123/' if provider=='fish' else 'https://elevenlabs.io/app/voice-library','model':'s2.1-pro' if provider=='fish' else 'eleven_multilingual_v2'}
        r=self.client.put(self.base+'/voice',json=profile);self.assertEqual(r.status_code,200,r.text)
        return profile

    def test_voice_card_audio_reference_and_invalid_link(self):
        self.setup_production();profile=self.save_voice()
        folder=main.PRODUCTIONS_ROOT/self.char['relative_dir']
        self.assertIn('test_voice_123',(folder/'04_Голос'/'ГОЛОС.json').read_text(encoding='utf-8'))
        r=self.client.post(self.base+'/upload',data={'category':'04_Голос'},files={'file':('sample.wav',b'reference-file','audio/wav')});self.assertEqual(r.status_code,200,r.text)
        card=self.client.get(self.base+'/reference-card');self.assertEqual(card.status_code,200);self.assertIn('sample.wav',card.content.decode())
        profile['url']='https://fish.audio.evil.test/m/voice';self.assertEqual(self.client.put(self.base+'/voice',json=profile).status_code,400)
        profile['url']='javascript:alert(1)';self.assertEqual(self.client.put(self.base+'/voice',json=profile).status_code,400)

    def test_approved_voice_saved_in_character_and_frame_and_never_repeats(self):
        self.setup_production();self.setup_frame();self.save_voice()
        body={'text':'Привет, пассажир!','project_id':self.frameproject}
        q=self.client.post(self.base+'/voice/estimate',json=body);self.assertEqual(q.status_code,200,q.text)
        quote=q.json();self.assertAlmostEqual(quote['estimated_usd'],len(body['text'].encode())*.000015)
        generate={**body,'request_id':'test_voice_request_123','quote_token':quote['quote_token'],'max_cost_usd':quote['estimated_usd'],'approved':True}
        with patch.object(main,'provider_key',return_value='fake-key'),patch.object(character_voice,'request_audio',AsyncMock(return_value=b'mocked-audio')) as provider,patch.object(character_voice,'inspect_audio',return_value=2.5):
            altered={**generate,'text':'другая фраза'};self.assertEqual(self.client.post(self.base+'/voice/generate',json=altered).status_code,400);provider.assert_not_called()
            r=self.client.post(self.base+'/voice/generate',json=generate);self.assertEqual(r.status_code,200,r.text)
            self.assertTrue(self.client.post(self.base+'/voice/generate',json=generate).json()['duplicate']);provider.assert_awaited_once()
        files=self.client.get(self.base).json()['files'];self.assertEqual(sum(f['kind']=='audio' for f in files),1)
        files=self.client.get(self.framebase).json()['files'];self.assertEqual(sum(f['kind']=='audio' and '04_Звук' in f['relative_path'] for f in files),1)
        economics=self.client.get('/api/economics',params={'project_id':self.frameproject}).json();self.assertAlmostEqual(economics['estimated_usd'],quote['estimated_usd'],places=6)
        self.assertEqual(self.client.post('/api/productions/'+self.pid+'/sync').status_code,200)
        files=self.client.get(self.base).json()['files'];self.assertFalse(any('03_Архив' in f['relative_path'] and f['kind']=='audio' for f in files))

    def test_missing_voice_budget_rejection_and_timeout_no_retry(self):
        self.setup_production();body={'text':'Привет','project_id':self.project}
        self.assertEqual(self.client.post(self.base+'/voice/estimate',json=body).status_code,400)
        self.save_voice();quote=self.client.post(self.base+'/voice/estimate',json=body).json()
        generate={**body,'request_id':'unknown_voice_request_123','quote_token':quote['quote_token'],'max_cost_usd':quote['estimated_usd'],'approved':True}
        with patch.object(main,'provider_key',return_value='fake'),patch.object(character_voice,'request_audio',AsyncMock(side_effect=main.HTTPException(502,'timeout'))) as provider:
            self.client.put('/api/budgets/limits',json={'project_usd':0,'daily_usd':0})
            self.assertEqual(self.client.post(self.base+'/voice/generate',json=generate).status_code,400);provider.assert_not_called()
            self.client.put('/api/budgets/limits',json={'project_usd':1,'daily_usd':2})
            self.assertEqual(self.client.post(self.base+'/voice/generate',json=generate).status_code,502)
            retry=self.client.post(self.base+'/voice/generate',json=generate).json();self.assertTrue(retry['duplicate']);self.assertEqual(retry['status'],'submission_unknown');provider.assert_awaited_once()

    def test_character_replacement_from_frame_updates_common_character_and_archive(self):
        self.setup_production();self.setup_frame()
        def image(color):
            content=io.BytesIO();Image.new('RGB',(32,48),color).save(content,format='PNG')
            r=self.client.post('/api/library/import-image',data={'project_id':self.frameproject},files={'file':('image.png',content.getvalue(),'image/png')});self.assertEqual(r.status_code,200,r.text);return r.json()['id']
        first=image('blue');second=image('green')
        for aid in [first,second]:
            r=self.client.post(f'/api/characters/{self.frameproject}/grem/replace',json={'asset_id':aid});self.assertEqual(r.status_code,200,r.text)
        for project in [self.project,self.frameproject]:
            char=self.client.get('/api/projects/'+project).json()['state']['characters'][0];self.assertEqual(char['working_asset_id'],second);self.assertIn(first,char['version_history'])
        files=self.client.get(self.base).json()['files']
        self.assertTrue(any(f['asset_id']==first and '03_Архив' in f['relative_path'] for f in files))
        self.assertFalse(any(f['asset_id']==first and '01_Основной_образ' in f['relative_path'] for f in files))
        other=self.client.post('/api/projects',json={'title':'Other','state':{}}).json()['id']
        content=io.BytesIO();Image.new('RGB',(8,8)).save(content,format='PNG')
        foreign=self.client.post('/api/library/import-image',data={'project_id':other},files={'file':('image.png',content.getvalue(),'image/png')}).json()['id']
        self.assertEqual(self.client.post(self.base+'/assets',json={'asset_id':foreign,'category':'02_Референсы'}).status_code,404)

    def test_voice_adapters_use_documented_headers_and_payloads(self):
        captured=[]
        def handler(request):
            captured.append(request);return httpx.Response(200,content=b'audio',headers={'Content-Type':'audio/mpeg'})
        original=httpx.AsyncClient
        with patch.object(character_voice.httpx,'AsyncClient',side_effect=lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs)):
            for provider,model in [('fish','s2.1-pro'),('elevenlabs','eleven_multilingual_v2')]:
                self.assertEqual(asyncio.run(character_voice.request_audio({'provider':provider,'voice_id':'voice_123','model':model},'Привет','fake')),b'audio')
        self.assertEqual(str(captured[0].url),'https://api.fish.audio/v1/tts')
        self.assertEqual(captured[0].headers['model'],'s2.1-pro')
        self.assertEqual(json.loads(captured[0].content)['reference_id'],'voice_123')
        self.assertEqual(captured[1].url.path,'/v1/text-to-speech/voice_123')
        self.assertEqual(captured[1].headers['xi-api-key'],'fake')
        self.assertEqual(json.loads(captured[1].content)['model_id'],'eleven_multilingual_v2')


if __name__=='__main__':unittest.main()
