"""Звук: библиотека голосов (ElevenLabs и Fish по ID), привязка голоса к герою, звуковые заметки кадров и их файлы.

Платных вызовов здесь нет: озвучка реплики идёт через уже существующую оценку и подтверждение у карточки героя."""
import csv
import io
import json
import re
import uuid
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import httpx
from fastapi import File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend import character_voice, production_folders as folders

# Рекомендуемый уровень в дБ по типу заметки (подсказка, правится руками).
DEFAULT_LEVEL = {'voice': 0.0, 'ambience': -20.0, 'sfx': -6.0, 'music': -12.0}
KIND_LABEL = {'voice': 'Реплика', 'ambience': 'Атмосфера', 'sfx': 'SFX', 'music': 'Музыка'}
AUDIO_EXT = {'.mp3', '.wav', '.m4a'}
MAX_AUDIO = 100 * 1024 * 1024
Kind = Literal['voice', 'ambience', 'sfx', 'music']


class NewVoice(BaseModel):
    provider: Literal['elevenlabs', 'fish'] = 'elevenlabs'
    name: str = Field(min_length=1, max_length=150)
    voice_id: str = Field(min_length=1, max_length=100)
    model: str | None = None
    url: str = Field(default='', max_length=1000)
    note: str = Field(default='', max_length=500)


class Assign(BaseModel):
    character_node_id: str = Field(min_length=1, max_length=100)


class CueIn(BaseModel):
    kind: Kind
    text: str = Field(default='', max_length=3000)
    hero_node_id: str | None = Field(default=None, max_length=100)
    level_db: float | None = Field(default=None, ge=-60, le=12, allow_inf_nan=False)
    start_s: float = Field(default=0, ge=0, le=3600, allow_inf_nan=False)
    duration_s: float | None = Field(default=None, ge=0, le=3600, allow_inf_nan=False)


class LinkAsset(BaseModel):
    asset_id: str = Field(min_length=1, max_length=100)


def check_voice(provider, model, voice_id, name, url):
    """Те же правила, что у карточки голоса героя: модель из списка, безопасный ID, ссылка только на сервис провайдера."""
    if model not in character_voice.MODELS[provider]:
        raise HTTPException(400, 'Выбери поддерживаемую модель озвучки')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', voice_id):
        raise HTTPException(400, 'Некорректный Voice ID')
    if not name.strip():
        raise HTTPException(400, 'Укажи название голоса')
    if url:
        parsed = urlparse(url)
        domain = parsed.hostname or ''
        allowed = 'elevenlabs.io' if provider == 'elevenlabs' else 'fish.audio'
        if parsed.scheme != 'https' or (domain != allowed and not domain.endswith('.' + allowed)) or parsed.username or parsed.password:
            raise HTTPException(400, 'Нужна HTTPS-ссылка на страницу выбранного сервиса')


def frame_node(db, pid, nid):
    row = db.execute("SELECT * FROM production_nodes WHERE id=? AND production_id=? AND kind='frame'", (nid, pid)).fetchone()
    if not row:
        raise HTTPException(404, 'Кадр не найден в этом проекте')
    return dict(row)


def cue_row(db, pid, cid):
    row = db.execute('SELECT * FROM frame_sound_cues WHERE id=? AND production_id=? AND archived=0', (cid, pid)).fetchone()
    if not row:
        raise HTTPException(404, 'Звуковая заметка не найдена')
    return dict(row)


def check_hero(db, pid, kind, hero):
    if kind != 'voice':
        return None
    if not hero:
        raise HTTPException(400, 'Для реплики выбери героя')
    if not db.execute("SELECT 1 FROM production_nodes WHERE id=? AND production_id=? AND kind='character'", (hero, pid)).fetchone():
        raise HTTPException(400, 'Герой не принадлежит этому общему проекту')
    return hero


def public_cue(row, files):
    f = files.get(row['file_id'])
    return {'id': row['id'], 'frame_id': row['frame_id'], 'kind': row['kind'], 'text': row['text'], 'hero_node_id': row['hero_node_id'],
            'level_db': row['level_db'], 'start_s': row['start_s'], 'duration_s': row['duration_s'], 'file_id': row['file_id'],
            'filename': f['filename'] if f else None, 'url': '/api/production-files/' + row['file_id'] if f else None,
            'status': 'file' if f else 'plan'}


