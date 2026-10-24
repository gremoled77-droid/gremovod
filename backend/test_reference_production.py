"""Contract tests for offline reference-driven production preflight."""
import copy
import json
import sqlite3

import pytest

from backend import reference_production as production


def valid_contracts():
    stage = {
        'schema_version': '1.0.0',
        'world_axes': {'forward': '+Y', 'right': '+X', 'up': '+Z'},
        'world_bounds': [[-10, 10], [-10, 10], [-1, 10]],
        'approval_status': 'APPROVED',
        'not_approved_3d_asset': False,
    }
    shots = {
        'schema_version': '1.0.0',
        'assets': {'character_ids': ['C1'], 'prop_ids': ['P1'], 'location_ids': ['L1']},
        'video_stream': {'fps_num': 24, 'fps_den': 1, 'frame_count': 4},
        'shots': [
            {'shot_id': 'S1', 'start_frame': 0, 'end_frame': 2, 'location_id': 'L1',
             'character_ids': ['C1'], 'prop_ids': ['P1'], 'world_position': [0, 0, 0],
             'prop_state_start': {'P1': 'table'}, 'prop_state_end': {'P1': 'table'}},
            {'shot_id': 'S2', 'start_frame': 2, 'end_frame': 4, 'location_id': 'L1',
             'character_ids': ['C1'], 'prop_ids': ['P1'], 'world_position': [1, 0, 0],
             'prop_state_start': {'P1': 'table'}, 'prop_state_end': {'P1': 'table'}},
        ],
    }
    refs = {
        'schema_version': '1.0.0', 'shot_id': 'S1',
        'reference_mapping': [
            {'asset_id': 'asset-1', 'asset_version': 'v1', 'sha256': 'a' * 64,
             'provider_slot': '@image1', 'source_role': 'character_identity',
             'source_type': 'image'},
        ],
        'prompt_template': 'Use approved identity @image1 for this shot.',
    }
    trusted = {'asset-1': {'approved': True, 'version': 'v1', 'sha256': 'a' * 64,
                           'kind': 'image', 'roles': ['character_identity']}}
    return stage, shots, refs, trusted


def codes(result):
    return {issue['code'] for issue in result['issues']}


def run_mutation(change):
    stage, shots, refs, trusted = valid_contracts()
    change(stage, shots, refs, trusted)
    return production.preflight(stage, shots, refs, trusted)


def test_valid_synthetic_contract_passes():
    result = production.preflight(*valid_contracts())
    assert result['status'] == 'OK'
    assert result['execution_allowed'] is False
    assert result['visual_acceptance'] == 'NOT_PERFORMED'


def test_reconstructed_animios_inputs_are_unverified_not_approved():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / 'docs' / 'research' / 'animios-seedance25'
    stage = json.loads((root / 'PILOT_STAGE.json').read_text(encoding='utf-8'))
    shots = json.loads((root / 'SHOT_MANIFEST_AnimioS_example.json').read_text(encoding='utf-8'))
    refs = json.loads((root / 'REFERENCE_MANIFEST_example.json').read_text(encoding='utf-8'))
    result = production.preflight(stage, shots, refs, {})
    assert result['status'] == 'BLOCKED'
    assert 'BLOCKED_UNVERIFIED_ASSET' in codes(result)
    assert 'UNAPPROVED_STAGE' in codes(result)


