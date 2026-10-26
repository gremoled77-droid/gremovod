"""Strict local previz contract. No URLs, file loading or provider dispatch from JSON."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path, PureWindowsPath
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / 'schemas/blender/previz-v1.schema.json'
ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$')


class InvalidManifest(ValueError):
    pass


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    if path.stat().st_size > 1024 * 1024:
        raise InvalidManifest('MANIFEST_TOO_LARGE')
    return json.loads(path.read_text(encoding='utf-8'),
                      object_pairs_hook=_unique_keys,
                      parse_constant=lambda _: (_ for _ in ()).throw(InvalidManifest('NON_FINITE')))


def _unique_keys(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidManifest('DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def identifier(value: str) -> str:
    if not ID.fullmatch(value) or re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]', value, re.I):
        raise InvalidManifest('INVALID_ID')
    return value


def relative_file(root: Path, name: str) -> Path:
    """Reject foreign drive, UNC, URL, traversal and symlinks escaping trusted root."""
    if not name or '\\' in name or ':' in name or PureWindowsPath(name).is_absolute():
        raise InvalidManifest('INVALID_PATH')
    if any(p in ('', '.', '..') for p in name.split('/')) or name.startswith('/'):
        raise InvalidManifest('INVALID_PATH')
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise InvalidManifest('PATH_ESCAPE')
    return target


def _walk(value: Any, key: str = '') -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            _walk(v, k)
    elif isinstance(value, list):
        for v in value:
            _walk(v, key)
    elif isinstance(value, float) and not math.isfinite(value):
        raise InvalidManifest('NON_FINITE')
    elif isinstance(value, str):
        if key.endswith(('_id', '_ids')) and value:
            identifier(value)
        if key.endswith('sha256') and value == '0' * 64:
            raise InvalidManifest('PLACEHOLDER_HASH')


def camera_samples(shot: dict) -> list[dict]:
    keys = shot['camera']['keys']
    result = []
    for frame in range(shot['start_frame'], shot['end_frame_exclusive']):
        right = next((i for i, k in enumerate(keys) if k['frame'] >= frame), len(keys) - 1)
        a, b = keys[max(0, right - 1)], keys[right]
        t = (frame - a['frame']) / (b['frame'] - a['frame']) if b['frame'] != a['frame'] else 0
        row = {'frame': frame}
        for field in ('position_m', 'look_at_m'):
            row[field] = [x + (y - x) * t for x, y in zip(a[field], b[field])]
        result.append(row)
    return result


def validate(document: dict, *, stage: dict | None = None,
             registry: Mapping[str, dict] | None = None, data_root: Path | None = None,
             owner: tuple[str, str] | None = None) -> dict:
    validator = Draft202012Validator(load(SCHEMA), format_checker=FormatChecker())
    error = next(validator.iter_errors(document), None)
    if error:
        raise InvalidManifest('SCHEMA: ' + error.message[:300])
    _walk(document)
    kind = document['kind']
    if owner and kind in ('stage_bible', 'shot_manifest'):
        if (document['production_id'], document['node_id']) != owner:
            raise InvalidManifest('OWNER_MISMATCH')
    assets = document.get('assets', []) if kind == 'stage_bible' else [r['source'] for r in document.get('ordered_refs', [])]
    if kind == 'stage_bible' and len({a['entity_id'] for a in assets}) != len(assets):
        raise InvalidManifest('DUPLICATE_ENTITY')
    for asset in assets:
        if registry is not None:
            item = registry.get(asset['file_id'])
            if not item or any(item.get(k) != asset[k] for k in ('entity_id', 'version', 'sha256')):
                raise InvalidManifest('REGISTRY_MISMATCH')
            if not owner or (item.get('production_id'), item.get('node_id')) != owner:
                raise InvalidManifest('ASSET_OWNER_MISMATCH')
            if data_root is None or file_hash(relative_file(data_root, item['relative_path'])) != asset['sha256']:
                raise InvalidManifest('ASSET_BYTES_MISMATCH')
    if kind == 'stage_bible':
        low, high = document['protected_bounds_m']
        if not all(a < b for a, b in zip(low, high)):
            raise InvalidManifest('INVALID_PROTECTED_BOUNDS')
        if abs(sum(x*x for x in document['north']) - 1) > 1e-6:
            raise InvalidManifest('NORTH_NOT_UNIT')
        for name in document['landmarks']:
            identifier(name)
        if document['asset_policy'] == 'APPROVED_MASTER' and not document['approval_id']:
            raise InvalidManifest('CANON_APPROVAL_MISSING')
    if kind == 'shot_manifest':
        if stage is not None:
            validate(stage)
        start, end = document['start_frame'], document['end_frame_exclusive']
        if not 0 < end - start <= 1440:
            raise InvalidManifest('FRAME_INTERVAL')
        keys = document['camera']['keys']
        frames = [k['frame'] for k in keys]
        if frames != sorted(set(frames)) or frames[0] != start or frames[-1] != end - 1:
            raise InvalidManifest('CAMERA_KEYS')
        w, h = document['resolution']
        if w % 2 or h % 2 or (w * 9 != h * 16 if document['aspect'] == '16:9' else w * 16 != h * 9):
            raise InvalidManifest('ASPECT_RESOLUTION')
        if stage is not None:
            if document['stage_id'] != stage['stage_id'] or document['stage_sha256'] != digest(stage):
                raise InvalidManifest('STAGE_MISMATCH')
            if (document['production_id'], document['node_id']) != (stage['production_id'], stage['node_id']):
                raise InvalidManifest('STAGE_OWNER_MISMATCH')
            known = {a['entity_id'] for a in stage['assets']} | set(stage['landmarks'])
            for beat in document['beats']:
                if not start <= beat['frame'] < end or beat['entity_id'] not in known or not set(beat['visible_ids']) <= known:
                    raise InvalidManifest('BEAT_REFERENCE')
            if not set(document['continuity']['required_last_visible_ids']) <= known:
                raise InvalidManifest('CONTINUITY_REFERENCE')
        for sample in camera_samples(document):
            p, q = sample['position_m'], sample['look_at_m']
            if p[2] <= document['camera']['clip_start_m'] or sum((x-y)**2 for x,y in zip(p,q)) < .01:
                raise InvalidManifest('CAMERA_GROUND_OR_TARGET')
            if stage:
                low, high = stage['protected_bounds_m']
                margin = document['camera']['clip_start_m']
                if all(a-margin <= x <= b+margin for a,x,b in zip(low,p,high)):
                    raise InvalidManifest('CAMERA_ASSET_COLLISION')
    if kind == 'generation_manifest':
        if document['approval']['approved'] and not document['approval']['evidence_id']:
            raise InvalidManifest('APPROVAL_EVIDENCE_MISSING')
        if document['cost_state'] == 'UNKNOWN' and document['actual_usd'] is not None:
            raise InvalidManifest('UNKNOWN_COST')
    if kind == 'qc_report' and document['human']['status'] == 'APPROVED':
        if not document['human']['reviewer_id'] or not document['human']['approval_id']:
            raise InvalidManifest('HUMAN_EVIDENCE_MISSING')
    return {'status': 'PASS_SCHEMA_SEMANTIC', 'sha256': digest(document),
            'asset_bytes_verified': registry is not None}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--stage', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(load(args.manifest), stage=load(args.stage) if args.stage else None)))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({'status': 'FAIL', 'error': str(exc)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
