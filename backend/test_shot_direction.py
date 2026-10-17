"""Storyboard settings survive saves and control future jobs without generation."""
import json
import unittest
from types import SimpleNamespace
from backend import main, production_entities, shot_direction, test_production


class ShotDirectionTests(unittest.TestCase):
    setUp = test_production.ProductionTests.setUp
    tearDown = test_production.ProductionTests.tearDown
    setup_production = test_production.ProductionTests.setup_production
    setup_frame = test_production.ProductionTests.setup_frame
    new = test_production.ProductionTests.new

    def prepare(self):
        self.setup_production()
        self.setup_frame()
        self.scene_path = f'/api/productions/{self.pid}/nodes/{self.frame["parent_id"]}'
        self.save(self.scene_path, character_node_ids=[self.char['id']])

    def save(self, path, **patch):
        card = self.client.get(path+'/editor').json()
        response = self.client.put(path+'/editor', json={**card['data'], 'notes': card['node']['notes'],
                                                       'base_revision': card['revision'], **patch})
        self.assertEqual(response.status_code, 200, response.text)
        return self.client.get(path+'/editor').json()

    def context(self, target='gpt-image-2.5'):
        card = self.client.get(self.framebase+'/editor').json()
        return production_entities.context(main, SimpleNamespace(production_id=self.pid,
            production_node_id=self.frame['id'], project_id=self.frameproject,
            entity_revision=card['revision'], entity_instruction='Test task', target=target))

    def test_save_revision_disk_and_image_video_intent(self):
        self.prepare()
        old = self.client.get(self.framebase+'/editor').json()
        shot = {'size': 'close', 'subject_ids': [self.char['id']], 'movement': 'dolly-in',
                'focal_mm': 50, 'aperture': 2.8, 'focus': 'subject', 'note': 'Show the reaction'}
        card = self.save(self.framebase, shooting=shot)
        self.assertEqual(card['data']['shooting'], shot)
        self.assertNotEqual(old['revision'], card['revision'])
        disk = main.PRODUCTIONS_ROOT/self.frame['relative_dir']/'КАРТОЧКА.json'
        self.assertEqual(json.loads(disk.read_text(encoding='utf-8'))['shooting'], shot)
        image = self.context()['brief']
        self.assertIn('50 mm', image)
        self.assertIn('f/2.8', image)
        self.assertIn('STILL KEYFRAME:', image)
        self.assertNotIn('CAMERA MOTION:', image)
        self.assertIn('CAMERA MOTION:', self.context('seedance-2.5')['brief'])
        stale = self.client.put(self.framebase+'/editor', json={**old['data'],
            'notes': '', 'base_revision': old['revision'], 'shooting': shot})
        self.assertEqual(stale.status_code, 409)

    def test_inherited_explicit_and_empty_subjects(self):
        self.prepare()
        self.assertIn(self.char['id'], [p['id'] for p in self.context()['scene']['participants']])
        self.save(self.framebase, shooting={'subject_ids': []})
        self.assertNotIn(self.char['id'], [p['id'] for p in self.context()['scene']['participants']])
        self.assertIn('No characters', self.context()['brief'])
        self.save(self.framebase, shooting={'subject_ids': None})
        self.assertIn(self.char['id'], [p['id'] for p in self.context()['scene']['participants']])

    def test_invalid_subject_movement_and_lens_rejected(self):
        self.prepare()
        card = self.client.get(self.framebase+'/editor').json()
        body = {**card['data'], 'notes': '', 'base_revision': card['revision']}
        for shot, status in [({'subject_ids': ['foreign']}, 400),
                             ({'subject_ids': [self.char['id']]*2}, 400),
                             ({'movement': 'invented'}, 400),
                             ({'focal_mm': -1}, 422), ({'aperture': 0}, 422)]:
            response = self.client.put(self.framebase+'/editor', json={**body, 'shooting': shot})
            self.assertEqual(response.status_code, status, response.text)

    def test_legacy_client_keeps_saved_direction(self):
        self.prepare()
        self.save(self.framebase, shooting={'size': 'wide'})
        card = self.client.get(self.framebase+'/editor').json()
        legacy = {k: v for k, v in card['data'].items() if k != 'shooting'}
        response = self.client.put(self.framebase+'/editor', json={**legacy, 'notes': 'Edited',
                                                                  'base_revision': card['revision']})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get(self.framebase+'/editor').json()['data']['shooting']['size'], 'wide')


if __name__ == '__main__':
    unittest.main()