@pytest.mark.parametrize('change,expected', [
    (lambda s, h, r, t: r['reference_mapping'][0].update(sha256='broken'), 'BLOCKED_UNVERIFIED_ASSET'),
    (lambda s, h, r, t: r['reference_mapping'][0].update(asset_version='v2'), 'BLOCKED_ASSET_REVISION'),
    (lambda s, h, r, t: h['shots'][0].update(character_ids=['C404']), 'BLOCKED_ENTITY'),
    (lambda s, h, r, t: h['shots'][1].update(start_frame=3), 'BLOCKED_TIMING'),
    (lambda s, h, r, t: r['reference_mapping'][0].update(source_role='voice'), 'BLOCKED_ROLE'),
    (lambda s, h, r, t: r['reference_mapping'][0].update(provider_slot='@image2'), 'BLOCKED_SLOT'),
    (lambda s, h, r, t: h['shots'][1].update(world_position=[100, 0, 0]), 'BLOCKED_GEOGRAPHY'),
    (lambda s, h, r, t: h['shots'][1].update(prop_state_start={'P1': 'hand'}), 'BLOCKED_PROP_CONTINUITY'),
])
def test_preflight_detects_contract_and_continuity_errors(change, expected):
    result = run_mutation(change)
    assert result['status'] == 'BLOCKED'
    assert expected in codes(result)


def test_reference_kind_and_trusted_roles_must_match():
    result = run_mutation(lambda s, h, r, t: r['reference_mapping'][0].update(source_type='video'))
    assert 'BLOCKED_ROLE' in codes(result)
    result = run_mutation(lambda s, h, r, t: t['asset-1'].update(roles=['style']))
    assert 'BLOCKED_ASSET_REVISION' in codes(result)


def test_missing_prop_exit_event_is_warning():
    result = run_mutation(lambda s, h, r, t: h['shots'][1].update(prop_ids=[]))
    assert result['status'] == 'WARN'
    assert 'PROP_EXIT_UNVERIFIED' in codes(result)


@pytest.mark.parametrize('stage,shots,refs,trusted', [
    (None, {}, {}, {}),
    ({'schema_version': '1.0.0', 'world_axes': {}}, {}, {}, {}),
    (*valid_contracts()[:2], {'schema_version': '1.0.0', 'shot_id': 'S1',
                               'reference_mapping': [None], 'prompt_template': ''}, valid_contracts()[3]),
    (*valid_contracts()[:2], {'schema_version': '1.0.0', 'shot_id': 'S1',
                               'reference_mapping': [{'source_role': 'style'}], 'prompt_template': ''}, valid_contracts()[3]),
])
def test_malformed_inputs_return_schema_block_without_raising(stage, shots, refs, trusted):
    result = production.preflight(stage, shots, refs, trusted)
    assert result['status'] == 'BLOCKED'
    assert 'BLOCKED_SCHEMA' in codes(result)


@pytest.mark.parametrize('variant,price', [('A', 1.5), ('B', 1.5), ('C', 2.25)])
@pytest.mark.parametrize('aspect_ratio', ['16:9', '9:16'])
def test_preview_uses_adapter_pricing_but_cannot_submit(variant, price, aspect_ratio):
    result = production.build_preview(variant=variant, aspect_ratio=aspect_ratio, duration=10)
    assert result['estimated_cost_usd'] == price
    assert result['actual_cost_usd'] is None
    assert result['approval_id'] is None
    assert result['execution_allowed'] is False
    payload = result['wire_payload']['input']
    assert payload['aspect_ratio'] == aspect_ratio
    urls = payload.get('image_urls', []) + payload.get('video_urls', []) + payload.get('audio_urls', [])
    assert all('.invalid' in url for url in urls)
    assert 'billing' not in result['wire_payload']
    assert not any(key in result['wire_payload'] for key in ('submit', 'confirm_token', 'authorization'))


def test_blocked_source_manifest_has_no_generation_payload():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / 'docs' / 'research' / 'animios-seedance25'
    stage = json.loads((root / 'PILOT_STAGE.json').read_text(encoding='utf-8'))
    shots = json.loads((root / 'SHOT_MANIFEST_AnimioS_example.json').read_text(encoding='utf-8'))
    refs = json.loads((root / 'REFERENCE_MANIFEST_example.json').read_text(encoding='utf-8'))
    manifest = production.generation_manifest(stage, shots, refs, {})
    assert manifest['status'] == 'BLOCKED'
    assert manifest['wire_payload'] is None
    assert manifest['estimated_cost_usd'] is None
    assert manifest['execution_allowed'] is False


