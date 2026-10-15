"""Validate staging through real local prompt routes with external calls forbidden."""
import json
import unittest
from backend import main, native_chat, frame_composition, test_smoke


class DirectorStudioTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def composition(self, **car):
        return {'shot_size':'medium-close', 'car':{'shot_id':'car-rear-guest', 'steering':'left',
                'guest_seat':'rear-right', 'vehicle_state':'moving', 'light_id':'night', **car}}

    def test_additive_catalogue_preserves_original_sets(self):
        data = self.client.get('/api/frame-presets').json()
        self.assertEqual((len(data['frames']),len(data['lights']),len(data['car_shots']),len(data['car_lights'])), (15,8,12,4))
        self.assertEqual(len({s['id'] for s in data['car_shots']}),12)
        self.assertTrue(next(s for s in data['car_shots'] if s['id']=='car-windshield')['complex'])

    def test_seating_and_world_space_light_reach_still_scene_and_draft(self):
        composition=self.composition()
        project=self.client.post('/api/projects',json={'title':'Cabin test','state':{'brief':'Existing Grem and guest in the approved taxi', 'composition':composition, 'scene':{'brief':'They talk in the taxi','assets':[]}}}).json()
        for scene in (False,True):
            response=self.client.post('/api/compose/preview',json={'project_id':project['id'],'target':'gpt-image-2.5','use_scene':scene})
            self.assertEqual(response.status_code,200,response.text)
            instruction=response.json()['context']['frame_composition']['instruction']
            for expected in ('VEHICLE RIGHT rear seat','VEHICLE LEFT','world-space','not move the light','medium close-up','CAR LIGHTING'):
                self.assertIn(expected,instruction)
        draft=self.client.post('/api/prompt-drafts',json={'target':'gpt-image-2.5','brief':'Taxi conversation','composition':composition})
        self.assertEqual(draft.status_code,200,draft.text)
        self.assertIn('CAR SHOT',draft.json()['prompt'])
        video=self.client.post('/api/compose/preview',json={'project_id':project['id'],'target':'seedance-2.5'}).json()['context']
        self.assertIsNone(video['frame_composition'])
        main.agent_completion.assert_not_awaited();main.request_piapi.assert_not_awaited()

    def test_incompatible_seats_invalid_ids_and_conflicting_recipes_fail(self):
        values=[self.composition(shot_id='car-front-two'),self.composition(shot_id='car-rear-guest',guest_seat='front'),
                self.composition(shot_id='car-guest-window',guest_seat='rear-center'),self.composition(shot_id='missing'),
                self.composition(guest_seat='roof'),self.composition(light_id='missing'),
                {**self.composition(),'frame_id':'profile'},{**self.composition(),'lighting_id':'soft-window'},
                self.composition(shot_id='car-detail'),{'shot_size':'invented-size'}]
        for value in values:
            with self.subTest(value=value):
                response=self.client.post('/api/prompt-drafts',json={'target':'gpt-image-2.5','brief':'Taxi','composition':value})
                self.assertEqual(response.status_code,400,response.text)
        main.agent_completion.assert_not_awaited();main.request_piapi.assert_not_awaited()

    def test_all_car_shots_have_a_compatible_recipe(self):
        data=self.client.get('/api/frame-presets').json()
        for shot in data['car_shots']:
            car=self.composition(shot_id=shot['id'],guest_seat='front' if shot['guest_row']=='front' else 'rear-right')
            if shot['target'] not in ('driver','guest'):car['shot_size']=''
            instruction=frame_composition.context(car)['instruction']
            self.assertIn('CAR SHOT:',instruction)
            if shot['id']=='car-windshield':self.assertIn('OUTSIDE',instruction)
            if shot['id']=='car-mirror-eyes':self.assertIn('one physically correct reflection',instruction)

    def test_crop_and_angle_are_independent_and_old_signatures_unchanged(self):
        value={'frame_id':'profile','lighting_id':'rim','direction':'preset','softness':'preset','temperature':'preset','note':''}
        self.assertEqual(frame_composition.basis(value),json.dumps(value,ensure_ascii=False,separators=(',',':')))
        combined=frame_composition.context({**value,'shot_size':'close-up'})
        self.assertIn('profile view',combined['instruction']);self.assertIn('face close-up',combined['instruction'])
        self.assertIn('overrides any generic crop',combined['instruction'])

    def test_delayed_result_preserves_original_car_setup(self):
        original=self.composition()
        project=self.client.post('/api/projects',json={'title':'Delayed cabin','state':{'composition':original,'brief':'Existing driver and guest'}}).json()
        job=self.client.post('/api/chatgpt/jobs',json={'project_id':project['id'],'target':'gpt-image-2.5','operation':'prompt','request_id':'car_staging_delayed_request_123'}).json()
        headers={'X-Studio-Worker':(native_chat.RUNTIME/'worker-token.txt').read_text()}
        self.assertEqual(self.client.post('/api/chatgpt/worker/claim',headers=headers).status_code,200)
        latest=self.client.get('/api/projects/'+project['id']).json()
        changed=self.composition(guest_seat='rear-left',light_id='day')
        response=self.client.post('/api/projects',json={'id':project['id'],'title':latest['title'],'state':{**latest['state'],'composition':changed},'base_revision':latest['revision']})
        self.assertEqual(response.status_code,200,response.text)
        ready=self.client.post('/api/chatgpt/worker/jobs/'+job['id']+'/progress',headers=headers,json={'status':'prompt_ready','prompt':'Existing guest sits in rear right, night taxi light.'})
        self.assertEqual(ready.status_code,200,ready.text)
        state=self.client.get('/api/projects/'+project['id']).json()['state']
        self.assertEqual(state['composition'],changed)
        self.assertEqual(state['compositionPromptBasis']['gpt-image-2.5'],frame_composition.basis(original))
        self.assertNotEqual(state['compositionPromptBasis']['gpt-image-2.5'],frame_composition.basis(changed))


if __name__ == '__main__':
    unittest.main()
