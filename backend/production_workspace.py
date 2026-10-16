"""Explicit maintenance operation: separate a production library from its old frame project.

Generation records, library IDs, costs and old character files stay intact.
Run only through the backup-taking maintenance command, not at application startup.
"""
import json
import shutil
import os
import uuid
from fastapi import HTTPException
from backend import production_folders as folders


def promote_workspace(studio, production_id, target_id, expected_source_id, *, apply=False):
    with studio.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        production = db.execute('SELECT * FROM productions WHERE id=?', (production_id,)).fetchone()
        if not production:
            raise HTTPException(404, 'Общий проект не найден')
        if production['source_project_id'] == target_id:
            return {'already_applied': True, 'source_project_id': target_id}
        if production['source_project_id'] != expected_source_id or target_id == expected_source_id:
            raise HTTPException(409, 'Исходный проект изменён; перенос остановлен')
        target = db.execute('SELECT * FROM projects WHERE id=?', (target_id,)).fetchone()
        source = db.execute('SELECT * FROM projects WHERE id=?', (expected_source_id,)).fetchone()
        if not target or not source:
            raise HTTPException(404, 'Рабочий или исходный проект не найден')
        if db.execute('SELECT 1 FROM production_links WHERE project_id=?', (target_id,)).fetchone():
            raise HTTPException(409, 'Рабочий проект уже связан с другой папкой')
        old_link = db.execute('SELECT * FROM production_links WHERE project_id=? AND production_id=?',
                              (expected_source_id, production_id)).fetchone()
        frame = db.execute("SELECT * FROM production_nodes WHERE id=? AND production_id=? AND kind='frame'",
                           (old_link['node_id'] if old_link else None, production_id)).fetchone()
        if not frame:
            raise HTTPException(409, 'Исходный проект должен оставаться связанным с кадром')
        # No movement of in-flight work or prepared chat tasks.
        for table in ('jobs', 'native_chat_jobs', 'external_jobs'):
            columns = {r['name'] for r in db.execute('PRAGMA table_info(' + table + ')')}
            if not {'project_id', 'status'} <= columns:
                continue
            pending = db.execute(f"SELECT 1 FROM {table} WHERE project_id=? AND status NOT IN "
                                 "('completed','succeeded','done','failed','cancelled','canceled','expired') LIMIT 1",
                                 (expected_source_id,)).fetchone()
            if pending:
                raise HTTPException(409, 'Сначала заверши или отмени задания исходного проекта')
        source_state, target_state = json.loads(source['state']), json.loads(target['state'])
        shared_ids = {r['character_id'] for r in db.execute(
            "SELECT character_id FROM production_nodes WHERE production_id=? AND kind='character'", (production_id,))}
        source_characters = {c['id']: c for c in source_state.get('characters', [])}
        target_characters = {c['id']: c for c in target_state.get('characters', [])}
        if not shared_ids <= source_characters.keys():
            raise HTTPException(409, 'Не все общие персонажи найдены в исходном проекте')
        for cid in shared_ids:
            if cid in target_characters and target_characters[cid] != source_characters[cid]:
                raise HTTPException(409, 'Конфликт версий персонажа: ' + cid)
        copied = []
        refs = db.execute('SELECT * FROM character_assets WHERE project_id=?', (expected_source_id,)).fetchall()
        for ref in refs:
            if ref['character_id'] not in shared_ids:
                continue
            old = (studio.char_directory(expected_source_id, ref['character_id'], ref['category'], ref['model_id'] or '') / ref['filename']).resolve()
            new = (studio.char_directory(target_id, ref['character_id'], ref['category'], ref['model_id'] or '') / ref['filename']).resolve()
            if not old.is_relative_to(studio.CHAR_ROOT.resolve()) or not new.is_relative_to(studio.CHAR_ROOT.resolve()):
                raise HTTPException(409, 'Недопустимый путь референса')
            if not old.is_file():
                raise HTTPException(409, 'Исходный референс отсутствует: ' + ref['id'])
            if new.exists() and new.read_bytes() != old.read_bytes():
                raise HTTPException(409, 'Файл назначения отличается: ' + ref['id'])
            copied.append((ref, old, new))
        target_state['characters'] = [source_characters[cid] for cid in source_characters if cid in shared_ids] + [
            c for c in target_state.get('characters', []) if c['id'] not in shared_ids]
        if not target_state.get('selectedCharacter'):
            target_state['selectedCharacter'] = source_state.get('selectedCharacter', '')
        # A new workspace may have no world bible; preserve an existing one field by field.
        target_state['style'] = {**source_state.get('style', {}), **target_state.get('style', {})}
        frame_title = production['title'] + ' / ' + frame['title']
        result = {'already_applied': False, 'source_project_id': target_id,
                  'frame_project_id': expected_source_id, 'frame_title': frame_title,
                  'shared_character_ids': sorted(shared_ids), 'character_files': len(copied)}
        if not apply:
            return result
        # Copies are additive and checked above. Originals remain for rollback.
        # If copying fails, the database transaction rolls back; a retry accepts identical copies.
        for ref, old, new in copied:
            new.parent.mkdir(parents=True, exist_ok=True)
            if not new.exists():
                temporary = new.with_name(new.name + '.' + uuid.uuid4().hex + '.tmp')
                try:
                    with temporary.open('xb') as output, old.open('rb') as source_file:
                        shutil.copyfileobj(source_file, output)
                    os.link(temporary, new)
                finally:
                    temporary.unlink(missing_ok=True)
            db.execute('UPDATE character_assets SET project_id=? WHERE id=?', (target_id, ref['id']))
        db.execute('INSERT INTO production_links VALUES(?,?,NULL)', (target_id, production_id))
        db.execute('UPDATE productions SET source_project_id=? WHERE id=?', (target_id, production_id))
        db.execute('UPDATE projects SET title=?,updated_at=? WHERE id=?', (frame_title, studio.now(), expected_source_id))
        db.execute('UPDATE projects SET state=?,updated_at=? WHERE id=?',
                   (json.dumps(target_state, ensure_ascii=False), studio.now(), target_id))
    return result


def sync_workspace_documents(studio, production_id):
    production = folders.production(studio, production_id)
    state = studio.project(production['source_project_id'])['state']
    base = production['folder']
    folders.write_text(studio, base + '/ПРОЕКТ.json', json.dumps(production, ensure_ascii=False, indent=2))
    folders.write_text(studio, base + '/БИБЛИЯ_МИРА.json', json.dumps(state.get('style', {}), ensure_ascii=False, indent=2))
    with studio.connect() as db:
        characters = db.execute("SELECT * FROM production_nodes WHERE production_id=? AND kind='character'", (production_id,)).fetchall()
    from backend import character_voice
    for item in characters:
        character = next(c for c in state['characters'] if c['id'] == item['character_id'])
        folders.write_text(studio, item['relative_dir'] + '/ПРОФИЛЬ.json', json.dumps(character, ensure_ascii=False, indent=2))
        character_voice.document(studio, dict(item))
