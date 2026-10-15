"""Единая лента заданий проекта и долгий опрос изменений.

Собирает задания трёх источников (API-провайдеры, внешняя генерация, чат Codex) в один список
с общими статусами. Вместо шести независимых таймеров интерфейс держит один запрос
GET /api/activity?since=<версия>: сервер отвечает сразу при изменении или через wait секунд.
"""
import asyncio
import hashlib
import json

from fastapi import HTTPException

MAX_WAIT = 25
POLL_STEP = 1.0

API_STATUS = {'completed': 'done', 'failed': 'failed', 'submission_unknown': 'attention', 'submitting': 'running',
              'pending': 'queued', 'processing': 'running', 'staged': 'queued'}
EXTERNAL_STATUS = {'waiting_external': 'waiting_external', 'received': 'done', 'cancelled': 'cancelled'}
NATIVE_STATUS = {'queued': 'queued', 'preparing': 'running', 'generating': 'running', 'completed': 'done',
                 'failed': 'failed', 'cancelled': 'cancelled'}


def _prompt_of(request_json):
    try:
        data = json.loads(request_json)
    except (TypeError, ValueError):
        return ''
    payload = data.get('payload') or {}
    return str((payload.get('input') or {}).get('prompt') or data.get('prompt') or '')[:200]


def collect(studio, project_id):
    items = []
    with studio.connect() as db:
        delivery = {d['job_id']: d for d in db.execute('SELECT * FROM job_delivery')}
        assets = {}
        for a in db.execute('SELECT id,job_id FROM library_assets WHERE project_id=?', (project_id,)):
            assets.setdefault(a['job_id'], []).append(a['id'])
        for r in db.execute('SELECT * FROM jobs WHERE project_id=?', (project_id,)):
            d = delivery.get(r['id'])
            status = API_STATUS.get(r['status'], 'running')
            if status == 'done' and d and d['state'] != 'saved':
                status = 'saving' if d['state'] == 'retry' else 'attention'
            request = json.loads(r['request'] or '{}')
            items.append({'id': r['id'], 'source': 'api', 'kind': r['kind'], 'provider': r['provider'],
                          'model': (request.get('payload') or {}).get('task_type') or r['kind'],
                          'status': status, 'raw_status': r['status'], 'created_at': r['created_at'],
                          'prompt': _prompt_of(r['request']), 'asset_ids': assets.get(r['id'], []),
                          'delivery': dict(d) if d else None})
        for r in db.execute('SELECT * FROM external_jobs WHERE project_id=?', (project_id,)):
            items.append({'id': r['id'], 'source': 'external', 'kind': 'image', 'provider': 'external:' + r['service'],
                          'model': r['target'], 'status': EXTERNAL_STATUS.get(r['status'], r['status']),
                          'raw_status': r['status'], 'created_at': r['created_at'], 'node_id': r['node_id'],
                          'prompt': r['prompt'][:200], 'asset_ids': assets.get(r['id'], [])})
        for r in db.execute("SELECT * FROM native_chat_jobs WHERE project_id=? AND operation!='describe_character'", (project_id,)):
            items.append({'id': r['id'], 'source': 'native', 'kind': 'image' if r['operation'] in {'generate', 'edit'} else 'prompt',
                          'provider': 'codex_chat', 'model': r['target'], 'status': NATIVE_STATUS.get(r['status'], 'running'),
                          'raw_status': r['status'], 'created_at': r['created_at'], 'prompt': (r['prompt'] or '')[:200],
                          'asset_ids': [r['asset_id']] if r['asset_id'] else []})
    items.sort(key=lambda x: x['created_at'], reverse=True)
    return items


def version_of(items):
    digest = hashlib.sha1(json.dumps([(x['id'], x['status'], x['raw_status'], len(x['asset_ids']),
                                       (x.get('delivery') or {}).get('state'), (x.get('delivery') or {}).get('saved'))
                                      for x in items], sort_keys=True).encode()).hexdigest()
    return digest[:16]


def register(app, studio):
    @app.get('/api/activity')
    async def activity(project_id: str, since: str = '', wait: float = 0):
        studio.project(project_id)
        wait = max(0.0, min(float(wait), MAX_WAIT))
        waited = 0.0
        while True:
            items = collect(studio, project_id)
            version = version_of(items)
            if version != since or waited >= wait:
                return {'version': version, 'changed': version != since, 'items': items}
            await asyncio.sleep(POLL_STEP)
            waited += POLL_STEP
