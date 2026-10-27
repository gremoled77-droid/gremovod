"""Ревизии контрактов: оригинал, принятое, предложенное и отпечатки состояния.

Отпечаток (fingerprint) — sha256 от каноничного JSON. Он отвечает на вопрос
«то ли это состояние, которое видел человек, когда подписывал предложение».
Устаревший отпечаток означает, что основание изменилось, и применение должно
быть отклонено, а не «применено по-новому».
"""
import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def payload_of(payload: Any) -> Any:
    """Приводит любой контракт к каноническому виду.

    Модель Pydantic разворачивается в словарь, всё остальное — как есть.
    Без этого отпечаток модели и отпечаток её словаря не совпали бы, и
    проверка «устарела ли ревизия» всегда отвечала бы «да».
    """
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode='json')
    if isinstance(payload, (list, tuple)):
        return [payload_of(item) for item in payload]
    if isinstance(payload, dict):
        return {key: payload_of(value) for key, value in payload.items()}
    return payload


def canonical(payload: Any) -> str:
    """Каноничный JSON: ключи отсортированы, порядок не влияет на отпечаток."""
    return json.dumps(
        payload_of(payload), sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str
    )


def fingerprint(payload: Any) -> str:
    """sha256 от каноничного представления."""
    return hashlib.sha256(canonical(payload).encode('utf-8')).hexdigest()


def fingerprint_events(events) -> str:
    """Отпечаток реестра событий в порядке хронологии."""
    payload = [
        {
            'event_id': event.event_id,
            'text': event.text,
            'kind': event.kind,
            'locked': event.locked,
            'causal_after': list(event.causal_after),
            'timeline_order': event.timeline_order,
            'presentation_order': event.presentation_order,
        }
        for event in sorted(events, key=lambda e: (e.timeline_order, e.event_id))
    ]
    return fingerprint(payload)


def fingerprint_shot(shot) -> str:
    """Отпечаток карточки кадра."""
    return fingerprint(shot)


class Revision(BaseModel):
    """Состояние ревизии: что было, что принято, что предложено."""

    model_config = ConfigDict(extra='forbid', arbitrary_types_allowed=True)

    original: Any = None
    accepted: Any = None
    proposed: Any = None
    original_fingerprint: str = Field(default='', max_length=64)
    accepted_fingerprint: str = Field(default='', max_length=64)
    proposed_fingerprint: str = Field(default='', max_length=64)

    @property
    def has_proposal(self) -> bool:
        return self.proposed is not None and self.proposed_fingerprint != ''


def current_revision(payload: Any) -> Revision:
    """Ревизия без предложения: оригинал и принятое совпадают."""
    digest = fingerprint(payload)
    return Revision(
        original=payload,
        accepted=payload,
        proposed=None,
        original_fingerprint=digest,
        accepted_fingerprint=digest,
        proposed_fingerprint='',
    )


def propose(original: Any, proposal: Any) -> Revision:
    """Ревизия с предложением: оригинал, принятое и то, что предлагают изменить."""
    base = current_revision(original)
    return Revision(
        original=original,
        accepted=base.accepted,
        proposed=proposal,
        original_fingerprint=base.original_fingerprint,
        accepted_fingerprint=base.accepted_fingerprint,
        proposed_fingerprint=fingerprint(proposal),
    )


def is_stale(expected_fingerprint: str, payload: Any) -> bool:
    """Состояние изменилось с момента, как человек его видел."""
    if not expected_fingerprint:
        return False
    return fingerprint(payload) != expected_fingerprint


def changed_paths(before: Any, after: Any) -> list[str]:
    """Список изменённых путей между двумя состояниями — для диффа в интерфейсе."""
    before_map = payload_of(before) or {}
    after_map = payload_of(after) or {}
    found: list[str] = []

    def walk(left, right, prefix: str) -> None:
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                path = f'{prefix}.{key}' if prefix else key
                if key not in left or key not in right:
                    found.append(path)
                else:
                    walk(left[key], right[key], path)
            return
        if isinstance(left, list) and isinstance(right, list):
            for index in range(max(len(left), len(right))):
                path = f'{prefix}[{index}]'
                if index >= len(left) or index >= len(right):
                    found.append(path)
                else:
                    walk(left[index], right[index], path)
            return
        if left != right:
            found.append(prefix)

    walk(before_map, after_map, '')
    return found
