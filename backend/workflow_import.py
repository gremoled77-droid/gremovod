"""Загрузка референсов для воркфлоу: картинка, аудио или файл-документ в библиотеку проекта."""
import hashlib
import json
import uuid
from pathlib import Path

from fastapi import File, Form, HTTPException, UploadFile

IMAGE = {'.png', '.jpg', '.jpeg', '.webp'}
AUDIO = {'.mp3', '.wav', '.m4a'}
TEXT = {'.txt', '.md', '.srt', '.json'}
DOCUMENT = TEXT | {'.pdf'}
LIMITS = {'image': 20 * 1024 * 1024, 'audio': 50 * 1024 * 1024, 'document': 20 * 1024 * 1024}
EXCERPT_CHARS = 8000


def classify(name):
    ext = Path(name or '').suffix.lower()
    if ext in IMAGE:
        return 'image', ext
    if ext in AUDIO:
        return 'audio', ext
    if ext in DOCUMENT:
        return 'document', ext
    raise HTTPException(400, 'Допустимы картинки (png, jpg, webp), аудио (mp3, wav, m4a) и файлы (txt, md, srt, json, pdf)')


def check_signature(kind, ext, content):
    """Грубая защита от файла с чужим расширением; полную проверку формата делает потребитель."""
    head = content[:16]
    if kind == 'audio':
        ok = {'.mp3': head[:3] == b'ID3' or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0),
              '.wav': head[:4] == b'RIFF' and content[8:12] == b'WAVE',
              '.m4a': content[4:8] == b'ftyp'}[ext]
        if not ok:
            raise HTTPException(422, 'Содержимое файла не похоже на выбранный аудиоформат')
    elif kind == 'document':
        if ext == '.pdf':
            if not content.startswith(b'%PDF'):
                raise HTTPException(422, 'Файл не похож на PDF')
        elif b'\x00' in content[:4096]:
            raise HTTPException(422, 'Текстовый файл содержит двоичные данные')


def excerpt(ext, content):
    if ext not in TEXT:
        return ''
    for encoding in ('utf-8-sig', 'cp1251'):
        try:
            return content.decode(encoding)[:EXCERPT_CHARS]
        except UnicodeDecodeError:
            continue
    return ''


def register(app, studio):
    @app.post('/api/library/import-reference')
    async def import_reference(project_id: str = Form(...), file: UploadFile = File(...)):
        studio.project(project_id)
        kind, ext = classify(file.filename)
        limit = LIMITS[kind]
        content = await file.read(limit + 1)
        if len(content) > limit:
            raise HTTPException(413, f'Максимальный размер: {limit // (1024 * 1024)} МБ')
        if not content:
            raise HTTPException(400, 'Файл пустой')
        metadata = {}
        if kind == 'image':
            info = studio.inspect_image(content)
            ext = {'PNG': '.png', 'JPEG': '.jpg', 'WEBP': '.webp'}[info['format']]
            metadata.update(info)
        else:
            check_signature(kind, ext, content)
        aid = uuid.uuid4().hex
        filename = aid + ext
        studio.LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
        path = studio.LIBRARY_ROOT / filename
        path.write_bytes(content)
        metadata.update({'kind': kind, 'provider': 'local_import', 'role': 'user_reference', 'original_name': (file.filename or '')[:200],
                         'size': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
                         'request': {'payload': {'task_type': 'local-reference', 'input': {'prompt': ''}}}})
        text = excerpt(ext, content)
        if text:
            metadata['excerpt'] = text
        try:
            with studio.connect() as db:
                db.execute('INSERT INTO library_assets VALUES(?,?,?,?,?,?,?,?)',
                           (aid, 'import-' + aid, project_id, 0, filename, '', json.dumps(metadata, ensure_ascii=False), studio.now()))
                row = db.execute('SELECT * FROM library_assets WHERE id=?', (aid,)).fetchone()
        except Exception:
            path.unlink(missing_ok=True)
            raise
        studio.production_folders.sync_asset(studio, aid)
        return studio.library_record(row)
