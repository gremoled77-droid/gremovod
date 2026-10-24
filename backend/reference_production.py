"""Offline production contracts. No network, uploads, database writes or generation.

Approval evidence is supplied separately by the existing asset registry, never by
the reference manifest being checked. Reconstructed observations remain observations.
"""
import hashlib
import json
import math
import re
from types import SimpleNamespace

from backend import adapters
from backend.model_catalog import MODEL_SPECS

VERSION = '1.0.0'
ROLES = {
    'image': {'character_identity', 'location_layout', 'style', 'keyframe_start', 'keyframe_end'},
    'video': {'motion', 'previz'},
    'audio': {'sound', 'voice'},
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def registry_snapshot(db, production_id):
    """Read assets already attached to this production; no parallel asset store.

    reference_production metadata is optional, explicit approval evidence. Legacy
    assets without it remain unverified. File paths and public URLs are not exported.
    """
    rows = db.execute('''SELECT DISTINCT a.id,a.metadata FROM library_assets a
        JOIN production_files f ON f.asset_id=a.id
        JOIN production_nodes n ON n.id=f.node_id WHERE n.production_id=?''',
                      (production_id,)).fetchall()
    result = {}
    for row in rows:
        try:
            evidence = json.loads(row['metadata'] or '{}').get('reference_production', {})
            if not isinstance(evidence, dict):
                evidence = {}
        except (ValueError, TypeError):
            evidence = {}
        result[row['id']] = {**evidence, 'asset_id': row['id'],
                             'approved': evidence.get('approved') is True}
    return result


def preflight(stage, shots, refs, trusted_assets):
    """Validate JSON-shaped contracts against a separately trusted registry snapshot.

    Optional continuity ledger lives in shot fields prop_state_start/end and
    continuity_events; coordinates are world_position with optional stage bounds.
    Missing spatial evidence is a warning, never visual acceptance.
    """
    issues = []

    def issue(code, severity, detail):
        issues.append({'code': code, 'severity': severity, 'detail': str(detail)})

    try:
        for label, contract in [('stage', stage), ('shots', shots), ('references', refs)]:
            if not isinstance(contract, dict) or contract.get('schema_version') != VERSION:
                issue('BLOCKED_SCHEMA', 'BLOCKED', label + ': schema_version must be ' + VERSION)
        if issues:
            raise ValueError('Unsupported contract schema')
        if not isinstance(trusted_assets, dict):
            raise ValueError('trusted_assets must be a mapping')
        # Do not interpret paths, URLs or executable instructions from contracts.
        def unsafe(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key.lower() in {'path', 'file_path', 'url', 'download_url', 'script', 'code', 'command'}:
                        issue('BLOCKED_UNSAFE_INPUT', 'BLOCKED', key)
                    unsafe(item)
            elif isinstance(value, list):
                for item in value:
                    unsafe(item)
        for value in (stage, shots, refs):
            unsafe(value)
        axes = stage.get('world_axes', {})
        if axes.get('forward') != '+Y' or axes.get('right') != '+X' or axes.get('up') not in ('+Z', 'Z-up'):
            issue('BLOCKED_GEOGRAPHY', 'BLOCKED', 'Expected +Y forward, +X right, +Z up')
        if stage.get('not_approved_3d_asset') or stage.get('approval_status') != 'APPROVED':
            issue('UNAPPROVED_STAGE', 'WARN', 'Stage geometry requires owner review')
        geometry = stage.get('assets', {}).get('approved_vehicle_geometry_id')
        if geometry is not None:
            asset = trusted_assets.get(geometry, {})
            if (asset.get('approved') is not True or not re.fullmatch('[0-9a-f]{64}', stage['assets'].get('master_asset_sha256') or '')
                    or asset.get('sha256') != stage['assets']['master_asset_sha256']):
                issue('BLOCKED_GEOMETRY_APPROVAL', 'BLOCKED', geometry)
        registry = shots['assets']
        categories = {'character_ids': set(registry['character_ids']),
                      'prop_ids': set(registry['prop_ids']),
                      'location_id': set(registry['location_ids'])}
        stream = shots['video_stream']
        if type(stream['fps_num']) is not int or type(stream['fps_den']) is not int or min(stream['fps_num'], stream['fps_den']) <= 0:
            raise ValueError('Invalid rational FPS')
        cursor, seen, previous = 0, set(), None
        for shot in shots['shots']:
            sid, start, end = shot['shot_id'], shot['start_frame'], shot['end_frame']
            if sid in seen:
                issue('BLOCKED_DUPLICATE_SHOT', 'BLOCKED', sid)
            seen.add(sid)
            if stage.get('scene_id') and shot.get('scene_id') != stage['scene_id']:
                issue('BLOCKED_GEOGRAPHY', 'BLOCKED', sid + ': stage/shot scene mismatch')
            links = stage.get('location_links')
            if previous and links is not None and previous['location_id'] != shot['location_id']:
                if [previous['location_id'], shot['location_id']] not in links:
                    issue('BLOCKED_GEOGRAPHY', 'BLOCKED', sid + ': no directed location link')
            if type(start) is not int or type(end) is not int or start != cursor or end <= start:
                issue('BLOCKED_TIMING', 'BLOCKED', sid)
            cursor = end
            for field, known in categories.items():
                values = [shot[field]] if field == 'location_id' else shot[field]
                for value in values:
                    if value not in known:
                        issue('BLOCKED_ENTITY', 'BLOCKED', sid + ':' + str(value))
            position = shot.get('world_position')
            bounds = stage.get('world_bounds')
            if position is not None:
                if len(position) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in position):
                    raise ValueError('world_position must contain three numbers')
                if bounds and any(not lo <= v <= hi for v, (lo, hi) in zip(position, bounds, strict=True)):
                    issue('BLOCKED_GEOGRAPHY', 'BLOCKED', sid + ': outside stage bounds')
            else:
                issue('UNVERIFIED_GEOGRAPHY', 'WARN', sid)
            if previous:
                events = shot.get('continuity_events', [])
                for cid in set(previous['character_ids']) - set(shot['character_ids']):
                    if not any(e.get('entity_id') == cid for e in events):
                        issue('CHARACTER_EXIT_UNVERIFIED', 'WARN', sid + ':' + cid)
                for pid, old in previous.get('prop_state_end', {}).items():
                    new = shot.get('prop_state_start', {}).get(pid)
                    if old != new and not any(e.get('entity_id') == pid for e in events):
                        issue('BLOCKED_PROP_CONTINUITY', 'BLOCKED', sid + ':' + pid)
                for pid in set(previous['prop_ids']) - set(shot['prop_ids']):
                    if not any(e.get('entity_id') == pid for e in events):
                        issue('PROP_EXIT_UNVERIFIED', 'WARN', sid + ':' + pid)
                if previous['location_id'] != shot['location_id'] and not events:
                    issue('GEOGRAPHY_TRANSITION_UNVERIFIED', 'WARN', sid)
            for field in ('prop_state_start', 'prop_state_end'):
                if not set(shot.get(field, {})) <= categories['prop_ids']:
                    issue('BLOCKED_ENTITY', 'BLOCKED', sid + ':' + field)
            previous = shot
        if not seen or type(stream['frame_count']) is not int or cursor != stream['frame_count']:
            issue('BLOCKED_TIMING', 'BLOCKED', 'Frame coverage does not match stream')
        if refs['shot_id'] not in seen:
            issue('BLOCKED_ENTITY', 'BLOCKED', refs['shot_id'])
        entries = refs['reference_mapping']
        if not entries:
            issue('BLOCKED_EMPTY_REFERENCES', 'BLOCKED', 'Reference task requires assets')
        slots, asset_keys, counts = set(), set(), dict.fromkeys(ROLES, 0)
        for entry in entries:
            slot = entry['provider_slot']
            match = re.fullmatch(r'@(image|video|audio)([1-9][0-9]*)', slot)
            if not match or slot in slots:
                issue('BLOCKED_SLOT', 'BLOCKED', slot)
                continue
            kind, index = match.group(1), int(match.group(2))
            counts[kind] += 1
            if index != counts[kind]:
                issue('BLOCKED_SLOT', 'BLOCKED', 'Wire ordering: ' + slot)
            slots.add(slot)
            if entry['source_role'] not in ROLES[kind] or entry.get('source_type', kind) != kind:
                issue('BLOCKED_ROLE', 'BLOCKED', slot)
            aid = entry['asset_id']
            key = (aid, entry['asset_version'])
            if key in asset_keys:
                issue('BLOCKED_DUPLICATE_REFERENCE', 'BLOCKED', aid)
            asset_keys.add(key)
            actual = trusted_assets.get(aid, {})
            if kind in ('video', 'audio'):
                seconds = actual.get('duration_seconds')
                if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 30:
                    issue('BLOCKED_REFERENCE_DURATION', 'BLOCKED', aid)
            checksum = entry.get('sha256')
            if (actual.get('approved') is not True or not re.fullmatch('[0-9a-f]{64}', checksum or '')
                    or entry['asset_version'] in (None, '', 'UNVERIFIED')):
                issue('BLOCKED_UNVERIFIED_ASSET', 'BLOCKED', aid)
            elif (actual.get('version') != entry['asset_version'] or actual.get('sha256') != checksum
                  or actual.get('kind') != kind or entry['source_role'] not in actual.get('roles', [])):
                issue('BLOCKED_ASSET_REVISION', 'BLOCKED', aid)
        tags = set(re.findall(r'@(image|video|audio)([1-9][0-9]*)', refs['prompt_template']))
        if {'@' + kind + index for kind, index in tags} != slots:
            issue('BLOCKED_PROMPT_BINDING', 'BLOCKED', 'Prompt tags differ from ordered slots')
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        issue('BLOCKED_SCHEMA', 'BLOCKED', str(exc))
    status = 'BLOCKED' if any(i['severity'] == 'BLOCKED' for i in issues) else 'WARN' if issues else 'OK'
    return {'schema_version': VERSION, 'contract_type': 'continuity_report', 'status': status,
            'issues': issues, 'visual_acceptance': 'NOT_PERFORMED', 'execution_allowed': False,
            'input_digest': digest([stage, shots, refs])}


def generation_manifest(stage, shots, refs, trusted_assets, *, duration=10, aspect_ratio='16:9'):
    """Bind a validated reference contract to the existing adapter, with fake URLs.

    Never exports real registry paths or uploads media. An explicit production
    execution integration must use the existing GenerationReview/confirm gates;
    this manifest cannot authorize it. Historical attempts and actual cost remain
    empty/unknown rather than fabricated from a preview.
    """
    report = preflight(stage, shots, refs, trusted_assets)
    manifest = {'schema_version': VERSION, 'contract_type': 'generation_manifest',
                'shot_id': refs.get('shot_id'), 'provider': 'piapi', 'model_id': 'seedance-2.5',
                'status': report['status'], 'execution_allowed': False,
                'source_digest': report['input_digest'], 'approval_id': None,
                'reference_mapping': refs.get('reference_mapping', []), 'attempts': [],
                'estimated_cost_usd': None, 'actual_cost_usd': None,
                'hold_status': 'NOT_RESERVED', 'wire_payload': None,
                'cost_basis': 'LOCAL_CATALOG_UNVERIFIED_LIVE'}
    if report['status'] == 'BLOCKED':
        return manifest
    media = {kind: [] for kind in ROLES}
    seconds = {'video': 0, 'audio': 0}
    for entry in refs['reference_mapping']:
        kind = re.fullmatch(r'@(image|video|audio)([1-9][0-9]*)', entry['provider_slot']).group(1)
        media[kind].append('https://preview.invalid/' + digest(entry))
        if kind in seconds:
            seconds[kind] += trusted_assets[entry['asset_id']].get('duration_seconds', 0)
    options = {'duration': duration, 'resolution': '480p', 'aspect_ratio': aspect_ratio}
    for kind in seconds:
        if media[kind]:
            options[kind + '_seconds'] = seconds[kind]
    spec = MODEL_SPECS['seedance-2.5']
    body = SimpleNamespace(prompt=refs['prompt_template'], reference_urls=media['image'],
                           video_urls=media['video'], audio_urls=media['audio'], options=options)
    payload = adapters.build(spec, body)
    manifest.update(status='SYNTHETIC_PREVIEW_ONLY', wire_payload=adapters.wire_body(spec, payload),
                    estimated_cost_usd=adapters.cost(spec, payload), launch_enabled=spec['launch_enabled'])
    manifest['payload_sha256'] = digest(manifest['wire_payload'])
    return manifest


def build_preview(variant='A', aspect_ratio='16:9', duration=10):
    """Synthetic transport proof through the real adapter; never a submit payload.

    .invalid references cannot become real media or confer approval. Source asset
    preflight remains separate and BLOCKED until trusted media evidence exists.
    """
    if variant not in ('A', 'B', 'C'):
        raise ValueError('variant must be A, B or C')
    images = [] if variant == 'A' else [f'https://preview.invalid/key{i}.png' for i in range(1, 5)]
    videos = ['https://preview.invalid/clay.mp4'] if variant == 'C' else []
    prompt = 'A camera reveals the full length of a rigid yellow VAZ-2106 limousine; fixed geometry.'
    if images:
        prompt += ' Identity and reveal keys: @image1 @image2 @image3 @image4.'
    if videos:
        prompt += ' Camera motion reference: @video1.'
    options = {'resolution': '480p', 'duration': duration, 'aspect_ratio': aspect_ratio}
    if videos:
        options['video_seconds'] = 10
    body = SimpleNamespace(prompt=prompt, options=options, reference_urls=images,
                           video_urls=videos, audio_urls=[])
    spec = MODEL_SPECS['seedance-2.5']
    payload = adapters.build(spec, body)
    wire = adapters.wire_body(spec, payload)
    return {'schema_version': VERSION, 'contract_type': 'generation_manifest',
            'variant': variant, 'provider': 'piapi', 'model_id': 'seedance-2.5',
            'status': 'SYNTHETIC_PREVIEW_ONLY', 'execution_allowed': False,
            'launch_enabled': spec['launch_enabled'], 'approval_id': None,
            'estimated_cost_usd': adapters.cost(spec, payload), 'actual_cost_usd': None,
            'cost_basis': 'LOCAL_CATALOG_UNVERIFIED_LIVE', 'hold_status': 'NOT_RESERVED',
            'attempts': [], 'wire_payload': wire, 'payload_sha256': digest(wire)}
