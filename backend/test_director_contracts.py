"""P0-контракты режиссура: реестр событий и физическая непрерывность.

Тестовый канон — пилот: Грэм, жёлтый ВАЗ-2106 *удлинённый VIP-лимузин*,
пассажир, аэропорт, раскрытие длины. Геометрия машины и внешность — locked.
"""
import unittest

from backend.director_contracts import (
    PhysicalFact,
    ShotContract,
    SourceEvent,
    check_chain,
    check_continuity,
    check_ids_stable,
    film_order,
    has_errors,
    timeline_order,
    validate_contracts,
)

PILOT_EPISODE = 'pilot-01'
CAR = 'car_2106'
GRAEM = 'grem'
LOCKED_CAR_ASSET = 'approved_car_2106_left_v4'
LOCKED_GEOMETRY = 'vaz_2106_vip_extended_v4'


def pilot_events() -> list[SourceEvent]:
    """События пилота. E001 показывается вторым, но по времени идёт первым."""
    return [
        SourceEvent(
            event_id='E001',
            episode_id=PILOT_EPISODE,
            text='Камера раскрывает истинную длину жёлтого лимузина',
            kind='mandatory_action',
            locked=True,
            presentation_order=2,
            timeline_order=1,
        ),
        SourceEvent(
            event_id='E002',
            episode_id=PILOT_EPISODE,
            text='Грэм садится за руль и смотрит на пассажира',
            kind='mandatory_action',
            locked=True,
            causal_after=['E001'],
            presentation_order=1,
            timeline_order=2,
        ),
        SourceEvent(
            event_id='E003',
            episode_id=PILOT_EPISODE,
            text='Пассажир просит ехать в аэропорт',
            kind='dialogue',
            locked=True,
            causal_after=['E002'],
            presentation_order=3,
            timeline_order=3,
        ),
    ]


def pilot_shot() -> ShotContract:
    """Кадр раскрытия длины лимузина."""
    return ShotContract(
        shot_id='SHOT-003',
        scene_id='SCENE-001',
        source_event_ids=['E001'],
        duration_sec=5.0,
        narrative_role='reveal',
        character_ids=[GRAEM],
        asset_reference_ids=[LOCKED_CAR_ASSET],
        camera={'framing': 'wide', 'movement': 'dolly', 'direction': 'left-to-right'},
        physical_state={
            'continuity_mode': 'continuous',
            'opening': [
                PhysicalFact(subject_id=CAR, predicate='vehicle_pose', value='stationary'),
                PhysicalFact(subject_id=CAR, predicate='vehicle_geometry', value=LOCKED_GEOMETRY),
            ],
            'transitions': [
                PhysicalFact(
                    subject_id='camera_1',
                    predicate='camera_position',
                    from_value='front_left',
                    to_value='full_side',
                    action='dolly reveals long body',
                    event_id='E001',
                )
            ],
            'closing': [
                PhysicalFact(subject_id=CAR, predicate='vehicle_pose', value='stationary'),
                PhysicalFact(subject_id=CAR, predicate='vehicle_geometry', value=LOCKED_GEOMETRY),
            ],
        },
        author_lock_version=4,
        status='draft',
    )


def pilot_assets() -> set[str]:
    return {LOCKED_CAR_ASSET}


