"""Camera choices must reach prompt preparation and retain their original snapshot."""
import json
import unittest
from backend import main, native_chat, camera_movements, test_smoke

class CameraTests(unittest.TestCase):
    setUp=test_smoke.StudioSmokeTests.setUp
    tearDown=test_smoke.StudioSmokeTests.tearDown

    def make_project(self):
        self.camera={'preset_id':'dolly-in','speed':'slow','amplitude':'small','note':'Finish at the face'}
        return self.client.post('/api/projects',json={'title':'Camera test','state':{'brief':'A person waits at the window','motionBrief':'The person turns toward the window','camera':self.camera,'scene':{'brief':'A person crosses the courtyard','assets':[]}}}).json()['id']

    def test_catalogue_has_original_previews_and_unique_ids(self):
        response=self.client.get('/api/camera-presets');self.assertEqual(response.status_code,200)
        data=response.json();self.assertEqual(data['preview_type'],'original_schematic')
        ids=[p['id'] for p in data['presets']];self.assertEqual(len(ids),19);self.assertEqual(len(set(ids)),len(ids))
        self.assertIn('dolly-in',ids);self.assertIn('zoom-in',ids)

    def test_camera_reaches_video_and_scene_but_not_still_images(self):
        pid=self.make_project()
        for scene in [False,True]:
            r=self.client.post('/api/compose/preview',json={'project_id':pid,'target':'seedance-2.5','provider':'codex_chat','use_scene':scene});self.assertEqual(r.status_code,200,r.text)
            camera=r.json()['context']['camera_movement'];self.assertEqual(camera['preset_id'],'dolly-in');self.assertIn('Advance the camera',camera['instruction']);self.assertIn('Finish at the face',camera['instruction'])
            self.assertIn('camera_movement',r.json()['system_rules'])
        photo=self.client.post('/api/compose/preview',json={'project_id':pid,'target':'gpt-image-2.5'}).json()['context']
        self.assertIsNone(photo['camera_movement']);self.assertEqual(photo['motion_brief'],'')
        main.agent_completion.assert_not_awaited();main.request_piapi.assert_not_awaited()

    def test_local_video_draft_includes_selected_camera_and_actor_motion(self):
        self.make_project();body={'target':'seedance-2.5','brief':'A person at the window','camera':self.camera,'motion_brief':'Turns toward the window'}
        r=self.client.post('/api/prompt-drafts',json=body);self.assertEqual(r.status_code,200,r.text)
        self.assertIn('Advance the camera',r.json()['prompt']);self.assertIn('Turns toward the window',r.json()['prompt'])
        still=self.client.post('/api/prompt-drafts',json={**body,'target':'seedream-5-lite'}).json()['prompt'];self.assertNotIn('Advance the camera',still)

    def test_invalid_camera_settings_are_rejected_without_calls(self):
        self.make_project()
        for value in [{'preset_id':'invented'},{'preset_id':'dolly-in','speed':'warp'},{'preset_id':'pan-left','amplitude':'infinite'}]:
            r=self.client.post('/api/prompt-drafts',json={'target':'seedance-2.5','brief':'A person','camera':value});self.assertEqual(r.status_code,400,r.text)
        main.agent_completion.assert_not_awaited();main.request_piapi.assert_not_awaited()

    def test_delayed_native_prompt_keeps_camera_snapshot_after_user_changes_it(self):
        pid=self.make_project()
        r=self.client.post('/api/chatgpt/jobs',json={'project_id':pid,'target':'seedance-2.5','operation':'prompt','request_id':'camera_snapshot_request_123'})
        self.assertEqual(r.status_code,200,r.text);jid=r.json()['id']
        headers={'X-Studio-Worker':(native_chat.RUNTIME/'worker-token.txt').read_text()}
        claim=self.client.post('/api/chatgpt/worker/claim',headers=headers);self.assertEqual(claim.status_code,200,claim.text)
        project=self.client.get('/api/projects/'+pid).json();project['state']['camera']['preset_id']='dolly-out'
        self.assertEqual(self.client.post('/api/projects',json={'id':pid,'title':project['title'],'state':project['state'],'base_revision':project['revision']}).status_code,200)
        response=self.client.post('/api/chatgpt/worker/jobs/'+jid+'/progress',headers=headers,json={'status':'prompt_ready','prompt':'A person at the window. The camera advances toward them.'});self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['camera_movement']['preset_id'],'dolly-in')
        state=self.client.get('/api/projects/'+pid).json()['state'];self.assertEqual(state['camera']['preset_id'],'dolly-out')
        self.assertEqual(state['cameraPromptBasis']['seedance-2.5'],camera_movements.basis(self.camera))
        self.assertNotEqual(state['cameraPromptBasis']['seedance-2.5'],camera_movements.basis(state['camera']))

if __name__=='__main__':unittest.main()
