"""Run the shipped AnimioS example offline. Exit 2 means expected source blockers.

No runtime database is opened. Use registry_snapshot with a caller-owned read-only
connection for real production integration; do not trust an approval file from a client.
"""
import argparse
import csv
from decimal import Decimal
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.reference_production import build_preview, generation_manifest, preflight  # noqa: E402


def run(directory):
    def read(name):
        return json.loads((directory / name).read_text(encoding='utf-8-sig'))
    shots = read('SHOT_MANIFEST_AnimioS_example.json')
    refs = read('REFERENCE_MANIFEST_example.json')
    stage = {'schema_version': '1.0.0', 'scene_id': 'ANIMIOS_RECONSTRUCTION',
             'world_axes': {'up': '+Z', 'forward': '+Y', 'right': '+X'},
             'approval_status': 'RECONSTRUCTED_UNVERIFIED', 'not_approved_3d_asset': True}
    report = preflight(stage, shots, refs, {})
    report['stage_note'] = 'Axes are a proposed convention; source world geography is unverified.'
    # Decimal avoids float truncation at boundaries printed to three decimals.
    with (directory / 'AnimioS_shotlist_GremoVOD.csv').open(encoding='utf-8-sig', newline='') as source:
        rows = list(csv.DictReader(source))
    fps = Decimal(shots['video_stream']['fps_num']) / Decimal(shots['video_stream']['fps_den'])
    if len(rows) != len(shots['shots']):
        report['issues'].append({'code': 'BLOCKED_CSV_TIMING', 'severity': 'BLOCKED', 'detail': 'Row count'})
    for row, shot in zip(rows, shots['shots']):
        # CSV has short IDs SH01 whereas manifest prefixes ANIMIOS_.
        valid = shot['shot_id'].endswith(row['shot_id'])
        for column, field in [('start_s', 'start_frame'), ('end_s', 'end_frame')]:
            valid = valid and abs(Decimal(row[column]) - Decimal(shot[field]) / fps) <= Decimal('0.001')
        if not valid:
            report['issues'].append({'code': 'BLOCKED_CSV_TIMING', 'severity': 'BLOCKED', 'detail': shot['shot_id']})
    report['status'] = 'BLOCKED' if any(i['severity'] == 'BLOCKED' for i in report['issues']) else report['status']
    report['timing_summary'] = {'shots': len(shots['shots']),
                                'hard_cuts': sum(bool(s['cut_after']) for s in shots['shots']),
                                'frames': shots['video_stream']['frame_count'],
                                'impact_candidate_frame': 672, 'impact_is_cut': False}
    previews = [build_preview(v, ratio) for ratio in ('16:9', '9:16') for v in ('A', 'B', 'C')]
    return report, {'schema_version': '1.0.0', 'previews': previews,
                    'source_generation': generation_manifest(stage, shots, refs, {}),
                    'source_preflight_status': report['status'], 'execution_allowed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-reports', action='store_true', help='Write only derived JSON in the research directory')
    args = parser.parse_args()
    directory = ROOT / 'docs' / 'research' / 'animios-seedance25'
    report, previews = run(directory)
    if args.write_reports:
        for name, data in [('CONTINUITY_REPORT.json', report), ('GENERATION_MANIFEST.json', previews)]:
            (directory / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'issues': len(report['issues']),
                      'timing': report['timing_summary'], 'paid_calls': 0}, ensure_ascii=False))
    return 2 if report['status'] == 'BLOCKED' else 0


if __name__ == '__main__':
    sys.exit(main())
