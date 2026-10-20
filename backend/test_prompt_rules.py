import unittest

from backend import prompt_rules
from backend.model_catalog import MODEL_SPECS


class PillarsRulesTest(unittest.TestCase):
    def test_version_bumped(self):
        self.assertEqual(prompt_rules.RULES_VERSION, '2026-10-20.1')

    def test_found_footage_profile_applies_only_when_explicit(self):
        spec = MODEL_SPECS['seedance-2.5']
        default_rules = prompt_rules.system_rules(spec)
        self.assertNotIn('FOUND-FOOTAGE PROFILE', default_rules)
        self.assertNotIn('WORLD LOCK:', default_rules)

        rules = prompt_rules.system_rules(spec, prompt_style='found-footage')
        self.assertIn('FOUND-FOOTAGE PROFILE', rules)
        self.assertIn('WORLD LOCK:', rules)
        self.assertIn('TIMECODED BEATS:', rules)
        self.assertIn('0-3s:', rules)
        self.assertIn('MANDATORY:', rules)
        self.assertIn('NEGATIVE:', rules)

    def test_found_footage_profile_does_not_leak_into_other_models(self):
        for model in ('seedream-5-lite', 'gpt-image-2'):
            with self.subTest(model=model):
                rules = prompt_rules.system_rules(MODEL_SPECS[model])
                self.assertNotIn('FOUND-FOOTAGE PROFILE', rules)
                self.assertNotIn('WORLD LOCK:', rules)

    def test_found_footage_profile_requires_video_model(self):
        with self.assertRaises(ValueError):
            prompt_rules.system_rules(
                MODEL_SPECS['gpt-image-2'],
                prompt_style='found-footage',
            )

    def test_found_footage_profile_keeps_output_contract_and_pillars(self):
        rules = prompt_rules.system_rules(
            MODEL_SPECS['seedance-2.5'],
            prompt_style='found-footage',
        )
        self.assertIn('Return ONLY the finished English generation prompt', rules)
        self.assertIn('DIRECTING PRINCIPLES', rules)
        self.assertIn('five pillars of film language', rules)

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
