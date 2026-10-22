"""GA-03 — release gate: imported → technical_pass → owner_approved | rejected.

Состояние вычисляется сервером из фактов при каждом чтении, клиент флагов не присылает.
Техническая часть берётся у существующих N34 (`media_qc.master_facts`) и N35
(`qa_reviews.freeze_media`); здесь они не дублируются. Сверх них gate добавляет
только привязку решения владельца к SHA-256 мастера и к хешу утверждённого содержимого.

Что это НЕ является. `owner_id` из запроса сверяется с `GREMOVOD_OWNER_ID` сервера:
это атрибуция решения, а не аутентификация человека. Локальная сессия студии общая на
процесс, машинный токен решение принять не может. Настоящий вход владельца (PIN/пароль)
— отдельное решение владельца: OWNER_AUTH_REQUIRED.
"""
import hashlib
import hmac
import json
import os
import uuid
from types import SimpleNamespace

from fastapi import HTTPException

from backend import media_qc, qa_reviews, service_auth

IMPORTED = 'IMPORTED'
TECHNICAL_PASS = 'TECHNICAL_PASS'
OWNER_APPROVED = 'OWNER_APPROVED'
REJECTED = 'REJECTED'
APPROVED_DECISION = 'APPROVED'
REJECTED_DECISION = 'REJECTED'
OWNER_ENV = 'GREMOVOD_OWNER_ID'

SCHEMA = '''CREATE TABLE IF NOT EXISTS release_decisions (
    decision_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES release_artifacts(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL,
    version_id TEXT,
    master_sha256 TEXT NOT NULL DEFAULT '',
    content_sha256 TEXT NOT NULL DEFAULT '',
    project_revision INTEGER NOT NULL,
    decision TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    processing_rights_confirmed INTEGER NOT NULL DEFAULT 0,
    qc_verdict TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
)'''
INDEX = 'CREATE INDEX IF NOT EXISTS release_decisions_artifact ON release_decisions(artifact_id,created_at DESC)'

MESSAGES = {
    'QC_NOT_RUN': 'Техническая проверка N34 ещё не проводилась.',
    'QC_NOT_PASSED': 'Техническая проверка N34 не пройдена.',
    'QC_STALE': 'Файл изменён после технической проверки: запустите проверку заново.',
    'MASTER_FILE_MISSING': 'Файл мастера отсутствует в библиотеке.',
    'MASTER_CHANGED': 'Файл на экране устарел: на диске другой MP4. Обновите страницу.',
    'CONTENT_CHANGED': 'Содержимое проекта изменилось после утверждения: нужно подтвердить заново.',
    'PROCESSING_RIGHTS_NOT_CONFIRMED': 'Не подтверждено право на обработку контента.',
    'MEDIA_NOT_CONFIRMED': 'Мастер не покрывает требуемые модальности.',
    'OWNER_ID_NOT_CONFIGURED': 'Владелец студии не настроен на сервере: решение невозможно.',
    'OWNER_ID_MISMATCH': 'Идентификатор владельца не совпадает с настроенным.',
    'MACHINE_TOKEN_FORBIDDEN': 'Машинный токен не может принимать решение о выпуске.',
}


def fail(code, status=409, **extra):
    return HTTPException(status, {'code': code, 'message': MESSAGES.get(code, code), **extra})


