"""Static Blender preflight report. This module never launches Blender."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
from pathlib import Path
from typing import Any


MIN_FREE_BYTES = 4 * 1024**3
EXPECTED_BLENDER_VERSION = "4.5.15"
EXPECTED_BLENDER_BUILD_ID = "5afeabba6097"
SCRIPT_DIR = Path(__file__).resolve().parent
REVIEWED_SCRIPTS = ("run_preflight.py", "benchmark_render.py", "render_shot.py", "scene_build.py", "validate_manifests.py")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_report(blender_path: str | None, output_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    binary_sha256: str | None = None
    if not blender_path:
        errors.append("BLENDER_PATH_REQUIRED")
    else:
        candidate = Path(blender_path).expanduser()
        if not candidate.is_file():
            errors.append("BLENDER_EXECUTABLE_NOT_FOUND")
        else:
            try:
                binary_sha256 = sha256_file(candidate)
            except OSError:
                errors.append("BLENDER_EXECUTABLE_UNREADABLE")

    try:
        disk_path = output_path.parent.resolve()
        while not disk_path.exists() and disk_path != disk_path.parent:
            disk_path = disk_path.parent
        usage = shutil.disk_usage(disk_path)
        free_bytes = usage.free
    except OSError:
        free_bytes = None
        errors.append("OUTPUT_DISK_SPACE_UNAVAILABLE")
    if free_bytes is not None and free_bytes < MIN_FREE_BYTES:
        errors.append("LESS_THAN_4_GIB_FREE")

    script_hashes: dict[str, str | None] = {}
    for name in REVIEWED_SCRIPTS:
        source = SCRIPT_DIR / name
        try:
            script_hashes[name] = sha256_file(source)
        except OSError:
            script_hashes[name] = None
            errors.append("REVIEWED_SCRIPT_HASH_UNAVAILABLE")

    # This report deliberately cannot attest to OS isolation. The gate remains
    # closed until the environment is provisioned and attested outside this CLI.
    return {
        "schema_version": 1,
        "status": "BLOCKED_G1",
        "render_executed": False,
        "provider_holds_created": False,
        "blocker": "G1_EXTERNAL_ISOLATED_NO_SECRETS_ENVIRONMENT_REQUIRED",
        "blender": {
            "expected_version": EXPECTED_BLENDER_VERSION,
            "expected_build_id": EXPECTED_BLENDER_BUILD_ID,
            "actual_version": "NOT_EXECUTED",
            "binary_sha256": binary_sha256,
        },
        "runtime": {
            "os": platform.system(),
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
            "free_disk_gib_rounded": (
                round(free_bytes / (1024**3), 1) if free_bytes is not None else None
            ),
            "reviewed_script_sha256": script_hashes,
        },
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", help="Blender executable path (hashed only; never run)")
    parser.add_argument("--output", type=Path, required=True, help="JSON report path")
    args = parser.parse_args(argv)

    report = collect_report(args.blender, args.output)
    try:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except OSError:
        print(json.dumps({"status": "ERROR", "errors": ["REPORT_WRITE_FAILED"]}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
