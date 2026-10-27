"""Точечный ремонт контракта: только незаблокированные поля, проверка целиком.

Правила ремонта:
- патч меняет ровно перечисленные поля, ничего больше;
- заблокированные автором поля не меняются никогда;
- неизменяемые свойства (геометрия, внешность) не меняются текстом;
- результат проверяется целиком: если после правки появились новые
  замечания по непрерывности, правка отклоняется и исходный контракт
  остаётся нетронутым.
"""
import copy
import re
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from .continuity import check_continuity, state_after
from .schemas import LOCKED_PREDICATES, ShotContract
from .validation import Issue

_SEGMENT = re.compile(r'([^.\[\]]+)|\[(\d+)\]')


class RepairError(Exception):
    """Правка отклонена. Исходный контракт не изменён."""


@dataclass(frozen=True)
class PatchOp:
    """Одна точечная правка: путь и новое значение."""

    path: str
    value: Any


def parse_path(path: str) -> list[tuple[str, int | None]]:
    """Разбирает 'physical_state.opening[0].value' в список сегментов."""
    if not path or not path.strip():
        raise RepairError('Путь правки не указан')
    segments: list[tuple[str, int | None]] = []
    for name, index in _SEGMENT.findall(path):
        if index:
            segments.append(('', int(index)))
        elif name:
            segments.append((name, None))
    if not segments:
        raise RepairError(f'Некорректный путь правки: {path}')
    return segments


def _get(container: Any, segments: list[tuple[str, int | None]]) -> Any:
    current = container
    for name, index in segments:
        if index is not None:
            if not isinstance(current, list) or index >= len(current):
                raise RepairError(f'Путь правки указывает на несуществующий элемент: {name}[{index}]')
            current = current[index]
        else:
            if not isinstance(current, dict) or name not in current:
                raise RepairError(f'Неизвестное поле контракта: {name}')
            current = current[name]
    return current


def _set(container: Any, segments: list[tuple[str, int | None]], value: Any) -> None:
    current = container
    for position, (name, index) in enumerate(segments):
        last = position == len(segments) - 1
        if index is not None:
            if not isinstance(current, list) or index >= len(current):
                raise RepairError(f'Путь правки указывает на несуществующий элемент: {name}[{index}]')
            if last:
                current[index] = value
            else:
                current = current[index]
        else:
            if not isinstance(current, dict) or name not in current:
                raise RepairError(f'Неизвестное поле контракта: {name}')
            if last:
                current[name] = value
            else:
                current = current[name]


def build_patch(shot: ShotContract, changes: dict[str, Any]) -> list[PatchOp]:
    """Собирает список правок из плоского словаря {'путь': значение}."""
    if not changes:
        raise RepairError('Нет изменений для применения')
    locked = set(shot.locked_paths)
    operations: list[PatchOp] = []
    for path, value in changes.items():
        if path in locked:
            raise RepairError(f'Поле {path} заблокировано автором')
        if path.startswith('asset_reference_ids'):
            raise RepairError(f'Поле {path} заблокировано автором')
        if path.startswith('source_event_ids') or path.startswith('author_lock_version'):
            raise RepairError(f'Поле {path} заблокировано автором')
        segments = parse_path(path)
        _get(shot.model_dump(mode='json'), segments)
        operations.append(PatchOp(path=path, value=value))
    return operations


def _locked_state_change(before: ShotContract, after: ShotContract) -> str | None:
    """Возвращает описание неизменяемого свойства, которое попытались изменить."""
    before_state = state_after(before)
    after_state = state_after(after)
    for key, value in sorted(before_state.items()):
        subject, predicate = key
        if predicate not in LOCKED_PREDICATES:
            continue
        if after_state.get(key, value) != value:
            return f'{subject}.{predicate}: {value!r} → {after_state.get(key)!r}'
    return None


def apply_patch(shot: ShotContract, operations: list[PatchOp]) -> ShotContract:
    """Применяет правку целиком или не применяет ничего.

    Возвращает новый контракт. Исходный объект не мутируется.
    """
    if not operations:
        raise RepairError('Нет изменений для применения')

    locked = set(shot.locked_paths)
    working = copy.deepcopy(shot.model_dump(mode='json'))
    for operation in operations:
        if operation.path in locked:
            raise RepairError(f'Поле {operation.path} заблокировано автором')
        if operation.path.startswith(('asset_reference_ids', 'source_event_ids', 'author_lock_version')):
            raise RepairError(f'Поле {operation.path} заблокировано автором')
        segments = parse_path(operation.path)
        _set(working, segments, operation.value)

    try:
        candidate = ShotContract.model_validate(working)
    except ValidationError as error:
        raise RepairError(f'Правка нарушает схему контракта: {error.errors()[0].get("msg", "ошибка")}') from error

    changed = _locked_state_change(shot, candidate)
    if changed:
        raise RepairError(f'Нельзя менять неизменяемое свойство: {changed}')

    before_issues = {issue.code + issue.path for issue in check_continuity(shot)}
    new_issues = [
        issue for issue in check_continuity(candidate) if issue.code + issue.path not in before_issues
    ]
    if new_issues:
        first = new_issues[0]
        raise RepairError(f'Правка ломает непрерывность: {first.message}')

    return candidate


def repair(shot: ShotContract, changes: dict[str, Any]) -> ShotContract:
    """Собирает и применяет правку одним вызовом."""
    return apply_patch(shot, build_patch(shot, changes))


def diff(shot: ShotContract, candidate: ShotContract) -> list[Issue]:
    """Что именно изменилось между двумя состояниями — для показа владельцу."""
    from .revisions import changed_paths

    return [
        Issue(code='field_changed', severity='info', path=path, message='Поле изменено')
        for path in changed_paths(shot, candidate)
    ]
