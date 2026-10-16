"""Временная папка и «Избранное».

Результаты генераций живут 7 дней. Сердечко (favorite) делает файл постоянным. Файл, который
где-либо использован (в папке постановки, в решении по ассету, в состоянии проекта, в референсах
персонажа), не удаляется. Удаление мягкое: файл уходит в library/.trash, строка и путь пишутся в
журнал cleanup_journal, откуда запись можно восстановить. Корзина чистится через 30 дней.
"""
import asyncio
import json
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel

TTL_DAYS = 7
TRASH_DAYS = 30
GENERATED_PROVIDERS_EXCLUDED = {'local_import'}


class Favorite(BaseModel):
    favorite: bool


class Cleanup(BaseModel):
    project_id: str | None = None
    approved: bool = False


def _parse(ts):
    try:
        value = datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except (AttributeError, ValueError):
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def used_reason(db, row, state_texts):
    aid = row['id']
    if db.execute('SELECT 1 FROM production_files WHERE asset_id=?', (aid,)).fetchone():
        return 'используется в папке постановки'
    outcome = db.execute('SELECT decision FROM asset_outcomes WHERE asset_id=?', (aid,)).fetchone() \
        if _has(db, 'asset_outcomes') else None
    if outcome and outcome['decision'] != 'undecided':
        return 'по ассету принято решение'
    if db.execute('SELECT 1 FROM character_assets WHERE note LIKE ?', (f'%{aid}%',)).fetchone():
        return 'отправлен в референсы персонажа'
    if any(aid in text for text in state_texts):
        return 'используется в проекте'
    return ''


def _has(db, table):
    return bool(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())


def candidates(studio, project_id=None, now=None):
    now = now or datetime.now(timezone.utc)
    items = []
    with studio.connect() as db:
        state_texts = [r['state'] for r in db.execute('SELECT state FROM projects')]
        query = 'SELECT * FROM library_assets' + (' WHERE project_id=?' if project_id else '')
        for row in db.execute(query, (project_id,) if project_id else ()):
            meta = json.loads(row['metadata'])
            if meta.get('favorite') or meta.get('kind', 'image') not in {'image', 'video'}:
                continue
            if meta.get('provider') in GENERATED_PROVIDERS_EXCLUDED or meta.get('keep'):
                continue
            created = _parse(row['created_at'])
            if not created:
                continue
            expires = created + timedelta(days=TTL_DAYS)
            reason = used_reason(db, row, state_texts)
            items.append({'asset_id': row['id'], 'project_id': row['project_id'], 'created_at': row['created_at'],
                          'expires_at': expires.isoformat(), 'expired': expires <= now,
                          'protected': reason, 'days_left': max(0, (expires - now).days)})
    return items


def move_to_trash(studio, asset_id, now, automatic=False):
    """Recheck protection under the SQLite writer lock; compensate filesystem on rollback."""
    moved = False
    source = target = None
    try:
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM library_assets WHERE id=?', (asset_id,)).fetchone()
            if not row:
                if automatic:
                    return False
                raise HTTPException(404, 'Ассет не найден')
            if automatic:
                meta = json.loads(row['metadata'])
                created = _parse(row['created_at'])
                if (meta.get('favorite') or meta.get('keep')
                        or meta.get('provider') in GENERATED_PROVIDERS_EXCLUDED
                        or meta.get('kind', 'image') not in {'image', 'video'}
                        or not created or created + timedelta(days=TTL_DAYS) > now):
                    return False
            state_texts = [r['state'] for r in db.execute('SELECT state FROM projects')]
            reason = used_reason(db, row, state_texts)
            if reason:
                if automatic:
                    return False
                raise HTTPException(409, 'Нельзя убрать: ' + str(reason))
            root = studio.LIBRARY_ROOT.resolve()
            source = (root / row['filename']).resolve()
            trash = (root / '.trash').resolve()
            if not source.is_relative_to(root) or not trash.is_relative_to(root):
                raise HTTPException(400, 'Недопустимый путь')
            trash.mkdir(exist_ok=True)
            name = f"{uuid.uuid4().hex}_{Path(row['filename']).name}"
            target = (trash / name).resolve()
            if not target.is_relative_to(trash):
                raise HTTPException(400, 'Недопустимый путь корзины')
            db.execute('CREATE TABLE IF NOT EXISTS cleanup_journal(id INTEGER PRIMARY KEY AUTOINCREMENT,asset_id TEXT,project_id TEXT,'
                       'trash_name TEXT,row_json TEXT,trashed_at TEXT,restored_at TEXT)')
            if source.is_file():
                source.rename(target)
                moved = True
            db.execute('INSERT INTO cleanup_journal(asset_id,project_id,trash_name,row_json,trashed_at) VALUES(?,?,?,?,?)',
                       (row['id'], row['project_id'], name, json.dumps(dict(row), ensure_ascii=False), now.isoformat()))
            db.execute('DELETE FROM library_assets WHERE id=?', (asset_id,))
        return True
    except Exception:
        if moved and target is not None and source is not None:
            # Never overwrite an independently recreated original.
            if target.is_file() and not source.exists():
                target.rename(source)
        raise


