"""Рецепты рилсов: меню готовых сценариев с шаблонами промптов и свои рецепты.

Встроенные рецепты лежат в reel_recipes_data.py и только читаются. Свои рецепты владельца хранятся в SQLite
(reel_recipes_custom) и не удаляются насовсем: «удаление» ставит отметку archived_at. Ничего не запускается и
не оплачивается: рецепт отдаёт только текст промпта и оценку цены, запуск идёт через общий экран оценки.
"""
import json
import uuid
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

from backend.model_catalog import MODEL_SPECS
from backend.reel_recipes_data import LOOKS, RECIPES

VERSION = '2026-10-16'
VIDEO_MODEL = 'seedance-2.5'


class RefSlot(BaseModel):
    role: str = Field(min_length=1, max_length=80)
    note: str = Field(default='', max_length=300)
    required: bool = False


class RecipeIn(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    family: str = Field(default='Свои', max_length=40)
    hook: str = Field(default='', max_length=500)
    duration: int = Field(ge=4, le=30)
    aspect_ratio: Literal['16:9', '9:16', '4:3', '3:4', '21:9', '1:1'] = '9:16'
    resolution: Literal['480p', '720p', '1080p'] = '720p'
    audio: bool = False
    prompt: str = Field(min_length=1, max_length=8000)
    notes: str = Field(default='', max_length=2000)
    ref_slots: list[RefSlot] = Field(default_factory=list, max_length=30)
    based_on: str | None = Field(default=None, max_length=80)


def estimate(steps, rates=None):
    """Цена одной попытки всех видеошагов по ставкам каталога за секунду, по разрешениям."""
    rates = rates or MODEL_SPECS.get(VIDEO_MODEL, {}).get('price_per_second_usd', {})
    seconds = sum(int(s.get('duration') or 0) for s in steps if s.get('kind') == 'video')
    return {res: round(seconds * rate, 2) for res, rate in rates.items()}


def builtin():
    items = []
    for recipe in RECIPES:
        items.append({**recipe, 'builtin': True, 'verified_at': None, 'estimate_usd': estimate(recipe['steps'])})
    return items


def custom_item(row):
    data = json.loads(row['data'])
    return {**data, 'id': row['id'], 'builtin': False, 'verified_at': None,
            'estimate_usd': estimate(data['steps'])}


def from_input(body: RecipeIn):
    spec = MODEL_SPECS.get(VIDEO_MODEL, {})
    if body.aspect_ratio not in spec.get('aspect_ratio', []):
        raise HTTPException(400, 'Формат кадра не поддерживается моделью')
    if body.resolution not in spec.get('resolution', []):
        raise HTTPException(400, 'Разрешение не поддерживается моделью')
    if not spec.get('duration_min', 4) <= body.duration <= spec.get('duration_max', 30):
        raise HTTPException(400, 'Длительность вне допустимого диапазона модели')
    notes = [line.strip() for line in body.notes.splitlines() if line.strip()]
    return {
        'title': body.title.strip(),
        'emoji': '✎',
        'family': body.family.strip() or 'Свои',
        'kind': 'custom',
        'difficulty': '',
        'hook': body.hook.strip(),
        'duration': body.duration,
        'aspect_ratio': body.aspect_ratio,
        'resolution': body.resolution,
        'audio': body.audio,
        'looks': [],
        'ref_slots': [{'n': i + 1, **slot.model_dump()} for i, slot in enumerate(body.ref_slots)],
        'fields': [],
        'beats': [],
        'why': [],
        'pitfalls': notes,
        'source': 'Свой рецепт' + (f' (на основе {body.based_on})' if body.based_on else ''),
        'steps': [{'title': 'Видео', 'kind': 'video', 'model': VIDEO_MODEL, 'duration': body.duration,
                   'prompt': body.prompt.strip()}],
    }


def register(app, studio):
    def ensure(db):
        db.execute('CREATE TABLE IF NOT EXISTS reel_recipes_custom('
                   'id TEXT PRIMARY KEY, data TEXT NOT NULL, created_at TEXT NOT NULL, archived_at TEXT)')

    @app.get('/api/reel-recipes')
    def listing():
        with studio.connect() as db:
            ensure(db)
            rows = db.execute('SELECT * FROM reel_recipes_custom WHERE archived_at IS NULL ORDER BY created_at DESC').fetchall()
        return {'version': VERSION, 'looks': LOOKS, 'recipes': builtin() + [custom_item(r) for r in rows]}

    @app.post('/api/reel-recipes')
    def create(body: RecipeIn):
        data = from_input(body)
        rid = 'custom-' + uuid.uuid4().hex[:12]
        with studio.connect() as db:
            ensure(db)
            db.execute('INSERT INTO reel_recipes_custom VALUES(?,?,?,NULL)',
                       (rid, json.dumps(data, ensure_ascii=False), studio.now()))
            row = db.execute('SELECT * FROM reel_recipes_custom WHERE id=?', (rid,)).fetchone()
        return custom_item(row)

    @app.delete('/api/reel-recipes/{recipe_id}')
    def archive(recipe_id: str):
        studio.checked_id(recipe_id)
        if not recipe_id.startswith('custom-'):
            raise HTTPException(400, 'Встроенный рецепт нельзя убрать, только свой')
        with studio.connect() as db:
            ensure(db)
            row = db.execute('SELECT 1 FROM reel_recipes_custom WHERE id=? AND archived_at IS NULL', (recipe_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Рецепт не найден')
            db.execute('UPDATE reel_recipes_custom SET archived_at=? WHERE id=?', (studio.now(), recipe_id))
        return {'archived': recipe_id}
