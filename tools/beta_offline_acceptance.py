"""BETA-02 — одна команда офлайн-приёмки кандидата GremoVOD (GA-01 деньги + GA-03 выпуск MP4).

    python tools/beta_offline_acceptance.py --quick              # адресные проверки
    python tools/beta_offline_acceptance.py --full               # + весь backend pytest
    python tools/beta_offline_acceptance.py --quick --fault b1   # самопроверка: сломанный продукт обязан дать NO_GO (b1|owner|ledger)
Запускать из корня репозитория, python с зависимостями backend (`backend/requirements.lock.txt`) и pytest.

Что гарантируется. Данные — во временной папке (STUDIO_DATA_DIR), ролики — локальный ffmpeg, сеть закрыта
ловушкой (`tools/beta02_tripwire.py`), платный провайдер заменён. «unpaid_calls = 0» пишется только если все
обязательные шаги выполнены и ловушка зафиксировала ноль попыток. Пропуск или блокировка обязательной проверки —
не зелёный: код выхода 2, отказ — 1, зелёный — 0. Но `release_verdict` в этом отчёте всегда NO_GO, пока владелец
не закрыл OWNER_AUTH_REQUIRED и решения GA-01, а живые проверки (браузер, CapCut, реальный MP4, CI) не выполнены.
Автоустановок нет; GA-01, GA-02, frontend и деньги эта команда не меняет.

Происхождение — обязательный шаг: каждый SHA манифеста полный, существует, совпадает с головой origin/<ветка>
и входит в HEAD; база тоже; дерево чистое. Любое расхождение — BLOCKED, а не «меньше проверок».
Секреты: pytest получает окружение по списку разрешённых переменных (ключи провайдеров, токены, пароли не
передаются), домашняя папка подменена пустой песочницей (ключ ElevenLabs из ~/Documents не читается), файлы
ключей в дереве (`*_API_KEY.txt`, `.env*`, `kie-access/api-key.dpapi`) — BLOCKED: запускать на одноразовой копии
(`tools/beta02_candidate.py`). В отчёт попадают только имена убранных переменных, значения маскируются.
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from beta02_candidate import check_pins, git as git_run, is_ancestor, load_manifest  # noqa: E402
PASS, FAIL, BLOCKED, NOT_RUN = 'PASS', 'FAIL', 'BLOCKED', 'NOT_RUN'

# (id, заголовок, обязательный, режим, цели pytest (пути относительно корня), допустимы ли пропуски, нужен ли ffmpeg)
STEPS = [
    ('release-gate', 'GA-03: release gate (backend/test_release_gate.py)', True, 'quick',
     ['backend/test_release_gate.py'], False, True),
    ('qc-n34-n35', 'N34/N35 и приёмка QA (B1: старый QC не наследуется)', True, 'quick',
     ['backend/test_media_qc.py', 'backend/test_n35_freeze.py', 'backend/test_qa_reviews.py'], False, True),
    ('integration-release', 'BETA-02: контракт HTTP, перезапуск, резервная копия', True, 'quick',
     ['tests/test_beta02_integration.py::ReleaseFlowTests'], False, True),
    ('integration-failclosed', 'BETA-02: fail-closed матрица, токен, гонка', True, 'quick',
     ['tests/test_beta02_integration.py::FailClosedTests'], False, True),
    ('ga01-money-coexistence', 'GA-01 рядом с выпуском: неизвестная сумма держит траты (нужен #79)', True, 'quick',
     ['tests/test_beta02_integration.py::MoneyCoexistenceTests'], False, True),
    ('ga01-money-suites', 'GA-01: тесты денег (R3, расчёт LLM, граница денег, резервы)', True, 'quick',
     ['backend/test_ga01_unreadable_barrier.py', 'backend/test_llm_settlement.py', 'backend/test_money_boundary.py',
      'backend/test_llm_guard.py', 'backend/test_p0_budget_authz.py'], False, False),
    ('backend-full', 'Весь backend pytest', True, 'full', ['backend'], True, False),
]
# GA-01-набор обязан целиком присутствовать в дереве: отсутствие файла = BLOCKED, а не «меньше проверок»
REQUIRED_FILES = {'ga01-money-suites': ['backend/test_ga01_unreadable_barrier.py', 'backend/test_llm_settlement.py']}
NOT_RUN_CHECKS = [
    ('browser-ui', 'Браузерный smoke экрана «Выпуск» (frontend — отдельная задача MiniMax #84/#86)'),
    ('capcut', 'CapCut GUI и реальный MP4 владельца'),
    ('working-sqlite', 'Рабочая SQLite и реальные файлы владельца (запрещено)'),
    ('github-actions', 'GitHub Actions: тесты backend/frontend в CI не запускаются, идут только scope и handoff'),
    ('live-providers', 'Живые платные провайдеры (запрещено)'),
]
# Окружение дочернего pytest: только эти переменные (и ничего похожего на секрет).
ENV_ALLOW = ('PATH', 'PATHEXT', 'SYSTEMROOT', 'SYSTEMDRIVE', 'WINDIR', 'COMSPEC', 'PROCESSOR_ARCHITECTURE',
             'NUMBER_OF_PROCESSORS', 'OS', 'LANG', 'LANGUAGE', 'LC_ALL', 'LC_CTYPE', 'LC_MESSAGES', 'TZ',
             'PYTHONIOENCODING', 'PYTHONUTF8', 'SSL_CERT_FILE')
SENSITIVE = re.compile(r'^(?!(OLD)?PWD$).*(KEY|TOKEN|SECRET|PASS|PWD|CREDENTIAL|AUTH|COOKIE|SESSION|PRIVATE|DPAPI|BEARER)', re.I)
SECRET_PATTERNS = [re.compile(r'sk-[A-Za-z0-9_-]{8,}'), re.compile(r'(?i)bearer\s+[^\s\'"]+'),
                   re.compile(r'(?i)\b(api[_-]?key|token|secret|password|passwd)\b(\s*[=:]\s*)[^\s\'",]+')]
# Шаблоны без значений (`.env.example`) — не ключи.
TEMPLATE_SUFFIXES = ('.example', '.sample', '.template', '.dist')
KEY_FILE_GLOBS = ('*_API_KEY.txt', '.env', '.env.*', 'backend/*_API_KEY.txt', 'backend/.env', 'backend/.env.*',
                  'kie-access/api-key.dpapi')
STANDING_NO_GO = [
    'OWNER_AUTH_REQUIRED: идентификатор владельца сверяется с GREMOVOD_OWNER_ID — это не аутентификация (пароль отложен владельцем)',
    'GA-01: решения владельца по сверке нечитаемой суммы и приёмка #58/#76/#79 не получены',
    'Живые проверки (браузер, CapCut, реальный MP4, CI с тестами) не выполнялись',
]


def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def classify(exit_code, counts, allow_skips, missing=()):
    """Статус шага по коду выхода и счётчикам junit. Чистая функция."""
    if missing:
        return BLOCKED, 'нет обязательных файлов: ' + ', '.join(missing)
    if exit_code == 5 or (counts['tests'] == 0 and exit_code == 0):
        return BLOCKED, 'не собрано ни одного теста'
    if exit_code != 0:
        return FAIL, f'pytest завершился кодом {exit_code}: failed={counts["failures"]}, errors={counts["errors"]}'
    if counts['skipped'] and not allow_skips:
        return BLOCKED, f'пропущено тестов: {counts["skipped"]} — обязательная проверка не выполнена'
    return PASS, ''


def evaluate(steps, tripwire_ok):
    """Итоговый вердикт. Чистая функция: тот же вход — тот же результат."""
    required = [s for s in steps if s['required']]
    failed = [s['id'] for s in required if s['status'] == FAIL]
    blocked = [s['id'] for s in required if s['status'] in (BLOCKED, NOT_RUN)]
    technical = FAIL if failed else (BLOCKED if blocked else PASS)
    exit_code = {PASS: 0, FAIL: 1, BLOCKED: 2}[technical]
    reasons = list(STANDING_NO_GO)
    reasons += [f'обязательный шаг упал: {name}' for name in failed]
    reasons += [f'обязательный шаг заблокирован: {name}' for name in blocked]
    unpaid = 0 if (technical == PASS and tripwire_ok is True) else 'unknown'
    return {'technical_verdict': technical, 'release_verdict': 'NO_GO', 'exit_code': exit_code,
            'unpaid_calls': unpaid, 'no_go_reasons': reasons}


def git(args, root=ROOT):
    return git_run(args, root).stdout.strip()


def scrub(base):
    """(разрешённые переменные, имена убранных чувствительных, их значения для маскировки). Чистая функция.

    Берутся только переменные из ENV_ALLOW; всё похожее на секрет отбрасывается даже из него.
    """
    env = {key: value for key, value in base.items() if key.upper() in ENV_ALLOW and not SENSITIVE.search(key)}
    removed = sorted(key for key in base if key not in env and SENSITIVE.search(key))
    values = sorted({value for key, value in base.items() if key in removed and len(value) >= 6}, key=len, reverse=True)
    return env, removed, values


def child_env(base, sandbox, extra):
    """Окружение дочернего pytest: scrub() плюс песочница вместо домашней папки и временных каталогов.

    Код, ищущий ключи в ~/Documents (ElevenLabs, KIE DPAPI), их не найдёт. Возвращает как scrub().
    """
    env, removed, values = scrub(base)
    home, tmp = sandbox / 'home', sandbox / 'tmp'
    home.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)
    env.update({'HOME': str(home), 'USERPROFILE': str(home), 'APPDATA': str(home / 'AppData' / 'Roaming'),
                'LOCALAPPDATA': str(home / 'AppData' / 'Local'), 'TMPDIR': str(tmp), 'TEMP': str(tmp), 'TMP': str(tmp),
                'ELEVENLABS_KEY_FILE': str(sandbox / 'absent-elevenlabs-key.txt')})
    env.update(extra)
    return env, removed, values


def key_files(root=ROOT):
    """Файлы ключей в дереве (пути относительно корня). Содержимое не читается."""
    found = set()
    for pattern in KEY_FILE_GLOBS:
        found.update(str(path.relative_to(root)).replace(os.sep, '/') for path in root.glob(pattern)
                     if path.is_file() and not path.name.endswith(TEMPLATE_SUFFIXES))
    return sorted(found)


def synthetic(sid, title, status, reason):
    return {'id': sid, 'title': title, 'required': True, 'status': status, 'reason': reason, 'command': '',
            'exit_code': None, 'duration_s': 0.0, 'counts': {'tests': 0, 'failures': 0, 'errors': 0, 'skipped': 0},
            'tripwire_attempts': None, 'skipped_tests': [], 'pytest': False}


def provenance(sources_path, root=ROOT):
    """Точное происхождение дерева: сверка каждого SHA манифеста и состояние HEAD.

    Возвращает (данные для отчёта, список проблем). Пустой список — происхождение доказано.
    """
    info = {'head': git(['rev-parse', 'HEAD'], root), 'branch': git(['rev-parse', '--abbrev-ref', 'HEAD'], root),
            'dirty': bool(git(['status', '--porcelain'], root)), 'sources': []}
    manifest, errors = load_manifest(sources_path)
    if errors:
        return {**info, 'sources_error': errors}, errors
    problems = ['дерево грязное: отчёт не относится к HEAD'] if info['dirty'] else []
    for row in check_pins(manifest, root):
        present = is_ancestor(row['sha'], root) if row['exists'] else None
        role = 'база' if row['pr'] is None else next(s['role'] for s in manifest['sources'] if s['sha'] == row['sha'])
        info['sources'].append({'pr': row['pr'], 'branch': row['branch'], 'sha': row['sha'], 'role': role,
                                'exists': row['exists'], 'in_tree': present is True, 'remote_head': row['remote_head'],
                                'drift': row['drift']})
        label = 'база' if row['pr'] is None else f'#{row["pr"]}'
        if 'problem' in row:
            problems.append(f'{label}: {row["problem"]}')
        if row['exists'] and present is not True:
            problems.append(f'{label}: {row["sha"][:12]} ' + ('отсутствует в HEAD' if present is False else 'не проверен git'))
    return info, problems


def run_step(step, workdir, fault, python, base_env=None):
    sid, title, required, _, targets, allow_skips, needs_ffmpeg = step
    result = {'id': sid, 'title': title, 'required': required, 'status': NOT_RUN, 'reason': '', 'command': '',
              'exit_code': None, 'duration_s': 0.0, 'counts': {'tests': 0, 'failures': 0, 'errors': 0, 'skipped': 0},
              'tripwire_attempts': None, 'skipped_tests': [], 'pytest': True}
    missing = [p for p in REQUIRED_FILES.get(sid, []) if not (ROOT / p).exists()]
    present = [t for t in targets if (ROOT / t.split('::')[0]).exists()]
    if missing or not present:
        result['status'], result['reason'] = classify(0, result['counts'], False, missing or targets)
        return result
    if needs_ffmpeg and not (shutil.which('ffmpeg') and shutil.which('ffprobe')):
        result['status'], result['reason'] = BLOCKED, 'ffmpeg/ffprobe не установлены (автоустановки нет)'
        return result
    data = workdir / sid
    data.mkdir(parents=True, exist_ok=True)
    junit, trip = data / 'junit.xml', data / 'tripwire.json'
    extra = {'STUDIO_DATA_DIR': str(data / 'studio'), 'PYTHONPATH': os.pathsep.join([str(ROOT / 'tools'), str(ROOT)]),
             'BETA02_TRIPWIRE_FILE': str(trip), 'PYTHONDONTWRITEBYTECODE': '1', 'GREMOVOD_OWNER_ID': 'beta02-owner'}
    if fault:
        extra['BETA02_FAULT'] = fault
    env, _, secret_values = child_env(os.environ if base_env is None else base_env, data / 'sandbox', extra)
    cmd = [python, '-m', 'pytest', *present, '-p', 'beta02_tripwire', '-q', '-W', 'ignore', f'--junitxml={junit}', '-p', 'no:cacheprovider']
    result['command'] = 'python -m pytest ' + ' '.join(present) + ' -p beta02_tripwire -q'
    started = datetime.now(timezone.utc)
    done = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    result['duration_s'] = round((datetime.now(timezone.utc) - started).total_seconds(), 1)
    result['exit_code'] = done.returncode
    try:
        root = ET.parse(junit).getroot()
        suite = root if root.tag == 'testsuite' else root.find('testsuite')
        result['counts'] = {key: int(suite.get(key, 0)) for key in ('tests', 'failures', 'errors', 'skipped')}
        result['skipped_tests'] = redact([f'{c.get("classname", "").rsplit(".", 1)[-1]}::{c.get("name")}: {(c.find("skipped").get("message") or "")[:120]}'
                                          for c in root.iter('testcase') if c.find('skipped') is not None], secret_values)
    except (OSError, ET.ParseError, AttributeError):
        pass
    try:
        result['tripwire_attempts'] = json.loads(trip.read_text(encoding='utf-8'))['count']
    except (OSError, ValueError, KeyError):
        result['tripwire_attempts'] = None
    result['status'], result['reason'] = classify(done.returncode, result['counts'], allow_skips)
    if result['status'] == PASS and result['tripwire_attempts'] != 0:
        result['status'], result['reason'] = FAIL, f'сетевые попытки: {result["tripwire_attempts"]} (ловушка не отчиталась или сработала)'
    if result['status'] != PASS:
        result['tail'] = '\n'.join(redact(done.stdout.splitlines()[-12:], secret_values))
    return result


def redact(lines, secrets=()):
    """Маскирует значения убранных секретов, похожие на ключи строки, домашнюю папку и временные пути."""
    home = str(Path.home())
    root = str(ROOT)
    out = []
    for line in lines:
        for value in secrets:
            line = line.replace(value, '<secret>')
        for pattern in SECRET_PATTERNS:
            line = pattern.sub(lambda m: (m.group(1) + m.group(2) + '<secret>') if m.lastindex else '<secret>', line)
        line = line.replace(root, '<repo>').replace(home, '<home>')
        out.append(re.sub(r'(/tmp|/var/folders)/[^\s\'"]+', '<tmp>', line))
    return out


def markdown(report):
    lines = [f'# BETA-02 — офлайн-приёмка ({report["mode"]})', '',
             f'- Время: {report["timestamp"]}', f'- HEAD: `{report["provenance"]["head"]}` ({report["provenance"]["branch"]}, dirty={report["provenance"]["dirty"]})',
             f'- Технический вердикт: **{report["technical_verdict"]}** · релизный: **{report["release_verdict"]}** · код выхода {report["exit_code"]}',
             f'- Платных вызовов: **{report["unpaid_calls"]}** · данные: {report["dataset"]} · fault: {report["fault"] or "нет"}',
             f'- Среда: {report["environment"]["python"]}, {report["environment"]["platform"]}', '',
             '| Шаг | Обязательный | Статус | Тесты (всего/упало/ошибки/пропущено) | Код | Сеть | Причина |', '|---|---|---|---|---|---|---|']
    for step in report['steps']:
        c = step['counts']
        lines.append(f'| {step["title"]} | {"да" if step["required"] else "нет"} | **{step["status"]}** | {c["tests"]}/{c["failures"]}/{c["errors"]}/{c["skipped"]} | '
                     f'{step["exit_code"] if step["exit_code"] is not None else "—"} | {step["tripwire_attempts"] if step["tripwire_attempts"] is not None else "—"} | {step["reason"]} |')
    lines += ['', '## Не выполнялось (NOT_RUN)'] + [f'- {c["title"]}' for c in report['not_run']]
    lines += ['', '## Источники (точные SHA)'] + [
        f'- {"база" if s["pr"] is None else "#" + str(s["pr"])} `{s["sha"]}` {s["role"]}: '
        f'{"в HEAD" if s["in_tree"] else "ОТСУТСТВУЕТ в HEAD"}; origin/{s["branch"]}: '
        f'{"нет ссылки" if s["remote_head"] is None else ("совпадает" if not s["drift"] else "ДРЕЙФ " + s["remote_head"][:12])}'
        for s in report['provenance']['sources']]
    secrets = report['environment']['secrets']
    lines += ['', '## Секреты', f'- Убрано из окружения pytest: {len(secrets["removed_env"])} ({", ".join(secrets["removed_env"]) or "нет"}); '
              f'домашняя папка — песочница; файлы ключей в дереве: {", ".join(secrets["key_files"]) or "нет"}']
    lines += ['', '## Почему NO_GO'] + [f'- {r}' for r in report['no_go_reasons']]
    lines += ['', '## Разделение статусов', '- CODE_COMPLETE: ' + str(report['separation']['code_complete']),
              '- CI_PASS: NOT_RUN (в Actions не гоняются тесты)', '- OWNER_ACCEPTED: false', '- RELEASE_GO: false']
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--quick', action='store_true', help='адресные проверки (по умолчанию)')
    group.add_argument('--full', action='store_true', help='адресные проверки и весь backend pytest')
    parser.add_argument('--fault', choices=['b1', 'owner', 'ledger'], default='', help='самопроверка: сломать продукт, гейт обязан дать NO_GO')
    parser.add_argument('--out', default='', help='папка отчётов (по умолчанию временная)')
    parser.add_argument('--sources', default=str(ROOT / 'tools' / 'beta02_sources.json'))
    parser.add_argument('--timestamp', default='', help='зафиксировать время отчёта (для воспроизводимости)')
    args = parser.parse_args(argv)
    mode = 'full' if args.full else 'quick'
    out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix='beta02-report-'))
    out.mkdir(parents=True, exist_ok=True)
    origin, problems = provenance(args.sources)
    found_keys = key_files()
    _, removed_env, _ = scrub(os.environ)
    steps = [synthetic('provenance', 'Происхождение: точные SHA манифеста, дрейф, чистое дерево',
                       BLOCKED if problems else PASS, '; '.join(problems)),
             synthetic('secrets-isolation', 'Секреты: нет файлов ключей в дереве, окружение pytest очищено',
                       BLOCKED if found_keys else PASS,
                       ('файлы ключей в дереве: ' + ', '.join(found_keys) + ' — запускай на копии tools/beta02_candidate.py')
                       if found_keys else '')]
    selected = [s for s in STEPS if s[3] == 'quick' or mode == 'full']
    if found_keys:
        steps += [{**synthetic(s[0], s[1], NOT_RUN, 'не запускался: в дереве файлы ключей'), 'required': s[2], 'pytest': True}
                  for s in selected]
    else:
        with tempfile.TemporaryDirectory(prefix='beta02-data-') as work:
            steps += [run_step(s, Path(work), args.fault, sys.executable) for s in selected]
    attempts = [s['tripwire_attempts'] for s in steps if s['pytest'] and s['exit_code'] is not None]
    tripwire_ok = all(a == 0 for a in attempts) and bool(attempts)
    verdict = evaluate(steps, tripwire_ok)
    report = {'schema': 1, 'timestamp': args.timestamp or now_iso(), 'mode': mode, 'fault': args.fault, 'dataset': 'temp',
              'provenance': origin, 'steps': steps,
              'not_run': [{'id': i, 'title': t, 'status': NOT_RUN} for i, t in NOT_RUN_CHECKS],
              'environment': {'python': platform.python_version(), 'platform': platform.system(), 'ffmpeg': bool(shutil.which('ffmpeg')),
                              'secrets': {'removed_env': removed_env, 'key_files': found_keys, 'home': 'sandbox'}},
              'separation': {'code_complete': verdict['technical_verdict'] == PASS, 'ci_pass': NOT_RUN, 'owner_accepted': False, 'release_go': False},
              **verdict}
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'report.md').write_text(markdown(report), encoding='utf-8')
    print(markdown(report))
    print(f'Отчёт: {out / "report.json"}')
    return verdict['exit_code']


if __name__ == '__main__':
    sys.exit(main())
