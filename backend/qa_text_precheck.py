"""Sandbox-only TEXT_PRECHECK. No LLM, media, billing or canonical mutations.

Source snapshots are built from saved storyboard, story plan and project identity.
An authenticated owner explicitly approves a snapshot. Mock reviewer observations
can validate the transport but NEVER establish production-quality PASS.
"""
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Literal, Annotated

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from backend import storyboard

PREFIX = '/api/v1/qa/text'
ROLES = ('REVIEW-REQ', 'REVIEW-SYSTEM')
ROLE_MODELS = {'REVIEW-REQ': 'mock-a6-v1', 'REVIEW-SYSTEM': 'mock-a7-v1'}


def stable(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def sha(value):
    return hashlib.sha256(stable(value).encode('utf-8')).hexdigest()


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ApproveSources(Strict):
    project_id: str = Field(min_length=1, max_length=100)
    production_id: str = Field(min_length=1, max_length=100)
    series_id: str = Field(min_length=1, max_length=100)
    artifact_revision: str = Field(pattern=r'^[0-9a-f]{64}$')
    brief_revision: str = Field(pattern=r'^[0-9a-f]{64}$')
    canon_revision: str = Field(pattern=r'^[0-9a-f]{64}$')
    confirm_source_approval: Literal[True]


class CreateReview(Strict):
    approval_id: str = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=100)
    review_phase: Literal['TEXT_PRECHECK'] = 'TEXT_PRECHECK'
    requested_scopes: tuple[Literal['TEXT']] = ('TEXT',)


class Claim(Strict):
    execution_id: str = Field(min_length=1, max_length=100)


class Block(Strict):
    execution_id: str = Field(min_length=1, max_length=100)
    error_code: Literal['REVIEWER_UNAVAILABLE', 'MOCK_ENGINE_ERROR', 'STOPPED_BY_OPERATOR']


class Evidence(Strict):
    scope: Literal['TEXT']
    evidence_type: Literal['text_quote']
    source_text_revision: str = Field(pattern=r'^[0-9a-f]{64}$')
    observation: str = Field(min_length=1, max_length=2000)
    quote: str = Field(min_length=1, max_length=2000)
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    source_kind: Literal['artifact', 'requirements', 'canon']


class Verdict(Strict):
    role: Literal['REVIEW-REQ', 'REVIEW-SYSTEM']
    task_id: str = Field(min_length=1, max_length=100)
    project_id: str = Field(min_length=1, max_length=100)
    artifact_id: str = Field(min_length=1, max_length=100)
    artifact_revision: str = Field(pattern=r'^[0-9a-f]{64}$')
    review_round: Literal[1] = 1
    requested_scopes: tuple[Literal['TEXT']] = ('TEXT',)
    checked_scopes: list[Literal['TEXT']] = Field(max_length=1)
    scope_results: dict[Literal['TEXT'], Literal['PASS', 'FAIL', 'BLOCKED']] = Field(max_length=1)
    verdict: Literal['PASS', 'FAIL', 'BLOCKED']
    evidence: list[Evidence] = Field(default_factory=list, max_length=20)
    missing_inputs: list[Annotated[str, Field(min_length=1, max_length=256)]] = Field(default_factory=list, max_length=20)
    biggest_gap: str | None = Field(default=None, max_length=1500)
    model_used: Literal['mock-a6-v1', 'mock-a7-v1']
    estimated_cost_usd: Literal[0] = 0
    actual_cost_usd: Literal[0] = 0
    event_id: str = Field(min_length=8, max_length=100)
    execution_id: str = Field(min_length=1, max_length=100)


def owner(request):
    from backend import security
    token = request.headers.get('x-studio-session') or request.cookies.get('studio_session', '')
    # Bearer service credentials cannot create approvals, even if browser cookie supplied.
    if request.headers.get('authorization') or not hmac.compare_digest(token.encode('utf-8'), security.LAUNCH_TOKEN.encode('utf-8')):
        raise HTTPException(401, 'Authenticated Studio owner required')


