"""Emit an honest, blocked benchmark template without invoking Blender."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_report() -> dict[str, Any]:
    rows = []
    for name, renderer in (
        ("baseline_workbench", "WORKBENCH"),
        ("candidate_cycles_cpu_low", "CYCLES_CPU_LOW"),
    ):
        for orientation, width, height in (
            ("landscape_16_9", 960, 540),
            ("portrait_9_16", 540, 960),
        ):
            rows.append(
                {
                    "variant": name,
                    "renderer": renderer,
                    "orientation": orientation,
                    "width": width,
                    "height": height,
                    "frames": 192,
                    "duration_seconds": 8,
                    "elapsed_seconds": None,
                    "peak_memory_bytes": None,
                    "geometry_sha256": None,
                    "status": "NOT_MEASURED",
                }
            )
    return {
        "schema_version": 1,
        "status": "NOT_MEASURED",
        "blocker": "G1_EXTERNAL_ISOLATED_NO_SECRETS_ENVIRONMENT_REQUIRED",
        "render_executed": False,
        "provider_holds_created": False,
        "speedup": None,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="JSON report path")
    args = parser.parse_args(argv)
    report = build_report()
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
