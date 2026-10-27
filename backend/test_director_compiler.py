"""Компилятор промптов: режимы, поля, привязки референсов, предупреждения."""
import unittest

from backend.director_contracts import CapabilityProfile, compile_prompt, profile_from_catalog
from backend.model_catalog import MODEL_SPECS
from backend.test_director_contracts import LOCKED_CAR_ASSET, pilot_events, pilot_shot


def video_profile(**overrides) -> CapabilityProfile:
    """Профиль видео с подтверждёнными возможностями."""
    data = {
        'model_id': 'seedance-2.5',
        'provider': 'piapi',
        'kind': 'video',
        'modes': ['image_to_video'],
        'duration_min_sec': 4.0,
        'duration_max_sec': 30.0,
        'fps': [24],
        'aspect_ratio': ['16:9', '9:16'],
        'resolution': ['480p', '720p', '1080p'],
        'reference_roles': ['subject', 'start_frame'],
        'max_images': 10,
        'max_video_refs': 10,
        'supports_start_frame': True,
        'supports_end_frame': False,
        'supports_sound': False,
        'supports_negative_prompt': False,
        'accepted_fields': ['prompt', 'duration', 'aspect_ratio', 'resolution'],
        'price_source': 'https://piapi.ai/docs/seedance-api/seedance-25',
        'price_verified_at': '2026-10-15',
        'launch_enabled': True,
        'approval_gate': 'required',
        'verified': True,
    }
    data.update(overrides)
    return CapabilityProfile(**data)


class CompileModeTests(unittest.TestCase):
    def test_video_with_start_frame_uses_image_to_video(self):
        compiled = compile_prompt(pilot_shot(), video_profile(), pilot_events())
        self.assertEqual(compiled.mode, 'image_to_video')

    def test_profile_without_start_frame_falls_back_to_text_video(self):
        """Видеомодель без подтверждённого стартового кадра — текстовый режим видео."""
        compiled = compile_prompt(
            pilot_shot(), video_profile(supports_start_frame=False), pilot_events()
        )
        self.assertEqual(compiled.mode, 'text_to_video')

    def test_profile_with_both_frames_uses_start_end_video(self):
        compiled = compile_prompt(
            pilot_shot(), video_profile(supports_end_frame=True), pilot_events()
        )
        self.assertEqual(compiled.mode, 'start_end_video')


class CompiledTextTests(unittest.TestCase):
    def test_start_frame_describes_the_initial_state_not_the_event(self):
        """Ключевое правило: стартовый кадр — это состояние ДО действия."""
        compiled = compile_prompt(pilot_shot(), video_profile(), pilot_events())
        state_line = next(line for line in compiled.text.splitlines() if line.startswith('STATE:'))
        self.assertIn('vehicle_pose = stationary', state_line)
        self.assertNotIn('раскрывает', state_line)

    def test_action_is_taken_from_the_assigned_event(self):
        compiled = compile_prompt(pilot_shot(), video_profile(), pilot_events())
        self.assertIn('Камера раскрывает истинную длину', compiled.text)

    def test_movement_keeps_transition_order(self):
        compiled = compile_prompt(pilot_shot(), video_profile(), pilot_events())
        movement = next(line for line in compiled.text.splitlines() if line.startswith('MOVEMENT:'))
        self.assertIn('dolly reveals long body', movement)
        self.assertIn('front_left -> full_side', movement)

    def test_camera_and_duration_are_present(self):
        compiled = compile_prompt(pilot_shot(), video_profile(), pilot_events())
        self.assertIn('CAMERA: wide, dolly, left-to-right', compiled.text)
        self.assertIn('DURATION: 5s', compiled.text)

    def test_events_without_text_do_not_appear(self):
        events = pilot_events()
        events[0] = events[0].model_copy(update={'text': '   '})
        compiled = compile_prompt(pilot_shot(), video_profile(), events)
        self.assertNotIn('раскрывает', compiled.text)

    def test_actions_follow_the_timeline(self):
        shot = pilot_shot().model_copy(update={'source_event_ids': ['E003', 'E001']})
        compiled = compile_prompt(shot, video_profile(), pilot_events())
        action_line = next(line for line in compiled.text.splitlines() if line.startswith('ACTION:'))
        self.assertLess(action_line.index('раскрывает'), action_line.index('аэропорт'))