def content_sha256(studio, project_id):
    """Хеш сырого `projects.state` в каноническом виде; title и revision в него не входят."""
    with studio.connect() as db:
        row = db.execute('SELECT state FROM projects WHERE id=?', (project_id,)).fetchone()
    if row is None:
        raise HTTPException(404, 'Проект не найден')
    try:
        canonical = json.dumps(json.loads(row['state']), sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        canonical = str(row['state'])
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def owner_configured():
    return bool(os.environ.get(OWNER_ENV, '').strip())


def require_owner(request, owner_id):
    """Машинный токен отклоняется всегда; owner_id сверяется с настройкой сервера (не аутентификация)."""
    if service_auth.identify(request)[0] or getattr(request.state, 'service_scopes', None):
        raise fail('MACHINE_TOKEN_FORBIDDEN', 403)
    configured = os.environ.get(OWNER_ENV, '').strip()
    if not configured:
        raise fail('OWNER_ID_NOT_CONFIGURED')
    if not owner_id or not hmac.compare_digest(str(owner_id).encode(), configured.encode()):
        raise fail('OWNER_ID_MISMATCH')
    return configured


def _artifact(studio, project_id, artifact_id):
    return media_qc._artifact(studio, project_id, artifact_id)


def _latest_decision(db, artifact_id):
    return db.execute('SELECT * FROM release_decisions WHERE artifact_id=? ORDER BY created_at DESC, rowid DESC LIMIT 1',
                      (artifact_id,)).fetchone()


def _technical(facts):
    """Блокеры технической части (коды). Источник — N34, как он отдан master_facts."""
    if not facts['exists']:
        return 'MASTER_FILE_MISSING'
    if facts['qc_stale']:
        return 'QC_STALE'
    if not facts['qc_verdict']:
        return 'QC_NOT_RUN'
    if facts['qc_verdict'] != media_qc.PASS_TECHNICAL:
        return 'QC_NOT_PASSED'
    return ''


def freeze(studio, project_id, artifact_id, rights, modalities):
    """N35 как функция: права на обработку и покрытие модальностей. Новой логики здесь нет."""
    body = SimpleNamespace(project_id=project_id, media_asset_id=artifact_id, media_url=None,
                           processing_rights_confirmed=bool(rights), required_modalities=list(modalities))
    return qa_reviews.freeze_media(studio, body)


def evidence(studio, project_id, artifact_id, rights_confirmed):
    """Свидетельство N35 для экрана: покрытие мастера. Права на обработку берутся из решения владельца, не из допущения."""
    manifest = freeze(studio, project_id, artifact_id, True, ['VIDEO'])
    return {'master': manifest.get('master') or {}, 'qc': manifest.get('qc') or {},
            'coverage': manifest.get('coverage') or {}, 'reason': manifest.get('reason') or '',
            'coverage_status': manifest.get('status') or '', 'processing_rights_confirmed': rights_confirmed,
            'stt_is_voice_evidence': False}


def _decision_view(row):
    keys = ('decision_id', 'decision', 'master_sha256', 'content_sha256', 'version_id', 'project_revision',
            'owner_id', 'processing_rights_confirmed', 'qc_verdict', 'note', 'created_at')
    return {key: row[key] for key in keys}


def release_gate(studio, project_id, artifact_id):
    """Состояние выпуска, вычисленное из фактов. Ничего не берёт у клиента."""
    artifact = _artifact(studio, project_id, artifact_id)
    facts = media_qc.master_facts(studio, project_id, artifact_id)
    live = facts['sha256']
    content = content_sha256(studio, project_id)
    with studio.connect() as db:
        latest = _latest_decision(db, artifact_id)
        history = db.execute('SELECT * FROM release_decisions WHERE artifact_id=? ORDER BY created_at DESC, rowid DESC LIMIT 20',
                             (artifact_id,)).fetchall()
    technical = _technical(facts)
    state = TECHNICAL_PASS if not technical else IMPORTED
    decision_valid, stale_code = False, ''
    if latest is not None:
        if latest['master_sha256'] != live:
            stale_code = 'MASTER_CHANGED'
        elif latest['decision'] == APPROVED_DECISION:
            if technical:
                stale_code = technical if technical != 'QC_NOT_RUN' else 'QC_NOT_PASSED'
            elif latest['content_sha256'] != content:
                stale_code = 'CONTENT_CHANGED'
        decision_valid = not stale_code
        if decision_valid:
            state = OWNER_APPROVED if latest['decision'] == APPROVED_DECISION else REJECTED
    blockers = [] if not technical else [technical]
    if not owner_configured():
        blockers.append('OWNER_ID_NOT_CONFIGURED')
    return {
        'artifact_id': artifact_id, 'project_id': project_id, 'state': state,
        'master_sha256': live, 'qc_verdict': facts['qc_verdict'], 'qc_stale': facts['qc_stale'],
        'qc_reason': '' if not technical else MESSAGES.get(technical, technical),
        'version_id': artifact['version_id'], 'project_revision': artifact['project_revision'],
        'content_sha256': content,
        'decision': latest['decision'] if latest is not None and decision_valid else '',
        'decided_at': latest['created_at'] if latest is not None and decision_valid else None,
        'owner_id': latest['owner_id'] if latest is not None and decision_valid else None,
        'decision_stale': bool(latest is not None and not decision_valid),
        'decision_stale_code': stale_code,
        'decision_stale_reason': MESSAGES.get(stale_code, '') if stale_code else '',
        'approve_blockers': [{'code': code, 'message': MESSAGES[code]} for code in blockers],
        'can_approve': not blockers and state != OWNER_APPROVED,
        'can_reject': state != REJECTED,
        'blocked_reason': MESSAGES[blockers[0]] if blockers else None,
        'n35_evidence': evidence(studio, project_id, artifact_id, bool(latest is not None and decision_valid and latest['processing_rights_confirmed'])),
        'history': [_decision_view(row) for row in history],
    }


def _record(studio, project_id, artifact, decision, owner, live, content, rights, verdict, note):
    row_id = uuid.uuid4().hex
    with studio.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO release_decisions(decision_id,artifact_id,project_id,version_id,master_sha256,content_sha256,'
                   'project_revision,decision,owner_id,processing_rights_confirmed,qc_verdict,note,created_at) '
                   'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (row_id, artifact['id'], project_id, artifact['version_id'], live, content, artifact['project_revision'],
                    decision, owner, 1 if rights else 0, verdict, note, studio.now()))
    return row_id


