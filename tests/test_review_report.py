"""Офлайн-проверки отчёта: неизвестное значение не превращается в «успех»."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.ai_review.contract import build_summary  # noqa: E402
from tools.ai_review.report import (  # noqa: E402
    NOT_CONFIRMED,
    NOT_SPECIFIED,
    render_report,
    render_short_summary,
)


def summary(**overrides):
    data = build_summary(
        task_id="T-27",
        run_id="R-27",
        provider="mock",
        mode="MOCK",
        base_sha="a" * 40,
        head_sha="b" * 40,
        diff_sha256="c" * 64,
        branch="experiment/minimax-observability-20261020",
        scope="Проверка контракта",
        code_changes=["tools/ai_review/contract.py"],
        tests_status="PASS",
        review_status="PASS",
    )
    data.update(overrides)
    return data


class ReportTest(unittest.TestCase):
    def test_all_sections_present(self):
        text = render_report(summary())
        for heading in (
            "## 1. Задача",
            "## 2. Что менялось",
            "## 3. Тесты",
            "## 4. Результат ревью",
            "## 5. Квота и расход",
            "## 6. Ссылки",
            "## 7. Решение владельца",
        ):
            self.assertIn(heading, text)

    def test_missing_scope_is_marked_not_specified(self):
        text = render_report(summary(scope=None))
        self.assertIn(NOT_SPECIFIED, text)

    def test_missing_quota_and_cost_are_not_confirmed(self):
        text = render_report(summary())
        self.assertIn(NOT_CONFIRMED, text)

    def test_findings_are_rendered(self):
        data = summary(
            review_status="FINDINGS",
            findings=[
                {
                    "severity": "P1",
                    "file": "x.py",
                    "line": 12,
                    "evidence": "shell=True",
                    "reproduction": "вызов",
                    "fix": "убрать",
                }
            ],
        )
        text = render_report(data)
        self.assertIn("shell=True", text)
        self.assertIn("x.py", text)

    def test_report_warns_that_code_change_is_not_n8n_update(self):
        text = render_report(summary())
        self.assertIn("не означает", text)

    def test_short_summary_has_table_with_findings(self):
        data = summary(
            review_status="FINDINGS",
            findings=[{"severity": "P2", "file": "x.py", "evidence": "bug"}],
        )
        text = render_short_summary(data)
        self.assertIn("| Severity |", text)
        self.assertIn("x.py", text)

    def test_short_summary_without_findings_is_compact(self):
        text = render_short_summary(summary())
        self.assertNotIn("| Severity |", text)
        self.assertIn("Режим", text)


if __name__ == "__main__":
    unittest.main()
