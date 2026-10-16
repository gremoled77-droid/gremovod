"""Visual plan per scene/frame and visual rules per series/scene/location/character (Bruce Block components).

Stored apart from entity state so edits never invalidate entity revisions."""
import json
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

SPACES = ('', 'deep', 'flat', 'limited', 'ambiguous')
LINES = ('', 'horizontal', 'vertical', 'diagonal', 'mixed')
TONES = ('', 'reveal', 'conceal')
SHAPES = ('', 'circle', 'square', 'triangle')


class VisualPlan(BaseModel):
    space: Literal['', 'deep', 'flat', 'limited', 'ambiguous'] = ''
    line: Literal['', 'horizontal', 'vertical', 'diagonal', 'mixed'] = ''
    shape: Literal['', 'circle', 'square', 'triangle'] = ''
    tone: Literal['', 'reveal', 'conceal'] = ''
    beat: int | None = Field(default=None, ge=1, le=99)
    sector_start: int | None = Field(default=None, ge=1, le=9)
    sector_end: int | None = Field(default=None, ge=1, le=9)
    story: int | None = Field(default=None, ge=0, le=10)
    visual: int | None = Field(default=None, ge=0, le=10)
    note: str = Field(default='', max_length=500)
    beats: str = Field(default='', max_length=3000)


class VisualRules(BaseModel):
    space: Literal['', 'deep', 'flat', 'limited', 'ambiguous'] = ''
    line: Literal['', 'horizontal', 'vertical', 'diagonal', 'mixed'] = ''
    shape: Literal['', 'circle', 'square', 'triangle'] = ''
    tone: Literal['', 'reveal', 'conceal'] = ''
    palette: str = Field(default='', max_length=300)
    camera: str = Field(default='', max_length=300)
    rhythm: str = Field(default='', max_length=300)
    note: str = Field(default='', max_length=500)


RULE_KINDS = ('series', 'episode', 'location', 'character')
PHRASES = {
    'space': {'deep': 'deep space with converging perspective lines and a clear foreground-background size difference',
              'flat': 'flat frontal composition without vanishing lines, subjects on one plane',
              'limited': 'two or three separated frontal layers, no lines receding into depth',
              'ambiguous': 'ambiguous space, unreadable scale and camera position'},
    'line': {'horizontal': 'dominant horizontal lines', 'vertical': 'dominant vertical lines',
             'diagonal': 'strong diagonal lines', 'mixed': 'mixed horizontal, vertical and diagonal lines'},
    'shape': {'circle': 'soft rounded shapes and silhouettes', 'square': 'stable squared shapes and silhouettes',
              'triangle': 'sharp triangular shapes and silhouettes'},
    'tone': {'reveal': 'lighting clearly reveals the subject', 'conceal': 'shadow partly conceals the subject'},
}
SCOPES = {'series': 'Series', 'episode': 'Scene', 'location': 'Location', 'character': 'Character', 'frame': 'Shot'}


def _clean(model, raw):
    base = model().model_dump()
    if not isinstance(raw, dict):
        return base
    try:
        return model(**{k: v for k, v in raw.items() if k in base}).model_dump()
    except ValueError:
        return base


def clean(raw):
    """Stored JSON -> plan dict with every field present; unknown or damaged values fall back to empty."""
    return _clean(VisualPlan, raw)


def clean_rules(raw):
    return _clean(VisualRules, raw)


def rule_clauses(data):
    parts = [PHRASES[k][data[k]] for k in ('space', 'line', 'shape', 'tone') if data.get(k) in PHRASES[k]]
    for key, label in (('palette', 'color palette'), ('camera', 'camera'), ('rhythm', 'rhythm')):
        if data.get(key, '').strip():
            parts.append(f'{label}: {data[key].strip()}')
    if data.get('note', '').strip():
        parts.append(data['note'].strip())
    return parts


