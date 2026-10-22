"""Тесты самого гейта BETA-02: вердикт, честность статусов, отчёт, отказ на сломанном продукте."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import beta_offline_acceptance as gate  # noqa: E402

COUNTS = {'tests': 5, 'failures': 0, 'errors': 0, 'skipped': 0}


def step(status, required=True, sid='x'):
    return {'id': sid, 'required': required, 'status': status}


class VerdictTests(unittest.TestCase):
    def test_required_fail_is_nonzero_and_no_go(self):
        verdict = gate.evaluate([step(gate.PASS), step(gate.FAIL, sid='bad')], True)
        self.assertEqual((verdict['technical_verdict'], verdict['exit_code'], verdict['release_verdict']), ('FAIL', 1, 'NO_GO'))
        self.assertEqual(verdict['unpaid_calls'], 'unknown')
        self.assertTrue(any('bad' in reason for reason in verdict['no_go_reasons']))

    def test_blocked_or_not_run_required_is_never_green(self):
        for status in (gate.BLOCKED, gate.NOT_RUN):
            verdict = gate.evaluate([step(gate.PASS), step(status)], True)
            self.assertEqual((verdict['technical_verdict'], verdict['exit_code']), ('BLOCKED', 2), status)

    def test_all_pass_is_still_no_go_and_zero_paid_calls_needs_the_tripwire(self):
        green = gate.evaluate([step(gate.PASS)], True)
        self.assertEqual((green['exit_code'], green['release_verdict'], green['unpaid_calls']), (0, 'NO_GO', 0))
        self.assertEqual(gate.evaluate([step(gate.PASS)], False)['unpaid_calls'], 'unknown')
        self.assertEqual(gate.evaluate([step(gate.PASS)], None)['unpaid_calls'], 'unknown')

    def test_optional_failure_does_not_decide_but_required_does(self):
        self.assertEqual(gate.evaluate([step(gate.PASS), step(gate.FAIL, required=False)], True)['exit_code'], 0)


class ClassifyTests(unittest.TestCase):
    def test_exit_codes_and_skips(self):
        self.assertEqual(gate.classify(0, COUNTS, False)[0], gate.PASS)
        self.assertEqual(gate.classify(1, {**COUNTS, 'failures': 1}, False)[0], gate.FAIL)
        self.assertEqual(gate.classify(0, {**COUNTS, 'skipped': 2}, False)[0], gate.BLOCKED)  # пропуск обязательного — не зелёный
        self.assertEqual(gate.classify(0, {**COUNTS, 'skipped': 2}, True)[0], gate.PASS)
        self.assertEqual(gate.classify(5, {**COUNTS, 'tests': 0}, False)[0], gate.BLOCKED)  # ничего не собрано
        self.assertEqual(gate.classify(0, {**COUNTS, 'tests': 0}, False)[0], gate.BLOCKED)
        self.assertEqual(gate.classify(0, COUNTS, False, missing=['a.py'])[0], gate.BLOCKED)

    def test_report_redacts_home_and_temp_paths(self):
        lines = gate.redact([f'{Path.home()}/secret/file.py failed', f'{ROOT}/backend/x.py', '/tmp/abc/def.sqlite3'])
        text = '\n'.join(lines)
        self.assertNotIn(str(Path.home()), text)
        self.assertIn('<repo>/backend/x.py', text)
        self.assertIn('<tmp>', text)


class EndToEndTests(unittest.TestCase):
    """Настоящий запуск гейта подпроцессом (медленно: десятки секунд)."""

    def run_gate(self, *extra, out):
        env = {key: value for key, value in os.environ.items() if key != 'BETA02_FAULT'}
        env['PIAPI_API_KEY'] = 'sk-canary0123456789abcdef'  # канарейка: не должна дойти ни до pytest, ни до отчёта
        done = subprocess.run([sys.executable, str(ROOT / 'tools' / 'beta_offline_acceptance.py'), '--quick', '--out', out,
                               '--timestamp', '2026-01-01T00:00:00Z', *extra], cwd=ROOT, env=env, capture_output=True, text=True)
        return done.returncode, json.loads((Path(out) / 'report.json').read_text(encoding='utf-8'))

    @unittest.skipUnless(os.environ.get('BETA02_SLOW') == '1', 'медленный: BETA02_SLOW=1')
    def test_fault_injection_b1_makes_the_gate_fail(self):
        with tempfile.TemporaryDirectory() as out:
            code, report = self.run_gate('--fault', 'b1', out=out)
        self.assertEqual(code, 1)
        self.assertEqual(report['technical_verdict'], 'FAIL')
        self.assertEqual(report['release_verdict'], 'NO_GO')
        self.assertEqual(report['unpaid_calls'], 'unknown')
        self.assertIn('integration-failclosed', [s['id'] for s in report['steps'] if s['status'] == 'FAIL'])

    @unittest.skipUnless(os.environ.get('BETA02_SLOW') == '1', 'медленный: BETA02_SLOW=1')
    def test_two_runs_give_the_same_outcome_and_a_clean_report(self):
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            code1, first = self.run_gate(out=one)
            code2, second = self.run_gate(out=two)
            text = (Path(one) / 'report.json').read_text(encoding='utf-8') + (Path(one) / 'report.md').read_text(encoding='utf-8')
        self.assertEqual(code1, code2)
        summary = lambda r: [(s['id'], s['status'], s['counts']) for s in r['steps']]  # noqa: E731
        self.assertEqual(summary(first), summary(second))
        for key in ('schema', 'timestamp', 'mode', 'provenance', 'steps', 'not_run', 'technical_verdict', 'release_verdict', 'exit_code', 'unpaid_calls', 'separation'):
            self.assertIn(key, first)
        self.assertNotIn(str(Path.home()), text)
        self.assertFalse(re.search(r'sk-[A-Za-z0-9]{8,}|studio_session|Bearer ', text))
        self.assertIn('PIAPI_API_KEY', first['environment']['secrets']['removed_env'])
        self.assertEqual([s['id'] for s in first['steps'][:2]], ['provenance', 'secrets-isolation'])
        self.assertEqual(first['dataset'], 'temp')


if __name__ == '__main__':
    unittest.main()