def series_cues(db, pid, sid):
    """Заметки всех кадров серии по порядку: сцена, кадр, смещение."""
    frames = db.execute('''SELECT f.id AS fid, f.title AS ftitle, f.number AS fnum, s.id AS sid, s.title AS stitle, s.number AS snum
        FROM production_nodes f JOIN production_nodes s ON s.id=f.parent_id
        WHERE f.production_id=? AND f.kind='frame' AND s.kind='episode' AND s.parent_id=?
        ORDER BY s.number, f.number, f.id''', (pid, sid)).fetchall()
    if not frames:
        return []
    marks = ','.join('?' * len(frames))
    rows = db.execute(f'SELECT * FROM frame_sound_cues WHERE production_id=? AND archived=0 AND frame_id IN ({marks}) ORDER BY start_s, created_at, id',
                      (pid, *[r['fid'] for r in frames])).fetchall()
    files = {r['id']: dict(r) for r in db.execute(
        f"SELECT id, filename FROM production_files WHERE production_id=? AND kind='audio' AND node_id IN ({marks})", (pid, *[r['fid'] for r in frames]))}
    by_frame = {}
    for r in rows:
        by_frame.setdefault(r['frame_id'], []).append(public_cue(dict(r), files))
    return [{'frame_id': f['fid'], 'frame': f['ftitle'], 'frame_number': f['fnum'], 'scene_id': f['sid'], 'scene': f['stitle'],
             'scene_number': f['snum'], 'cues': by_frame.get(f['fid'], [])} for f in frames]


def to_csv(frames, heroes):
    stream = io.StringIO()
    writer = csv.writer(stream, delimiter=';')
    writer.writerow(['Сцена', 'Кадр', 'Тип', 'Текст', 'Герой', 'Уровень, дБ', 'Смещение, с', 'Длительность, с', 'Файл', 'Статус'])
    for fr in frames:
        for c in fr['cues']:
            writer.writerow([f"{fr['scene_number']}. {fr['scene']}", f"{fr['scene_number']}.{fr['frame_number']} {fr['frame']}", KIND_LABEL[c['kind']], c['text'],
                             heroes.get(c['hero_node_id'], ''), c['level_db'], c['start_s'], '' if c['duration_s'] is None else c['duration_s'],
                             c['filename'] or '', 'файл есть' if c['status'] == 'file' else 'план'])
    return '﻿' + stream.getvalue()


