"""Генерация картинки через PiAPI по API студии: оценка цены -> подтверждение -> запуск.

Без --yes только показывает оценку (платного вызова нет). С --yes запускает и ждёт результат.
Ключ PiAPI не читается здесь: его берёт бэкенд студии.
"""
import argparse, json, sys, time, urllib.error, urllib.request, uuid

BASE = 'http://127.0.0.1:8000'


_session = {}


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {'Content-Type': 'application/json'}
    if path != '/api/session':
        if 'token' not in _session:  # локальный токен сессии, как у браузера студии
            _session['token'] = call('GET', '/api/session')['token']
        headers['x-studio-session'] = _session['token']
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', 'replace')[:600]
        sys.exit(f'Ошибка {e.code} на {path}: {detail}')
    except urllib.error.URLError:
        sys.exit('Бэкенд студии не отвечает на :8000. Запусти: .\\.venv\\Scripts\\python.exe scripts\\start_studio.py')


def pick_project(project_id):
    projects = call('GET', '/api/projects')
    if not projects:
        sys.exit('В студии нет проектов. Создай проект в интерфейсе.')
    if project_id:
        match = [p for p in projects if p['id'] == project_id]
        if not match:
            sys.exit('Проект не найден: ' + project_id)
        return match[0]
    return projects[0]  # самый недавно обновлённый


def find_urls(node, found=None):
    found = [] if found is None else found
    if isinstance(node, dict):
        for value in node.values():
            find_urls(value, found)
    elif isinstance(node, list):
        for value in node:
            find_urls(value, found)
    elif isinstance(node, str) and node.startswith('https://'):
        found.append(node)
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('prompt')
    ap.add_argument('--model', default='seedream-5-pro')
    ap.add_argument('--aspect', default='16:9')
    ap.add_argument('--size', help='например 1K или 2K (зависит от модели)')
    ap.add_argument('--project', help='id проекта; по умолчанию последний обновлённый')
    ap.add_argument('--yes', action='store_true', help='подтверждаю платный запуск по показанной цене')
    args = ap.parse_args()

    project = pick_project(args.project)
    options = {'aspect_ratio': args.aspect}
    if args.size:
        options['size'] = args.size
    body = {'project_id': project['id'], 'model_id': args.model, 'prompt': args.prompt, 'options': options}

    est = call('POST', '/api/model-jobs/estimate', body)
    cost = est['estimated_usd']
    print(f"Проект: {project['title']}")
    print(f"Модель: {args.model}, формат {args.aspect}")
    for line in est.get('lines') or []:
        print('  ' + str(line))
    print(f'Цена: ${cost:.3f} ({est.get("note", "")})')
    if not args.yes:
        print('Не запущено. Для запуска повтори с --yes.')
        return

    job = call('POST', '/api/model-jobs', {**body, 'approved': True, 'max_cost_usd': cost, 'quote_token': est['quote_token'],
                                          'request_id': 'gen-' + uuid.uuid4().hex})
    jid = job['job_id']
    print('Запущено, job_id:', jid)
    for _ in range(60):
        time.sleep(5)
        data = call('GET', '/api/jobs/' + jid).get('upstream', {}).get('data') or {}
        status = str(data.get('status', '')).lower()
        if status in ('completed', 'failed'):
            if status == 'failed':
                sys.exit('Провайдер вернул ошибку: ' + json.dumps(data.get('error') or data, ensure_ascii=False)[:400])
            print('Готово:')
            for url in dict.fromkeys(find_urls(data.get('output'))):
                print('  ' + url)
            return
    print('Ещё считается; результат появится в ленте заданий студии (job_id выше).')


if __name__ == '__main__':
    main()
