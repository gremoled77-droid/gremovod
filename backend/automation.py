"""Durable sandbox automation contract. No provider calls or canonical writes."""
import hmac
import hashlib
import json
import os
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from backend import storyboard

PREFIX = '/api/v1/automation'


class Message(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Skill(Message):
    name: str = Field(pattern=r'^[a-z0-9][a-z0-9-]{0,99}$')
    skill_commit_sha: str = Field(pattern=r'^[0-9a-f]{40}$')


class Job(Message):
    project_id: str = Field(min_length=1, max_length=100)
    production_id: str = Field(min_length=1, max_length=100)
    series_id: str = Field(min_length=1, max_length=100)
    scene_id: str | None = Field(default=None, max_length=100)
    shot_id: str | None = Field(default=None, max_length=100)
    canon_revision: str = Field(pattern=r'^[0-9a-f]{64}$')
    base_revision: str = Field(pattern=r'^[0-9a-f]{64}$')
    idempotency_key: str = Field(min_length=8, max_length=100)
    correlation_id: str = Field(min_length=8, max_length=100)
    stage: Literal['storyboard'] = 'storyboard'
    agent_role: Literal['A2'] = 'A2'
    instruction: str = Field(min_length=1, max_length=20000)
    skills: list[Skill] = Field(default_factory=list, max_length=20)
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=20)
    model_provider: Literal['stub'] = 'stub'
    model: Literal['echo'] = 'echo'
    model_reason: str = Field(default='Sandbox contract verification', max_length=1000)
    estimated_cost: Literal[0] = 0
    allowed_paid_media: Literal[False] = False


class Claim(Message):
    execution_id: str = Field(min_length=1, max_length=100)


class Callback(Claim):
    task_id: str = Field(min_length=1, max_length=100)
    event_id: str = Field(min_length=8, max_length=100)
    status: Literal['review_required', 'failed']
    proposal: str = Field(default='', max_length=30000)
    error_code: str = Field(default='', max_length=100, pattern=r'^[A-Z0-9_]*$')


class Review(Message):
    decision: Literal['approved', 'rejected']


def service_project(request: Request):
    """Fail closed; one credential is scoped to exactly one working project."""
    secret = os.environ.get('STUDIO_AUTOMATION_TOKEN', '')
    project_id = os.environ.get('STUDIO_AUTOMATION_PROJECT_ID', '')
    if len(secret) < 32 or not project_id:
        raise HTTPException(503, 'Automation service credential is not configured')
    supplied = request.headers.get('authorization', '')
    if not hmac.compare_digest(supplied.encode(), ('Bearer ' + secret).encode()):
        raise HTTPException(401, 'Invalid automation credential')
    return project_id


def owner(request: Request):
    # Never allow the service credential to approve or enqueue its own work.
    from backend import security
    token = request.headers.get('x-studio-session') or request.cookies.get('studio_session', '')
    if request.headers.get('authorization') or not hmac.compare_digest(token.encode(), security.LAUNCH_TOKEN.encode()):
        raise HTTPException(401, 'Studio session required')


def scoped(row, project_id):
    if not row or row['project_id'] != project_id:
        raise HTTPException(404, 'Automation job not found')
    return row


def context(db, project_id, production_id, series_id):
    project = db.execute('SELECT state,revision FROM projects WHERE id=?', (project_id,)).fetchone()
    linked = db.execute('SELECT 1 FROM productions WHERE source_project_id=? AND id=?', (project_id, production_id)).fetchone()
    if not project or not linked:
        raise HTTPException(404, 'Project is not linked to this production')
    parent, nodes, script, revision = storyboard.snapshot(db, production_id, series_id)
    vault = [dict(r) for r in db.execute('SELECT id,character_id,category,model_id,note,created_at FROM character_assets WHERE project_id=? ORDER BY id', (project_id,))]
    files = [dict(r) for r in db.execute('SELECT id,node_id,asset_id,kind FROM production_files WHERE production_id=? ORDER BY id', (production_id,))]
    canon_revision = hashlib.sha256(encoded([project['revision'], vault, files]).encode()).hexdigest()
    characters = [{k: c[k] for k in ('id', 'name', 'identity', 'working_asset_id') if k in c}
                  for c in json.loads(project['state']).get('characters', [])]
    # IDs and text only: no local paths, credentials, raw media or signed URL creation.
    return {'project_id': project_id, 'production_id': production_id, 'series_id': series_id,
            'canon_revision': canon_revision, 'base_revision': revision, 'script': script,
            'characters': characters, 'vault_references': vault, 'file_references': files,
            'nodes': [{k: n[k] for k in ('id', 'parent_id', 'kind', 'title', 'notes')} for n in nodes]}


