"""Локальный скан диффа — общий для всех ревьюеров.

Правила отбора файлов, ограничения размера и проверка на секреты НЕ дублируются
здесь: реализация общая с Argon-ревьюером (PR #22, `tools/ai_review/argon_review.py`),
чтобы охранники не разъехались между провайдерами. Ни одного сетевого вызова.

Публичный интерфейс нейтрален, чтобы добавление нового провайдера не требовало
менять этот модуль.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from . import argon_review

MAX_DIFF_BYTES = argon_review.MAX_DIFF_BYTES
MAX_CHANGED_FILES = argon_review.MAX_CHANGED_FILES
BLOCKED_SUFFIXES = argon_review.BLOCKED_SUFFIXES
BLOCKED_FILES = argon_review.BLOCKED_FILES


class LocalScanError(Exception):
    """Локальная проверка отклонила материал. Сетевых вызовов не было."""


def _git(repo: Path, *args: str) -> bytes:
    try:
        return argon_review.run_git(repo, *args)
    except argon_review.ReviewError as ex:
        raise LocalScanError(str(ex)) from None


def resolve_sha(repo: Path, ref: str) -> str:
    """Полный SHA фиксации по имени ref/ветке/commit."""
    try:
        checked = argon_review.validate_ref(ref)
    except argon_review.ReviewError as ex:
        raise LocalScanError(str(ex)) from None
    raw = _git(repo, "rev-parse", "--verify", f"{checked}^{{commit}}")
    return raw.decode("ascii", errors="replace").strip()


def collect_diff(
    repo: Path,
    base: str,
    head: str,
    allowed_paths: list[str] | None = None,
) -> dict:
    """Собрать безопасный «замороженный» дифф.

    Возвращает словарь: base_sha, head_sha, files, diff, diff_sha256, truncated.

    `allowed_paths` ограничивает материал конкретным списком путей; ограничение
    привязано к тем же SHA, что и согласие владельца.
    """
    repo = Path(repo).resolve()
    try:
        files, diff, digest = argon_review.snapshot(repo, base, head)
    except argon_review.ReviewError as ex:
        raise LocalScanError(str(ex)) from None

    base_sha = resolve_sha(repo, base)
    head_sha = resolve_sha(repo, head)

    if allowed_paths is not None:
        wanted = {str(p).replace("\\", "/") for p in allowed_paths}
        if not wanted:
            raise LocalScanError("allowed_paths is empty: nothing to review")
        selected = [f for f in files if f.replace("\\", "/") in wanted]
        if not selected:
            raise LocalScanError("allowed_paths does not intersect the changed files")
        data = _git(
            repo,
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--no-color",
            "--unified=3",
            base,
            head,
            "--",
            *selected,
        )
        if len(data) > MAX_DIFF_BYTES:
            raise LocalScanError(f"Diff exceeds {MAX_DIFF_BYTES} bytes; select smaller commits")
        subset = data.decode("utf-8", errors="replace")
        if argon_review.SECRET.search(subset):
            raise LocalScanError("Potential secret in diff; review locally before any API request")
        files = selected
        diff = subset
        digest = hashlib.sha256(data).hexdigest()

    return {
        "base_sha": base_sha,
        "head_sha": head_sha,
        "files": list(files),
        "diff": diff,
        "diff_sha256": digest,
        "diff_bytes": len(diff.encode("utf-8")),
        "truncated": False,
    }


def redact_secrets(text: str) -> str:
    """Замаскировать возможные секреты в свободном тексте (например, в отчёте)."""
    return argon_review.SECRET.sub("[REDACTED]", text)
