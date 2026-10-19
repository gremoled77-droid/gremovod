"""Адаптеры провайдеров ревью.

* `mock`   — MOCK/OFFLINE, без сети и без ключей.
* `minimax` — MiniMax-M3.1-Flash через официальный OpenAI-совместимый API.
* `argon`  — независимый внешний ревьюер (KIE route из PR #22).
"""

from .argon_adapter import ArgonReviewer  # noqa: F401
from .minimax_adapter import MiniMaxReviewer  # noqa: F401
from .mock_adapter import MockReviewer  # noqa: F401

__all__ = ["ArgonReviewer", "MiniMaxReviewer", "MockReviewer"]
