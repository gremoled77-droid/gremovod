"""Ручной маршрут «Внешняя генерация»: скопировать промпт, сгенерировать вне студии
(ChatGPT и др.) и вернуть готовую картинку в тот же кадр.

Результат сохраняется как отдельная попытка с provider=external:<сервис>, ссылкой на промпт,
модель и референсы. Оригинал не перезаписывается; стоимость по API равна нулю, эквивалент
считается в экономике отдельно. Сетевых вызовов модуль не делает.
"""
import hashlib
import json
import re
import uuid
from typing import Literal

from fastapi import File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

MAX_BYTES = 20 * 1024 * 1024
REQUEST_ID = re.compile(r'^[a-zA-Z0-9_-]{16,100}$')
EXTENSIONS = {'PNG': '.png', 'JPEG': '.jpg', 'WEBP': '.webp'}


class ExternalReference(BaseModel):
    asset_id: str = Field(min_length=1, max_length=100)
    role: str = Field(default='reference', max_length=100)


class ExternalJobRequest(BaseModel):
    project_id: str
    request_id: str
    target: str = Field(default='gpt-image-2.5', max_length=100)
    prompt: str = Field(min_length=1, max_length=20000)
    service: Literal['chatgpt', 'other'] = 'chatgpt'
    node_id: str | None = Field(default=None, max_length=100)
    references: list[ExternalReference] = Field(default_factory=list, max_length=16)


def copy_text(job):
    """Текст для вставки во внешний сервис: промпт и порядок референсов."""
    lines = [job['prompt'].strip()]
    refs = job['references']
    if refs:
        lines += ['', 'Референсы (приложить к запросу в этом порядке):']
        lines += [f'Image {r["index"]} — {r["role"]}' for r in refs]
    return '\n'.join(lines)


def register(app, studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS external_jobs(
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, node_id TEXT, target TEXT NOT NULL,
                service TEXT NOT NULL, prompt TEXT NOT NULL, refs TEXT NOT NULL, status TEXT NOT NULL,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')

    def present(db, row):
        refs = json.loads(row['refs'])
        results = [dict(x) for x in db.execute(
            'SELECT id,output_index,created_at FROM library_assets WHERE job_id=? ORDER BY output_index', (row['id'],))]
        job = {'id': row['id'], 'project_id': row['project_id'], 'node_id': row['node_id'], 'target': row['target'],
               'service': row['service'], 'prompt': row['prompt'], 'status': row['status'], 'references': refs,
               'created_at': row['created_at'], 'updated_at': row['updated_at'],
               'results': [{'asset_id': x['id'], 'url': f'/api/library/{x["id"]}/file'} for x in results]}
        job['copy_text'] = copy_text(job)
        return job

    def load(db, job_id):
        row = db.execute('SELECT * FROM external_jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Внешнее задание не найдено')
        return row

    @app.post('/api/external-jobs')
    def create_job(body: ExternalJobRequest):
        studio.project(body.project_id)
        if not REQUEST_ID.fullmatch(body.request_id):
            raise HTTPException(400, 'Нужен уникальный request_id')
        if body.target not in studio.MODEL_SPECS or studio.MODEL_SPECS[body.target]['kind'] != 'image':
            raise HTTPException(400, 'Выбери модель изображений из каталога')
        refs = []
        with studio.connect() as db:
            for index, ref in enumerate(body.references, 1):
                row = studio.production_folders.accessible_asset(studio, db, ref.asset_id, body.project_id)
                if not row:
                    raise HTTPException(404, 'Референс не найден в библиотеке этого проекта')
                refs.append({'index': index, 'asset_id': ref.asset_id, 'role': ref.role.strip() or 'reference',
                             'file_url': f'/api/library/{ref.asset_id}/file'})
            existing = db.execute('SELECT * FROM external_jobs WHERE id=?', (body.request_id,)).fetchone()
            if existing:
                if (existing['project_id'], existing['prompt'], existing['target']) != (body.project_id, body.prompt, body.target):
                    raise HTTPException(409, 'Этот request_id уже использован с другими параметрами')
                return {**present(db, existing), 'duplicate': True}
            now = studio.now()
            db.execute('INSERT INTO external_jobs VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (body.request_id, body.project_id, body.node_id, body.target, body.service, body.prompt,
                        json.dumps(refs, ensure_ascii=False), 'waiting_external', now, now))
            return present(db, load(db, body.request_id))

    @app.get('/api/external-jobs')
    def list_jobs(project_id: str, node_id: str | None = None):
        studio.project(project_id)
        with studio.connect() as db:
            sql, args = 'SELECT * FROM external_jobs WHERE project_id=?', [project_id]
            if node_id:
                sql, args = sql + ' AND node_id=?', args + [node_id]
            return [present(db, row) for row in db.execute(sql + ' ORDER BY created_at DESC', args)]

    @app.get('/api/external-jobs/{job_id}')
    def get_job(job_id: str):
        with studio.connect() as db:
            return present(db, load(db, job_id))

    @app.post('/api/external-jobs/{job_id}/cancel')
    def cancel_job(job_id: str):
        with studio.connect() as db:
            row = load(db, job_id)
            if row['status'] == 'waiting_external':
                db.execute('UPDATE external_jobs SET status=?,updated_at=? WHERE id=?', ('cancelled', studio.now(), job_id))
            return present(db, load(db, job_id))

    @app.post('/api/external-jobs/{job_id}/result')
    async def attach_result(job_id: str, file: UploadFile = File(...), note: str = Form('')):
        with studio.connect() as db:
            row = load(db, job_id)
        if row['status'] == 'cancelled':
            raise HTTPException(409, 'Задание отменено; создай новое')
        content = await file.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise HTTPException(413, 'Максимальный размер — 20 МБ')
        info = studio.inspect_image(content)
        digest = hashlib.sha256(content).hexdigest()
        with studio.connect() as db:
            for other in db.execute('SELECT id,metadata FROM library_assets WHERE job_id=?', (job_id,)):
                if json.loads(other['metadata']).get('sha256') == digest:
                    raise HTTPException(409, 'Эта картинка уже добавлена к заданию')
            index = db.execute('SELECT COUNT(*) FROM library_assets WHERE job_id=?', (job_id,)).fetchone()[0]
        aid = uuid.uuid4().hex
        filename = aid + EXTENSIONS[info['format']]
        studio.LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
        path = studio.LIBRARY_ROOT / filename
        path.write_bytes(content)
        metadata = {**info, 'kind': 'image', 'provider': 'external:' + row['service'], 'external_job_id': job_id,
                    'target': row['target'], 'original_name': (file.filename or '')[:200], 'sha256': digest,
                    'note': note[:500], 'role': 'generated', 'node_id': row['node_id'],
                    'request': {'payload': {'task_type': row['target'], 'input': {'prompt': row['prompt']}}}}
        try:
            with studio.connect() as db:
                db.execute('INSERT INTO library_assets VALUES(?,?,?,?,?,?,?,?)',
                           (aid, job_id, row['project_id'], index, filename, '', json.dumps(metadata, ensure_ascii=False), studio.now()))
                db.execute('UPDATE external_jobs SET status=?,updated_at=? WHERE id=?', ('received', studio.now(), job_id))
                library_row = db.execute('SELECT * FROM library_assets WHERE id=?', (aid,)).fetchone()
        except Exception:
            path.unlink(missing_ok=True)
            raise
        studio.production_folders.sync_asset(studio, aid)
        return {'job_id': job_id, 'status': 'received', 'asset': studio.library_record(library_row)}
