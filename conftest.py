"""Pytest bootstrap for the GremoVOD studio.

`backend/` is an implicit namespace package (there is no `backend/__init__.py`),
and every test module imports it as `from backend.xxx import ...`. That only
resolves when the repository root is importable.

`python -m pytest` happens to add the current working directory to `sys.path`,
which is why the suite used to pass only with that exact invocation, while a
bare `pytest` failed with 36 collection errors ("No module named 'backend'").

`pythonpath = ["."]` in `pyproject.toml` already covers pytest itself. This
file keeps the same guarantee for runners that do not read that setting, e.g.
IDE test runners and `unittest`-based harnesses, so every invocation style
behaves identically.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
