"""QA-контур приёмки: серверная проверка вердиктов, версии артефакта и границы доказательств.

Правила (integrations/n8n/QA_EVIDENCE_POLICY.md, утверждено владельцем 19.10.2026):

- вердикт привязан к ревизии артефакта; результат старой ревизии не переносится на новую;
- PASS по области выдаётся только если сервер знает доверенный источник для этой области
  и доказательство ссылается ровно на него;
- флаги из полезной нагрузки модели (verified_evidence_by_backend, approved_expert_model,
  quality_claim, all_passed) игнорируются: итог считает сервер;
- TEXT не повышает IMAGE/VIDEO/AUDIO; без подключённого media inspector медиа-области
  остаются BLOCKED, а не PASS;
- успешная проверка не публикует ролик: финальное решение остаётся за владельцем.

Ревизии считает сервер (sha256 от содержимого), поэтому вызывающий не может объявить
канон, которого сервер не выдавал критику."""
import hashlib
import json
import uuid

from fastapi import HTTPException, Request
from pydantic import BaseModel, Field

SCOPES = ('TEXT', 'IMAGE', 'VIDEO', 'AUDIO')
EVIDENCE_TYPES = {
    'TEXT': ('text_quote', 'transcript_quote'),
    'IMAGE': ('image_observation',),
    'VIDEO': ('video_frame', 'video_segment'),
    'AUDIO': ('audio_observation',),
}
PHASES = ('TEXT_PRECHECK', 'FINAL_MEDIA')
ROLES = ('REVIEW-REQ', 'REVIEW-SYSTEM', 'REVIEW-CRAFT')
PHASE_ROLES = {'TEXT_PRECHECK': ('REVIEW-REQ', 'REVIEW-SYSTEM'), 'FINAL_MEDIA': ROLES}
PHASE_SCOPES = {'TEXT_PRECHECK': ('TEXT',), 'FINAL_MEDIA': SCOPES}
VERDICTS = ('PASS', 'FAIL', 'BLOCKED')


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


