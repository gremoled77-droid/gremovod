"""Explicit user approval of an existing image as a character's working version."""
import json
import uuid
from fastapi import HTTPException
from pydantic import BaseModel


class Replacement(BaseModel):
    asset_id: str


def register(app, studio):
    @app.post('/api/characters/{project_id}/{character_id}/replace')
    def replace(project_id: str, character_id: str, body: Replacement):
        owner=studio.production_folders.character_owner(studio,project_id,character_id)
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            project = db.execute('SELECT state FROM projects WHERE id=?', (owner,)).fetchone()
            if not project:
                raise HTTPException(404, 'Проект не найден')
            state = json.loads(project['state'])
            character = next((c for c in state.get('characters', []) if c['id'] == character_id), None)
            if not character:
                raise HTTPException(404, 'Персонаж не найден в проекте')
            asset = studio.production_folders.accessible_asset(studio,db,body.asset_id,project_id)
            if not asset:
                raise HTTPException(404, 'Изображение не найдено в этом проекте')
            metadata = json.loads(asset['metadata'])
            if metadata.get('kind') in {'video','audio','document'}:
                raise HTTPException(400, 'Выбери изображение персонажа')
            if metadata.get('character_id') not in (None, '', character_id):
                raise HTTPException(409, 'Изображение связано с другим персонажем')
            path = (studio.LIBRARY_ROOT / asset['filename']).resolve()
            if not path.is_relative_to(studio.LIBRARY_ROOT.resolve()) or not path.is_file():
                raise HTTPException(404, 'Оригинал изображения отсутствует')
            studio.inspect_image(path.read_bytes())
            previous = character.get('working_asset_id')
            history = character.setdefault('version_history', [])
            # Keep prior approved images as explicit history, never delete originals.
            prior = db.execute('SELECT id,metadata FROM library_assets WHERE project_id=? OR project_id IN (SELECT other.project_id FROM production_links mine JOIN production_links other ON mine.production_id=other.production_id WHERE mine.project_id=?)', (owner,owner)).fetchall()
            for item in prior:
                info = json.loads(item['metadata'])
                if item['id'] != body.asset_id and info.get('character_id') == character_id and info.get('character_status') == 'approved':
                    if item['id'] not in history:
                        history.append(item['id'])
                    info['character_status'] = 'archived'
                    db.execute('UPDATE library_assets SET metadata=? WHERE id=?', (json.dumps(info, ensure_ascii=False), item['id']))
            if previous and previous != body.asset_id:
                if previous not in history:
                    history.append(previous)
                old = db.execute('SELECT metadata FROM library_assets WHERE id=?', (previous,)).fetchone()
                if old:
                    old_metadata = json.loads(old['metadata'])
                    old_metadata['character_status'] = 'archived'
                    db.execute('UPDATE library_assets SET metadata=? WHERE id=?', (json.dumps(old_metadata, ensure_ascii=False), previous))
            character['working_asset_id'] = body.asset_id
            vault_id = uuid.uuid5(uuid.NAMESPACE_URL, f'{owner}/{character_id}/{body.asset_id}').hex
            vault = db.execute("SELECT * FROM character_assets WHERE project_id=? AND character_id=? AND category='approved_generations'", (owner, character_id)).fetchall()
            for item in vault:
                if item['id'] == vault_id:
                    continue
                old_path = studio.char_directory(owner, character_id, 'approved_generations') / item['filename']
                archive = studio.char_directory(owner, character_id, 'archived_generations')
                archive.mkdir(parents=True, exist_ok=True)
                if old_path.is_file():
                    (archive / item['filename']).write_bytes(old_path.read_bytes())
                db.execute("UPDATE character_assets SET category='archived_generations' WHERE id=?", (item['id'],))
            directory = studio.char_directory(owner, character_id, 'approved_generations')
            directory.mkdir(parents=True, exist_ok=True)
            filename = vault_id + path.suffix
            (directory / filename).write_bytes(path.read_bytes())
            db.execute('INSERT INTO character_assets(id,project_id,character_id,category,model_id,filename,original_name,external_url,note,created_at) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET category=excluded.category',
                       (vault_id, owner, character_id, 'approved_generations', '', filename, character.get('name', character_id) + ' — рабочий образ' + path.suffix, asset['source_url'], 'Рабочий образ из библиотеки: ' + body.asset_id, studio.now()))
            metadata.update(character_id=character_id, character_status='approved')
            state.setdefault('refinement', {}).update(source_asset_id=body.asset_id, reference_asset_id='', instruction='')
            db.execute('UPDATE library_assets SET metadata=? WHERE id=?', (json.dumps(metadata, ensure_ascii=False), body.asset_id))
            db.execute('UPDATE projects SET state=?,updated_at=? WHERE id=?', (json.dumps(state, ensure_ascii=False), studio.now(), owner))
            if owner!=project_id:
                current=db.execute('SELECT state FROM projects WHERE id=?',(project_id,)).fetchone()
                if not current:raise HTTPException(404,'Проект кадра не найден')
                current_state=json.loads(current['state']);current_state['refinement']=state['refinement']
                db.execute('UPDATE projects SET state=?,updated_at=? WHERE id=?',(json.dumps(current_state,ensure_ascii=False),studio.now(),project_id))
        studio.production_folders.sync_character(studio,owner,character_id)
        studio.production_folders.sync_asset(studio,body.asset_id)
        return {'character': character, 'refinement': state['refinement']}
