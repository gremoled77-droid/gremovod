from __future__ import annotations

import json
from pathlib import Path

from scripts.blender import benchmark_render, run_preflight


def test_preflight_reports_blocked_without_running_blender(tmp_path: Path, monkeypatch):
    executable = tmp_path / "blender.exe"
    executable.write_bytes(b"fixture, not an executable")
    report_path = tmp_path / "preflight.json"

    def forbidden(*_args, **_kwargs):
        raise AssertionError("preflight must never execute Blender")

    monkeypatch.setattr(run_preflight, "Popen", forbidden, raising=False)
    result = run_preflight.collect_report(str(executable), report_path)

    assert result["status"] == "BLOCKED_G1"
    assert result["render_executed"] is False
    assert result["provider_holds_created"] is False
    assert result["blender"]["actual_version"] == "NOT_EXECUTED"
    assert result["blender"]["binary_sha256"]
    assert "BLOCKED_G1" == result["status"]  # No CLI flag can waive the gate.


def test_preflight_cli_writes_safe_json(tmp_path: Path):
    output = tmp_path / "preflight.json"
    assert run_preflight.main(["--blender", str(tmp_path / "missing.exe"), "--output", str(output)]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "BLOCKED_G1"
    assert result["errors"] == ["BLENDER_EXECUTABLE_NOT_FOUND"]
    assert "missing.exe" not in output.read_text(encoding="utf-8")


def test_benchmark_is_unmeasured_with_null_metrics(tmp_path: Path):
    report = benchmark_render.build_report()
    assert report["status"] == "NOT_MEASURED"
    assert report["blocker"].startswith("G1_")
    assert report["render_executed"] is False
    assert report["provider_holds_created"] is False
    assert report["speedup"] is None
    assert len(report["rows"]) == 4
    assert {(row["width"], row["height"]) for row in report["rows"]} == {
        (960, 540),
        (540, 960),
    }
    assert all(row["frames"] == 192 and row["duration_seconds"] == 8 for row in report["rows"])
    assert all(row["elapsed_seconds"] is None for row in report["rows"])
    assert all(row["peak_memory_bytes"] is None for row in report["rows"])
    assert all(row["geometry_sha256"] is None for row in report["rows"])

    output = tmp_path / "benchmark.json"
    assert benchmark_render.main(["--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "NOT_MEASURED"
