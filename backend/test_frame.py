"""Still-frame setup is preserved through local drafts, scenes and delayed chat results."""
import unittest
from backend import main, native_chat, frame_composition, test_smoke

class FrameTests(unittest.TestCase):
    setUp=test_smoke.StudioSmokeTests.setUp
    tearDown=test_smoke.StudioSmokeTests.tearDown

    def make_project(self):
        self.selection={'frame_id':'three-quarter','lighting_id':'soft-window','direction':'left','softness':'soft','temperature':'warm','note':'Leave space to the right'}
        return self.client.post('/api/projects',json={'title':'Frame test','state':{'brief':'The existing character at a window','composition':self.selection,'scene':{'brief':'The existing character in the existing room','assets':[]}}}).json()['id']

    def test_catalogue_has_fifteen_camera_samples_and_eight_lights(self):
        r=self.client.get('/api/frame-presets');self.assertEqual(r.status_code,200)
        data=r.json();self.assertEqual(len(data['frames']),15);self.assertEqual(len(set(p['id'] for p in data['frames'])),15);self.assertEqual(len(data['lights']),8)
        self.assertEqual(data['preview_type'],'original_schematic')
        self.assertIn('over-shoulder',[p['id'] for p in data['frames']]);self.assertIn('top-down',[p['id'] for p in data['frames']])

    def test_camera_and_lighting_enter_image_context_and_scene_but_not_video(self):
        pid=self.make_project()
        for target in ['gpt-image-2.5','seedream-5-lite']:
            for scene in [False,True]:
                r=self.client.post('/api/compose/preview',json={'project_id':pid,'target':target,'use_scene':scene});self.assertEqual(r.status_code,200,r.text)
                context=r.json()['context'];self.assertEqual(context['frame_composition']['frame_id'],'three-quarter')
                self.assertIn('camera-left',context['frame_composition']['instruction']);self.assertIn('Leave space to the right',context['frame_composition']['instruction'])
                self.assertIn('frame_composition',r.json()['system_rules']);self.assertIsNone(context['camera_movement'])
        video=self.client.post('/api/compose/preview',json={'project_id':pid,'target':'seedance-2.5'}).json()['context'];self.assertIsNone(video['frame_composition'])
        self.assertEqual(self.client.get('/api/projects/'+pid).json()['state']['composition'],self.selection)
        main.agent_completion.assert_not_awaited();main.request_piapi.assert_not_awaited()

    def test_local_image_draft_includes_frame_and_light_and_preserves_subject(self):
        self.make_project();body={'target':'seedream-5-lite','brief':'Existing character','composition':self.selection}
        r=self.client.post('/api/prompt-drafts',json=body);self.assertEqual(r.status_code,200,r.text)
        text=r.json()['prompt'];self.assertIn('three-quarter',text);self.assertIn('diffused',text);self.assertIn('camera-left',text);self.assertIn('Preserve identity',text)
        video=self.client.post('/api/prompt-drafts',json={**body,'target':'seedance-2.5'}).json()['prompt'];self.assertNotIn('Frame and light',video)
        self.assertIsNone(frame_composition.context({}))
        ots=frame_composition.context({'frame_id':'over-shoulder'})['instruction'];self.assertIn('do not invent another person',ots)

    def test_invalid_frame_and_light_are_rejected_before_external_calls(self):
        for selection in [{'frame_id':'missing'},{'lighting_id':'missing'},{'frame_id':'medium','direction':'impossible'},{'frame_id':'medium','note':'x'*1001}]:
            r=self.client.post('/api/prompt-drafts',json={'target':'gpt-image-2.5','brief':'Existing subject','composition':selection});self.assertEqual(r.status_code,400,r.text)
        main.agent_completion.assert_not_awaited();main.request_piapi.assert_not_awaited()

    def test_delayed_prompt_retains_original_frame_and_light_snapshot(self):
        pid=self.make_project()
        response=self.client.post('/api/chatgpt/jobs',json={'project_id':pid,'target':'gpt-image-2.5','operation':'prompt','request_id':'frame_snapshot_request_123'});self.assertEqual(response.status_code,200,response.text);jid=response.json()['id']
        headers={'X-Studio-Worker':(native_chat.RUNTIME/'worker-token.txt').read_text()}
        self.assertEqual(self.client.post('/api/chatgpt/worker/claim',headers=headers).status_code,200)
        project=self.client.get('/api/projects/'+pid).json();project['state']['composition']['lighting_id']='rim'
        self.assertEqual(self.client.post('/api/projects',json={'id':pid,'title':project['title'],'state':project['state'],'base_revision':project['revision']}).status_code,200)
        response=self.client.post('/api/chatgpt/worker/jobs/'+jid+'/progress',headers=headers,json={'status':'prompt_ready','prompt':'The existing character in three-quarter view with soft side lighting.'});self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['frame_composition']['lighting_id'],'soft-window')
        state=self.client.get('/api/projects/'+pid).json()['state'];self.assertEqual(state['composition']['lighting_id'],'rim')
        self.assertEqual(state['compositionPromptBasis']['gpt-image-2.5'],frame_composition.basis(self.selection))
        self.assertNotEqual(state['compositionPromptBasis']['gpt-image-2.5'],frame_composition.basis(state['composition']))

if __name__=='__main__':unittest.main()