def service(request):
    secret = os.environ.get('STUDIO_QA_SANDBOX_TOKEN', '')
    project_id = os.environ.get('STUDIO_QA_SANDBOX_PROJECT_ID', '')
    if len(secret) < 32 or not project_id:
        raise HTTPException(503, 'QA sandbox service is not configured')
    supplied = request.headers.get('authorization', '')
    if not hmac.compare_digest(supplied.encode('utf-8'), ('Bearer ' + secret).encode('utf-8')):
        raise HTTPException(401, 'Invalid QA sandbox credential')
    # Forbid any remote caller, even if a web deployment changes middleware.
    # Live n8n cannot connect until separate HTTPS service-gate review.
    from backend import remote_access
    if not remote_access.is_loopback(request):
        raise HTTPException(403, 'QA sandbox service is loopback-only')
    return project_id


def record(db, table, key):
    row = db.execute(f'SELECT * FROM {table} WHERE id=?', (key,)).fetchone()
    if row is None:
        raise HTTPException(404, 'QA record not found')
    return dict(row)


def context(db, project_id, production_id, series_id):
    project = db.execute('SELECT state,revision FROM projects WHERE id=?', (project_id,)).fetchone()
    prod = db.execute('SELECT 1 FROM productions WHERE id=? AND source_project_id=?',
                      (production_id, project_id)).fetchone()
    if not project or not prod:
        raise HTTPException(404, 'Project or production not found')
    # storyboard.snapshot's third value is the historical import, NOT the current edited scenes.
    parent, nodes, _historical_import, board_revision = storyboard.snapshot(db, production_id, series_id)
    episodes = sorted((n for n in nodes if n['kind'] == 'episode'),
                      key=lambda n: (n['number'], n['id']))
    frames_by_scene = {}
    for frame in (n for n in nodes if n['kind'] == 'frame'):
        frames_by_scene.setdefault(frame['parent_id'], []).append(frame)
    parts = []
    contains_actual_notes = False

    def append_node(kind, node):
        nonlocal contains_actual_notes
        notes = (node.get('notes') or '').strip()
        contains_actual_notes |= bool(notes)
        parts.append(f"{kind} [id={node['id']}] {node.get('title', '')}\\n{notes}".strip())

    append_node('Серия', parent)
    for scene in episodes:
        append_node('Сцена', scene)
        for frame in sorted(frames_by_scene.get(scene['id'], []),
                            key=lambda n: (n['number'], n['id'])):
            append_node('Кадр', frame)
    text = '\\n\\n'.join(parts)
    artifact_revision = sha([board_revision, text])
    plan = db.execute('SELECT revision,data FROM story_plans WHERE series_id=?', (series_id,)).fetchone()
    if not contains_actual_notes or not plan:
        raise HTTPException(409, 'BLOCKED_MISSING_APPROVED_SOURCE: current scene notes or story plan absent')
    parsed = json.loads(plan['data'])
    if not isinstance(parsed, dict):
        raise HTTPException(409, 'BLOCKED_INVALID_STORY_PLAN')
    from backend.story_plan import Card
    from pydantic import ValidationError
    try:
        cards = [Card.model_validate(item) for item in parsed.get('cards', [])]
    except (ValidationError, TypeError):
        raise HTTPException(409, 'BLOCKED_INVALID_STORY_PLAN')
    source = str(parsed.get('source') or '').strip()
    source_kind = str(parsed.get('source_kind') or 'idea')
    requirements = [f'Исходный замысел ({source_kind}): {source}'] if source else []
    for i, card in enumerate(cards, 1):
        requirements.append('\\n'.join([
            f'Карточка {i} [id={card.id}]: {card.title}',
            f'summary: {card.summary}',
            f'change: {card.change}',
            f'stage: {card.stage}',
            f'scene_id: {card.scene_id or ""}',
            f'character_ids: {stable(card.character_ids)}',
            f'location_id: {card.location_id or ""}',
        ]))
    requirements = [item for item in requirements if item.strip()]
    state = json.loads(project['state'])
    canon = []
    for char in state.get('characters', []):
        if not isinstance(char, dict) or not char.get('identity'):
            continue
        canon.append(str(char.get('name') or char.get('id')) + ': ' + stable(char['identity']))
    if not requirements or not canon:
        raise HTTPException(409, 'BLOCKED_MISSING_APPROVED_SOURCE: requirements or text canon absent')
    vault = [dict(row) for row in db.execute('SELECT id,character_id,category,model_id,note,created_at FROM character_assets WHERE project_id=? ORDER BY id', (project_id,))]
    snapshot = {'project_id': project_id, 'production_id': production_id,
                'series_id': series_id, 'artifact_id': series_id,
                'artifact_revision': artifact_revision, 'artifact_text': text,
                'requirements': '\n'.join(requirements), 'canon': '\n'.join(canon),
                'brief_revision': sha([plan['revision'], parsed, requirements]),
                'canon_revision': sha([project['revision'], canon, vault]),
                'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                'source_provenance': {'artifact': 'production_nodes.current_notes',
                                      'requirements': 'story_plans',
                                      'canon': 'projects.state.characters[].identity',
                                      'canon_images_reviewed': False}}
    if any(len(snapshot[k]) > 150000 for k in ('artifact_text', 'requirements', 'canon')):
        raise HTTPException(422, 'QA text snapshot is too large')
    return snapshot


