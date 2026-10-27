"""Режиссура в студии: контракты кадра, ревизии и непрерывность.

Проверяется тонкая интеграция контрактов в существующую доску: контракт
хранится отдельно от сцен, конфликт ревизии не перетирает чужую правку,
а нарушения непрерывности видны до того, как кадр уйдёт в генерацию.
"""
import unittest

from backend import test_production as production_tests


class DirectorStudioTests(unittest.TestCase):
    setUp = production_tests.ProductionTests.setUp
    tearDown = production_tests.ProductionTests.tearDown
    setup_production = production_tests.ProductionTests.setup_production
    new = production_tests.ProductionTests.new

    def prepare(self):
        self.setup_production()
        self.series = self.new('series', 'Режиссура')
        self.episode = self.new('episode', 'Встреча', self.series['id'])
        self.frame = self.new('frame', 'Крупный план', self.episode['id'])
        self.second = self.new('frame', 'Общий план', self.episode['id'])
        base = f'/api/productions/{self.pid}/series/{self.series["id"]}'
        self.url = base + '/director/contracts'
        self.plan_url = base + '/story-plan'
        self.client.put(self.plan_url, json={
            'base_revision': 0, 'source': 'Таксист встречает необычного гостя.', 'source_kind': 'idea',
            'cards': [{'id': 'card-1', 'scene_id': self.episode['id'], 'title': 'Встреча',
                       'summary': 'Гость садится в машину.', 'character_ids': [], 'location_id': None,
                       'stage': 'setup', 'change': ''}]})

    def fact(self, value, subject='vaz', predicate='door_state'):
        return {'subject_id': subject, 'predicate': predicate, 'value': value, 'from_value': None,
                'to_value': None, 'action': '', 'event_id': None}

    def contract(self, shot=None, scene=None, **kwargs):
        data = {
            'shot_id': shot or self.frame['id'],
            'scene_id': scene or self.episode['id'],
            'source_event_ids': ['card-1'],
            'duration_sec': 3.0,
            'narrative_role': 'setup',
            'character_ids': [],
            'asset_reference_ids': [],
            'camera': {'framing': 'medium', 'movement': '', 'direction': '', 'coordinate_space': 'actor_world'},
            'physical_state': {'continuity_mode': 'continuous', 'opening': [], 'transitions': [], 'closing': []},
            'author_lock_version': 1,
            'status': 'draft',
            'locked_paths': [],
        }
        data.update(kwargs)
        return data

    def save(self, contract, base_revision=0):
        return self.client.put(f'{self.url}/{contract["shot_id"]}',
                               json={'base_revision': base_revision, 'contract': contract})

    def test_view_lists_frames_plan_events_and_empty_contracts(self):
        self.prepare()
        view = self.client.get(self.url)
        self.assertEqual(view.status_code, 200, view.text)
        data = view.json()
        self.assertEqual([c['shot_id'] for c in data['contracts']], [self.frame['id'], self.second['id']])
        self.assertEqual([c['contract'] for c in data['contracts']], [None, None])
        self.assertEqual([c['revision'] for c in data['contracts']], [0, 0])
        self.assertEqual([e['event_id'] for e in data['events']], ['card-1'])
        self.assertTrue(data['predicates'])
        self.assertIn('vehicle_geometry', data['locked_predicates'])
        # Событие плана ещё не закреплено ни за одним кадром.
        self.assertIn('event_missing', [i['code'] for i in data['issues']])

    def test_contract_saves_once_and_conflicting_revision_is_rejected(self):
        self.prepare()
        saved = self.save(self.contract())
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()['revision'], 1)
        self.assertEqual(self.save(self.contract(), base_revision=0).status_code, 409)
        again = self.save(self.contract(status='approved'), base_revision=1)
        self.assertEqual(again.status_code, 200, again.text)
        self.assertEqual(again.json()['revision'], 2)
        stored = self.client.get(self.url).json()['contracts'][0]
        self.assertEqual(stored['revision'], 2)
        self.assertEqual(stored['contract']['status'], 'approved')

    def test_contract_of_foreign_frame_or_scene_is_rejected(self):
        self.prepare()
        self.assertEqual(self.save(self.contract(shot='foreign')).status_code, 404)
        self.assertEqual(self.save(self.contract(scene='foreign')).status_code, 400)
        other = self.new('episode', 'Другая сцена', self.series['id'])
        self.assertEqual(self.save(self.contract(scene=other['id'])).status_code, 400)

    def test_unknown_event_reference_is_reported_and_contract_stays_draft(self):
        self.prepare()
        r = self.save(self.contract(source_event_ids=['card-404'], status='approved'))
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertTrue(data['downgraded'])
        self.assertEqual(data['contract']['status'], 'draft')
        self.assertIn('shot_unknown_event', [i['code'] for i in data['issues']])

    def test_locked_property_change_is_reported(self):
        self.prepare()
        contract = self.contract(physical_state={
            'continuity_mode': 'continuous',
            'opening': [self.fact('yellow', predicate='vehicle_color')],
            'transitions': [{'subject_id': 'vaz', 'predicate': 'vehicle_color', 'value': '',
                             'from_value': 'yellow', 'to_value': 'red', 'action': '', 'event_id': 'card-1'}],
            'closing': []})
        r = self.save(contract)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn('continuity_locked_change', [i['code'] for i in r.json()['issues']])
        self.assertTrue(r.json()['downgraded'])

    def test_chain_break_between_neighbouring_shots_is_reported(self):
        self.prepare()
        first = self.contract(physical_state={'continuity_mode': 'continuous', 'opening': [self.fact('closed')],
                                              'transitions': [], 'closing': []})
        second = self.contract(shot=self.second['id'],
                               physical_state={'continuity_mode': 'continuous', 'opening': [self.fact('open')],
                                               'transitions': [], 'closing': []})
        self.assertEqual(self.save(first).status_code, 200)
        self.assertEqual(self.save(second).status_code, 200)
        issues = self.client.get(self.url).json()['issues']
        breaks = [i for i in issues if i['code'] == 'continuity_chain_break']
        self.assertEqual(len(breaks), 1)
        self.assertEqual(breaks[0]['shot_id'], self.second['id'])

    def test_state_change_inside_the_shot_saves_without_downgrade(self):
        """Объявленный переход — законное изменение, контракт остаётся утверждённым."""
        self.prepare()
        contract = self.contract(status='approved', physical_state={
            'continuity_mode': 'continuous',
            'opening': [self.fact('closed')],
            'transitions': [{'subject_id': 'vaz', 'predicate': 'door_state', 'value': '',
                             'from_value': 'closed', 'to_value': 'open',
                             'action': 'гость открывает дверь', 'event_id': 'card-1'}],
            'closing': [self.fact('open')]})
        r = self.save(contract)
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertFalse(data['downgraded'])
        self.assertEqual(data['contract']['status'], 'approved')
        self.assertEqual([i['code'] for i in data['issues'] if i['severity'] == 'error'], [])

    def test_capability_registry_is_readable(self):
        """Реестр возможностей отдаётся интерфейсу без платных вызовов."""
        self.prepare()
        r = self.client.get(f'/api/productions/{self.pid}/director/capabilities')
        self.assertEqual(r.status_code, 200, r.text)
        profiles = r.json()['profiles']
        self.assertTrue(profiles)
        kling = next(p for p in profiles if p['model_id'] == 'kling-3.0')
        self.assertTrue(kling['supports_start_frame'])
        self.assertTrue(kling['supports_end_frame'])
        self.assertIn('start_end_video', kling['available_modes'])
        h3 = next(p for p in profiles if p['model_id'] == 'minimax-h3')
        self.assertNotIn('start_end_video', h3['available_modes'])

    def test_capability_registry_reports_unknown_model(self):
        self.prepare()
        r = self.client.get(f'/api/productions/{self.pid}/director/capabilities?model=no-such-model')
        self.assertEqual(r.status_code, 404)

    def test_check_endpoint_does_not_store_anything(self):
        self.prepare()
        r = self.client.post(self.url + '/check', json={'contract': self.contract(source_event_ids=['card-404'])})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse(r.json()['ok'])
        self.assertIn('shot_unknown_event', [i['code'] for i in r.json()['issues']])
        stored = self.client.get(self.url).json()['contracts'][0]
        self.assertIsNone(stored['contract'])
        self.assertEqual(stored['revision'], 0)

    def test_plan_response_carries_director_registry(self):
        self.prepare()
        plan = self.client.get(self.plan_url).json()
        self.assertEqual([e['event_id'] for e in plan['director']['events']], ['card-1'])
        self.assertIn('door_state', plan['director']['predicates'])
        self.assertIn('vehicle_geometry', plan['director']['locked_predicates'])
