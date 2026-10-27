"""Компиляция режиссёрского промпта под конкретный профиль модели.

Модуль чистый: собирает текст и поля запроса, ничего не отправляет и не знает
ни о какой цене. Сетевые вызовы и оценка стоимости — в других модулях.

Главное правило, ради которого модуль существует: **кадр стартового изображения
описывает исходное состояние, а не то, что случится через четыре секунды**.
Действия и камера в видео-промпте идут в хронологическом порядке.

Формат: структура подсказок — на английском (так их ожидают модели), значения
остаются на языке автора.
"""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .revisions import fingerprint, fingerprint_shot
from .schemas import CapabilityProfile, Mode, ShotContract, SourceEvent

# Роли референсов: что именно прикрепляется к запросу.
REFERENCE_ROLES = ('subject', 'start_frame', 'end_frame', 'style', 'reference')


class ReferenceBinding(BaseModel):
    """Привязка ассета к роли в запросе."""

    model_config = ConfigDict(extra='forbid')

    asset_id: str = Field(min_length=1, max_length=128)
    role: str = Field(default='reference', max_length=32)
    locked: bool = False


class CompiledPrompt(BaseModel):
    """Результат компиляции: текст, поля запроса и предупреждения."""

    model_config = ConfigDict(extra='forbid')

    shot_revision: str = Field(max_length=64)
    provider_profile_revision: str = Field(max_length=64)
    mode: Mode
    text: str = ''
    fields: dict[str, Any] = Field(default_factory=dict)
    reference_bindings: list[ReferenceBinding] = Field(default_factory=list, max_length=32)
    warnings: list[str] = Field(default_factory=list, max_length=32)
    immutable_source_digest: str = Field(default='', max_length=64)


def _events_of(shot: ShotContract, events: list[SourceEvent]) -> list[SourceEvent]:
    """События кадра в хронологическом порядке."""
    known = {event.event_id: event for event in events}
    selected = [known[event_id] for event_id in shot.source_event_ids if event_id in known]
    return sorted(selected, key=lambda event: (event.timeline_order, event.event_id))


def _state_lines(shot: ShotContract) -> list[str]:
    """Начальное состояние кадра — то, что видно в кадре до действия."""
    return [
        f'{fact.subject_id}.{fact.predicate} = {fact.value}'
        for fact in shot.physical_state.opening
        if fact.value
    ]


def _movement_lines(shot: ShotContract) -> list[str]:
    """Действия внутри кадра в порядке переходов."""
    lines: list[str] = []
    for fact in shot.physical_state.transitions:
        description = fact.action.strip()
        if not description:
            continue
        if fact.from_value and fact.to_value:
            description = f'{description} ({fact.from_value} -> {fact.to_value})'
        lines.append(description)
    return lines


def _camera_line(shot: ShotContract) -> str:
    parts = [
        part
        for part in (shot.camera.framing, shot.camera.movement, shot.camera.direction)
        if part
    ]
    return ', '.join(parts)


def _immutable_digest(shot: ShotContract) -> str:
    """Отпечаток неизменяемой части источника: референсы и заблокированные факты."""
    from .continuity import state_after

    locked_state = {
        f'{subject}.{predicate}': value
        for (subject, predicate), value in sorted(state_after(shot).items())
    }
    return fingerprint(
        {
            'asset_reference_ids': sorted(shot.asset_reference_ids),
            'locked_paths': sorted(shot.locked_paths),
            'state': locked_state,
        }
    )


def _mode_for(shot: ShotContract, profile: CapabilityProfile) -> Mode:
    """Режим выбирается по возможностям профиля, а не по желанию автора."""
    if profile.kind == 'audio':
        return 'audio'
    if profile.kind == 'video':
        if profile.supports_start_frame and profile.supports_end_frame:
            return 'start_end_video'
        if profile.supports_start_frame:
            return 'image_to_video'
        # Fail-closed: неподтверждённый флаг не даёт права собирать запрос
        # с картинкой, даже если модель в принципе умеет.
        return 'text_to_image'
    if profile.modes:
        for mode in ('reference_image_edit', 'text_to_image'):
            if mode in profile.modes:
                return mode
    return 'text_to_image'