def is_current(db, approval):
    snap = context(db, approval['project_id'], approval['production_id'], approval['series_id'])
    frozen = json.loads(approval['snapshot'])
    for key in ('artifact_revision', 'brief_revision', 'canon_revision', 'text_sha256'):
        if frozen[key] != snap[key]:
            raise HTTPException(409, 'STALE_REVISION: source changed; approve a new snapshot')
    return frozen


def role_package(snapshot, job, role):
    common = {'task_id': job['id'], 'project_id': job['project_id'],
              'artifact_id': snapshot['artifact_id'], 'artifact_revision': snapshot['artifact_revision'],
              'review_round': 1, 'review_phase': 'TEXT_PRECHECK', 'requested_scopes': ['TEXT'],
              'artifact_text': snapshot['artifact_text'], 'text_sha256': snapshot['text_sha256'],
              'model': ROLE_MODELS[role], 'mock_only': True, 'quality_claim': False,
              'source_provenance': snapshot['source_provenance']}
    if role == 'REVIEW-REQ':
        return {**common, 'role': role, 'approved_requirements': snapshot['requirements'],
                'brief_revision': snapshot['brief_revision']}
    return {**common, 'role': role, 'approved_canon': snapshot['canon'],
            'canon_revision': snapshot['canon_revision']}


def verify_verdict(snapshot, job, body):
    if (body.task_id != job['id'] or body.project_id != job['project_id']
            or body.artifact_id != snapshot['artifact_id']
            or body.artifact_revision != snapshot['artifact_revision']
            or body.model_used != ROLE_MODELS[body.role]):
        raise HTTPException(409, 'Reviewer identity or frozen revision mismatch')
    if body.checked_scopes not in ([], ['TEXT']) or set(body.scope_results) != {'TEXT'}:
        raise HTTPException(422, 'Only TEXT scope is supported')
    status = body.scope_results['TEXT']
    if body.verdict != status or (status == 'BLOCKED' and body.checked_scopes):
        raise HTTPException(422, 'Scope and verdict inconsistent')
    if status in ('PASS', 'FAIL') and body.checked_scopes != ['TEXT']:
        raise HTTPException(422, 'Checked TEXT scope required')
    if status == 'PASS' and (not body.evidence or body.missing_inputs):
        raise HTTPException(422, 'PASS requires evidence and no missing inputs')
    if status == 'FAIL' and (not body.evidence or not body.biggest_gap):
        raise HTTPException(422, 'FAIL requires a citation and biggest_gap')
    if status == 'BLOCKED' and (not body.missing_inputs or body.evidence):
        raise HTTPException(422, 'BLOCKED requires missing inputs, not fabricated evidence')
    kind = 'requirements' if body.role == 'REVIEW-REQ' else 'canon'
    seen_artifact = False
    for ev in body.evidence:
        if ev.source_kind not in ('artifact', kind):
            raise HTTPException(422, 'Evidence from another reviewer is forbidden')
        source = snapshot['artifact_text'] if ev.source_kind == 'artifact' else snapshot[kind]
        revision = snapshot['text_sha256'] if ev.source_kind == 'artifact' else snapshot['brief_revision' if kind == 'requirements' else 'canon_revision']
        if ev.source_text_revision != revision or ev.end > len(source) or source[ev.start:ev.end] != ev.quote:
            raise HTTPException(422, 'Evidence text locator not verified by FastAPI')
        seen_artifact |= ev.source_kind == 'artifact'
    if status in ('PASS', 'FAIL') and not seen_artifact:
        raise HTTPException(422, 'An observation of the actual artifact is required')


