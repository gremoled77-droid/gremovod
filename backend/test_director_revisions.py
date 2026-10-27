"""Ревизии и точечный ремонт: отпечатки состояния, транзакционные правки."""
import unittest

from backend.director_contracts import (
    RepairError,
    apply_patch,
    build_patch,
    changed_paths,
    current_revision,
    fingerprint,
    fingerprint_shot,
    is_stale,
    propose,
    repair,
)
from backend.test_director_contracts import (
    LOCKED_CAR_ASSET,
    LOCKED_GEOMETRY,
    pilot_events,
    pilot_shot,
)


class FingerprintTests(unittest.TestCase):
    def test_fingerprint_ignores_key_order(self):
        self.assertEqual(fingerprint({'a': 1, 'b': 2}), fingerprint({'b': 2, 'a': 1}))

    def test_fingerprint_changes_with_content(self):
        self.assertNotEqual(fingerprint({'a': 1}), fingerprint({'a': 2}))

    def test_shot_fingerprint_is_stable_for_equal_contracts(self):
        self.assertEqual(fingerprint_shot(pilot_shot()), fingerprint_shot(pilot_shot()))

    def test_stale_is_detected_after_change(self):
        shot = pilot_shot()
        digest = fingerprint_shot(shot)
        self.assertFalse(is_stale(digest, shot))
        changed = shot.model_copy(update={'duration_sec': 6.0})
        self.assertTrue(is_stale(digest, changed))

    def test_empty_expected_fingerprint_is_never_stale(self):
        self.assertFalse(is_stale('', pilot_shot()))

    def test_proposal_keeps_original_and_accepted(self):
        shot = pilot_shot()
        revision = current_revision(shot)
        self.assertFalse(revision.has_proposal)
        proposal = shot.model_copy(update={'duration_sec': 6.0})
        revision = propose(shot, proposal)
        self.assertTrue(revision.has_proposal)
        self.assertEqual(revision.accepted_fingerprint, fingerprint_shot(shot))
        self.assertNotEqual(revision.proposed_fingerprint, revision.accepted_fingerprint)

    def test_changed_paths_lists_only_differences(self):
        before = pilot_shot()
        after = before.model_copy(update={'duration_sec': 6.0, 'narrative_role': 'setup'})
        paths = changed_paths(before, after)
        self.assertIn('duration_sec', paths)
        self.assertIn('narrative_role', paths)
        self.assertNotIn('shot_id', paths)


class RepairTests(unittest.TestCase):
    def test_repair_changes_only_named_field(self):
        shot = pilot_shot()
        fixed = repair(shot, {'duration_sec': 6.0})
        self.assertEqual(fixed.duration_sec, 6.0)
        self.assertEqual(fixed.shot_id, shot.shot_id)
        self.assertEqual(fixed.camera.framing, shot.camera.framing)

    def test_repair_does_not_mutate_the_original(self):
        shot = pilot_shot()
        repair(shot, {'duration_sec': 6.0})
        self.assertEqual(shot.duration_sec, 5.0)

    def test_locked_path_is_rejected(self):
        shot = pilot_shot().model_copy(update={'locked_paths': ['camera.framing']})
        with self.assertRaises(RepairError):
            repair(shot, {'camera.framing': 'close'})

    def test_asset_references_cannot_be_replaced(self):
        with self.assertRaises(RepairError):
            repair(pilot_shot(), {'asset_reference_ids': ['other_asset']})

    def test_source_events_cannot_be_rewritten(self):
        with self.assertRaises(RepairError):
            repair(pilot_shot(), {'source_event_ids': []})

    def test_unknown_field_is_rejected(self):
        with self.assertRaises(RepairError):
            repair(pilot_shot(), {'nonsense_field': 1})

    def test_schema_violation_leaves_contract_untouched(self):
        shot = pilot_shot()
        with self.assertRaises(RepairError):
            repair(shot, {'duration_sec': -5})
        self.assertEqual(shot.duration_sec, 5.0)

    def test_locked_geometry_cannot_be_changed_by_patch(self):
        shot = pilot_shot()
        with self.assertRaises(RepairError):
            repair(shot, {'physical_state.closing[1].value': 'vaz_2106_sedan'})
        self.assertEqual(shot.physical_state.closing[1].value, LOCKED_GEOMETRY)

    def test_patch_that_breaks_continuity_is_rejected(self):
        shot = pilot_shot()
        with self.assertRaises(RepairError):
            repair(shot, {'physical_state.closing[0].value': 'moving'})
        self.assertEqual(shot.physical_state.closing[0].value, 'stationary')

    def test_valid_nested_patch_is_applied(self):
        shot = pilot_shot()
        fixed = repair(shot, {'camera.movement': 'crane'})
        self.assertEqual(fixed.camera.movement, 'crane')
        self.assertEqual(fixed.camera.framing, 'wide')

    def test_build_patch_rejects_empty_changes(self):
        with self.assertRaises(RepairError):
            build_patch(pilot_shot(), {})

    def test_apply_patch_rejects_empty_operations(self):
        with self.assertRaises(RepairError):
            apply_patch(pilot_shot(), [])

    def test_patch_may_touch_unlocked_physical_facts(self):
        shot = pilot_shot()
        fixed = repair(
            shot,
            {
                'physical_state.opening[0].value': 'stationary_rear',
                'physical_state.closing[0].value': 'stationary_rear',
            },
        )
        self.assertEqual(fixed.physical_state.opening[0].value, 'stationary_rear')
        self.assertEqual(fixed.physical_state.closing[0].value, 'stationary_rear')
        self.assertEqual(shot.physical_state.opening[0].value, 'stationary')

    def test_rejected_patch_does_not_change_event_coverage(self):
        events = pilot_events()
        shot = pilot_shot()
        with self.assertRaises(RepairError):
            repair(shot, {'source_event_ids': []})
        self.assertEqual(shot.source_event_ids, ['E001'])
        self.assertEqual(len(events), 3)


if __name__ == '__main__':
    unittest.main()
