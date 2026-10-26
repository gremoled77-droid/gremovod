"""One-time extraction of the existing proposed RFC contract, with P0 extensions."""
import json
import re
from pathlib import Path


def build(root: Path) -> dict:
    text = (root / 'docs/BLENDER_PIPELINE_RFC.md').read_text(encoding='utf-8')
    schema = json.loads(re.search(r'```json\s*(\{.*?\})\s*```', text, re.S)[1])
    defs = schema['$defs']
    for name in ('stage', 'shot'):
        obj = defs[name]
        for key in ('production_id', 'node_id'):
            obj['required'].append(key)
            obj['properties'][key] = {'type': 'string', 'pattern': '^[A-Za-z0-9][A-Za-z0-9_-]{0,95}$'}
    stage = defs['stage']
    additions = {
        'asset_policy': {'enum': ['NON_CANONICAL_PROXY', 'APPROVED_MASTER']},
        'approval_id': {'type': ['string', 'null']},
        'protected_bounds_m': {'type': 'array', 'minItems': 2, 'maxItems': 2, 'items': {'$ref': '#/$defs/vec3'}},
    }
    stage['required'].extend(additions)
    stage['properties'].update(additions)
    shot = defs['shot']
    shot['required'].append('resolution')
    shot['properties']['resolution'] = {'type': 'array', 'minItems': 2, 'maxItems': 2,
                                      'items': {'type': 'integer', 'minimum': 64, 'maximum': 1920}}
    camera = shot['properties']['camera']
    camera['properties']['interpolation'] = {'const': 'linear'}
    camera['required'].extend(['clip_start_m', 'clip_end_m'])
    camera['properties'].update({'clip_start_m': {'type': 'number', 'minimum': .01, 'maximum': 1},
                                 'clip_end_m': {'type': 'number', 'minimum': 2, 'maximum': 1000}})
    return schema


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[2]
    path = root / 'schemas/blender/previz-v1.schema.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build(root), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
