"""Живая проверка моделей PiAPI с жёсткими лимитами расходов.

Запуск на Windows из корня проекта:
    .venv\\Scripts\\python scripts\\live_piapi_test.py --dry-run     (ничего не отправляет)
    .venv\\Scripts\\python scripts\\live_piapi_test.py               (платные вызовы после подтверждения)
    .venv\\Scripts\\python scripts\\live_piapi_test.py --only qwen-image-2.1 --yes

Лимиты: не более 1 USD на вызов и 5 USD суммарно (оценка по каталогу); качество минимальное/среднее.
Каждый платный POST отправляется ровно один раз, без повторов. Ключ читается из PIAPI_API_KEY
или PIAPI_API_KEY.txt и нигде не печатается. Результаты: runtime/piapi-live-test-<дата>/.
"""
import argparse
import base64
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from backend import adapters  # noqa: E402
from backend.image_assets import output_urls  # noqa: E402
from backend.model_catalog import MODEL_SPECS  # noqa: E402

BASE = 'https://api.piapi.ai'
PER_CALL_LIMIT = 1.0
TOTAL_LIMIT = 5.0
PROMPT = ('A purple 1980s Soviet sedan parked on a rainy night street in Minsk, warm street lamps, '
          'reflections on wet asphalt, cinematic still, no text')

CASES = [  # от дешёвых к дорогим
    ('gpt-image-2.5', {'variant': 'flare', 'quality': 'low'}),
    ('qwen-image-2.1', {'width': 1024, 'height': 1024}),
    ('gpt-image-2.5', {'variant': 'standard'}),
    ('nano-banana-2.1', {'resolution': '1K', 'aspect_ratio': '16:9'}),
    ('gpt-image-2', {'quality': 'medium'}),
    ('seedream-5-pro', {'size': '1K', 'aspect_ratio': '16:9'}),
    ('minimax-h3', {'resolution': '480p', 'duration': 5, 'aspect_ratio': '16:9'}),
]


def load_key():
    key = os.environ.get('PIAPI_API_KEY', '').strip()
    if not key:
        path = ROOT / 'PIAPI_API_KEY.txt'
        key = path.read_text(encoding='utf-8').strip() if path.is_file() else ''
    if not key or not key.isascii():
        sys.exit('Нет корректного ключа PIAPI_API_KEY')
    return key


def case_label(model, options):
    extra = options.get('variant') or options.get('quality') or options.get('size') or options.get('resolution') or ''
    return f'{model}{"-" + extra if extra else ""}'


def unwrap(body):
    """Единый и асинхронный GPT-эндпоинты отвечают по-разному: приводим к {'data': {...}}."""
    if isinstance(body, dict) and 'data' not in body and 'task_id' in body:
        return {'data': body}
    if isinstance(body, dict) and isinstance(body.get('data'), dict) and 'task_id' not in body['data'] and 'task_id' in body:
        return {'data': body}
    return body


def clean(text, key):
    return str(text).replace(key, '***')


def save_output(directory, label, url_or_b64, is_video, client):
    ext = '.mp4' if is_video else '.png'
    target = directory / (label + ext)
    if url_or_b64.startswith('https://'):
        data = client.get(url_or_b64, timeout=120, follow_redirects=True).content
    else:
        data = base64.b64decode(url_or_b64)
    target.write_bytes(data)
    return target.name, len(data)


