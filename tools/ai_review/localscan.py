"""Локальный скан диффа — общий для всех ревьюеров.

Правила отбора файлов, ограничения размера и проверка на секреты НЕ дублируются
здесь: реализация общая с Argon-ревьюером (PR #22, `tools/ai_review/argon_review.py`),
чтобы охранники не разъехались между провайдерами. Ни одного сетевого вызова.

Публичный интерфейс нейтрален, чтобы добавление нового провайдера не требовало
менять этот модуль.

Порядок проверок важен: `allowed_paths` сужает материал **до** проверки лимитов.
Иначе невозможно отревьюить узкое место большого диффа — общий лимит файлов
срабатывал бы на всём изменении, а не на выбранном фрагменте.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from . import argon_review

MAX_DIFF_BYTES = argon_review.MAX_DIFF_BYTES
MAX_CHANGED_FILES = argon_review.MAX_CHANGED_FILES
BLOCKED_SUFFIXES = argon_review.BLOCKED_SUFFIXES
BLOCKED_FILES = argon_review.BLOCKED_FILES
SENSITIVE_DIRS = {".git", "secrets", "private"}


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


def check_file_allowed(path: str) -> None:
    """Проверить файл по тем же правилам, что и Argon-ревьюер.

    Тест `test_review_payload.py::ParityTest` следит за совпадением правил.
    """
    candidate = Path(path)
    if candidate.name.lower() in BLOCKED_FILES or candidate.suffix.lower() in BLOCKED_SUFFIXES:
        raise LocalScanError(f"Sensitive/binary file in diff: {path}")
    if any(part.lower() in SENSITIVE_DIRS for part in candidate.parts):
        raise LocalScanError(f"Sensitive directory in diff: {path}")


def changed_files(repo: Path, base: str, head: str) -> list[str]:
    """Список изменённых файлов без ограничения по количеству."""
    raw = _git(
        repo,
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--name-only",
        "-z",
        base,
        head,
        "--",
    )
    return [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]


def collect_diff(
    repo: Path,
    base: str,
    head: str,
    allowed_paths: list[str] | None = None,
) -> dict:
    """Собрать безопасный «замороженный» дифф.

    Возвращает словарь: base_sha, head_sha, files, diff, diff_sha256, diff_bytes.

    `allowed_paths` ограничивает материал конкретным списком путей; ограничение
    привязано к тем же SHA, что и согласие владельца.
    """
    repo = Path(repo).resolve()
    base_sha = resolve_sha(repo, base)
    head_sha = resolve_sha(repo, head)

    if allowed_paths is None:
        try:
            files, diff, digest = argon_review.snapshot(repo, base, head)
        except argon_review.ReviewError as ex:
            raise LocalScanError(str(ex)) from None
        return {
            "base_sha": base_sha,
            "head_sha": head_sha,
            "files": list(files),
            "diff": diff,
            "diff_sha256": digest,
            "diff_bytes": len(diff.encode("utf-8")),
            "truncated": False,
        }

    wanted = {str(path).replace("\\", "/") for path in allowed_paths}
    if not wanted:
        raise LocalScanError("allowed_paths is empty: nothing to review")

    everything = changed_files(repo, base, head)
    selected = [path for path in everything if path.replace("\\", "/") in wanted]
    if not selected:
        raise LocalScanError("allowed_paths does not intersect the changed files")
    if len(selected) > MAX_CHANGED_FILES:
        raise LocalScanError(f"Too many changed files ({len(selected)} > {MAX_CHANGED_FILES})")

    for path in selected:
        check_file_allowed(path)

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

    diff = data.decode("utf-8", errors="replace")
    if "Binary files " in diff or "GIT binary patch" in diff:
        raise LocalScanError("Binary changes are excluded from AI review")
    if argon_review.SECRET.search(diff):
        raise LocalScanError("Potential secret in diff; review locally before any API request")

    return {
        "base_sha": base_sha,
        "head_sha": head_sha,
        "files": selected,
        "diff": diff,
        "diff_sha256": hashlib.sha256(data).hexdigest(),
        "diff_bytes": len(diff.encode("utf-8")),
        "truncated": False,
    }


def redact_secrets(text: str) -> str:
    """Замаскировать возможные секреты в свободном тексте (например, в отчёте)."""
    return argon_review.SECRET.sub("[REDACTED]", text)