def test_valid_generation_manifest_binds_ordered_placeholders_to_slots():
    stage, shots, refs, trusted = valid_contracts()
    manifest = production.generation_manifest(stage, shots, refs, trusted)
    assert manifest['status'] == 'SYNTHETIC_PREVIEW_ONLY'
    assert manifest['execution_allowed'] is False
    assert manifest['wire_payload']['input']['image_urls'] == [
        'https://preview.invalid/' + production.digest(refs['reference_mapping'][0])]
    assert '@image1' in manifest['wire_payload']['input']['prompt']
    assert manifest['estimated_cost_usd'] == 1.5


def test_registry_snapshot_is_read_only_and_scoped_to_production():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.executescript('''
        CREATE TABLE library_assets(id TEXT PRIMARY KEY, metadata TEXT NOT NULL);
        CREATE TABLE production_files(id TEXT PRIMARY KEY, node_id TEXT NOT NULL, asset_id TEXT);
        CREATE TABLE production_nodes(id TEXT PRIMARY KEY, production_id TEXT NOT NULL);
        INSERT INTO library_assets VALUES
          ('a1', '{"reference_production":{"approved":true,"version":"v1","sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","kind":"image","roles":["style"]}}'),
          ('a2', '{}');
        INSERT INTO production_nodes VALUES ('n1','p1'),('n2','p2');
        INSERT INTO production_files VALUES ('f1','n1','a1'),('f2','n2','a2');
    ''')
    before = db.total_changes
    db.execute('PRAGMA query_only=ON')
    snapshot = production.registry_snapshot(db, 'p1')
    assert set(snapshot) == {'a1'}
    assert snapshot['a1']['approved'] is True
    assert snapshot['a1']['version'] == 'v1'
    assert db.total_changes == before
    assert production.registry_snapshot(db, 'p2')['a2']['approved'] is False


@pytest.mark.parametrize('change,expected', [
    (lambda s, h, r, t: r['reference_mapping'][0].update(sha256='b' * 64), 'BLOCKED_ASSET_REVISION'),
    (lambda s, h, r, t: r.update(prompt_template='unbound @image2'), 'BLOCKED_PROMPT_BINDING'),
    (lambda s, h, r, t: r.update(command='do not execute'), 'BLOCKED_UNSAFE_INPUT'),
    (lambda s, h, r, t: s.update(scene_id='OTHER_SCENE'), 'BLOCKED_GEOGRAPHY'),
    (lambda s, h, r, t: s.update(assets={'approved_vehicle_geometry_id': 'missing',
                                       'master_asset_sha256': 'a' * 64}), 'BLOCKED_GEOMETRY_APPROVAL'),
])
def test_tampered_evidence_and_unsafe_contracts_are_blocked(change, expected):
    result = run_mutation(change)
    assert result['status'] == 'BLOCKED'
    assert expected in codes(result)


def test_declared_event_explains_prop_handoff_but_does_not_approve_visuals():
    stage, shots, refs, trusted = valid_contracts()
    shots['shots'][1]['prop_state_start'] = {'P1': 'hand'}
    shots['shots'][1]['continuity_events'] = [{'entity_id': 'P1', 'action': 'picked up'}]
    result = production.preflight(stage, shots, refs, trusted)
    assert result['status'] == 'OK'
    assert result['visual_acceptance'] == 'NOT_PERFORMED'


def test_video_reference_requires_verified_duration():
    stage, shots, refs, trusted = valid_contracts()
    refs['reference_mapping'][0].update(provider_slot='@video1', source_type='video', source_role='previz')
    refs['prompt_template'] = 'Follow @video1'
    trusted['asset-1'].update(kind='video', roles=['previz'])
    assert 'BLOCKED_REFERENCE_DURATION' in codes(production.preflight(stage, shots, refs, trusted))
    trusted['asset-1']['duration_seconds'] = 10
    manifest = production.generation_manifest(stage, shots, refs, trusted)
    assert manifest['estimated_cost_usd'] == 2.25
    assert manifest['execution_allowed'] is False
