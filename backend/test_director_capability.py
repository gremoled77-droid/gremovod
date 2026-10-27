"""Реестр возможностей моделей: подтверждённое — да, неподтверждённое — нет.

Требование ТЗ: выбор first/last-frame недоступен у модели, которая этот способ
не поддерживает, и неуспешный платный запрос не инициируется. Значит профиль
должен уметь сказать «не подтверждено», а не молчать.
"""
import unittest

from backend.director_contracts import (
    CapabilityProfile,
    available_modes,
    facts_for,
    mode_available,
    profile_for,
    registry,
)
from backend.model_catalog import MODEL_SPECS


class CapabilityRegistryTests(unittest.TestCase):
    def test_registry_covers_every_model_of_the_catalog(self):
        profiles = registry()
        self.assertEqual(len(profiles), len(MODEL_SPECS))
        self.assertEqual({p.model_id for p in profiles}, {str(k) for k in MODEL_SPECS})

    def test_kling_3_confirms_start_and_end_frame(self):
        profile = profile_for('kling-3.0')
        self.assertTrue(profile.supports_start_frame)
        self.assertTrue(profile.supports_end_frame)
        self.assertTrue(profile.supports_sound)
        self.assertEqual(profile.duration_min_sec, 3)
        self.assertEqual(profile.duration_max_sec, 15)
        self.assertIn('start_end_video', available_modes(profile))

    def test_minimax_h3_confirms_only_the_first_frame(self):
        profile = profile_for('minimax-h3')
        self.assertTrue(profile.supports_start_frame)
        self.assertFalse(profile.supports_end_frame)
        self.assertNotIn('start_end_video', available_modes(profile))
        self.assertIn('image_to_video', available_modes(profile))

    def test_seedance_2_5_has_no_confirmed_key_frames(self):
        """У Seedance 2.5 в источнике режимы edit/extend, отдельных first/last нет."""
        profile = profile_for('seedance-2.5')
        self.assertFalse(profile.supports_start_frame)
        self.assertFalse(profile.supports_end_frame)
        self.assertNotIn('image_to_video', available_modes(profile))

    def test_unconfirmed_model_stays_unverified_and_blocked(self):
        profile = profile_for('wan-3.0')
        self.assertEqual(profile.state, 'UNVERIFIED')
        self.assertFalse(profile.launch_enabled)
        self.assertFalse(mode_available(profile, 'start_end_video'))

    def test_model_without_facts_gets_no_capabilities(self):
        profile = profile_for('flux-3')
        self.assertEqual(facts_for('flux-3'), {})
        self.assertFalse(profile.supports_start_frame)
        self.assertFalse(profile.supports_end_frame)
        self.assertEqual(available_modes(profile), ['text_to_video'])

    def test_facts_are_cited_by_the_source(self):
        profile = profile_for('kling-3.0')
        self.assertIn('kling-3-start-end-frame', profile.capability_source)

    def test_unknown_model_is_not_invented(self):
        with self.assertRaises(KeyError):
            profile_for('model-that-does-not-exist')

    def test_image_models_keep_text_to_image_mode(self):
        profile = profile_for('seedream-5-lite')
        self.assertEqual(profile.kind, 'image')
        self.assertIn('text_to_image', available_modes(profile))
        self.assertNotIn('image_to_video', available_modes(profile))

    def test_profile_of_a_verified_model_is_ready(self):
        profile = profile_for('minimax-h3')
        self.assertTrue(profile.verified)
        self.assertEqual(profile.state, 'READY')


if __name__ == '__main__':
    unittest.main()
