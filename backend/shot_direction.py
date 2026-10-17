"""Saved directing intent for storyboard frames, independent of provider settings."""
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, Field
from backend import camera_movements

SIZES = [
    ('wide', 'Общий план · Wide shot', 'wide shot'),
    ('full', 'Ростовой · Full shot', 'full shot'),
    ('medium', 'Средний · Medium shot', 'medium shot'),
    ('medium-close', 'Средне-крупный · Medium close-up', 'medium close-up'),
    ('close', 'Крупный · Close-up', 'close-up'),
    ('detail', 'Деталь · Extreme close-up', 'extreme close-up'),
]

class Direction(BaseModel):
    size: Literal['', 'wide', 'full', 'medium', 'medium-close', 'close', 'detail'] = ''
    # None inherits the scene; [] explicitly means no characters in the shot.
    subject_ids: list[str] | None = Field(default=None, max_length=100)
    movement: str = Field(default='', max_length=60)
    focal_mm: float | None = Field(default=None, ge=8, le=1000)
    aperture: float | None = Field(default=None, ge=0.7, le=64)
    focus: Literal['', 'subject', 'deep', 'rack'] = ''
    note: str = Field(default='', max_length=2000)

def catalogue():
    return {'sizes': [{'id': p[0], 'title': p[1]} for p in SIZES],
            'movements': [{'id': p['id'], 'title': p['title']+' · '+p['english']}
                          for p in camera_movements.catalogue()]}

def validate(value):
    if value.subject_ids is not None and len(value.subject_ids) != len(set(value.subject_ids)):
        raise HTTPException(400, 'Персонаж выбран дважды')
    if value.movement and not any(p[0] == value.movement for p in camera_movements.PRESETS):
        raise HTTPException(400, 'Движение камеры отсутствует в каталоге')

def instructions(value, video=False):
    selected = Direction.model_validate(value)
    validate(selected)
    lines = []
    if selected.size:
        lines.append('SHOT SIZE: '+next(p[2] for p in SIZES if p[0] == selected.size)+'.')
    if selected.focal_mm is not None:
        lines.append(f'LENS INTENT: {selected.focal_mm:g} mm focal length (full-frame equivalent).')
    if selected.aperture is not None:
        lines.append(f'APERTURE INTENT: f/{selected.aperture:g}.')
    if selected.focus:
        lines.append('FOCUS: '+{'subject': 'focus on the named subject', 'deep': 'deep focus across the scene',
                                  'rack': 'motivated focus transition between named subjects' if video else 'choose a clear starting focus for the planned focus transition'}[selected.focus]+'.')
    if selected.movement:
        motion = next(p for p in camera_movements.PRESETS if p[0] == selected.movement)
        lines.append(('CAMERA MOTION: '+motion[5]) if video else
                     'STILL KEYFRAME: compose the starting view for the planned '+motion[2]+'. Do not depict motion or multiple frames.')
    if selected.note.strip():
        lines.append('SHOT TASK: '+selected.note.strip())
    if lines:
        lines.append('These are visual directing intentions for the prompt, not guaranteed physical camera or provider API settings.')
    return '\n'.join(lines)
