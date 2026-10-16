import unittest

from backend.model_catalog import MODEL_SPECS

NEW_PROMPT_ONLY = ('seedance-2.0', 'flux-3', 'kling-3.0-omni', 'kling-3.0')
ALL_PROFILED = NEW_PROMPT_ONLY + ('seedance-2.5', 'minimax-h3')


class RefProfilesTest(unittest.TestCase):
    def test_profiles_present(self):
        for model in ALL_PROFILED:
            spec = MODEL_SPECS[model]
            self.assertIn('ref_limits', spec, model)
            self.assertIn('ref_syntax', spec, model)

    def test_new_models_not_launchable(self):
        for model in NEW_PROMPT_ONLY:
            self.assertFalse(MODEL_SPECS[model]['launch_enabled'], model)
            self.assertNotIn('verified_at', MODEL_SPECS[model], model)

    def test_seedance_tags_and_limits(self):
        self.assertEqual(MODEL_SPECS['seedance-2.0']['ref_limits']['image'], 9)
        self.assertEqual(MODEL_SPECS['seedance-2.5']['ref_limits']['total'], 50)
        self.assertEqual(MODEL_SPECS['seedance-2.5']['ref_syntax']['image'], '@image{n}')
        self.assertEqual(MODEL_SPECS['seedance-2.5']['ref_syntax']['tasks'], ['auto', 'reference', 'edit', 'extend'])
        self.assertEqual(MODEL_SPECS['minimax-h3']['ref_syntax']['image'], 'Image {n}')
        self.assertTrue(MODEL_SPECS['minimax-h3']['ref_syntax']['piapi']['first_frame_only'])

    def test_existing_launch_flags_untouched(self):
        self.assertTrue(MODEL_SPECS['seedance-2.5']['launch_enabled'])
        self.assertTrue(MODEL_SPECS['minimax-h3']['launch_enabled'])


if __name__ == '__main__':
    unittest.main()