def decide(studio, project_id, artifact_id, request, body):
    """APPROVED — строго, fail-closed; REJECTED — всегда записывается (только снимает разрешение)."""
    owner = require_owner(request, body.owner_id)
    artifact = _artifact(studio, project_id, artifact_id)
    note = (body.note or '').strip()
    facts = media_qc.master_facts(studio, project_id, artifact_id)
    live = facts['sha256']
    content = content_sha256(studio, project_id)
    current = release_gate(studio, project_id, artifact_id)
    if body.decision == REJECTED_DECISION:
        if not note:
            raise HTTPException(400, {'code': 'REJECT_REASON_REQUIRED', 'message': 'Укажите причину отклонения.'})
        if current['state'] == REJECTED:  # повтор того же отказа: дубликата не создаём
            return {'duplicate': True, 'gate': current}
        if body.expected_master_sha256 and live and body.expected_master_sha256 != live:
            note = f'[MASTER_CHANGED] {note}'
        _record(studio, project_id, artifact, REJECTED_DECISION, owner, live, content, False, facts['qc_verdict'], note)
        return {'duplicate': False, 'gate': release_gate(studio, project_id, artifact_id)}
    # APPROVED: порядок проверок фиксирован, каждый отказ — собственный код.
    if not body.processing_rights_confirmed:
        raise fail('PROCESSING_RIGHTS_NOT_CONFIRMED')
    technical = _technical(facts)
    if technical in ('MASTER_FILE_MISSING', 'QC_NOT_RUN', 'QC_NOT_PASSED'):
        raise fail(technical)
    if not body.expected_master_sha256 or body.expected_master_sha256 != live:
        raise fail('MASTER_CHANGED')
    if technical:  # QC_STALE
        raise fail(technical)
    modalities = body.required_modalities or ['VIDEO']
    if 'VIDEO' not in modalities:
        modalities = ['VIDEO', *modalities]
    manifest = freeze(studio, project_id, artifact_id, True, modalities)
    if manifest['status'] != 'CONFIRMED':
        raise fail('MEDIA_NOT_CONFIRMED', detail=manifest.get('reason') or '')
    if current['state'] == OWNER_APPROVED:  # повтор: тот же файл и то же содержимое уже утверждены
        return {'duplicate': True, 'gate': current}
    _record(studio, project_id, artifact, APPROVED_DECISION, owner, live, content, True, facts['qc_verdict'], note)
    return {'duplicate': False, 'gate': release_gate(studio, project_id, artifact_id)}