class CompiledFieldsTests(unittest.TestCase):
    def test_only_accepted_fields_are_used(self):
        compiled = compile_prompt(pilot_shot(), video_profile(), pilot_events())
        self.assertIn('prompt', compiled.fields)
        self.assertIn('duration', compiled.fields)
        self.assertNotIn('negative_prompt', compiled.fields)
        self.assertNotIn('seed', compiled.fields)

    def test_duration_field_follows_the_contract(self):
        shot = pilot_shot().model_copy(update={'duration_sec': 7.5})
        compiled = compile_prompt(shot, video_profile(), pilot_events())
        self.assertEqual(compiled.fields['duration'], 7.5)

    def test_revisions_are_recorded(self):
        compiled = compile_prompt(pilot_shot(), video_profile(), pilot_events())
        self.assertTrue(compiled.shot_revision)
        self.assertTrue(compiled.provider_profile_revision)
        self.assertTrue(compiled.immutable_source_digest)

    def test_immutable_digest_is_stable_for_equal_contracts(self):
        first = compile_prompt(pilot_shot(), video_profile(), pilot_events())
        second = compile_prompt(pilot_shot(), video_profile(), pilot_events())
        self.assertEqual(first.immutable_source_digest, second.immutable_source_digest)

    def test_immutable_digest_changes_with_locked_source(self):
        shot = pilot_shot().model_copy(update={'asset_reference_ids': ['another_asset']})
        compiled = compile_prompt(shot, video_profile(), pilot_events())
        self.assertNotEqual(
            compiled.immutable_source_digest,
            compile_prompt(pilot_shot(), video_profile(), pilot_events()).immutable_source_digest,
        )


class ReferenceBindingTests(unittest.TestCase):
    def test_first_asset_is_the_subject(self):
        compiled = compile_prompt(pilot_shot(), video_profile(), pilot_events())
        binding = compiled.reference_bindings[0]
        self.assertEqual(binding.asset_id, LOCKED_CAR_ASSET)
        self.assertEqual(binding.role, 'subject')

    def test_extra_assets_become_start_frame_for_video(self):
        shot = pilot_shot().model_copy(update={'asset_reference_ids': [LOCKED_CAR_ASSET, 'frame_start']})
        compiled = compile_prompt(shot, video_profile(), pilot_events())
        roles = [binding.role for binding in compiled.reference_bindings]
        self.assertIn('start_frame', roles)

    def test_end_frame_only_when_profile_supports_it(self):
        shot = pilot_shot().model_copy(
            update={'asset_reference_ids': [LOCKED_CAR_ASSET, 'frame_start', 'frame_end']}
        )
        without = compile_prompt(shot, video_profile(supports_end_frame=False), pilot_events())
        self.assertNotIn('end_frame', [binding.role for binding in without.reference_bindings])
        with_end = compile_prompt(shot, video_profile(supports_end_frame=True), pilot_events())
        self.assertIn('end_frame', [binding.role for binding in with_end.reference_bindings])


class CompilerWarningTests(unittest.TestCase):
    def test_unverified_profile_warns(self):
        compiled = compile_prompt(
            pilot_shot(), video_profile(verified=False, launch_enabled=False), pilot_events()
        )
        self.assertTrue(any('UNVERIFIED' in warning for warning in compiled.warnings))

    def test_duration_over_limit_warns(self):
        shot = pilot_shot().model_copy(update={'duration_sec': 60.0})
        compiled = compile_prompt(shot, video_profile(duration_max_sec=30.0), pilot_events())
        self.assertTrue(any('превышает максимум' in warning for warning in compiled.warnings))

    def test_missing_asset_warns(self):
        compiled = compile_prompt(pilot_shot(), video_profile(), pilot_events(), assets=set())
        self.assertTrue(any('вне библиотеки' in warning for warning in compiled.warnings))

    def test_shot_without_events_warns(self):
        shot = pilot_shot().model_copy(update={'source_event_ids': []})
        compiled = compile_prompt(shot, video_profile(), pilot_events())
        self.assertTrue(any('ни одного события' in warning for warning in compiled.warnings))

    def test_start_end_video_without_support_warns(self):
        compiled = compile_prompt(
            pilot_shot(), video_profile(supports_start_frame=True, supports_end_frame=True),
            pilot_events(),
        )
        self.assertEqual(compiled.mode, 'start_end_video')
        compiled = compile_prompt(
            pilot_shot(), video_profile(supports_start_frame=True, supports_end_frame=False),
            pilot_events(),
        )
        self.assertNotIn('start_end_video', compiled.mode)


class CatalogProfileTests(unittest.TestCase):
    def test_profile_is_built_from_the_existing_catalog(self):
        profile = profile_from_catalog(MODEL_SPECS['seedance-2.5'])
        self.assertEqual(profile.kind, 'video')
        self.assertEqual(profile.provider, 'piapi')
        self.assertEqual(profile.duration_max_sec, 30.0)
        self.assertIn('16:9', profile.aspect_ratio)

    def test_unverified_catalog_entry_is_not_ready(self):
        profile = profile_from_catalog(MODEL_SPECS['kling-3.0'])
        self.assertNotEqual(profile.state, 'READY')

    def test_missing_capabilities_are_not_invented(self):
        profile = profile_from_catalog(MODEL_SPECS['seedance-2.5'])
        self.assertFalse(profile.supports_end_frame)
        self.assertFalse(profile.supports_sound)


if __name__ == '__main__':
    unittest.main()
