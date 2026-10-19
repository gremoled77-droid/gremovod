"""Editable scene acting notes; deterministic text export, no model calls."""
import hashlib
import json
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from backend import storyboard


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Beat(Strict):
    id: str = Field(min_length=1, max_length=100)
    actor_id: str = Field(min_length=1, max_length=100)
    partner_id: str | None = Field(default=None, max_length=100)
    shot_ids: list[str] = Field(default_factory=list, max_length=100)
    objective: str = Field(default='', max_length=2000)
    tactic: str = Field(default='', max_length=2000)
    obstacle: str = Field(default='', max_length=2000)
    trigger: str = Field(default='', max_length=2000)
    reaction: str = Field(default='', max_length=2000)
    next_tactic: str = Field(default='', max_length=2000)
    visible_action: str = Field(default='', max_length=2000)
    timing: str = Field(default='', max_length=2000)
    contact: str = Field(default='', max_length=2000)
    sound: str = Field(default='', max_length=2000)
    camera: str = Field(default='', max_length=2000)


class Version(Strict):
    base_revision: int = Field(ge=0, strict=True)
    source_revision: str = Field(pattern=r'^[a-f0-9]{64}$')


class Sheet(Version):
    status: Literal['draft', 'interpretation', 'approved'] = 'draft'
    beats: list[Beat] = Field(default_factory=list, max_length=50)


def context(db, pid, sid, scene_id):
    storyboard.series(db, pid, sid)
    scene = db.execute("""SELECT id,title,notes FROM production_nodes
        WHERE id=? AND production_id=? AND parent_id=? AND kind='episode'""",
        (scene_id, pid, sid)).fetchone()
    if not scene:
        raise HTTPException(404, 'Сцена не найдена в этой серии')
    row = db.execute('SELECT data FROM production_entity_state WHERE node_id=?', (scene_id,)).fetchone()
    cast = json.loads(row['data']).get('character_node_ids', []) if row else []
    actors = [dict(r) for r in db.execute("""SELECT id,title,notes FROM production_nodes
        WHERE production_id=? AND kind='character' ORDER BY id""", (pid,)) if r['id'] in cast]
    shots = [dict(r) for r in db.execute("""SELECT id,title,number FROM production_nodes
        WHERE production_id=? AND parent_id=? AND kind='frame' ORDER BY number,id""", (pid, scene_id))]
    source = {'scene': dict(scene), 'actors': actors, 'shots': shots}
    revision = hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return source, revision


def current(db, pid, sid, scene_id):
    source, source_revision = context(db, pid, sid, scene_id)
    row = db.execute('SELECT * FROM acting_notes WHERE scene_id=?', (scene_id,)).fetchone()
    data = json.loads(row['data']) if row else {'status': 'draft', 'beats': []}
    return {**data, 'revision': row['revision'] if row else 0,
            'source_revision': source_revision,
            'stale': bool(row and row['source_revision'] != source_revision), **source}


def check_version(saved, body):
    if saved['revision'] != body.base_revision or saved['source_revision'] != body.source_revision:
        raise HTTPException(409, 'Заметка или сцена изменились. Черновик не перезаписан; сравни версии.')


def validate(saved, body):
    ids = [b.id for b in body.beats]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, 'Повтор ID актёрского бита')
    actors = {a['id'] for a in saved['actors']}
    shots = {s['id'] for s in saved['shots']}
    if body.status == 'approved' and not body.beats:
        raise HTTPException(400, 'Добавь актёрскую задачу перед утверждением')
    for beat in body.beats:
        if beat.actor_id not in actors or beat.partner_id and beat.partner_id not in actors:
            raise HTTPException(400, 'Выбери актёра и партнёра из текущего состава сцены')
        if beat.partner_id == beat.actor_id:
            raise HTTPException(400, 'Актёр и партнёр должны различаться')
        if len(beat.shot_ids) != len(set(beat.shot_ids)) or not set(beat.shot_ids) <= shots:
            raise HTTPException(400, 'Кадр принадлежит другой сцене, удалён или указан дважды')
        if body.status == 'approved':
            if not all(getattr(beat, key).strip() for key in ('objective', 'tactic', 'visible_action')):
                raise HTTPException(400, 'Для утверждения нужны цель, тактика и видимое действие каждого бита')
            if beat.next_tactic.strip() and not beat.trigger.strip():
                raise HTTPException(400, 'Укажи повод смены тактики')


def instruction(saved):
    actors = {a['id']: a['title'] for a in saved['actors']}
    shots = {s['id']: s['title'] for s in saved['shots']}
    status = {'draft': 'Черновик', 'interpretation': 'Интерпретация', 'approved': 'Утверждено'}
    lines = [f"Актёрская заметка: {saved['scene']['title']}",
             f"Версия {saved['revision']} · {status[saved['status']]}",
             'Постановочный слой; исходные реплики и канон не изменены.']
    fields = [('objective', 'Цель'), ('tactic', 'Тактика'), ('obstacle', 'Препятствие'),
              ('trigger', 'Повод'), ('reaction', 'Реакция'), ('next_tactic', 'Следующая тактика'),
              ('visible_action', 'Видимое действие'), ('timing', 'Тайминг'),
              ('contact', 'Опора / контакт'), ('sound', 'Звук')]
    for index, beat in enumerate(saved['beats'], 1):
        lines += ['', f"{index}. {actors[beat['actor_id']]}"]
        if beat['partner_id']:
            lines.append('Партнёр: ' + actors[beat['partner_id']])
        if beat['shot_ids']:
            lines.append('Планы: ' + ', '.join(shots[s] for s in beat['shot_ids']))
        lines += [f"{label}: {beat[key]}" for key, label in fields if beat[key].strip()]
        if beat['camera'].strip():
            lines.append('Камера (отдельно от действия): ' + beat['camera'])
    return '\n'.join(lines) + '\n'


def register(app, studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS acting_notes(
                scene_id TEXT PRIMARY KEY REFERENCES production_nodes(id) ON DELETE CASCADE,
                revision INTEGER NOT NULL, source_revision TEXT NOT NULL, data TEXT NOT NULL)""")

    prefix = '/api/productions/{pid}/series/{sid}/scenes/{scene_id}/acting-notes'

    @app.get(prefix)
    def get(pid: str, sid: str, scene_id: str):
        with studio.connect() as db:
            return current(db, pid, sid, scene_id)

    @app.put(prefix)
    def save(pid: str, sid: str, scene_id: str, body: Sheet):
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            saved = current(db, pid, sid, scene_id)
            check_version(saved, body)
            validate(saved, body)
            data = body.model_dump(exclude={'base_revision', 'source_revision'})
            db.execute("""INSERT INTO acting_notes VALUES(?,?,?,?)
                ON CONFLICT(scene_id) DO UPDATE SET revision=excluded.revision,
                source_revision=excluded.source_revision,data=excluded.data""",
                (scene_id, saved['revision'] + 1, body.source_revision, json.dumps(data, ensure_ascii=False)))
            return current(db, pid, sid, scene_id)

    @app.post(prefix + '/export')
    def export(pid: str, sid: str, scene_id: str, body: Version):
        with studio.connect() as db:
            saved = current(db, pid, sid, scene_id)
            check_version(saved, body)
            if saved['stale'] or not saved['revision']:
                raise HTTPException(409, 'Сначала проверь и сохрани заметку для текущей версии сцены')
            return {'text': instruction(saved), 'revision': saved['revision']}