class EventLedgerTests(unittest.TestCase):
    def test_events_must_have_unique_ids(self):
        events = pilot_events()
        events.append(events[0].model_copy(update={'timeline_order': 9}))
        issues = validate_contracts(events, [pilot_shot()])
        self.assertIn('event_duplicate_id', [issue.code for issue in issues])

    def test_causal_order_must_follow_the_timeline(self):
        events = pilot_events()
        broken = events[2].model_copy(update={'causal_after': ['E001'], 'timeline_order': 0})
        issues = validate_contracts([events[0], events[1], broken], [pilot_shot()])
        self.assertIn('event_causal_order', [issue.code for issue in issues])

    def test_unknown_causal_reference_is_reported(self):
        events = pilot_events()
        broken = events[1].model_copy(update={'causal_after': ['E999']})
        issues = validate_contracts([events[0], broken, events[2]], [pilot_shot()])
        self.assertIn('event_unknown_causal', [issue.code for issue in issues])

    def test_locked_event_must_be_covered(self):
        issues = validate_contracts(pilot_events(), [])
        self.assertIn('event_missing', [issue.code for issue in issues])
        self.assertTrue(has_errors(issues))

    def test_locked_event_cannot_be_covered_twice(self):
        second = pilot_shot().model_copy(update={'shot_id': 'SHOT-004'})
        issues = validate_contracts(pilot_events(), [pilot_shot(), second])
        self.assertIn('event_covered_twice', [issue.code for issue in issues])

    def test_repeatable_motif_may_be_covered_twice(self):
        events = pilot_events()
        repeatable = events[0].model_copy(update={'repeatable': True})
        second = pilot_shot().model_copy(update={'shot_id': 'SHOT-004'})
        issues = validate_contracts([repeatable, events[1], events[2]], [pilot_shot(), second])
        self.assertNotIn('event_covered_twice', [issue.code for issue in issues])

    def test_shot_cannot_reference_unknown_event(self):
        shot = pilot_shot().model_copy(update={'source_event_ids': ['E404']})
        issues = validate_contracts(pilot_events(), [shot])
        self.assertIn('shot_unknown_event', [issue.code for issue in issues])

    def test_flashback_order_difference_is_not_an_error(self):
        events = pilot_events()
        issues = validate_contracts(events, [pilot_shot()])
        self.assertNotIn('event_causal_order', [issue.code for issue in issues])
        self.assertEqual(film_order(events), ['E002', 'E001', 'E003'])
        self.assertEqual(timeline_order(events), ['E001', 'E002', 'E003'])

    def test_locked_event_id_must_not_disappear(self):
        issues = check_ids_stable(pilot_events(), {'E001', 'E002', 'E003'})
        self.assertEqual(issues, [])
        issues = check_ids_stable(pilot_events()[:2], {'E001', 'E002', 'E003'})
        self.assertIn('event_id_unstable', [issue.code for issue in issues])

    def test_asset_reference_must_exist_in_library(self):
        issues = validate_contracts(pilot_events(), [pilot_shot()], assets={'other_asset'})
        self.assertIn('asset_unknown', [issue.code for issue in issues])
        issues = validate_contracts(pilot_events(), [pilot_shot()], assets=pilot_assets())
        self.assertNotIn('asset_unknown', [issue.code for issue in issues])


