"""Детерминированные замечания по контрактам: код, серьёзность, путь.

Один и тот же вход всегда даёт один и тот же список замечаний в одном порядке:
сначала ошибки, затем предупреждения, внутри — по коду и по пути.
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal['error', 'warning', 'info']

_SEVERITY_RANK: dict[str, int] = {'error': 0, 'warning': 1, 'info': 2}


class Issue(BaseModel):
    """Одно замечание по контракту."""

    model_config = ConfigDict(extra='forbid')

    code: str = Field(min_length=1, max_length=64)
    severity: Severity = 'error'
    path: str = Field(default='', max_length=300)
    message: str = Field(min_length=1, max_length=500)


def sort_issues(issues: list[Issue]) -> list[Issue]:
    """Канонический порядок замечаний."""
    return sorted(issues, key=lambda i: (_SEVERITY_RANK.get(i.severity, 9), i.code, i.path, i.message))


def errors(issues: list[Issue]) -> list[Issue]:
    return [issue for issue in issues if issue.severity == 'error']


def has_errors(issues: list[Issue]) -> bool:
    return any(issue.severity == 'error' for issue in issues)


def validate_contracts(events, shots, assets: set[str] | None = None) -> list[Issue]:
    """Собирает замечания по событиям, кадрам и непрерывности.

    `assets` — множество известных ID ассетов. Если множество не передано,
    проверка ссылок на ассеты не выполняется: неизвестная библиотека не значит
    «чужой ассет».
    """
    # Импорт внутри функции: event_ledger и continuity используют Issue отсюда.
    from . import continuity as continuity_module
    from . import event_ledger as ledger_module

    found: list[Issue] = []
    found.extend(ledger_module.check_events(events))
    found.extend(ledger_module.check_coverage(events, shots))
    found.extend(ledger_module.check_shots(events, shots))
    for shot in shots:
        found.extend(continuity_module.check_continuity(shot))
    if assets is not None:
        found.extend(ledger_module.check_asset_references(shots, assets))
    return sort_issues(found)
