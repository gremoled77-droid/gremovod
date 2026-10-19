"""Универсальный интерфейс AI-ревьюера GremoVOD.

Один контракт `dev-run-summary/1` и один интерфейс `Reviewer` на всех провайдеров:
`mock` (MOCK/OFFLINE, без сети), `minimax` (MiniMax-M3.1-Flash через официальный
OpenAI-совместимый API) и `argon` (независимый внешний ревьюер).

Переключение провайдера не должно менять архитектуру: вызывающий код работает
только с `ReviewRequest` / `ReviewOutcome`.
"""

from .contract import (  # noqa: F401
    CONTRACT_VERSION,
    MODES,
    OWNER_DECISIONS,
    REVIEW_STATUSES,
    SEVERITIES,
    TEST_STATUSES,
    ContractError,
    assert_valid,
    build_summary,
    validate_summary,
)
from .reviewer import (  # noqa: F401
    ReviewOutcome,
    ReviewRequest,
    Reviewer,
    get_reviewer,
)

__all__ = [
    "CONTRACT_VERSION",
    "MODES",
    "OWNER_DECISIONS",
    "REVIEW_STATUSES",
    "SEVERITIES",
    "TEST_STATUSES",
    "ContractError",
    "assert_valid",
    "build_summary",
    "validate_summary",
    "ReviewOutcome",
    "ReviewRequest",
    "Reviewer",
    "get_reviewer",
]