def run_cleanup(studio, project_id=None, now=None):
    now = now or datetime.now(timezone.utc)
    removed = []
    # The scan is advisory only; every candidate is reread and checked while holding the writer lock.
    for item in candidates(studio, project_id, now):
        if item['expired'] and not item['protected'] and move_to_trash(studio, item['asset_id'], now, automatic=True):
            removed.append(item['asset_id'])
    purge_trash(studio, now)
    return removed


def purge_trash(studio, now):
    trash = studio.LIBRARY_ROOT / '.trash'
    if not trash.is_dir():
        return
    limit = now - timedelta(days=TRASH_DAYS)
    with studio.connect() as db:
        if not _has(db, 'cleanup_journal'):
            return
        for entry in db.execute('SELECT * FROM cleanup_journal WHERE restored_at IS NULL').fetchall():
            when = _parse(entry['trashed_at'])
            if when and when < limit:
                (trash / entry['trash_name']).unlink(missing_ok=True)
                db.execute('UPDATE cleanup_journal SET restored_at=? WHERE id=?', ('purged', entry['id']))


def register(app, studio):
    @app.post('/api/library/{asset_id}/favorite')
    def favorite(asset_id: str, body: Favorite):
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM library_assets WHERE id=?', (asset_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Ассет не найден')
            meta = json.loads(row['metadata'])
            meta['favorite'] = body.favorite
            if body.favorite:
                meta['favorite_at'] = studio.now()
            else:
                meta.pop('favorite_at', None)
            db.execute('UPDATE library_assets SET metadata=? WHERE id=?', (json.dumps(meta, ensure_ascii=False), asset_id))
        return {'asset_id': asset_id, 'favorite': body.favorite}

    @app.post('/api/library/{asset_id}/trash')
    def trash_one(asset_id: str):
        """Ручное «удалить»: мягко, в корзину на 30 дней; используемые ассеты не трогаем."""
        move_to_trash(studio, asset_id, datetime.now(timezone.utc))
        return {'asset_id': asset_id, 'trashed': True, 'restore_days': 30}

    @app.get('/api/library/temp')
    def temp_list(project_id: str):
        studio.project(project_id)
        return {'ttl_days': TTL_DAYS, 'items': candidates(studio, project_id)}

    @app.post('/api/library/cleanup')
    def cleanup(body: Cleanup):
        if body.project_id:
            studio.project(body.project_id)
        pending = [i for i in candidates(studio, body.project_id) if i['expired'] and not i['protected']]
        if not body.approved:
            return {'removed': [], 'would_remove': [i['asset_id'] for i in pending]}
        return {'removed': run_cleanup(studio, body.project_id), 'would_remove': []}

    @app.get('/api/library/cleanup/journal')
    def journal(project_id: str):
        studio.project(project_id)
        with studio.connect() as db:
            if not _has(db, 'cleanup_journal'):
                return []
            return [{k: r[k] for k in ('id', 'asset_id', 'trashed_at', 'restored_at')}
                    for r in db.execute('SELECT * FROM cleanup_journal WHERE project_id=? ORDER BY id DESC', (project_id,))]

    @app.post('/api/library/cleanup/restore/{entry_id}')
    def restore(entry_id: int):
        with studio.connect() as db:
            if not _has(db, 'cleanup_journal'):
                raise HTTPException(404, 'Журнал пуст')
            entry = db.execute('SELECT * FROM cleanup_journal WHERE id=?', (entry_id,)).fetchone()
            if not entry or entry['restored_at']:
                raise HTTPException(404, 'Запись недоступна для восстановления')
            row = json.loads(entry['row_json'])
            trashed = studio.LIBRARY_ROOT / '.trash' / entry['trash_name']
            if not trashed.is_file():
                raise HTTPException(404, 'Файл уже удалён из корзины')
            target = studio.LIBRARY_ROOT / row['filename']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(trashed), str(target))
            meta = json.loads(row['metadata'])
            meta['keep'] = True
            row['metadata'] = json.dumps(meta, ensure_ascii=False)
            db.execute('INSERT INTO library_assets VALUES(?,?,?,?,?,?,?,?)',
                       (row['id'], row['job_id'], row['project_id'], row['output_index'], row['filename'],
                        row['source_url'], row['metadata'], row['created_at']))
            db.execute('UPDATE cleanup_journal SET restored_at=? WHERE id=?', (studio.now(), entry_id))
        return {'asset_id': row['id']}

    @app.on_event('startup')
    async def schedule():
        async def loop():
            while True:
                await asyncio.sleep(3600)
                try:
                    await asyncio.to_thread(run_cleanup, studio)
                except Exception:  # фоновая уборка не должна ронять сервер
                    pass
        asyncio.get_event_loop().create_task(loop())
