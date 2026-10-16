import unittest
from backend import main, test_production, visual_plan


class CompositionTests(unittest.TestCase):
    setUp = test_production.ProductionTests.setUp
    tearDown = test_production.ProductionTests.tearDown
    setup_production = test_production.ProductionTests.setup_production
    new = test_production.ProductionTests.new

    def tree(self):
        self.setup_production()
        series = self.new('series', 'Серия')
        scene = self.new('episode', 'Встреча', series['id'])
        return series, scene, self.new('frame', 'Крупный план', scene['id'])

    def put(self, node, body):
        return self.client.put(f'/api/productions/{self.pid}/nodes/{node["id"]}/visual-plan', json=body)

    def test_balance_and_counterweight_saved_validated_and_in_rules(self):
        series, scene, frame = self.tree()
        r = self.put(frame, {'balance': 'tense', 'counterweight': 'small lamp far left', 'sector_end': 6})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['balance'], 'tense')
        self.assertEqual(self.put(frame, {'balance': 'wobbly'}).status_code, 422)
        self.assertEqual(self.put(frame, {'counterweight': 'x' * 301}).status_code, 422)
        got = self.client.get(f'/api/productions/{self.pid}/series/{series["id"]}/visual-plan').json()['plans']
        self.assertEqual(got[frame['id']]['counterweight'], 'small lamp far left')
        self.assertEqual(visual_plan.clean({'balance': 'x'})['balance'], '')
        with main.connect() as db:
            self.assertIn('tense unbalanced', visual_plan.rules_text(db, self.pid, frame['id']))
            self.assertIn('counterweight: small lamp far left', visual_plan.rules_text(db, self.pid, frame['id']))

    def test_brief_uses_plan_and_scene_fallback(self):
        series, scene, frame = self.tree()
        self.put(scene, {'balance': 'stable', 'counterweight': 'distant tree'})
        self.put(frame, {'sector_end': 3})
        with main.connect() as db:
            brief = visual_plan.composition_brief(db, self.pid, frame['id'])
        self.assertTrue(brief.startswith('VISUAL COMPOSITION BRIEF'))
        self.assertIn('upper right', brief)
        self.assertIn('stable balanced', brief)
        self.assertIn('counterweight: distant tree', brief)
        self.assertIn('black and white', brief)

    def test_brief_without_plan_still_has_fixed_rules_and_sector_places(self):
        with main.connect() as db:
            generic = visual_plan.composition_brief(db, '', '')
        self.assertIn('Only one dominant element', generic)
        self.assertNotIn('counterweight:', generic)
        self.assertEqual([visual_plan.sector_place(n) for n in (1, 5, 9)], ['upper left', 'center', 'lower right'])
        self.assertEqual(visual_plan.sector_place(0), '')

    def test_project_endpoint(self):
        series, scene, frame = self.tree()
        self.put(frame, {'balance': 'tense'})
        opened = self.client.post(f'/api/productions/{self.pid}/nodes/{frame["id"]}/open-project').json()['project_id']
        self.assertIn('tense unbalanced', self.client.get(f'/api/projects/{opened}/composition-brief').json()['prompt'])
        alone = self.client.post('/api/projects', json={'title': 'Alone', 'state': {}}).json()['id']
        self.assertIn('VISUAL COMPOSITION BRIEF', self.client.get(f'/api/projects/{alone}/composition-brief').json()['prompt'])
        self.assertEqual(self.client.get('/api/projects/absent/composition-brief').status_code, 404)


if __name__ == '__main__':
    unittest.main()
