import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / 'docs' / 'HANDOFF_MINIMAX_LLM_GATEWAY.md'
REPORT = ROOT / 'docs' / 'LLM_GATEWAY_TEST_REPORT.md'
FRONTEND = ROOT / 'frontend'


def backend_suite_size() -> int:
    """Сколько тестов в бэкенд-наборе: столько же, сколько показывает unittest discover."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    suite = unittest.TestLoader().discover(str(ROOT / 'backend'), pattern='test_*.py',
                                           top_level_dir=str(ROOT / 'backend'))
    return suite.countTestCases()


def frontend_test_count() -> int:
    """Сколько тестов во фронтенд-наборе: вызовы test( в файлах *.test.mjs (без node_modules)."""
    total = 0
    for path in sorted(FRONTEND.rglob('*.test.mjs')):
        if 'node_modules' in path.parts:
            continue
        for line in path.read_text(encoding='utf-8').splitlines():
            if re.match(r'\s*test\(', line):
                total += 1
    return total


class DocsNumbersTests(unittest.TestCase):
    """Числа прогонов в документах — фактические: сверка с самим набором тестов.

    Документация про прогоны — часть сборки: расхождение с фактом ловится здесь,
    а не на приёмке.
    """

    def test_backend_test_count_in_docs_is_the_actual_one(self):
        count = backend_suite_size()
        handoff = HANDOFF.read_text(encoding='utf-8')
        report = REPORT.read_text(encoding='utf-8')
        self.assertIn(f'Ran {count} tests', handoff)
        self.assertIn(f'Ran {count} tests', report)
        self.assertIn(f'{count} тестов', report)
        # прошлая строка прогона в документах не остаётся строкой текущего прогона
        self.assertNotIn('Ran 359 tests', handoff)
        self.assertNotIn('Ran 359 tests in', report)

    def test_frontend_test_count_in_docs_is_the_actual_one(self):
        count = frontend_test_count()
        handoff = HANDOFF.read_text(encoding='utf-8')
        report = REPORT.read_text(encoding='utf-8')
        self.assertIn(f'pass {count}', handoff)
        self.assertIn(f'pass {count}', report)


if __name__ == '__main__':
    unittest.main()