def run_case(client, key, directory, model, options, wait):
    spec = MODEL_SPECS[model]
    body = SimpleNamespace(prompt=PROMPT, options=options, reference_urls=[])
    payload = adapters.build(spec, body)
    cost = adapters.cost(spec, payload)
    label = case_label(model, options)
    record = {'case': label, 'model': payload['model'], 'task_type': payload['task_type'],
              'estimated_usd': cost, 'path': adapters.submit_path(spec)}
    headers = {'X-API-KEY': key, 'Content-Type': 'application/json'}
    response = client.post(BASE + adapters.submit_path(spec), headers=headers,
                           json=adapters.wire_body(spec, payload), timeout=120)
    record['submit_http'] = response.status_code
    try:
        submitted = response.json()
    except ValueError:
        record['error'] = clean(response.text[:300], key)
        return record
    submitted = unwrap(submitted)
    record['submit_keys'] = sorted(submitted['data'].keys()) if isinstance(submitted, dict) else None
    task_id = ((submitted.get('data') or {}) if isinstance(submitted, dict) else {}).get('task_id')
    if not task_id:
        record['error'] = clean(json.dumps(submitted, ensure_ascii=False)[:400], key)
        return record
    record['task_id'] = task_id
    deadline = time.time() + wait
    status = ''
    result = submitted
    while time.time() < deadline:
        status = str((result.get('data') or {}).get('status', '')).lower()
        if status in {'completed', 'failed'}:
            break
        time.sleep(5)
        poll = client.get(f'{BASE}/api/v1/task/{task_id}', headers=headers, timeout=60)
        result = unwrap(poll.json())
    record['status'] = status or 'timeout'
    data = result.get('data') or {}
    output = data.get('output')
    record['output_keys'] = sorted(output.keys()) if isinstance(output, dict) else type(output).__name__
    record['usage'] = (data.get('meta') or {}).get('usage')
    record['error_object'] = clean(json.dumps(data.get('error'), ensure_ascii=False), key) if data.get('error') else None
    if status == 'completed':
        urls = output_urls(result, spec['kind'])
        if not urls and isinstance(output, dict):
            items = output.get('data')
            if isinstance(items, list) and items and isinstance(items[0], dict) and items[0].get('b64_json'):
                urls = [items[0]['b64_json']]
        record['output_urls_found'] = len(urls)
        if urls:
            record['url_host'] = urls[0].split('/')[2] if urls[0].startswith('https://') else 'inline-base64'
            try:
                record['saved'] = save_output(directory, label, urls[0], spec['kind'] == 'video', client)
            except Exception as exc:  # задача оплачена: сбой скачивания не должен терять task_id и ссылку
                record['download_error'] = clean(f'{type(exc).__name__}: {exc}', key)
                record['result_url'] = urls[0]
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--yes', action='store_true', help='не спрашивать подтверждение')
    parser.add_argument('--only', help='model_id, например qwen-image-2.1')
    args = parser.parse_args()
    cases = [c for c in CASES if not args.only or c[0] == args.only]
    plan, total = [], 0.0
    for model, options in cases:
        spec = MODEL_SPECS[model]
        payload = adapters.build(spec, SimpleNamespace(prompt=PROMPT, options=options, reference_urls=[]))
        cost = adapters.cost(spec, payload)
        if cost > PER_CALL_LIMIT or total + cost > TOTAL_LIMIT:
            sys.exit(f'Превышен лимит расходов на {model}: {cost} USD')
        total += cost
        plan.append((model, options, cost))
        print(f'{case_label(model, options):40s} ~${cost:.3f}')
    print(f'Итого по оценке: ${total:.3f} (лимит ${TOTAL_LIMIT}, на вызов ${PER_CALL_LIMIT})')
    if args.dry_run:
        print('Сухой прогон: ничего не отправлено.')
        return
    if not args.yes and input('Отправить платные вызовы? Введите yes: ').strip().lower() != 'yes':
        sys.exit('Отменено.')
    key = load_key()
    directory = ROOT / 'runtime' / f'piapi-live-test-{date.today().isoformat()}'
    directory.mkdir(parents=True, exist_ok=True)
    records = []
    with httpx.Client() as client:
        for model, options, _ in plan:
            wait = 600 if MODEL_SPECS[model]['kind'] == 'video' else 240
            try:
                record = run_case(client, key, directory, model, options, wait)
            except Exception as exc:  # один сбой не должен повторять другие платные вызовы
                record = {'case': case_label(model, options), 'error': clean(f'{type(exc).__name__}: {exc}', key)}
            records.append(record)
            print(json.dumps(record, ensure_ascii=False))
            (directory / 'summary.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Готово. Результаты:', directory)


if __name__ == '__main__':
    main()