def view(db, job):
    approval = record(db, 'qa_text_approvals', job['approval_id'])
    frozen = json.loads(approval['snapshot'])
    try:
        is_current(db, approval)
        source_current, source_issue = True, None
    except HTTPException as exc:
        if exc.status_code not in (404, 409):
            raise
        source_current, source_issue = False, str(exc.detail)
    reviews = [json.loads(r['body']) for r in db.execute('SELECT body FROM qa_text_verdicts WHERE job_id=? ORDER BY role', (job['id'],))]
    return {'task_id': job['id'], 'project_id': job['project_id'], 'status': job['status'],
            'approval_id': job['approval_id'],
            'source_revisions': {key: frozen[key] for key in
                                 ('artifact_revision', 'brief_revision', 'canon_revision', 'text_sha256')},
            'source_current': source_current, 'source_issue': source_issue,
            'historical_review': not source_current,
            'error_code': job['error_code'],
            'review_phase': 'TEXT_PRECHECK', 'requested_scopes': ['TEXT'],
            'required_reviewers': list(ROLES), 'review_round': 1,
            'verdicts': reviews, 'text_precheck_passed': False,
            'sandbox_mock_passed': (source_current and
                                    job['status'] == 'SANDBOX_TEXT_PRECHECK_PASSED_AWAITING_OWNER'),
            'all_passed': False, 'final_release_approved': False, 'quality_claim': False,
            'paid_calls_executed': False, 'owner_approval_required': True}


