from __future__ import annotations

from pathlib import Path

import pytest

from scripts.blender.check_skill_install import inspect_install
from scripts.blender.validate_manifests import InvalidManifest


def test_inspector_skips_existing_skill_and_preserves_destination_bytes(tmp_path: Path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    skill = source / "blender-core"
    skill.mkdir(parents=True)
    source_skill_md = skill / "SKILL.md"
    source_skill_md.write_text("source skill text\n", encoding="utf-8")
    (skill / "guide.md").write_text("source guide\n", encoding="utf-8")

    existing = destination / "blender-core"
    existing.mkdir(parents=True)
    sentinel = existing / "SKILL.md"
    sentinel_bytes = b"user-owned sentinel\x00bytes"
    sentinel.write_bytes(sentinel_bytes)

    report = inspect_install(source, destination, ["blender-core"])

    assert report["dry_run"] is True
    assert report["writes_performed"] is False
    row = report["skills"][0]
    assert row["action"] == "SKIP_EXISTING"
    assert row["source_available"] is True
    assert len(row["files"]["SKILL.md"]) == 64
    assert len(row["files"]["guide.md"]) == 64
    assert sentinel.read_bytes() == sentinel_bytes
    assert sorted(path.name for path in existing.iterdir()) == ["SKILL.md"]


def test_inspector_reports_missing_source_without_writing(tmp_path: Path):
    source = tmp_path / "empty-source"
    destination = tmp_path / "destination"
    source.mkdir()
    report = inspect_install(source, destination, ["blender-missing"])

    row = report["skills"][0]
    assert row["action"] == "WOULD_COPY"
    assert row["source_available"] is False
    assert row["files"] == {}
    assert not destination.exists()
    assert report["writes_performed"] is False


def test_inspector_rejects_traversal_name(tmp_path: Path):
    with pytest.raises(InvalidManifest):
        inspect_install(tmp_path / "source", tmp_path / "destination", ["../outside"])
