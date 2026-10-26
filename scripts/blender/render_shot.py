"""Offline render planner. Execution is withheld until G1 has an isolated launcher.

The process primitive is deliberately not wired to the CLI. Factory startup and
an environment allowlist cannot enforce filesystem/network isolation on Windows.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
from typing import Callable

try:
    from .validate_manifests import InvalidManifest, file_hash, identifier, load, validate
except ImportError:
    from validate_manifests import InvalidManifest, file_hash, identifier, load, validate

SCRIPT = Path(__file__).with_name('scene_build.py')


def clean_environment(attempt: Path, windows: Path) -> dict[str, str]:
    """No inherited credentials, Python paths, add-on profiles or provider keys."""
    return {'SystemRoot': str(windows), 'WINDIR': str(windows),
            'PATH': str(windows / 'System32'), 'TEMP': str(attempt / 'tmp'),
            'TMP': str(attempt / 'tmp'), 'USERPROFILE': str(attempt / 'profile'),
            'APPDATA': str(attempt / 'profile/AppData/Roaming'),
            'LOCALAPPDATA': str(attempt / 'profile/AppData/Local'),
            'BLENDER_USER_CONFIG': str(attempt / 'profile/config'),
            'BLENDER_USER_SCRIPTS': str(attempt / 'profile/scripts'),
            'BLENDER_USER_DATAFILES': str(attempt / 'profile/datafiles'),
            'PYTHONNOUSERSITE': '1', 'PYTHONUTF8': '1'}


def command(executable: Path, attempt: Path, phase: str) -> list[str]:
    if phase not in ('diagnostic', 'keyframes', 'full'):
        raise InvalidManifest('INVALID_PHASE')
    return [str(executable.resolve()), '--background', '--factory-startup',
            '--disable-autoexec', '--offline-mode', '--python-exit-code', '1',
            '--python', str(SCRIPT.resolve()), '--', '--manifest',
            str(attempt / 'shot_manifest.json'), '--output', str(attempt), '--phase', phase]


def bounded_process(argv: list[str], *, attempt: Path, env: dict[str, str],
                    invoke: Callable = subprocess.run) -> dict:
    """Low-level primitive for a future isolated launcher; no public execution path.

    stdout/stderr discarded: no secret-bearing process output enters API responses.
    The isolated launcher must impose disk/memory/process-tree limits externally.
    """
    try:
        result = invoke(argv, cwd=attempt, env=env, shell=False, timeout=120,
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, check=False)
        return {'status': 'PROCESS_OK' if result.returncode == 0 else 'NONZERO',
                'returncode': result.returncode}
    except subprocess.TimeoutExpired:
        return {'status': 'TIMEOUT', 'returncode': None}
    except FileNotFoundError:
        return {'status': 'BLOCKED_EXECUTABLE', 'returncode': None}
    except OSError:
        return {'status': 'PROCESS_ERROR', 'returncode': None}


def plan(stage: dict, shot: dict, *, data_root: Path, attempt_id: str,
         executable: Path) -> dict:
    validate(stage)
    validate(shot, stage=stage)
    identifier(attempt_id)
    # Reuse Studio's resolver; this does not read its database or production data.
    from types import SimpleNamespace
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
    from production_folders import checked_path
    relative = (f"{stage['production_id']}/nodes/{stage['node_id']}/previz/"
                f"{shot['shot_id']}/attempts/{attempt_id}")
    attempt = checked_path(SimpleNamespace(PRODUCTIONS_ROOT=data_root / 'productions'), relative)
    return {'status': 'BLOCKED_G1' if executable.is_file() else 'BLOCKED_EXECUTABLE',
            'render_executed': False, 'attempt_directory': str(attempt),
            'reviewed_source_sha256': file_hash(SCRIPT),
            'asset_bytes_verified': False, 'human_status': 'PENDING',
            'required': ['isolated no-secrets launcher with enforced network/filesystem limits',
                         'reviewed pinned executable and source', 'trusted owner asset lookup',
                         'resource limits and diagnostic/reopen evidence before full render']}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--blender', type=Path, required=True)
    parser.add_argument('--attempt-id', required=True)
    args = parser.parse_args()
    try:
        result = plan(load(args.stage), load(args.manifest), data_root=args.data_root,
                      executable=args.blender, attempt_id=args.attempt_id)
    except (ValueError, OSError):
        result = {'status': 'INVALID_INPUT', 'render_executed': False}
    print(json.dumps(result, ensure_ascii=False))
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
