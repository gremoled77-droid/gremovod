"""Реестр событий сценария: покрытие, стабильность ID, хронологические связи.

Правила:
- locked-событие обязано быть покрыто ровно одним кадром;
- повторять locked-событие нельзя (repeatable — отдельный режим);
- причинно-следственные связи не могут ссылаться на более позднее по времени
  событие;
- ID событий не переиспользуются: исчезновение locked-события — ошибка.
"""
from .schemas import SourceEvent
from .validation import Issue


def index_events(events: list[SourceEvent]) -> dict[str, SourceEvent]:
    """Индекс событий по ID. Дубликаты ID не теряются: побеждает первый."""
    return {event.event_id: event for event in events}


def check_events(events: list[SourceEvent]) -> list[Issue]:
    """Собственные правила реестра: дубли ID, неизвестные и перепутанные связи."""
    found: list[Issue] = []
    seen: dict[str, int] = {}
    for position, event in enumerate(events):
        if event.event_id in seen:
            found.append(
                Issue(
                    code='event_duplicate_id',
                    path=f'events[{position}].event_id',
                    message=f'ID события {event.event_id} уже использован',
                )
            )
        seen[event.event_id] = position

    known = set(seen)
    for position, event in enumerate(events):
        for order, parent in enumerate(event.causal_after):
            path = f'events[{position}].causal_after[{order}]'
            if parent not in known:
                found.append(
                    Issue(
                        code='event_unknown_causal',
                        path=path,
                        message=f'Причина {parent} не найдена среди событий',
                    )
                )
                continue
            if parent == event.event_id:
                found.append(
                    Issue(
                        code='event_self_causal',
                        path=path,
                        message='Событие не может быть причиной самого себя',
                    )
                )
                continue
            other = events[seen[parent]]
            if other.timeline_order >= event.timeline_order:
                found.append(
                    Issue(
                        code='event_causal_order',
                        path=path,
                        message=(
                            f'Причина {parent} идёт по хронологии не раньше '
                            f'события {event.event_id}'
                        ),
                    )
                )
    return found


def check_coverage(events: list[SourceEvent], shots) -> list[Issue]:
    """Каждое обязательное событие покрыто ровно одним кадром."""
    found: list[Issue] = []
    known_shots = {shot.shot_id for shot in shots}
    usage: dict[str, list[str]] = {}
    for shot in shots:
        for event_id in shot.source_event_ids:
            usage.setdefault(event_id, []).append(shot.shot_id)

    for event in events:
        if event.repeatable:
            continue
        covered = usage.get(event.event_id, [])
        if not covered:
            found.append(
                Issue(
                    code='event_missing',
                    path=f'events[{event.event_id}]',
                    message=f'Событие {event.event_id} не закреплено ни за одним кадром',
                )
            )
        elif len(covered) > 1:
            found.append(
                Issue(
                    code='event_covered_twice',
                    path=f'events[{event.event_id}]',
                    message=(
                        f'Событие {event.event_id} закреплено за несколькими кадрами: '
                        + ', '.join(sorted(covered))
                    ),
                )
            )
        for shot_id in covered:
            if shot_id not in known_shots:
                found.append(
                    Issue(
                        code='event_unknown_shot',
                        path=f'events[{event.event_id}]',
                        message=f'Кадр {shot_id} не существует',
                    )
                )
    return found


def check_shots(events: list[SourceEvent], shots) -> list[Issue]:
    """Ссылки кадров на события и стабильность ID кадров."""
    found: list[Issue] = []
    known_events = {event.event_id for event in events}
    seen: dict[str, int] = {}
    for position, shot in enumerate(shots):
        if shot.shot_id in seen:
            found.append(
                Issue(
                    code='shot_duplicate_id',
                    path=f'shots[{position}].shot_id',
                    message=f'ID кадра {shot.shot_id} уже использован',
                )
            )
        seen[shot.shot_id] = position
        for order, event_id in enumerate(shot.source_event_ids):
            if event_id not in known_events:
                found.append(
                    Issue(
                        code='shot_unknown_event',
                        path=f'shots[{position}].source_event_ids[{order}]',
                        message=f'Событие {event_id} не найдено в реестре',
                    )
                )
    return found


def check_asset_references(shots, assets: set[str]) -> list[Issue]:
    """Ссылка на ассет должна вести в библиотеку проекта."""
    found: list[Issue] = []
    for position, shot in enumerate(shots):
        for order, asset_id in enumerate(shot.asset_reference_ids):
            if asset_id not in assets:
                found.append(
                    Issue(
                        code='asset_unknown',
                        path=f'shots[{position}].asset_reference_ids[{order}]',
                        message=f'Ассет {asset_id} не найден в библиотеке',
                    )
                )
    return found


def check_ids_stable(events: list[SourceEvent], previous_ids: set[str]) -> list[Issue]:
    """Locked-события не должны исчезать при переработке сценария."""
    found: list[Issue] = []
    current = {event.event_id for event in events}
    for event_id in sorted(previous_ids - current):
        found.append(
            Issue(
                code='event_id_unstable',
                path=f'events[{event_id}]',
                message=f'Событие {event_id} пропало из реестра',
            )
        )
    return found


def film_order(events: list[SourceEvent]) -> list[str]:
    """Порядок показа: по presentation_order, при равенстве — по ID."""
    return [
        event.event_id
        for event in sorted(events, key=lambda e: (e.presentation_order, e.event_id))
    ]


def timeline_order(events: list[SourceEvent]) -> list[str]:
    """Хронологический порядок: по timeline_order, при равенстве — по ID."""
    return [
        event.event_id
        for event in sorted(events, key=lambda e: (e.timeline_order, e.event_id))
    ]