def current(db, body):
    value = context(db, body['project_id'], body['production_id'], body['series_id'])
    if value['canon_revision'] != body['canon_revision'] or value['base_revision'] != body['base_revision']:
        raise HTTPException(409, 'Context revision changed; create a new reviewed request')
    nodes = {n['id']: n for n in value['nodes']}
    scene, shot = body['scene_id'], body['shot_id']
    if scene and (scene not in nodes or nodes[scene]['kind'] != 'episode' or nodes[scene]['parent_id'] != body['series_id']):
        raise HTTPException(404, 'Scene is outside this series')
    if shot and (not scene or shot not in nodes or nodes[shot]['kind'] != 'frame' or nodes[shot]['parent_id'] != scene):
        raise HTTPException(404, 'Shot is outside this scene')
    for asset_id in body['reference_asset_ids']:
        if not db.execute('SELECT 1 FROM library_assets WHERE id=? AND project_id=?', (asset_id, body['project_id'])).fetchone():
            raise HTTPException(404, 'Reference is outside this project')
    return value


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def view(db, row):
    return {'task_id': row['id'], 'agent_run_id': row['id'], 'status': row['status'],
            'approval_state': row['status'] if row['status'] in {'approved', 'rejected'} else 'pending',
            'execution_id': row['execution_id'], 'request': json.loads(row['request']),
            'result_ref': ('automation:' + row['id']) if row['result'] else None,
            'result': json.loads(row['result']) if row['result'] else None,
            'events': [dict(r) for r in db.execute('SELECT event_id,status,created_at FROM automation_events WHERE task_id=? ORDER BY rowid', (row['id'],))]}


