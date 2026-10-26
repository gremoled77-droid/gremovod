"""Mock-only security contract tests for Blender's offline render planner."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from scripts.blender import render_shot
from scripts.blender.example_manifests import examples
from scripts.blender.validate_manifests import InvalidManifest


def test_command_uses_only_fixed_flags_and_phase_allowlist(tmp_path):
    exe = tmp_path / "blender.exe"
    attempt = tmp_path / "attempt"
    argv = render_shot.command(exe, attempt, "diagnostic")
    assert argv == [
        str(exe.resolve()), "--background", "--factory-startup", "--disable-autoexec",
        "--offline-mode", "--python-exit-code", "1", "--python",
        str(render_shot.SCRIPT.resolve()), "--", "--manifest",
        str(attempt / "shot_manifest.json"), "--output", str(attempt),
        "--phase", "diagnostic",
    ]
    assert "--" in argv
    with pytest.raises(InvalidManifest, match="INVALID_PHASE"):
        render_shot.command(exe, attempt, "full --python malicious.py")


def test_clean_environment_does_not_inherit_secret_or_python_path(tmp_path, monkeypatch):
    monkeypatch.setenv("VENDOR_API_KEY", "must-not-pass")
    monkeypatch.setenv("PYTHONPATH", "must-not-pass")
    env = render_shot.clean_environment(tmp_path / "attempt", tmp_path / "windows")
    assert "VENDOR_API_KEY" not in env
    assert "PYTHONPATH" not in env
    assert env["PYTHONNOUSERSITE"] == "1"
    assert set(env) == {
        "SystemRoot", "WINDIR", "PATH", "TEMP", "TMP", "USERPROFILE",
        "APPDATA", "LOCALAPPDATA", "BLENDER_USER_CONFIG", "BLENDER_USER_SCRIPTS",
        "BLENDER_USER_DATAFILES", "PYTHONNOUSERSITE", "PYTHONUTF8",
    }


@pytest.mark.parametrize(("returncode", "expected"), [(0, "PROCESS_OK"), (7, "NONZERO")])
def test_bounded_process_passes_fixed_limits_and_discards_output(tmp_path, returncode, expected):
    observed = {}

    def invoke(argv, **kwargs):
        observed.update(kwargs)
        return subprocess.CompletedProcess(argv, returncode, stdout="secret", stderr="secret")

    result = render_shot.bounded_process(["blender.exe"], attempt=tmp_path, env={"PATH": ""}, invoke=invoke)
    assert result == {"status": expected, "returncode": returncode}
    assert observed["shell"] is False
    assert observed["timeout"] == 120
    assert observed["stdin"] is subprocess.DEVNULL
    assert observed["stdout"] is subprocess.DEVNULL
    assert observed["stderr"] is subprocess.DEVNULL
    assert "secret" not in repr(result)


def test_bounded_process_timeout_does_not_expose_captured_output(tmp_path):
    def invoke(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 120, output=b"secret", stderr=b"secret")

    result = render_shot.bounded_process(["blender.exe"], attempt=tmp_path, env={}, invoke=invoke)
    assert result == {"status": "TIMEOUT", "returncode": None}
    assert "secret" not in repr(result)


@pytest.mark.parametrize(
    ("exception", "expected"),
    [(FileNotFoundError("missing"), "BLOCKED_EXECUTABLE"), (OSError("failed"), "PROCESS_ERROR")],
)
def test_bounded_process_reports_missing_or_os_error_without_details(tmp_path, exception, expected):
    def invoke(*args, **kwargs):
        raise exception

    result = render_shot.bounded_process(["blender.exe"], attempt=tmp_path, env={}, invoke=invoke)
    assert result == {"status": expected, "returncode": None}
    assert str(exception) not in repr(result)


def test_plan_existing_executable_stays_blocked_and_creates_no_attempt_directory(tmp_path):
    stage, shot = examples()
    data_root = tmp_path / "studio-data"
    executable = tmp_path / "blender.exe"
    executable.write_bytes(b"test placeholder; never executed")
    result = render_shot.plan(
        stage, shot, data_root=data_root, attempt_id="attempt-01", executable=executable
    )
    attempt = Path(result["attempt_directory"])
    assert result["status"] == "BLOCKED_G1"
    assert result["render_executed"] is False
    assert attempt == (data_root / "productions" / stage["production_id"] / "nodes" /
                       stage["node_id"] / "previz" / shot["shot_id"] / "attempts" / "attempt-01").resolve()
    assert not attempt.exists()
    assert not data_root.exists()