async def fetch_preview(voice_id, key):
    """Готовый пример звучания голоса ElevenLabs (preview_url из описания голоса): озвучка не запускается."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            r = await client.get('https://api.elevenlabs.io/v1/voices/' + voice_id, headers={'xi-api-key': key})
    except httpx.RequestError:
        raise HTTPException(502, 'ElevenLabs не ответил. Попробуй позже.')
    if r.status_code == 404:
        raise HTTPException(404, 'Голос не найден в аккаунте ElevenLabs. Добавь его в «Мои голоса» на сайте сервиса.')
    if r.status_code != 200:
        raise HTTPException(502, f'ElevenLabs отклонил запрос (HTTP {r.status_code}). Проверь ключ и права.')
    url = r.json().get('preview_url') or ''
    if not url.startswith('https://'):
        raise HTTPException(404, 'У голоса нет готового примера.')
    return url


def register(app, studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS voice_library(id TEXT PRIMARY KEY, production_id TEXT NOT NULL, provider TEXT NOT NULL,
                name TEXT NOT NULL, voice_id TEXT NOT NULL, model TEXT NOT NULL, url TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
                archived INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)''')
            db.execute('CREATE TABLE IF NOT EXISTS hero_voices(node_id TEXT NOT NULL, voice_lib_id TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(node_id, voice_lib_id))')
            db.execute('''CREATE TABLE IF NOT EXISTS frame_sound_cues(id TEXT PRIMARY KEY, production_id TEXT NOT NULL, frame_id TEXT NOT NULL,
                kind TEXT NOT NULL, text TEXT NOT NULL DEFAULT '', hero_node_id TEXT, level_db REAL NOT NULL, start_s REAL NOT NULL DEFAULT 0,
                duration_s REAL, file_id TEXT, archived INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')

    base = '/api/productions/{pid}'

    # ---------- библиотека голосов ----------
    @app.get(base + '/voices')
    def list_voices(pid: str):
        folders.production(studio, pid)
        with studio.connect() as db:
            voices = [dict(r) for r in db.execute('SELECT * FROM voice_library WHERE production_id=? AND archived=0 ORDER BY provider, created_at, id', (pid,))]
            heroes = db.execute('''SELECT n.id, n.title, v.profile FROM production_nodes n JOIN character_voices v ON v.node_id=n.id
                WHERE n.production_id=? AND n.kind='character' ''', (pid,)).fetchall()
            links = db.execute('''SELECT h.voice_lib_id, n.id, n.title FROM hero_voices h JOIN production_nodes n ON n.id=h.node_id
                WHERE n.production_id=? AND n.kind='character' ORDER BY h.created_at''', (pid,)).fetchall()
        cards = [(h['id'], h['title'], json.loads(h['profile'])) for h in heroes]
        for v in voices:
            assigned = {nid: title for lid, nid, title in links if lid == v['id']}
            # Старые привязки, сделанные до списка «несколько голосов», видны по активному голосу героя.
            assigned.update({nid: title for nid, title, p in cards if p.get('provider') == v['provider'] and p.get('voice_id') == v['voice_id']})
            v['assigned'] = [{'node_id': nid, 'title': title} for nid, title in assigned.items()]
        return voices

    @app.post(base + '/voices')
    def add_voice(pid: str, body: NewVoice):
        folders.production(studio, pid)
        model = body.model or next(iter(character_voice.MODELS[body.provider]))
        check_voice(body.provider, model, body.voice_id, body.name, body.url)
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM voice_library WHERE production_id=? AND provider=? AND voice_id=? AND archived=0', (pid, body.provider, body.voice_id)).fetchone():
                raise HTTPException(409, 'Голос с таким ID уже есть в библиотеке')
            vid = uuid.uuid4().hex
            db.execute('INSERT INTO voice_library(id,production_id,provider,name,voice_id,model,url,note,archived,created_at) VALUES(?,?,?,?,?,?,?,?,0,?)',
                       (vid, pid, body.provider, body.name.strip(), body.voice_id, model, body.url, body.note.strip(), studio.now()))
        return {'id': vid}

    @app.get(base + '/voices/{vid}/preview')
    async def voice_preview(pid: str, vid: str):
        folders.production(studio, pid)
        with studio.connect() as db:
            voice = db.execute('SELECT * FROM voice_library WHERE id=? AND production_id=? AND archived=0', (vid, pid)).fetchone()
        if not voice:
            raise HTTPException(404, 'Голос не найден')
        if voice['provider'] != 'elevenlabs':
            raise HTTPException(400, 'Предпрослушивание пока только для ElevenLabs')
        return {'preview_url': await fetch_preview(voice['voice_id'], studio.provider_key('elevenlabs'))}

    @app.delete(base + '/voices/{vid}')
    def archive_voice(pid: str, vid: str):
        """Голос убирается из списка, привязки героев не трогаются; удаления данных нет."""
        with studio.connect() as db:
            row = db.execute('SELECT 1 FROM voice_library WHERE id=? AND production_id=? AND archived=0', (vid, pid)).fetchone()
            if not row:
                raise HTTPException(404, 'Голос не найден')
            db.execute('UPDATE voice_library SET archived=1 WHERE id=?', (vid,))
        return {'archived': True}

    @app.post(base + '/voices/{vid}/assign')
    def assign_voice(pid: str, vid: str, body: Assign):
        with studio.connect() as db:
            voice = db.execute('SELECT * FROM voice_library WHERE id=? AND production_id=? AND archived=0', (vid, pid)).fetchone()
        if not voice:
            raise HTTPException(404, 'Голос не найден')
        info = character_voice.target(studio, pid, body.character_node_id)
        old = character_voice.read_voice(studio, info['id'])
        profile = {'provider': voice['provider'], 'name': voice['name'], 'voice_id': voice['voice_id'], 'url': voice['url'],
                   'model': voice['model'], 'cost_multiplier': old.get('cost_multiplier', 1)}
        with studio.connect() as db:
            # Герой может иметь несколько голосов; последний привязанный становится голосом по умолчанию.
            db.execute('INSERT OR IGNORE INTO hero_voices VALUES(?,?,?)', (info['id'], vid, studio.now()))
            db.execute('INSERT INTO character_voices VALUES(?,?,?) ON CONFLICT(node_id) DO UPDATE SET profile=excluded.profile,updated_at=excluded.updated_at',
                       (info['id'], json.dumps(profile, ensure_ascii=False), studio.now()))
        character_voice.document(studio, info)
        return profile

    @app.post(base + '/voices/{vid}/unassign')
    def unassign_voice(pid: str, vid: str, body: Assign):
        with studio.connect() as db:
            voice = db.execute('SELECT * FROM voice_library WHERE id=? AND production_id=? AND archived=0', (vid, pid)).fetchone()
        if not voice:
            raise HTTPException(404, 'Голос не найден')
        info = character_voice.target(studio, pid, body.character_node_id)
        current = character_voice.read_voice(studio, info['id'])
        is_default = current.get('voice_id') == voice['voice_id'] and current.get('provider') == voice['provider']
        with studio.connect() as db:
            linked = db.execute('SELECT 1 FROM hero_voices WHERE node_id=? AND voice_lib_id=?', (info['id'], vid)).fetchone()
            if not linked and not is_default:
                raise HTTPException(409, 'Этот голос не привязан к герою')
            db.execute('DELETE FROM hero_voices WHERE node_id=? AND voice_lib_id=?', (info['id'], vid))
            if not is_default:
                return current
            rest = db.execute('''SELECT v.* FROM hero_voices h JOIN voice_library v ON v.id=h.voice_lib_id
                WHERE h.node_id=? AND v.archived=0 ORDER BY h.created_at DESC LIMIT 1''', (info['id'],)).fetchone()
            profile = ({'provider': rest['provider'], 'name': rest['name'], 'voice_id': rest['voice_id'], 'url': rest['url'],
                        'model': rest['model'], 'cost_multiplier': current.get('cost_multiplier', 1)}
                       if rest else character_voice.Voice().model_dump())
            db.execute('INSERT INTO character_voices VALUES(?,?,?) ON CONFLICT(node_id) DO UPDATE SET profile=excluded.profile,updated_at=excluded.updated_at',
                       (info['id'], json.dumps(profile, ensure_ascii=False), studio.now()))
        character_voice.document(studio, info)
        return profile

    # ---------- звуковые заметки кадров ----------
    @app.get(base + '/series/{sid}/sound')
    def series_sound(pid: str, sid: str):
        with studio.connect() as db:
            if not db.execute("SELECT 1 FROM production_nodes WHERE id=? AND production_id=? AND kind='series'", (sid, pid)).fetchone():
                raise HTTPException(404, 'Серия не найдена в выбранном проекте')
            return series_cues(db, pid, sid)

    @app.get(base + '/series/{sid}/sound-list')
    def sound_list(pid: str, sid: str):
        """Звуковой список для CapCut: по строке на заметку, с рекомендуемыми уровнями."""
        with studio.connect() as db:
            if not db.execute("SELECT 1 FROM production_nodes WHERE id=? AND production_id=? AND kind='series'", (sid, pid)).fetchone():
                raise HTTPException(404, 'Серия не найдена в выбранном проекте')
            frames = series_cues(db, pid, sid)
            heroes = {r['id']: r['title'] for r in db.execute("SELECT id,title FROM production_nodes WHERE production_id=? AND kind='character'", (pid,))}
        return Response(to_csv(frames, heroes), media_type='text/csv; charset=utf-8',
                        headers={'Content-Disposition': 'attachment; filename="sound-list.csv"'})

    @app.post(base + '/nodes/{nid}/sound')
    def add_cue(pid: str, nid: str, body: CueIn):
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            frame_node(db, pid, nid)
            hero = check_hero(db, pid, body.kind, body.hero_node_id)
            cid = uuid.uuid4().hex
            level = DEFAULT_LEVEL[body.kind] if body.level_db is None else body.level_db
            db.execute('''INSERT INTO frame_sound_cues(id,production_id,frame_id,kind,text,hero_node_id,level_db,start_s,duration_s,file_id,archived,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,NULL,0,?,?)''', (cid, pid, nid, body.kind, body.text.strip(), hero, level, body.start_s, body.duration_s, studio.now(), studio.now()))
        return {'id': cid, 'level_db': level}

    @app.put(base + '/sound/{cid}')
    def update_cue(pid: str, cid: str, body: CueIn):
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = cue_row(db, pid, cid)
            if body.kind != row['kind']:
                raise HTTPException(400, 'Тип заметки не меняется: создай новую')
            hero = check_hero(db, pid, body.kind, body.hero_node_id)
            level = DEFAULT_LEVEL[body.kind] if body.level_db is None else body.level_db
            db.execute('UPDATE frame_sound_cues SET text=?,hero_node_id=?,level_db=?,start_s=?,duration_s=?,updated_at=? WHERE id=?',
                       (body.text.strip(), hero, level, body.start_s, body.duration_s, studio.now(), cid))
        return {'saved': True}

    @app.delete(base + '/sound/{cid}')
    def archive_cue(pid: str, cid: str):
        """Заметка скрывается, файлы остаются в папке кадра."""
        with studio.connect() as db:
            cue_row(db, pid, cid)
            db.execute('UPDATE frame_sound_cues SET archived=1,updated_at=? WHERE id=?', (studio.now(), cid))
        return {'archived': True}

    @app.post(base + '/sound/{cid}/file')
    async def upload_cue_file(pid: str, cid: str, file: UploadFile = File(...)):
        with studio.connect() as db:
            row = cue_row(db, pid, cid)
            frame = frame_node(db, pid, row['frame_id'])
        extension = Path(file.filename or '').suffix.lower()
        if extension not in AUDIO_EXT:
            raise HTTPException(415, 'Нужен звуковой файл MP3, WAV или M4A')
        content = await file.read(MAX_AUDIO + 1)
        if len(content) > MAX_AUDIO:
            raise HTTPException(413, 'Лимит звукового файла — 100 МБ')
        if not content:
            raise HTTPException(400, 'Файл пустой')
        fid = uuid.uuid4().hex
        name = folders.safe_name(Path(file.filename or 'Звук').stem) + extension
        relative = str(Path(frame['relative_dir']) / '04_Звук' / (fid[:8] + '_' + name))
        path = folders.checked_path(studio, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        with studio.connect() as db:
            db.execute('INSERT INTO production_files(id,production_id,node_id,asset_id,filename,relative_path,kind,created_at) VALUES(?,?,?,?,?,?,?,?)',
                       (fid, pid, frame['id'], None, name, relative, 'audio', studio.now()))
            db.execute('UPDATE frame_sound_cues SET file_id=?,updated_at=? WHERE id=?', (fid, studio.now(), cid))
        return {'file_id': fid, 'url': '/api/production-files/' + fid}

    @app.post(base + '/sound/{cid}/link-asset')
    def link_asset(pid: str, cid: str, body: LinkAsset):
        """Привязывает к заметке уже сгенерированный звук из библиотеки (например, озвучку реплики) и кладёт копию в папку кадра."""
        with studio.connect() as db:
            row = cue_row(db, pid, cid)
            frame = frame_node(db, pid, row['frame_id'])
            asset = db.execute('SELECT a.metadata FROM library_assets a WHERE a.id=? AND a.project_id IN (SELECT project_id FROM production_links WHERE production_id=?)',
                               (body.asset_id, pid)).fetchone()
        if not asset:
            raise HTTPException(404, 'Звук не найден в проектах этого общего проекта')
        if json.loads(asset['metadata']).get('kind') != 'audio':
            raise HTTPException(400, 'Нужен звуковой файл')
        fid = folders.copy_asset(studio, pid, frame['id'], body.asset_id)
        with studio.connect() as db:
            db.execute('UPDATE frame_sound_cues SET file_id=?,updated_at=? WHERE id=?', (fid, studio.now(), cid))
        return {'file_id': fid, 'url': '/api/production-files/' + fid}
