import unittest

from backend import prompt_rules
from backend.model_catalog import MODEL_SPECS


class PillarsRulesTest(unittest.TestCase):
    def test_version_bumped(self):
        self.assertEqual(prompt_rules.RULES_VERSION, '2026-10-16.1')

    def test_pillars_in_image_and_video_rules(self):
        for model in ('seedream-5-lite', 'gpt-image-2', 'seedance-2.5', 'minimax-h3'):
            rules = prompt_rules.system_rules(MODEL_SPECS[model])
            self.assertIn('DIRECTING PRINCIPLES', rules, model)
            self.assertIn('DOMINANT', rules, model)
            self.assertIn('never invent props or characters', rules, model)

    def test_camera_motive_only_for_video(self):
        video = prompt_rules.system_rules(MODEL_SPECS['seedance-2.5'])
        image = prompt_rules.system_rules(MODEL_SPECS['seedream-5-lite'])
        self.assertIn('push in (approach the emotion)', video)
        self.assertNotIn('exactly one camera motive', image)

    def test_output_contract_unchanged(self):
        rules = prompt_rules.system_rules(MODEL_SPECS['seedream-5-lite'])
        self.assertIn('Return ONLY the finished English generation prompt', rules)


if __name__ == '__main__':
    unittest.main()