class ContinuityTests(unittest.TestCase):
    def test_matching_opening_and_closing_pass(self):
        issues = check_continuity(pilot_shot())
        self.assertEqual([i for i in issues if i.severity == 'error'], [])

    def test_state_mismatch_between_opening_and_closing_is_reported(self):
        shot = pilot_shot()
        shot.physical_state.closing[0].value = 'moving'
        issues = check_continuity(shot)
        self.assertIn('continuity_value_mismatch', [issue.code for issue in issues])

    def test_change_declared_by_a_transition_is_not_a_mismatch(self):
        """Дверь открывается внутри кадра: конец кадра — это состояние после перехода."""
        shot = pilot_shot()
        shot.physical_state.opening.append(
            PhysicalFact(subject_id=CAR, predicate='door_state', value='closed')
        )
        shot.physical_state.transitions.append(
            PhysicalFact(
                subject_id=CAR,
                predicate='door_state',
                from_value='closed',
                to_value='open',
                action='guest opens the door',
                event_id='E001',
            )
        )
        shot.physical_state.closing.append(
            PhysicalFact(subject_id=CAR, predicate='door_state', value='open')
        )
        issues = check_continuity(shot)
        self.assertEqual([i for i in issues if i.severity == 'error'], [])
        self.assertNotIn('continuity_value_mismatch', [i.code for i in issues])

    def test_closing_must_match_the_state_after_transitions(self):
        """Переход открыл дверь, а в конце кадра она закрыта — это ошибка."""
        shot = pilot_shot()
        shot.physical_state.opening.append(
            PhysicalFact(subject_id=CAR, predicate='door_state', value='closed')
        )
        shot.physical_state.transitions.append(
            PhysicalFact(
                subject_id=CAR,
                predicate='door_state',
                from_value='closed',
                to_value='open',
                action='guest opens the door',
                event_id='E001',
            )
        )
        shot.physical_state.closing.append(
            PhysicalFact(subject_id=CAR, predicate='door_state', value='closed')
        )
        issues = check_continuity(shot)
        self.assertIn('continuity_value_mismatch', [i.code for i in issues])

    def test_fact_that_appears_only_at_the_end_is_a_warning(self):
        shot = pilot_shot()
        shot.physical_state.closing.append(
            PhysicalFact(subject_id=CAR, predicate='door_state', value='open')
        )
        issues = check_continuity(shot)
        undeclared = [i for i in issues if i.code == 'continuity_undeclared_closing']
        self.assertEqual(len(undeclared), 1)
        self.assertEqual(undeclared[0].severity, 'warning')

    def test_transition_must_reference_an_event(self):
        shot = pilot_shot()
        shot.physical_state.transitions[0].event_id = None
        issues = check_continuity(shot)
        self.assertIn('continuity_transition_without_event', [issue.code for issue in issues])

    def test_unknown_predicate_is_a_warning_not_an_error(self):
        shot = pilot_shot()
        shot.physical_state.opening[0].predicate = 'weather_vibe'
        issues = check_continuity(shot)
        unknown = [i for i in issues if i.code == 'continuity_unknown_predicate']
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0].severity, 'warning')

    def test_locked_geometry_cannot_change_inside_a_shot(self):
        shot = pilot_shot()
        shot.physical_state.closing[1].value = 'vaz_2106_sedan'
        issues = check_continuity(shot)
        self.assertIn('continuity_locked_change', [issue.code for issue in issues])

    def test_chain_break_between_neighbouring_shots(self):
        first = pilot_shot()
        second = pilot_shot().model_copy(update={'shot_id': 'SHOT-004', 'source_event_ids': []})
        second.physical_state.opening[0].value = 'moving'
        issues = check_chain([first, second])
        self.assertIn('continuity_chain_break', [issue.code for issue in issues])

    def test_time_jump_skips_state_comparison(self):
        first = pilot_shot()
        second = pilot_shot().model_copy(update={'shot_id': 'SHOT-004', 'source_event_ids': []})
        second.physical_state.continuity_mode = 'time_jump'
        second.physical_state.opening[0].value = 'moving'
        issues = check_chain([first, second])
        self.assertEqual([i for i in issues if i.code == 'continuity_chain_break'], [])

    def test_flashback_does_not_compare_states(self):
        shot = pilot_shot()
        shot.physical_state.continuity_mode = 'flashback'
        shot.physical_state.closing[0].value = 'moving'
        issues = check_continuity(shot)
        self.assertNotIn('continuity_value_mismatch', [issue.code for issue in issues])


class ValidationOrderTests(unittest.TestCase):
    def test_issue_order_is_deterministic(self):
        events = pilot_events()
        shot = pilot_shot().model_copy(update={'source_event_ids': ['E404']})
        first = validate_contracts(events, [shot])
        second = validate_contracts(events, [shot])
        self.assertEqual([i.code for i in first], [i.code for i in second])
        self.assertEqual(first, sorted(first, key=lambda i: (i.severity != 'error', i.code, i.path)))

    def test_validation_is_pure(self):
        events = pilot_events()
        shot = pilot_shot()
        validate_contracts(events, [shot])
        self.assertEqual(len(events), 3)
        self.assertEqual(shot.status, 'draft')
        self.assertEqual(shot.author_lock_version, 4)


if __name__ == '__main__':
    unittest.main()
