"""Отправка результата из библиотеки в референсы персонажа (кнопка «В референсы»)."""
import json
import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, Field

CATEGORIES = {'approved_generations', 'candidate_generations', 'model_references', 'real_references'}


class ToCharacter(BaseModel):
    project_id: str
    character_id: str
    category: str = 'approved_generations'
    model_id: str = Field(default='', max_length=100)
    note: str = Field(default='', max_length=500)


def register(app, studio):
    @app.post('/api/library/{asset_id}/to-character')
    def to_character(asset_id: str, body: ToCharacter):
        if body.category not in CATEGORIES:
            raise HTTPException(400, 'Недопустимая категория референса')
        studio.checked_id(body.project_id)
        studio.checked_id(body.character_id)
        studio.project(body.project_id)
        with studio.connect() as db:
            row = studio.production_folders.accessible_asset(studio, db, asset_id, body.project_id)
        if not row:
            raise HTTPException(404, 'Изображение не найдено в библиотеке этого проекта')
        metadata = json.loads(row['metadata'])
        if metadata.get('kind', 'image') != 'image':
            raise HTTPException(400, 'В референсы персонажа отправляются только изображения')
        if body.category == 'model_references' and body.model_id not in studio.MODEL_SPECS:
            raise HTTPException(400, 'Для референса модели выбери модель из каталога')
        source = (studio.LIBRARY_ROOT / row['filename']).resolve()
        if not source.is_relative_to(studio.LIBRARY_ROOT.resolve()) or not source.is_file():
            raise HTTPException(404, 'Файл изображения отсутствует')
        owner = studio.production_folders.character_owner(studio, body.project_id, body.character_id)
        directory = studio.char_directory(owner, body.character_id, body.category, body.model_id)
        directory.mkdir(parents=True, exist_ok=True)
        new_id = uuid.uuid4().hex
        filename = new_id + Path(row['filename']).suffix.lower()
        shutil.copyfile(source, directory / filename)
        note = (body.note or ('Из результата ' + asset_id))[:500]
        try:
            with studio.connect() as db:
                duplicate = db.execute(
                    'SELECT id FROM character_assets WHERE project_id=? AND character_id=? AND category=? AND note=?',
                    (owner, body.character_id, body.category, note)).fetchone()
                if duplicate:
                    (directory / filename).unlink(missing_ok=True)
                    raise HTTPException(409, 'Это изображение уже отправлено в эту категорию персонажа')
                db.execute('INSERT INTO character_assets VALUES(?,?,?,?,?,?,?,?,?,?)',
                           (new_id, owner, body.character_id, body.category,
                            body.model_id if body.category == 'model_references' else '', filename,
                            (metadata.get('original_name') or row['filename'])[:200], '', note, studio.now()))
        except HTTPException:
            raise
        except Exception:
            (directory / filename).unlink(missing_ok=True)
            raise
        studio.production_folders.sync_character(studio, owner, body.character_id)
        return {'id': new_id, 'url': f'/api/character-assets/{new_id}', 'category': body.category,
                'character_id': body.character_id, 'source_asset_id': asset_id}
