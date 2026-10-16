"""Clip chaining: save the last frame of a video as an image asset to start the next clip from it (free, local ffmpeg)."""
import hashlib
import json
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from fastapi import HTTPException


def ffmpeg_path(studio):
    found = shutil.which('ffmpeg')
    if found:
        return found
    local = Path(studio.ROOT).parent / 'tools' / 'ffmpeg' / 'bin' / 'ffmpeg.exe'
    return str(local) if local.is_file() else None


def last_frame_png(studio, video):
    binary = ffmpeg_path(studio)
    if not binary:
        raise HTTPException(503, 'FFmpeg не найден: извлечь последний кадр нельзя')
    with tempfile.TemporaryDirectory() as folder:
        target = Path(folder) / 'last.png'
        # Seek slightly before the end: the very last timestamp often has no decodable frame.
        for offset in ('-0.15', '-0.5', '-1.5'):
            subprocess.run([binary, '-v', 'error', '-y', '-sseof', offset, '-i', str(video), '-frames:v', '1', '-update', '1', str(target)],
                           capture_output=True, timeout=60)
            if target.is_file() and target.stat().st_size > 0:
                return target.read_bytes()
    raise HTTPException(422, 'Не удалось извлечь последний кадр из этого видео')


def register(app, studio):
    @app.post('/api/library/{asset_id}/last-frame')
    def last_frame(asset_id: str):
        studio.checked_id(asset_id)
        with studio.connect() as db:
            row = db.execute('SELECT * FROM library_assets WHERE id=?', (asset_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Ассет не найден')
        metadata = json.loads(row['metadata'])
        if metadata.get('kind') != 'video':
            raise HTTPException(400, 'Последний кадр берётся только из видео')
        path = (studio.LIBRARY_ROOT / row['filename']).resolve()
        if not path.is_relative_to(studio.LIBRARY_ROOT.resolve()) or not path.is_file():
            raise HTTPException(404, 'Файл видео отсутствует')
        content = last_frame_png(studio, path)
        info = studio.inspect_image(content)
        aid = uuid.uuid4().hex
        filename = aid + '.png'
        studio.LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
        target = studio.LIBRARY_ROOT / filename
        target.write_bytes(content)
        meta = {**info, 'kind': 'image', 'provider': 'local_extract', 'role': 'chain_frame', 'source_asset_id': asset_id,
                'sha256': hashlib.sha256(content).hexdigest(), 'request': {'payload': {'task_type': 'last-frame', 'input': {'prompt': ''}}}}
        try:
            with studio.connect() as db:
                db.execute('INSERT INTO library_assets VALUES(?,?,?,?,?,?,?,?)',
                           (aid, 'frame-' + aid, row['project_id'], 0, filename, '', json.dumps(meta, ensure_ascii=False), studio.now()))
                saved = db.execute('SELECT * FROM library_assets WHERE id=?', (aid,)).fetchone()
        except Exception:
            target.unlink(missing_ok=True)
            raise
        studio.production_folders.sync_asset(studio, aid)
        return studio.library_record(saved)