class ReviewCreate(BaseModel):
    project_id: str
    task_id: str
    artifact_id: str
    artifact_revision: str
    artifact_text: str = ''
    canon_text: str = ''
    brief_text: str = ''
    review_phase: str = 'TEXT_PRECHECK'
    requested_scopes: list[str] = Field(default_factory=lambda: ['TEXT'])
    required_reviewers: list[str] = Field(default_factory=list)
    review_round: int = Field(default=1, ge=1, le=99)
    request_id: str = Field(min_length=8, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')


class VerdictIn(BaseModel):
    role: str
    verdict: str
    artifact_revision: str
    model: str | None = None
    checked_scopes: list[str] = Field(default_factory=list)
    scope_results: dict[str, str] = Field(default_factory=dict)
    evidence: list[dict] = Field(default_factory=list)
    biggest_gap: str | None = None
    missing_inputs: list[str] = Field(default_factory=list)
    model_used: str | None = None
    actual_usd: float | None = Field(default=None, ge=0, le=1000, allow_inf_nan=False)


def trusted_sources(review, scope):
    """Доверенные источники для области: только то, что сервер сам выдал критику."""
    if scope == 'TEXT':
        sources = []
        if review['artifact_sha']:
            sources.append(review['artifact_sha'])
        if review['canon_sha']:
            sources.append(review['canon_sha'])
        if review['brief_sha']:
            sources.append(review['brief_sha'])
        return sources
    # Медиа-источники появятся вместе с media inspector. До него область не подтверждена.
    return []


def _evidence_matches(evidence, scope, sources):
    for item in evidence:
        if not isinstance(item, dict) or item.get('scope') != scope:
            continue
        if item.get('evidence_type') not in EVIDENCE_TYPES[scope]:
            continue
        for key in ('source_asset_id', 'source_text_revision'):
            value = item.get(key)
            if isinstance(value, str) and value and value in sources:
                return item
    return None


def verify_scopes(review, body):
    """Пересчитывает вердикт по областям. Возвращает (scope_results, notes, trusted_evidence)."""
    results, notes, trusted = {}, [], []
    for scope in review['requested']:
        claimed = body.scope_results.get(scope)
        sources = trusted_sources(review, scope)
        match = _evidence_matches(body.evidence, scope, sources)
        if scope not in body.checked_scopes or claimed not in VERDICTS:
            results[scope] = 'BLOCKED'
            notes.append(f'{scope}: область не проверена критиком')
            continue
        if not sources:
            results[scope] = 'BLOCKED'
            notes.append(f'{scope}: у сервера нет доверенного источника для области (media inspector не подключён)')
            continue
        if claimed in ('PASS', 'FAIL') and not match:
            results[scope] = 'BLOCKED'
            notes.append(f'{scope}: доказательство не ссылается на доверенный источник сервера')
            continue
        results[scope] = claimed
        if match:
            trusted.append(match)
    return results, notes, trusted


def overall_of(results):
    if any(value == 'FAIL' for value in results.values()):
        return 'FAIL'
    if any(value == 'BLOCKED' for value in results.values()):
        return 'BLOCKED'
    return 'PASS'


def review_status(review, verdicts):
    """Итог по собранным вердиктам. Решение о выпуске не принимается."""
    required = review['required_reviewers']
    submitted = {v['role'] for v in verdicts}
    missing = [role for role in required if role not in submitted]
    if missing:
        return {'status': 'AWAITING_VERDICTS', 'missing_reviewers': missing,
                'next_action': 'wait_for_remaining_critics; do not dispatch paid models'}
    overall = {v['role']: v['overall'] for v in verdicts}
    if any(value == 'FAIL' for value in overall.values()):
        return {'status': 'CHANGES_REQUESTED', 'missing_reviewers': [],
                'next_action': 'return_evidenced_gap_to_original_builder'}
    if any(value == 'BLOCKED' for value in overall.values()):
        return {'status': 'BLOCKED', 'missing_reviewers': [],
                'next_action': 'missing evidence or tool: coverage is incomplete'}
    return {'status': 'TEXT_PRECHECK_PASSED_AWAITING_OWNER' if review['review_phase'] == 'TEXT_PRECHECK'
            else 'AWAITING_OWNER_APPROVAL', 'missing_reviewers': [],
            'next_action': 'wait_for_owner_approval'}


def _row_to_review(row):
    return {
        'review_id': row['review_id'],
        'project_id': row['project_id'],
        'task_id': row['task_id'],
        'artifact_id': row['artifact_id'],
        'artifact_revision': row['artifact_revision'],
        'artifact_sha': row['artifact_sha'],
        'canon_sha': row['canon_sha'],
        'brief_sha': row['brief_sha'],
        'review_phase': row['review_phase'],
        'review_round': row['review_round'],
        'requested': json.loads(row['requested_scopes']),
        'required_reviewers': json.loads(row['required_reviewers']),
        'status': row['status'],
        'created_at': row['created_at'],
    }


def register(app, studio):
    from backend import service_auth

    @app.on_event('startup')
    def setup():
        with studio.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS qa_reviews(review_id TEXT PRIMARY KEY,request_id TEXT UNIQUE,project_id TEXT NOT NULL,
                task_id TEXT NOT NULL,artifact_id TEXT NOT NULL,artifact_revision TEXT NOT NULL,artifact_sha TEXT,canon_sha TEXT,brief_sha TEXT,
                review_phase TEXT NOT NULL,requested_scopes TEXT NOT NULL,required_reviewers TEXT NOT NULL,review_round INTEGER NOT NULL DEFAULT 1,
                artifact_text TEXT,canon_text TEXT,brief_text TEXT,status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS qa_verdicts(verdict_id TEXT PRIMARY KEY,review_id TEXT NOT NULL,role TEXT NOT NULL,model TEXT,
                verdict TEXT NOT NULL,artifact_revision TEXT NOT NULL,checked_scopes TEXT NOT NULL,claimed_scope_results TEXT NOT NULL,scope_results TEXT NOT NULL,evidence TEXT NOT NULL,
                trusted_evidence TEXT NOT NULL,biggest_gap TEXT,missing_inputs TEXT NOT NULL,model_used TEXT,actual_usd REAL,notes TEXT NOT NULL,
                overall TEXT NOT NULL,received_at TEXT NOT NULL,UNIQUE(review_id,role))''')

    def load(db, review_id):
        row = db.execute('SELECT * FROM qa_reviews WHERE review_id=?', (review_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Ревью не найдено')
        return row

    @app.post('/api/qa/reviews')
    def create_review(body: ReviewCreate, request: Request):
        """Создать ревью. Ревизии считает сервер от содержимого, а не берёт на веру."""
        service_auth.require_project(request, body.project_id)
        with studio.connect() as db:
            existing = db.execute('SELECT * FROM qa_reviews WHERE request_id=?', (body.request_id,)).fetchone()
        if existing:
            return {'review': _row_to_review(existing), 'duplicate': True}
        if body.review_phase not in PHASES:
            raise HTTPException(400, 'Неизвестная фаза ревью')
        scopes = [scope for scope in body.requested_scopes]
        if not scopes or len(set(scopes)) != len(scopes) or any(scope not in SCOPES for scope in scopes):
            raise HTTPException(400, 'Некорректный список областей проверки')
        allowed_scopes = PHASE_SCOPES[body.review_phase]
        if any(scope not in allowed_scopes for scope in scopes):
            raise HTTPException(400, f'В фазе {body.review_phase} нельзя запрашивать области кроме {", ".join(allowed_scopes)}')
        reviewers = body.required_reviewers or list(PHASE_ROLES[body.review_phase])
        if len(set(reviewers)) != len(reviewers) or any(role not in ROLES for role in reviewers):
            raise HTTPException(400, 'Некорректный набор критиков')
        if not set(reviewers).issubset(PHASE_ROLES[body.review_phase]):
            raise HTTPException(400, f'В фазе {body.review_phase} требуются критики {", ".join(PHASE_ROLES[body.review_phase])}')
        review_id = uuid.uuid4().hex
        now = studio.now()
        with studio.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''INSERT INTO qa_reviews(review_id,request_id,project_id,task_id,artifact_id,artifact_revision,artifact_sha,canon_sha,brief_sha,
                review_phase,requested_scopes,required_reviewers,review_round,artifact_text,canon_text,brief_text,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                       (review_id, body.request_id, body.project_id, body.task_id, body.artifact_id, body.artifact_revision,
                        sha(body.artifact_text) if body.artifact_text else '', sha(body.canon_text) if body.canon_text else '',
                        sha(body.brief_text) if body.brief_text else '', body.review_phase, json.dumps(scopes), json.dumps(reviewers),
                        body.review_round, body.artifact_text, body.canon_text, body.brief_text, 'AWAITING_VERDICTS', now, now))
        with studio.connect() as db:
            row = load(db, review_id)
        return {'review': _row_to_review(row), 'duplicate': False,
                'next_action': 'dispatch_isolated_packets_to_reviewers'}

    @app.get('/api/qa/reviews/{review_id}')
    def get_review(review_id: str, request: Request):
        service_auth.require_token(request)
        with studio.connect() as db:
            row = load(db, review_id)
            service_auth.require_project(request, row['project_id'])
            verdicts = db.execute('SELECT * FROM qa_verdicts WHERE review_id=? ORDER BY role', (review_id,)).fetchall()
            review = _row_to_review(row)
        collected = [dict(v) for v in verdicts]
        state = review_status(review, [{'role': v['role'], 'overall': v['overall']} for v in collected])
        return {'review': review, **state, 'verdicts': [_verdict_view(v) for v in collected]}

    @app.get('/api/qa/reviews/{review_id}/packet/{role}')
    def packet(review_id: str, role: str, request: Request):
        """Изолированный пакет для одного критика: без чужих вердиктов и истории."""
        service_auth.require_token(request)
        with studio.connect() as db:
            row = load(db, review_id)
            service_auth.require_project(request, row['project_id'])
        review = _row_to_review(row)
        if role not in review['required_reviewers']:
            raise HTTPException(403, 'Этот критик не участвует в ревью')
        payload = {
            'review_id': review['review_id'],
            'task_id': review['task_id'],
            'artifact_id': review['artifact_id'],
            'artifact_revision': review['artifact_revision'],
            'review_phase': review['review_phase'],
            'review_round': review['review_round'],
            'requested_scopes': review['requested'],
            'role': role,
            'artifact_text': row['artifact_text'],
            'canon_text': row['canon_text'],
            'brief_text': row['brief_text'],
            'trusted_revisions': {'artifact_sha': review['artifact_sha'], 'canon_sha': review['canon_sha'],
                                  'brief_sha': review['brief_sha']},
        }
        return payload

    @app.post('/api/qa/reviews/{review_id}/verdicts')
    def submit_verdict(review_id: str, body: VerdictIn, request: Request):
        """Приём вердикта: сервер перепроверяет и пересчитывает итог сам."""
        service_auth.require_token(request)
        with studio.connect() as db:
            row = load(db, review_id)
            service_auth.require_project(request, row['project_id'])
            review = _row_to_review(row)
            if body.artifact_revision != review['artifact_revision']:
                raise HTTPException(409, 'Ревензия артефакта устарела: вердикт относится к другой версии')
            if body.role not in review['required_reviewers']:
                raise HTTPException(403, 'Этот критик не участвует в ревью')
            if body.verdict not in VERDICTS:
                raise HTTPException(400, 'Вердикт должен быть PASS, FAIL или BLOCKED')
            duplicate = db.execute('SELECT * FROM qa_verdicts WHERE review_id=? AND role=?', (review_id, body.role)).fetchone()
            if duplicate:
                same = (duplicate['verdict'] == body.verdict
                        and json.loads(duplicate['checked_scopes']) == body.checked_scopes
                        and json.loads(duplicate['claimed_scope_results']) == body.scope_results)
                if same:
                    return {'verdict': _verdict_view(duplicate), 'duplicate': True}
                raise HTTPException(409, 'Вердикт этого критика уже принят и не совпадает с новым')
            results, notes, trusted = verify_scopes(review, body)
            overall = overall_of(results)
            verdict_id = uuid.uuid4().hex
            db.execute('INSERT INTO qa_verdicts(verdict_id,review_id,role,model,verdict,artifact_revision,checked_scopes,claimed_scope_results,scope_results,evidence,'
                       'trusted_evidence,biggest_gap,missing_inputs,model_used,actual_usd,notes,overall,received_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (verdict_id, review_id, body.role, body.model, body.verdict, body.artifact_revision, json.dumps(body.checked_scopes),
                        json.dumps(body.scope_results), json.dumps(results), json.dumps(body.evidence, ensure_ascii=False), json.dumps(trusted, ensure_ascii=False),
                        body.biggest_gap, json.dumps(body.missing_inputs), body.model_used, body.actual_usd, json.dumps(notes, ensure_ascii=False),
                        overall, studio.now()))
            verdicts = db.execute('SELECT * FROM qa_verdicts WHERE review_id=? ORDER BY role', (review_id,)).fetchall()
            state = review_status(review, [{'role': v['role'], 'overall': v['overall']} for v in verdicts])
            db.execute('UPDATE qa_reviews SET status=?,updated_at=? WHERE review_id=?', (state['status'], studio.now(), review_id))
            row = load(db, review_id)
        receipt = {'verified': True, 'review_id': review_id, 'artifact_revision': review['artifact_revision'],
                   'verdict_id': verdict_id, 'role': body.role, 'scope_results': results, 'overall': overall}
        return {'verdict': {'verdict_id': verdict_id, 'role': body.role, 'overall': overall, 'scope_results': results, 'notes': notes},
                'server_receipt': receipt, 'review_status': state['status'], 'next_action': state['next_action'], 'duplicate': False}


def _verdict_view(row):
    return {
        'verdict_id': row['verdict_id'],
        'role': row['role'],
        'model': row['model'],
        'verdict': row['verdict'],
        'overall': row['overall'],
        'artifact_revision': row['artifact_revision'],
        'checked_scopes': json.loads(row['checked_scopes']),
        'scope_results': json.loads(row['scope_results']),
        'evidence': json.loads(row['evidence']),
        'trusted_evidence': json.loads(row['trusted_evidence']),
        'biggest_gap': row['biggest_gap'],
        'missing_inputs': json.loads(row['missing_inputs']),
        'model_used': row['model_used'],
        'actual_usd': row['actual_usd'],
        'notes': json.loads(row['notes']),
        'received_at': row['received_at'],
    }
