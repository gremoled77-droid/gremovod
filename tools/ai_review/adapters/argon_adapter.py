"""Адаптер Argon — независимый внешний ревьюер.

Переносит уже проверенную логику PR #22 (`argon_review.py`) в единый контракт
`Reviewer`. Именно поэтому переключение MiniMax → Argon после 25.10.2026 —
это смена провайдера в конфигурации, а не правка архитектуры.

Локальная часть (отбор файлов, лимиты, поиск секретов) уже общая с MiniMax
через `localscan`, поэтому охранники не могут разойтись.
"""

from __future__ import annotations

from typing import Any

from .. import argon_review
from ..reviewer import ReviewOutcome, ReviewRequest


class ArgonReviewer:
    """Ревьюер через Argon (KIE route)."""

    name = "argon"

    def __init__(self, api_key: str | None = None, *, consent: bool = False, live: bool = False):
        self.api_key = api_key
        self.consent = consent
        self.live = live

    def review(self, request: ReviewRequest) -> ReviewOutcome:
        if request.mode != "LIVE" or not self.live:
            return ReviewOutcome(
                provider=self.name,
                reviewer_model="argon",
                status="NOT_RUN",
                findings=[],
                usage=None,
                raw=None,
                error=None,
                blocked_reason="Argon LIVE review requires mode=LIVE and explicit enablement",
            )

        if not self.api_key:
            return ReviewOutcome(
                provider=self.name,
                reviewer_model="argon",
                status="NOT_RUN",
                findings=[],
                usage=None,
                raw=None,
                error=None,
                blocked_reason="Argon API key is missing; no request sent",
            )

        if not self.consent:
            return ReviewOutcome(
                provider=self.name,
                reviewer_model="argon",
                status="NOT_RUN",
                findings=[],
                usage=None,
                raw=None,
                error=None,
                blocked_reason="explicit owner consent was not given",
            )

        messages = argon_review.make_prompt(request.scope, list(request.files), request.diff or "")
        try:
            content, credits = argon_review.ask_argon(messages, self.api_key)
        except argon_review.ReviewError as ex:
            return ReviewOutcome(
                provider=self.name,
                reviewer_model="argon",
                status="API_ERROR",
                findings=[],
                usage=None,
                raw=None,
                error=str(ex),
                blocked_reason=None,
            )

        verdict = content.strip().upper()
        if verdict == "PASS":
            return ReviewOutcome(
                provider=self.name,
                reviewer_model="argon",
                status="PASS",
                findings=[],
                usage=None,
                raw=content[:8000],
                error=None,
                blocked_reason=None,
            )

        findings: list[dict[str, Any]] = [
            {
                "severity": "P2",
                "file": "(argon report)",
                "line": None,
                "evidence": content[:4000],
                "reproduction": "см. отчёт Argon",
                "fix": "см. отчёт Argon",
            }
        ]
        if "НЕУВЕРЕННО" in content.upper():
            return ReviewOutcome(
                provider=self.name,
                reviewer_model="argon",
                status="UNCERTAIN",
                findings=findings,
                usage=None,
                raw=content[:8000],
                error="Argon reported НЕУВЕРЕННО",
                blocked_reason=None,
            )

        return ReviewOutcome(
            provider=self.name,
            reviewer_model="argon",
            status="FINDINGS",
            findings=findings,
            usage=None,
            raw=content[:8000],
            error=None,
            blocked_reason=None,
        )
