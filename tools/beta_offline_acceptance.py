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


def git(args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def provenance(sources_path):
    info = {'head': git(['rev-parse', 'HEAD']), 'branch': git(['rev-parse', '--abbrev-ref', 'HEAD']),
            'dirty': bool(git(['status', '--porcelain'])), 'sources': []}
    try:
        manifest = json.loads(Path(sources_path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {**info, 'sources_error': 'манифест источников не прочитан'}
    for item in manifest.get('sources', []):
        present = subprocess.run(['git', 'merge-base', '--is-ancestor', item['sha'], 'HEAD'], cwd=ROOT,
                                 capture_output=True).returncode == 0
        info['sources'].append({'pr': item['pr'], 'sha': item['sha'], 'role': item['role'], 'in_tree': present})
    return info


def run_step(step, workdir, fault, python):
    sid, title, required, _, targets, allow_skips, needs_ffmpeg = step
    result = {'id': sid, 'title': title, 'required': required, 'status': NOT_RUN, 'reason': '', 'command': '',
              'exit_code': None, 'duration_s': 0.0, 'counts': {'tests': 0, 'failures': 0, 'errors': 0, 'skipped': 0},
              'tripwire_attempts': None, 'skipped_tests': []}
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
    env = {**os.environ, 'STUDIO_DATA_DIR': str(data / 'studio'), 'PYTHONPATH': os.pathsep.join([str(ROOT / 'tools'), str(ROOT)]),
           'BETA02_TRIPWIRE_FILE': str(trip), 'PYTHONDONTWRITEBYTECODE': '1', 'GREMOVOD_OWNER_ID': 'beta02-owner'}
    env.pop('STUDIO_SERVICE_TOKENS', None)
    if fault:
        env['BETA02_FAULT'] = fault
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
        result['skipped_tests'] = [f'{c.get("classname", "").rsplit(".", 1)[-1]}::{c.get("name")}: {(c.find("skipped").get("message") or "")[:120]}'
                                   for c in root.iter('testcase') if c.find('skipped') is not None]
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
        result['tail'] = '\n'.join(redact(done.stdout.splitlines()[-12:]))
    return result


def redact(lines):
    home = str(Path.home())
    root = str(ROOT)
    out = []
    for line in lines:
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
    lines += ['', '## Источники в дереве'] + [f'- #{s["pr"]} `{s["sha"][:10]}` {s["role"]}: {"в дереве" if s["in_tree"] else "ОТСУТСТВУЕТ"}'
                                             for s in report['provenance']['sources']]
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
    with tempfile.TemporaryDirectory(prefix='beta02-data-') as work:
        steps = [run_step(s, Path(work), args.fault, sys.executable) for s in STEPS if s[3] == 'quick' or mode == 'full']
    attempts = [s['tripwire_attempts'] for s in steps if s['status'] != BLOCKED or s['exit_code'] is not None]
    tripwire_ok = all(a == 0 for a in attempts) and bool(attempts)
    verdict = evaluate(steps, tripwire_ok)
    report = {'schema': 1, 'timestamp': args.timestamp or now_iso(), 'mode': mode, 'fault': args.fault, 'dataset': 'temp',
              'provenance': provenance(args.sources), 'steps': steps,
              'not_run': [{'id': i, 'title': t, 'status': NOT_RUN} for i, t in NOT_RUN_CHECKS],
              'environment': {'python': platform.python_version(), 'platform': platform.system(), 'ffmpeg': bool(shutil.which('ffmpeg'))},
              'separation': {'code_complete': verdict['technical_verdict'] == PASS, 'ci_pass': NOT_RUN, 'owner_accepted': False, 'release_go': False},
              **verdict}
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'report.md').write_text(markdown(report), encoding='utf-8')
    print(markdown(report))
    print(f'Отчёт: {out / "report.json"}')
    return verdict['exit_code']


if __name__ == '__main__':
    sys.exit(main())