def stored(db, table, nid):
    row = db.execute(f'SELECT data FROM {table} WHERE node_id=?', (nid,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row['data'])
    except ValueError:
        return None


def rules_text(db, pid, nid):
    """English style block for a node: series, scene, cast location/characters, then own plan. Empty when nothing is set."""
    node = db.execute('SELECT * FROM production_nodes WHERE id=? AND production_id=?', (nid, pid)).fetchone()
    if not node:
        return ''
    scene = frame = None
    if node['kind'] == 'frame':
        frame = node
        scene = db.execute('SELECT * FROM production_nodes WHERE id=?', (node['parent_id'],)).fetchone()
    elif node['kind'] == 'episode':
        scene = node
    if scene:
        series = db.execute('SELECT * FROM production_nodes WHERE id=?', (scene['parent_id'],)).fetchone()
    else:
        series = node if node['kind'] == 'series' else None
    chain = []
    if series:
        chain.append(('series', series['id']))
    if scene:
        chain.append(('episode', scene['id']))
        cast = stored(db, 'production_entity_state', scene['id']) or {}
        if frame:
            own = stored(db, 'production_entity_state', frame['id']) or {}
            if own.get('character_node_ids') or own.get('location_node_id'):
                cast = own
        if cast.get('location_node_id'):
            chain.append(('location', cast['location_node_id']))
        chain += [('character', c) for c in cast.get('character_node_ids', [])]
    if node['kind'] in ('location', 'character'):
        chain.append((node['kind'], node['id']))
    lines = []
    for kind, ident in chain:
        data = stored(db, 'visual_rules', ident)
        clauses = rule_clauses(clean_rules(data)) if data else []
        if clauses:
            title = db.execute('SELECT title FROM production_nodes WHERE id=?', (ident,)).fetchone()
            lines.append(f'{SCOPES[kind]} "{title["title"] if title else ""}": ' + '; '.join(clauses))
    for kind, ident in ([('episode', scene['id'])] if scene else []) + ([('frame', frame['id'])] if frame else []):
        plan = stored(db, 'visual_plans', ident)
        if plan:
            plan = clean(plan)
            clauses = [PHRASES[k][plan[k]] for k in ('space', 'line', 'shape', 'tone') if plan.get(k) in PHRASES[k]]
            if plan.get('note', '').strip():
                clauses.append(plan['note'].strip())
            if clauses:
                lines.append(f'{SCOPES[kind]} plan: ' + '; '.join(clauses))
    return ('VISUAL RULES (keep consistent, never render as text):\n' + '\n'.join(lines)) if lines else ''


def register(app, studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS visual_plans(node_id TEXT PRIMARY KEY,data TEXT NOT NULL,updated_at TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS visual_rules(node_id TEXT PRIMARY KEY,data TEXT NOT NULL,updated_at TEXT NOT NULL)')

    @app.get('/api/productions/{pid}/series/{sid}/visual-plan')
    def read(pid: str, sid: str):
        with studio.connect() as db:
            if not db.execute("SELECT 1 FROM production_nodes WHERE id=? AND production_id=? AND kind='series'", (sid, pid)).fetchone():
                raise HTTPException(404, 'Серия не найдена в выбранном проекте')
            rows = db.execute('''SELECT v.node_id,v.data FROM visual_plans v JOIN production_nodes n ON n.id=v.node_id
                WHERE n.production_id=? AND (n.parent_id=? OR n.parent_id IN
                (SELECT id FROM production_nodes WHERE production_id=? AND parent_id=? AND kind='episode'))''', (pid, sid, pid, sid)).fetchall()
        plans = {}
        for r in rows:
            try:
                plans[r['node_id']] = clean(json.loads(r['data']))
            except ValueError:
                continue
        return {'plans': plans}

    @app.put('/api/productions/{pid}/nodes/{nid}/visual-plan')
    def write(pid: str, nid: str, body: VisualPlan):
        with studio.connect() as db:
            node = db.execute('SELECT kind FROM production_nodes WHERE id=? AND production_id=?', (nid, pid)).fetchone()
            if not node:
                raise HTTPException(404, 'Карточка не найдена в этом проекте')
            if node['kind'] not in ('episode', 'frame'):
                raise HTTPException(400, 'Визуальный план задаётся для сцены или кадра')
            data = body.model_dump()
            if node['kind'] == 'frame':
                data['beats'] = ''
            db.execute('INSERT INTO visual_plans(node_id,data,updated_at) VALUES(?,?,?) ON CONFLICT(node_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',
                       (nid, json.dumps(data, ensure_ascii=False), studio.now()))
        return data

    @app.get('/api/productions/{pid}/nodes/{nid}/visual-rules')
    def read_rules(pid: str, nid: str):
        with studio.connect() as db:
            node = db.execute('SELECT kind FROM production_nodes WHERE id=? AND production_id=?', (nid, pid)).fetchone()
            if not node:
                raise HTTPException(404, 'Карточка не найдена в этом проекте')
            return {'rules': clean_rules(stored(db, 'visual_rules', nid)), 'editable': node['kind'] in RULE_KINDS, 'prompt': rules_text(db, pid, nid)}

    @app.put('/api/productions/{pid}/nodes/{nid}/visual-rules')
    def write_rules(pid: str, nid: str, body: VisualRules):
        with studio.connect() as db:
            node = db.execute('SELECT kind FROM production_nodes WHERE id=? AND production_id=?', (nid, pid)).fetchone()
            if not node:
                raise HTTPException(404, 'Карточка не найдена в этом проекте')
            if node['kind'] not in RULE_KINDS:
                raise HTTPException(400, 'Визуальные правила задаются для серии, сцены, локации или героя')
            data = body.model_dump()
            db.execute('INSERT INTO visual_rules(node_id,data,updated_at) VALUES(?,?,?) ON CONFLICT(node_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',
                       (nid, json.dumps(data, ensure_ascii=False), studio.now()))
            return {'rules': data, 'editable': True, 'prompt': rules_text(db, pid, nid)}