def _bind_references(shot: ShotContract, profile: CapabilityProfile) -> list[ReferenceBinding]:
    """Раскладывает референсы по ролям с учётом возможностей профиля."""
    bindings: list[ReferenceBinding] = []
    assets = list(shot.asset_reference_ids)
    locked_paths = set(shot.locked_paths)

    subject_assets = assets[:1]
    rest = assets[1:]

    for index, asset_id in enumerate(subject_assets):
        bindings.append(
            ReferenceBinding(
                asset_id=asset_id,
                role='subject',
                locked=f'asset_reference_ids[{index}]' in locked_paths,
            )
        )

    if profile.kind == 'video':
        if profile.supports_start_frame and rest:
            bindings.append(ReferenceBinding(asset_id=rest[0], role='start_frame'))
            rest = rest[1:]
        if profile.supports_end_frame and rest:
            bindings.append(ReferenceBinding(asset_id=rest[0], role='end_frame'))
            rest = rest[1:]

    for asset_id in rest:
        bindings.append(ReferenceBinding(asset_id=asset_id, role='reference'))
    return bindings


def compile_prompt(
    shot: ShotContract,
    profile: CapabilityProfile,
    events: list[SourceEvent] | None = None,
    assets: set[str] | None = None,
) -> CompiledPrompt:
    """Собирает промпт кадра под выбранный профиль модели.

    Ни сети, ни БД, ни оценки цены: только текст, поля запроса и предупреждения.
    """
    events = events or []
    warnings: list[str] = []
    mode = _mode_for(shot, profile)

    if profile.state != 'READY':
        warnings.append(
            f'Профиль модели {profile.model_id} в состоянии {profile.state}: запуск возможен только после проверки'
        )
    if shot.duration_sec and profile.duration_max_sec and shot.duration_sec > profile.duration_max_sec:
        warnings.append(
            f'Длительность {shot.duration_sec} с превышает максимум профиля {profile.duration_max_sec} с'
        )
    if mode == 'start_end_video' and not profile.supports_end_frame:
        warnings.append('Профиль не подтверждает end frame — режим start_end_video недоступен')
    if assets is not None:
        missing = [asset_id for asset_id in shot.asset_reference_ids if asset_id not in assets]
        if missing:
            warnings.append('Референсы вне библиотеки проекта: ' + ', '.join(sorted(missing)))

    shot_events = _events_of(shot, events)
    action_lines = [event.text.strip() for event in shot_events if event.text.strip()]
    if not action_lines:
        warnings.append('К кадру не привязано ни одного события сценария')

    sections: list[tuple[str, list[str]]] = [
        ('SUBJECT', [f'character:{character_id}' for character_id in shot.character_ids]),
        ('STATE', _state_lines(shot)),
        ('ACTION', action_lines),
        ('MOVEMENT', _movement_lines(shot)),
        ('CAMERA', [_camera_line(shot)] if _camera_line(shot) else []),
        ('DURATION', [f'{shot.duration_sec:g}s']),
    ]
    text_parts = [
        f'{title}: ' + '; '.join(lines) for title, lines in sections if lines
    ]
    text = '\n'.join(text_parts)

    bindings = _bind_references(shot, profile)
    fields: dict[str, Any] = {'prompt': text}
    # В запрос попадают только поля, которые принимает конкретный endpoint.
    for name in profile.accepted_fields:
        if name == 'prompt':
            continue
        if name in ('duration', 'duration_sec'):
            fields[name] = shot.duration_sec
        elif name in ('aspect_ratio', 'resolution', 'size'):
            continue

    return CompiledPrompt(
        shot_revision=fingerprint_shot(shot),
        provider_profile_revision=fingerprint(profile.model_dump(mode='json')),
        mode=mode,
        text=text,
        fields=fields,
        reference_bindings=bindings,
        warnings=warnings,
        immutable_source_digest=_immutable_digest(shot),
    )
