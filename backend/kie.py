"""KIE (api.kie.ai): отправка задания и чтение статуса.

Ответы KIE приводятся к форме PiAPI ({'code', 'data': {'task_id', 'status', 'output'}}), поэтому очередь,
доставка в библиотеку и лента заданий работают без изменений. Ошибки KIE приходят с HTTP 200 и кодом в теле.
"""
import json
from urllib.parse import quote

import httpx
from fastapi import HTTPException

BASE = 'https://api.kie.ai'
SUBMIT_PATH = '/api/v1/jobs/createTask'
STATUS = {'waiting': 'pending', 'queuing': 'pending', 'generating': 'processing', 'success': 'completed', 'fail': 'failed'}


async def request(method, path, key, payload=None, spend=None):
    """Единая точка выхода к KIE.

    POST — платный вызов: допускается только с резервом в журнале расходов
    (spend=('job', ref)). Проверку резерва делает вызывающий (backend/main.py).
    """
    if method.upper()=='POST' and not spend:
        raise HTTPException(403,'Платный вызов без резерва в журнале расходов запрещён. Сначала оценка цены и подтверждение.')
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=False) as client:
            r = await client.request(method, BASE + path, headers={'Authorization': 'Bearer ' + key}, json=payload)
    except httpx.RequestError as e:
        raise HTTPException(502, f'Не удалось соединиться с KIE: {type(e).__name__}')
    if r.is_error:
        raise HTTPException(r.status_code, {'message': f'KIE вернул HTTP {r.status_code}. Проверь ключ и параметры; '
                                                       'повторный запуск требует проверки очереди.'})
    try:
        value = r.json()
    except ValueError:
        raise HTTPException(502, 'KIE вернул не-JSON ответ')
    if not isinstance(value, dict) or value.get('code') != 200:
        code = value.get('code') if isinstance(value, dict) else None
        message = str(value.get('msg') or '')[:300] if isinstance(value, dict) else ''
        status = 402 if code == 402 else 502
        raise HTTPException(status, f'KIE вернул ошибку {code}: {message}'.strip())
    return value


def submitted(value):
    """createTask → форма PiAPI. Без taskId вызывающий код помечает задание как неопределённое."""
    task_id = (value.get('data') or {}).get('taskId')
    return {'code': 200, 'message': value.get('msg', ''), 'data': {'task_id': task_id, 'status': 'pending'} if task_id else {}}


def status(value):
    """recordInfo → форма PiAPI: статус, ссылки на результат и списанные кредиты."""
    data = value.get('data') or {}
    state = STATUS.get(str(data.get('state')), 'processing')
    task = {'task_id': data.get('taskId'), 'status': state, 'model': data.get('model'),
            'credits_consumed': data.get('creditsConsumed')}
    if state == 'completed':
        result = data.get('response')
        if not isinstance(result, dict):
            try:
                result = json.loads(data.get('resultJson') or '{}')
            except ValueError:
                result = {}
        urls = result.get('resultUrls') if isinstance(result, dict) else None
        task['output'] = {'image_urls': [u for u in urls or [] if isinstance(u, str) and u.startswith('https://')]}
    if state == 'failed':
        task['error'] = {'code': data.get('failCode'), 'message': str(data.get('failMsg') or 'Генерация не удалась')[:500]}
    return {'code': 200, 'message': value.get('msg', ''), 'data': task}


async def submit(key, body, spend=None):
    """Отправка задания. Платный POST — только с резервом в журнале расходов."""
    return submitted(await request('POST', SUBMIT_PATH, key, body, spend=spend))


async def fetch(key, task_id):
    return status(await request('GET', '/api/v1/jobs/recordInfo?taskId=' + quote(task_id, safe=''), key))