def register(app, studio):
    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS automation_jobs(
                id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),
                idempotency_key TEXT NOT NULL,request TEXT NOT NULL,status TEXT NOT NULL,
                execution_id TEXT,result TEXT,created_at TEXT NOT NULL,
                UNIQUE(project_id,idempotency_key))''')
            db.execute('''CREATE TABLE IF NOT EXISTS automation_events(
                task_id TEXT NOT NULL REFERENCES automation_jobs(id),event_id TEXT NOT NULL,
                status TEXT NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,
                PRIMARY KEY(task_id,event_id))''')

    router = APIRouter(prefix=PREFIX)

    def event(db, task_id, event_id, status, payload=''):
        db.execute('INSERT INTO automation_events VALUES(?,?,?,?,?)', (task_id, event_id, status, payload, studio.now()))

    @router.get('/contexts/{project_id}/{production_id}/{series_id}')
    def get_context(project_id: str, production_id: str, series_id: str, request: Request):
        if request.headers.get('authorization'):
            if project_id != service_project(request):
                raise HTTPException(404, 'Context not found')
        else:
            owner(request)
        with studio.connect() as db:
            return context(db, project_id, production_id, series_id)

    @router.post('/jobs', dependencies=[Depends(owner)])
    def create(body: Job):
        payload = body.model_dump()
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM automation_jobs WHERE project_id=? AND idempotency_key=?', (body.project_id, body.idempotency_key)).fetchone()
            if old:
                if old['request'] != encoded(payload):
                    raise HTTPException(409, 'Idempotency key already used with different input')
                return view(db, old)
            current(db, payload)
            task_id = uuid.uuid4().hex
            db.execute('INSERT INTO automation_jobs VALUES(?,?,?,?,?,?,?,?)', (task_id, body.project_id, body.idempotency_key, encoded(payload), 'queued', None, None, studio.now()))
            event(db, task_id, 'created', 'queued')
            return view(db, db.execute('SELECT * FROM automation_jobs WHERE id=?', (task_id,)).fetchone())

    @router.get('/jobs')
    def pending(allowed: str = Depends(service_project)):
        with studio.connect() as db:
            return {'task_ids': [r['id'] for r in db.execute("SELECT id FROM automation_jobs WHERE project_id=? AND status='queued' ORDER BY created_at,id LIMIT 100", (allowed,))]}

    @router.get('/jobs/{task_id}')
    def get_job(task_id: str, request: Request):
        with studio.connect() as db:
            row = db.execute('SELECT * FROM automation_jobs WHERE id=?', (task_id,)).fetchone()
            if request.headers.get('authorization'):
                scoped(row, service_project(request))
            else:
                owner(request)
                if not row:
                    raise HTTPException(404, 'Automation job not found')
            return view(db, row)

    @router.post('/jobs/{task_id}/claim')
    def claim(task_id: str, body: Claim, allowed: str = Depends(service_project)):
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = scoped(db.execute('SELECT * FROM automation_jobs WHERE id=?', (task_id,)).fetchone(), allowed)
            if row['status'] == 'running' and row['execution_id'] == body.execution_id:
                return view(db, row)
            if row['status'] != 'queued':
                raise HTTPException(409, 'Job already claimed or terminal')
            current(db, json.loads(row['request']))
            db.execute("UPDATE automation_jobs SET status='running',execution_id=? WHERE id=?", (body.execution_id, task_id))
            event(db, task_id, 'claimed', 'running')
            return view(db, db.execute('SELECT * FROM automation_jobs WHERE id=?', (task_id,)).fetchone())

    @router.post('/callbacks')
    def callback(body: Callback, allowed: str = Depends(service_project)):
        payload = encoded(body.model_dump())
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = scoped(db.execute('SELECT * FROM automation_jobs WHERE id=?', (body.task_id,)).fetchone(), allowed)
            previous = db.execute('SELECT payload FROM automation_events WHERE task_id=? AND event_id=?', (body.task_id, body.event_id)).fetchone()
            if previous:
                if previous['payload'] != payload:
                    raise HTTPException(409, 'Event ID already used')
                return view(db, row)
            if row['status'] != 'running' or row['execution_id'] != body.execution_id:
                raise HTTPException(409, 'Callback does not match the active execution')
            if body.status == 'review_required':
                if not body.proposal.strip() or body.error_code:
                    raise HTTPException(400, 'A successful callback requires a proposal without an error')
                current(db, json.loads(row['request']))
            elif not body.error_code or body.proposal:
                raise HTTPException(400, 'A failed callback requires an error code without a proposal')
            db.execute('UPDATE automation_jobs SET status=?,result=? WHERE id=?', (body.status, payload, body.task_id))
            event(db, body.task_id, body.event_id, body.status, payload)
            return view(db, db.execute('SELECT * FROM automation_jobs WHERE id=?', (body.task_id,)).fetchone())

    @router.post('/jobs/{task_id}/cancel', dependencies=[Depends(owner)])
    def cancel(task_id: str):
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM automation_jobs WHERE id=?', (task_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Automation job not found')
            if row['status'] == 'cancelled':
                return view(db, row)
            if row['status'] not in {'queued', 'running', 'review_required'}:
                raise HTTPException(409, 'Terminal job cannot be cancelled')
            db.execute("UPDATE automation_jobs SET status='cancelled' WHERE id=?", (task_id,))
            event(db, task_id, 'cancelled', 'cancelled')
            return view(db, db.execute('SELECT * FROM automation_jobs WHERE id=?', (task_id,)).fetchone())

    @router.post('/jobs/{task_id}/review', dependencies=[Depends(owner)])
    def review(task_id: str, body: Review):
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM automation_jobs WHERE id=?', (task_id,)).fetchone()
            if not row:
                raise HTTPException(404, 'Automation job not found')
            if row['status'] == body.decision:
                return view(db, row)
            if row['status'] != 'review_required':
                raise HTTPException(409, 'Job is not awaiting review')
            if body.decision == 'approved':
                current(db, json.loads(row['request']))
            db.execute('UPDATE automation_jobs SET status=? WHERE id=?', (body.decision, task_id))
            event(db, task_id, 'reviewed', body.decision)
            return view(db, db.execute('SELECT * FROM automation_jobs WHERE id=?', (task_id,)).fetchone())

    app.include_router(router)
