"""Single source of truth for the Studio SQLite path.

The P0 ledger and the reference pilot must not silently open a SECOND
writable database next to the Studio database. Two independent ledgers mean
two independent budgets, two independent histories and a reconciliation that
nobody performs. The Studio database is the one database; every other path is
either that file or an explicitly disposable copy.

The Studio path mirrors backend/main.py:
    (STUDIO_DATA_DIR or backend/) / "studio.sqlite3"
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class ShadowState(ValueError):
    """A second writable Studio database was requested."""


def studio_db_path() -> Path:
    data = os.environ.get("STUDIO_DATA_DIR")
    base = Path(data).resolve() if data else ROOT
    return (base / "studio.sqlite3").resolve()


def is_studio_db(path: Path | str) -> bool:
    try:
        return Path(path).resolve() == studio_db_path()
    except OSError:
        return False


def resolve(path: Path | str, *, allow_disposable: bool = False) -> Path:
    """Return the resolved database path or refuse a shadow state.

    `allow_disposable` exists for tests and for explicitly disposable copies
    of the Studio database. It must never be set on a production code path.
    """
    resolved = Path(path).resolve()
    if is_studio_db(resolved):
        return resolved
    if allow_disposable:
        return resolved
    raise ShadowState(
        "P0 ledger may only use the Studio SQLite "
        f"({studio_db_path()}); a second writable database is not allowed: {resolved}"
    )
