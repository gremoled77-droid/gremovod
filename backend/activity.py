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


def _entity_node(request_json):
    try:
        return ((json.loads(request_json or '{}').get('context') or {}).get('entity') or {}).get('node_id')
    except (TypeError, ValueError, AttributeError):
        return None


def collect(studio, *project_ids):
    items = []
    if not project_ids:
        return items
    marks = ','.join('?' * len(project_ids))
    with studio.connect() as db:
        delivery = {d['job_id']: d for d in db.execute('SELECT * FROM job_delivery')}
        assets = {}
        for a in db.execute(f'SELECT id,job_id FROM library_assets WHERE project_id IN ({marks})', project_ids):
            assets.setdefault(a['job_id'], []).append(a['id'])
        for r in db.execute(f'SELECT * FROM jobs WHERE project_id IN ({marks})', project_ids):
            d = delivery.get(r['id'])
            status = API_STATUS.get(r['status'], 'running')
            if status == 'done' and d and d['state'] != 'saved':
                status = 'saving' if d['state'] == 'retry' else 'attention'
            request = json.loads(r['request'] or '{}')
            items.append({'id': r['id'], 'project_id': r['project_id'], 'source': 'api', 'kind': r['kind'], 'provider': r['provider'],
                          'model': request.get('model_id') or (request.get('payload') or {}).get('task_type') or r['kind'],
                          'status': status, 'raw_status': r['status'], 'created_at': r['created_at'],
                          'node_id': request.get('node_id'), 'prompt': _prompt_of(r['request']), 'asset_ids': assets.get(r['id'], []),
                          'delivery': dict(d) if d else None})
        for r in db.execute(f'SELECT * FROM external_jobs WHERE project_id IN ({marks})', project_ids):
            items.append({'id': r['id'], 'project_id': r['project_id'], 'source': 'external', 'kind': 'image', 'provider': 'external:' + r['service'],
                          'model': r['target'], 'status': EXTERNAL_STATUS.get(r['status'], r['status']),
                          'raw_status': r['status'], 'created_at': r['created_at'], 'node_id': r['node_id'],
                          'prompt': r['prompt'][:200], 'asset_ids': assets.get(r['id'], [])})
        for r in db.execute(f"SELECT * FROM native_chat_jobs WHERE project_id IN ({marks}) AND operation!='describe_character'", project_ids):
            items.append({'id': r['id'], 'project_id': r['project_id'], 'node_id': _entity_node(r['request']), 'source': 'native', 'kind': 'image' if r['operation'] in {'generate', 'edit'} else 'prompt',
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


def production_items(studio, pid):
    """Задания всех проектов постановки; без своего node_id задание относится к кадру, к которому привязан его проект."""
    with studio.connect() as db:
        if not db.execute('SELECT 1 FROM productions WHERE id=?', (pid,)).fetchone():
            raise HTTPException(404, 'Общий проект не найден')
        links = {r['project_id']: r['node_id'] for r in db.execute('SELECT project_id,node_id FROM production_links WHERE production_id=?', (pid,))}
    items = collect(studio, *links)
    for item in items:
        item['node_id'] = item.get('node_id') or links.get(item['project_id'])
    return items


async def long_poll(read, since, wait):
    wait = max(0.0, min(float(wait), MAX_WAIT))
    waited = 0.0
    while True:
        items = read()
        version = version_of(items)
        if version != since or waited >= wait:
            return {'version': version, 'changed': version != since, 'items': items}
        await asyncio.sleep(POLL_STEP)
        waited += POLL_STEP


def register(app, studio):
    @app.post('/api/activity/refresh/{job_id}')
    async def refresh(job_id: str):
        """Опрос провайдера по одному заданию и сохранение готового результата в библиотеку.
        Только чтение у провайдера (GET): новых платных запусков не создаёт."""
        from backend import job_delivery
        with studio.connect() as db:
            job = db.execute('SELECT status,task_id FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not job:
            raise HTTPException(404, 'Задание не найдено')
        if job['task_id'] and job['status'] not in {'completed', 'failed', 'submission_unknown'}:
            await studio.job_status(job_id, None)
        await job_delivery.deliver(studio, job_id)
        with studio.connect() as db:
            row = db.execute('SELECT status FROM jobs WHERE id=?', (job_id,)).fetchone()
        return {'job_id': job_id, 'status': API_STATUS.get(row['status'], 'running'), 'raw_status': row['status']}

    @app.get('/api/activity')
    async def activity(project_id: str, since: str = '', wait: float = 0):
        studio.project(project_id)
        return await long_poll(lambda: collect(studio, project_id), since, wait)

    @app.get('/api/productions/{pid}/activity')
    async def production_activity(pid: str, since: str = '', wait: float = 0):
        return await long_poll(lambda: production_items(studio, pid), since, wait)
