"""MOCK-ревьюер: полностью офлайн, детерминированный, без ключей и сети.

Нужен, чтобы вся архитектура (n8n-узлы, отчёт, GitHub summary, контракт)
проверялась до того, как появится первый реальный запрос к MiniMax.

Он ничего не «знает» о коде: только применяет набор простых эвристик к диффу.
Результат детерминирован — один и тот же дифф всегда даёт один и тот же вердикт.
"""

from __future__ import annotations

import re
from typing import Any

from ..reviewer import ReviewOutcome, ReviewRequest

#: (severity, описание, регулярное выражение по диффу)
HEURISTICS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("P1", "Включён `shell=True`: возможна инъекция команды", re.compile(r"shell\s*=\s*True")),
    ("P1", "Отключена проверка TLS-сертификата (`verify=False`)", re.compile(r"verify\s*=\s*False")),
    ("P2", "Исполняемый код из данных (`eval`/`exec`)", re.compile(r"\b(eval|exec)\s*\(")),
    ("P2", "Пустой `except:` подавляет ошибку целиком", re.compile(r"except\s*:\s*(pass|\.\.\.)")),
    ("P2", "Исключение проглочено без логирования", re.compile(r"except\s+Exception[^:]*:\s*pass")),
    ("P2", "Отладочный `print()` в production-коде", re.compile(r"^\+.*\bprint\s*\(", re.M)),
    ("P3", "Оставлен `TODO`/`FIXME` без срока", re.compile(r"^\+.*\b(TODO|FIXME)\b", re.M)),
    ("P3", "Жёстко зашитый абсолютный путь Windows", re.compile(r"^\+.*[A-Za-z]:\\\\[A-Za-z0-9_\\\\-]+", re.M)),
)


class MockReviewer:
    """Детерминированный офлайн-ревьюер."""

    name = "mock"

    def __init__(self, model_name: str = "mock-deterministic-v1"):
        self.model_name = model_name

    def review(self, request: ReviewRequest) -> ReviewOutcome:
        findings: list[dict[str, Any]] = []
        seen: set[str] = set()

        for severity, title, pattern in HEURISTICS:
            match = pattern.search(request.diff or "")
            if not match:
                continue
            line = (request.diff or "")[: match.start()].count("\n") + 1
            evidence = _line_at(request.diff or "", match.start())
            key = f"{severity}:{title}"
            if key in seen:
                continue
            seen.add(key)
            findings.append(
                {
                    "severity": severity,
                    "file": _guess_file(request.diff or "", request.files, match.start()),
                    "line": line,
                    "evidence": f"{title}: {evidence}".strip(),
                    "reproduction": "MOCK: воспроизведение не выполнялось (сеть не использовалась)",
                    "fix": f"MOCK: проверьте вручную — {title.lower()}",
                }
            )

        status = "FINDINGS" if findings else "PASS"
        return ReviewOutcome(
            provider="mock",
            reviewer_model=self.model_name,
            status=status,
            findings=findings,
            usage=None,
            raw=None,
            error=None,
            blocked_reason=None,
        )


def _line_at(text: str, offset: int) -> str:
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    if end == -1:
        end = len(text)
    return text[start:end].strip()[:300]


def _guess_file(diff: str, files: list[str], offset: int) -> str:
    """Грубое определение файла по заголовку диффа `+++ b/<path>`."""
    head = diff[:offset]
    marker = head.rfind("+++ b/")
    if marker == -1:
        return files[0] if files else ""
    rest = head[marker + len("+++ b/") :]
    newline = rest.find("\n")
    path = rest if newline == -1 else rest[:newline]
    return path.strip()
