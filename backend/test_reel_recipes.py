"""Меню рецептов рилсов: каталог, цены, свои рецепты. Внешних вызовов нет."""
import re
import unittest

from backend import main, reel_recipes, reel_recipes_data, test_smoke


class ReelRecipeTests(unittest.TestCase):
    setUp = test_smoke.StudioSmokeTests.setUp
    tearDown = test_smoke.StudioSmokeTests.tearDown

    def recipes(self):
        r = self.client.get('/api/reel-recipes')
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_catalogue_is_consistent_with_the_video_adapter(self):
        data = self.recipes()
        spec = main.MODEL_SPECS['seedance-2.5']
        ids = [r['id'] for r in data['recipes']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(ids), 10)
        for recipe in data['recipes']:
            videos = [s for s in recipe['steps'] if s['kind'] == 'video']
            self.assertTrue(videos, recipe['id'])
            self.assertIn(recipe['aspect_ratio'], spec['aspect_ratio'])
            self.assertIn(recipe['resolution'], spec['resolution'])
            for step in videos:
                self.assertTrue(spec['duration_min'] <= step['duration'] <= spec['duration_max'], recipe['id'])
            self.assertEqual(sum(s['duration'] for s in videos), recipe['duration'], recipe['id'])
            self.assertIsNone(recipe['verified_at'])

    def test_templates_use_only_known_placeholders_and_looks(self):
        data = self.recipes()
        for recipe in data['recipes']:
            keys = {f['key'] for f in recipe['fields']} | {'look'}
            for look in recipe['looks']:
                self.assertIn(look, data['looks'])
            for step in recipe['steps']:
                for key in re.findall(r'\{\{(\w+)\}\}', step['prompt']):
                    self.assertIn(key, keys, f"{recipe['id']}: {key}")
                # Теги референсов должны быть из слотов рецепта (клипы цепочки используют свой вход).
                tags = {int(n) for n in re.findall(r'@Image(\d+)', step['prompt'])}
                if recipe['kind'] != 'chain':
                    self.assertTrue(tags <= {s['n'] for s in recipe['ref_slots']}
                                    | set(range(1, 6)), recipe['id'])

    def test_estimate_uses_catalogue_rates(self):
        recipe = next(r for r in self.recipes()['recipes'] if r['id'] == 'night-visitor')
        self.assertEqual(recipe['estimate_usd']['480p'], round(10 * 0.15, 2))
        self.assertEqual(recipe['estimate_usd']['720p'], round(10 * 0.35, 2))
        chain = next(r for r in self.recipes()['recipes'] if r['id'] == 'butterfly-chain')
        self.assertEqual(chain['estimate_usd']['720p'], round(24 * 0.35, 2))

    def test_custom_recipe_roundtrip_and_soft_remove(self):
        body = {'title': 'Мой рецепт', 'duration': 12, 'prompt': 'One shot of a taxi at night.',
                'ref_slots': [{'role': 'Лицо героя', 'required': True}], 'notes': 'Не тряси камеру\nНе клади текст'}
        created = self.client.post('/api/reel-recipes', json=body)
        self.assertEqual(created.status_code, 200, created.text)
        item = created.json()
        self.assertFalse(item['builtin'])
        self.assertEqual(item['estimate_usd']['720p'], round(12 * 0.35, 2))
        self.assertEqual(item['pitfalls'], ['Не тряси камеру', 'Не клади текст'])
        self.assertIn(item['id'], [r['id'] for r in self.recipes()['recipes']])
        self.assertEqual(self.client.delete('/api/reel-recipes/' + item['id']).status_code, 200)
        self.assertNotIn(item['id'], [r['id'] for r in self.recipes()['recipes']])
        self.assertEqual(self.client.delete('/api/reel-recipes/' + item['id']).status_code, 404)

    def test_invalid_input_and_builtin_protection(self):
        for body in [{'title': '', 'duration': 10, 'prompt': 'x'},
                     {'title': 'a', 'duration': 3, 'prompt': 'x'},
                     {'title': 'a', 'duration': 31, 'prompt': 'x'},
                     {'title': 'a', 'duration': 10, 'prompt': ''},
                     {'title': 'a', 'duration': 10, 'prompt': 'x', 'resolution': '4k'}]:
            self.assertEqual(self.client.post('/api/reel-recipes', json=body).status_code, 422, body)
        self.assertEqual(self.client.delete('/api/reel-recipes/night-visitor').status_code, 400)
        main.request_piapi.assert_not_awaited()
        main.agent_completion.assert_not_awaited()

    def test_no_secrets_or_unknown_models_in_data(self):
        for recipe in reel_recipes_data.RECIPES:
            for step in recipe['steps']:
                self.assertIn(step['model'], main.MODEL_SPECS)
                self.assertTrue(main.MODEL_SPECS[step['model']]['launch_enabled'], step['model'])


if __name__ == '__main__':
    unittest.main()
