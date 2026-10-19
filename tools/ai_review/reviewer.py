"""Универсальный интерфейс ревьюера.

Один контракт на всех провайдеров. Вызывающий код (n8n-узлы, CLI, GitHub Actions)
не знает, кто именно ответил: MiniMax, Argon или MOCK. Смена провайдера после
25.10.2026 — это смена значения в конфигурации, а не правка архитектуры.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from .contract import REVIEW_STATUSES


@dataclass
class ReviewRequest:
    """Материал к ревью.

    Содержит только то, что провайдеру положено видеть: задачу, замороженный
    дифф и результат тестов. Ни чата разработчика, ни учётных данных, ни
    инструментов записи.
    """

    task_id: str
    run_id: str
    scope: str
    mode: str
    base_sha: str
    head_sha: str
    diff_sha256: str
    files: list[str]
    diff: str
    tests_status: str
    tests_summary: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewOutcome:
    """Результат ревью в едином виде."""

    provider: str
    reviewer_model: str
    status: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, Any] | None = None
    raw: str | None = None
    error: str | None = None
    blocked_reason: str | None = None

    def __post_init__(self) -> None:
        if self.status not in REVIEW_STATUSES:
            raise ValueError(
                f"unknown review status {self.status!r}; expected one of {list(REVIEW_STATUSES)}"
            )


@runtime_checkable
class Reviewer(Protocol):
    """Единая точка расширения: реализуется одним адаптером провайдера."""

    name: str

    def review(self, request: ReviewRequest) -> ReviewOutcome:
        """Выполнить ревью. Не должен бросать исключения вместо ReviewOutcome."""
        ...


def get_reviewer(name: str, **config: Any) -> Reviewer:
    """Создать ревьюера по имени: `mock`, `minimax`, `argon`.

    Импорт адаптеров локальный, чтобы n8n/CLI могли тянуть только нужный.
    """
    key = (name or "").strip().lower()
    if key == "mock":
        from .adapters.mock_adapter import MockReviewer

        return MockReviewer(**config)
    if key == "minimax":
        from .adapters.minimax_adapter import MiniMaxReviewer

        return MiniMaxReviewer(**config)
    if key == "argon":
        from .adapters.argon_adapter import ArgonReviewer

        return ArgonReviewer(**config)
    raise ValueError(f"unknown reviewer {name!r}; expected one of ['mock', 'minimax', 'argon']")


def status_from_findings(findings: list[dict[str, Any]]) -> str:
    """Один PASS — только когда замечаний нет и ответ разобран полностью."""
    return "FINDINGS" if findings else "PASS"