def register(app, studio):
    # Bound the request body at the HTTP boundary, even for malformed JSON or chunked clients.
    @app.middleware('http')
    async def qa_callback_size_limit(request: Request, call_next):
        if request.url.path.startswith(PREFIX + '/service/jobs/') and request.url.path.endswith('/verdict'):
            from fastapi.responses import JSONResponse
            declared = request.headers.get('content-length')
            if declared and (not declared.isdigit() or int(declared) > 32768):
                return JSONResponse({'detail': 'QA verdict payload too large'}, status_code=413)
            chunks, size = [], 0
            async for part in request.stream():
                size += len(part)
                if size > 32768:
                    return JSONResponse({'detail': 'QA verdict payload too large'}, status_code=413)
                chunks.append(part)
            consumed = False
            async def replay():
                nonlocal consumed
                if not consumed:
                    consumed = True
                    return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
                return {'type': 'http.request', 'body': b'', 'more_body': False}
            request._receive = replay
        return await call_next(request)

    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS qa_text_approvals (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, production_id TEXT NOT NULL,
                series_id TEXT NOT NULL, snapshot TEXT NOT NULL, created_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS qa_text_jobs (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, approval_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL, execution_id TEXT,
                status TEXT NOT NULL, error_code TEXT, created_at TEXT NOT NULL,
                UNIQUE(project_id,idempotency_key))''')
            db.execute('''CREATE TABLE IF NOT EXISTS qa_text_verdicts (
                job_id TEXT NOT NULL,role TEXT NOT NULL,event_id TEXT NOT NULL,body TEXT NOT NULL,
                created_at TEXT NOT NULL, PRIMARY KEY(job_id,role), UNIQUE(job_id,event_id))''')

    @app.get(PREFIX + '/contexts/{project_id}/{production_id}/{series_id}')
    def preview(project_id: str, production_id: str, series_id: str, request: Request):
        owner(request)
        with studio.connect() as db:
            snap = context(db, project_id, production_id, series_id)
        return {**snap, 'approved': False, 'status': 'AWAITING_EXPLICIT_OWNER_APPROVAL'}

    @app.post(PREFIX + '/approvals')
    def approve(body: ApproveSources, request: Request):
        owner(request)
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            snap = context(db, body.project_id, body.production_id, body.series_id)
            for k in ('artifact_revision', 'brief_revision', 'canon_revision'):
                if snap[k] != getattr(body, k):
                    raise HTTPException(409, 'STALE_REVISION: cannot approve outdated context')
            approval_id = uuid.uuid4().hex
            db.execute('INSERT INTO qa_text_approvals VALUES(?,?,?,?,?,?)',
                       (approval_id, body.project_id, body.production_id, body.series_id, stable(snap), utcnow()))
        return {'approval_id': approval_id, 'approved': True, 'source_revisions':
                {k: snap[k] for k in ('artifact_revision', 'brief_revision', 'canon_revision')}}

    @app.post(PREFIX + '/jobs')
    def enqueue(body: CreateReview, request: Request):
        owner(request)
        normalized = body.model_dump()
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            approval = record(db, 'qa_text_approvals', body.approval_id)
            # Deterministic idempotency; never use an old key to enqueue new source.
            existing = db.execute('SELECT * FROM qa_text_jobs WHERE project_id=? AND idempotency_key=?',
                                  (approval['project_id'], body.idempotency_key)).fetchone()
            if existing:
                if existing['approval_id'] != body.approval_id:
                    raise HTTPException(409, 'Idempotency key reused for different approval')
                return view(db, dict(existing))
            is_current(db, approval)
            job_id = uuid.uuid4().hex
            db.execute('INSERT INTO qa_text_jobs VALUES(?,?,?,?,?,?,?,?)',
                       (job_id, approval['project_id'], body.approval_id, body.idempotency_key, None, 'queued', None, utcnow()))
            return view(db, record(db, 'qa_text_jobs', job_id))

    @app.get(PREFIX + '/jobs/{task_id}')
    def owner_status(task_id: str, request: Request):
        owner(request)
        with studio.connect() as db:
            return view(db, record(db, 'qa_text_jobs', task_id))

    @app.post(PREFIX + '/jobs/{task_id}/cancel')
    def cancel(task_id: str, request: Request):
        owner(request)
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            job = record(db, 'qa_text_jobs', task_id)
            if job['status'] not in ('queued', 'running', 'CANCELLED'):
                raise HTTPException(409, 'Completed review cannot be cancelled')
            if job['status'] != 'CANCELLED':
                db.execute('UPDATE qa_text_jobs SET status=? WHERE id=?', ('CANCELLED', task_id))
            return view(db, record(db, 'qa_text_jobs', task_id))

    @app.get(PREFIX + '/service/queue')
    def queue(request: Request):
        project_id = service(request)
        with studio.connect() as db:
            return {'task_ids': [row['id'] for row in db.execute(
                'SELECT id FROM qa_text_jobs WHERE project_id=? AND status=? ORDER BY created_at LIMIT 100',
                (project_id, 'queued'))]}

    @app.post(PREFIX + '/service/jobs/{task_id}/claim')
    def claim(task_id: str, body: Claim, request: Request):
        project_id = service(request)
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            job = record(db, 'qa_text_jobs', task_id)
            if job['project_id'] != project_id:
                raise HTTPException(404, 'QA job not found')
            if job['status'] == 'running' and job['execution_id'] == body.execution_id:
                return view(db, job)
            if job['status'] != 'queued':
                raise HTTPException(409, 'Job already claimed or finalized')
            is_current(db, record(db, 'qa_text_approvals', job['approval_id']))
            db.execute('UPDATE qa_text_jobs SET status=?,execution_id=? WHERE id=?',
                       ('running', body.execution_id, task_id))
            return view(db, record(db, 'qa_text_jobs', task_id))

    @app.get(PREFIX + '/service/jobs/{task_id}/packet/{role}')
    def packet(task_id: str, role: str, request: Request):
        project_id = service(request)
        if role not in ROLES:
            raise HTTPException(404, 'Reviewer not found')
        with studio.connect() as db:
            job = record(db, 'qa_text_jobs', task_id)
            if job['project_id'] != project_id:
                raise HTTPException(404, 'QA job not found')
            if job['status'] != 'running':
                raise HTTPException(409, 'Job has not been claimed')
            approval = record(db, 'qa_text_approvals', job['approval_id'])
            snapshot = is_current(db, approval)
            return role_package(snapshot, job, role)

    @app.post(PREFIX + '/service/jobs/{task_id}/block')
    def block(task_id: str, body: Block, request: Request):
        project_id = service(request)
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            job = record(db, 'qa_text_jobs', task_id)
            if job['project_id'] != project_id:
                raise HTTPException(404, 'QA job not found')
            if job['execution_id'] != body.execution_id:
                raise HTTPException(409, 'Wrong execution ID')
            if job['status'] == 'BLOCKED' and job['error_code'] == body.error_code:
                return view(db, job)
            if job['status'] != 'running':
                raise HTTPException(409, 'Review no longer running')
            db.execute('UPDATE qa_text_jobs SET status=?,error_code=? WHERE id=?',
                       ('BLOCKED', body.error_code, task_id))
            return view(db, record(db, 'qa_text_jobs', task_id))

    @app.post(PREFIX + '/service/jobs/{task_id}/verdict')
    def submit(task_id: str, body: Verdict, request: Request):
        project_id = service(request)
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            job = record(db, 'qa_text_jobs', task_id)
            if job['project_id'] != project_id:
                raise HTTPException(404, 'QA job not found')
            prior = db.execute('SELECT body FROM qa_text_verdicts WHERE job_id=? AND role=?',
                               (task_id, body.role)).fetchone()
            normalized = stable(body.model_dump())
            if prior:
                if prior['body'] != normalized:
                    raise HTTPException(409, 'Reviewer run already recorded with different payload')
                return view(db, job)
            if job['status'] != 'running' or job['execution_id'] != body.execution_id:
                raise HTTPException(409, 'Unclaimed, stale or foreign execution')
            approval = record(db, 'qa_text_approvals', job['approval_id'])
            snapshot = is_current(db, approval)
            verify_verdict(snapshot, job, body)
            event = db.execute('SELECT 1 FROM qa_text_verdicts WHERE job_id=? AND event_id=?',
                               (task_id, body.event_id)).fetchone()
            if event:
                raise HTTPException(409, 'Event ID already used for another reviewer')
            db.execute('INSERT INTO qa_text_verdicts VALUES(?,?,?,?,?)',
                       (task_id, body.role, body.event_id, normalized, utcnow()))
            reviews = [json.loads(row['body']) for row in db.execute(
                'SELECT body FROM qa_text_verdicts WHERE job_id=?', (task_id,))]
            if len(reviews) == 2:
                statuses = {x['verdict'] for x in reviews}
                final = ('CHANGES_REQUESTED' if 'FAIL' in statuses else
                         'BLOCKED' if 'BLOCKED' in statuses else
                         'SANDBOX_TEXT_PRECHECK_PASSED_AWAITING_OWNER')
                db.execute('UPDATE qa_text_jobs SET status=? WHERE id=?', (final, task_id))
            return view(db, record(db, 'qa_text_jobs', task_id))