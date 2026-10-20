import json
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import File, Form, HTTPException, UploadFile
from pydantic import BaseModel

MAX_RELEASE_BYTES = 1024 * 1024 * 1024


class ReleaseArtifact(BaseModel):
    id: str
    project_id: str
    project_revision: int
    version_id: str | None
    library_asset_id: str
    title: str
    filename: str
    mime_type: str
    width: int
    height: int
    duration: float
    status: str
    created_at: str
    file_url: str


def artifact_record(row):
    item = dict(row)
    item['file_url'] = f"/api/library/{item['library_asset_id']}/file"
    return item


def probe_mp4(studio, path):
    try:
        probe = json.loads(studio.cmd([
            'ffprobe', '-v', 'error', '-show_entries',
            'stream=codec_type,width,height:format=duration,format_name',
            '-of', 'json', str(path)
        ]).stdout)
    except (TypeError, ValueError):
        raise HTTPException(422, 'FFmpeg не смог прочитать итоговый MP4')
    if not isinstance(probe, dict):
        raise HTTPException(422, 'FFmpeg вернул некорректные метаданные MP4')
    format_data = probe.get('format') if isinstance(probe.get('format'), dict) else {}
    format_names = {part.strip().lower() for part in str(format_data.get('format_name') or '').split(',')}
    if 'mp4' not in format_names:
        raise HTTPException(415, 'Итоговый артефакт должен быть в контейнере MP4')
    streams = probe.get('streams') if isinstance(probe.get('streams'), list) else []
    video = next((stream for stream in streams if stream.get('codec_type') == 'video'), None)
    if not video:
        raise HTTPException(422, 'В итоговом MP4 отсутствует видеопоток')
    try:
        width = int(video.get('width') or 0)
        height = int(video.get('height') or 0)
    except (TypeError, ValueError):
        width = height = 0
    try:
        duration = float(format_data.get('duration') or video.get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if width <= 0 or height <= 0:
        raise HTTPException(422, 'В итоговом MP4 нет корректного видеопотока')
    return width, height, duration


async def store_upload(studio, file):
    studio.LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.release-', suffix='.mp4', dir=studio.LIBRARY_ROOT)
    os.close(descriptor)
    path = Path(name)
    try:
        total = 0
        with path.open('wb') as output:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_RELEASE_BYTES:
                    raise HTTPException(413, 'Максимальный итоговый MP4 — 1 ГБ')
                output.write(chunk)
        width, height, duration = probe_mp4(studio, path)
        return path, width, height, duration
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


def persist_release_artifact(studio, project_id, project_revision, version_id, title, temporary, width, height, duration):
    asset_id = uuid.uuid4().hex
    artifact_id = uuid.uuid4().hex
    filename = asset_id + '.mp4'
    destination = studio.LIBRARY_ROOT / filename
    created_at = studio.now()
    metadata = {
        'kind': 'video',
        'format': 'MP4',
        'width': width,
        'height': height,
        'duration': duration,
        'provider': 'local_import',
        'release_artifact_id': artifact_id,
        'project_revision': project_revision,
        'version_id': version_id,
        'request': {
            'source': 'local_import',
            'project_revision': project_revision,
            'version_id': version_id,
        },
    }
    try:
        temporary.replace(destination)
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            project_row = db.execute('SELECT revision FROM projects WHERE id=?', (project_id,)).fetchone()
            if not project_row:
                raise HTTPException(404, 'Проект не найден')
            if int(project_row['revision']) != project_revision:
                raise HTTPException(409, {
                    'code': 'PROJECT_REVISION_CONFLICT',
                    'message': 'Проект изменился после подготовки выпуска',
                    'revision': project_row['revision'],
                })
            if version_id and not db.execute(
                'SELECT 1 FROM prompt_versions WHERE id=? AND project_id=?',
                (version_id, project_id),
            ).fetchone():
                raise HTTPException(404, 'Версия промпта не принадлежит проекту')
            db.execute(
                'INSERT INTO library_assets VALUES(?,?,?,?,?,?,?,?)',
                (asset_id, artifact_id, project_id, 0, filename, '', json.dumps(metadata, ensure_ascii=False), created_at),
            )
            db.execute(
                'INSERT INTO release_artifacts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (artifact_id, project_id, project_revision, version_id, asset_id, title, filename,
                 'video/mp4', width, height, duration, 'ready', created_at),
            )
            row = db.execute('SELECT * FROM release_artifacts WHERE id=?', (artifact_id,)).fetchone()
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return row


def register(app, studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS release_artifacts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                project_revision INTEGER NOT NULL,
                version_id TEXT REFERENCES prompt_versions(id) ON DELETE SET NULL,
                library_asset_id TEXT NOT NULL UNIQUE REFERENCES library_assets(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                duration REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            )''')
            db.execute('CREATE INDEX IF NOT EXISTS release_artifacts_project_created ON release_artifacts(project_id,created_at DESC)')

    @app.get('/api/projects/{project_id}/release-artifacts', response_model=list[ReleaseArtifact])
    def listing(project_id: str):
        studio.project(project_id)
        with studio.connect() as db:
            rows = db.execute(
                'SELECT * FROM release_artifacts WHERE project_id=? ORDER BY created_at DESC',
                (project_id,),
            ).fetchall()
        return [artifact_record(row) for row in rows]

    @app.post('/api/projects/{project_id}/release-artifacts', response_model=ReleaseArtifact)
    async def import_release_artifact(
        project_id: str,
        file: UploadFile = File(...),
        project_revision: int = Form(..., ge=0),
        version_id: str | None = Form(None),
        title: str = Form(''),
    ):
        studio.project(project_id)
        version_id = version_id.strip() if version_id else None
        if version_id and len(version_id) > 100:
            raise HTTPException(400, 'Некорректный идентификатор версии')
        title = title.strip() or Path(file.filename or 'release.mp4').stem
        if len(title) > 200:
            raise HTTPException(400, 'Название выпуска не длиннее 200 символов')
        temporary, width, height, duration = await store_upload(studio, file)
        row = persist_release_artifact(
            studio, project_id, project_revision, version_id, title,
            temporary, width, height, duration,
        )
        return artifact_record(row)
