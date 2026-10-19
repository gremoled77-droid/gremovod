"""Офлайн-проверки контракта `dev-run-summary/1`.

Сеть не используется. Проверяются формальные и смысловые правила контракта,
включая запрет на «успешный» статус при проваленных тестах.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.ai_review.contract import (  # noqa: E402
    CONTRACT_VERSION,
    ContractError,
    assert_valid,
    build_summary,
    validate_summary,
)


def good_summary(**overrides):
    summary = build_summary(
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
    summary.update(overrides)
    return summary


class ContractTest(unittest.TestCase):
    def test_valid_summary_passes(self):
        self.assertEqual(validate_summary(good_summary()), [])
        assert_valid(good_summary())

    def test_missing_required_field_is_reported(self):
        summary = good_summary()
        del summary["diff_sha256"]
        problems = validate_summary(summary)
        self.assertTrue(any("diff_sha256" in p for p in problems))

    def test_wrong_schema_version_is_rejected(self):
        problems = validate_summary(good_summary(schema_version="dev-run-summary/2"))
        self.assertTrue(any("schema_version" in p for p in problems))

    def test_pass_with_findings_is_rejected(self):
        summary = good_summary(
            review_status="PASS",
            findings=[{"severity": "P2", "file": "a.py", "evidence": "x"}],
        )
        problems = validate_summary(summary)
        self.assertTrue(any("PASS" in p for p in problems))

    def test_tests_fail_forbids_ai_pass(self):
        """CI FAIL несовместим с PASS от ИИ — Issue #27, офлайн-проверка #7."""
        summary = good_summary(tests_status="FAIL", review_status="PASS")
        problems = validate_summary(summary)
        self.assertTrue(any("tests_status=FAIL" in p for p in problems))

    def test_mock_mode_cannot_claim_usage_or_cost(self):
        problems = validate_summary(good_summary(provider_usage={"total_tokens": 10}))
        self.assertTrue(any("provider_usage" in p for p in problems))
        problems = validate_summary(good_summary(actual_cost={"amount": 1, "currency": "USD", "source": "PAYG"}))
        self.assertTrue(any("actual_cost" in p for p in problems))

    def test_unknown_enum_values_are_rejected(self):
        problems = validate_summary(good_summary(review_status="MAYBE"))
        self.assertTrue(any("review_status" in p for p in problems))

    def test_stale_review_requires_reviewed_sha(self):
        summary = good_summary(review_status="STALE_REVIEW", reviewed_sha=None)
        problems = validate_summary(summary)
        self.assertTrue(any("STALE_REVIEW" in p for p in problems))

    def test_blocked_status_requires_pending_decision(self):
        summary = good_summary(review_status="NOT_RUN", owner_decision="APPROVED")
        problems = validate_summary(summary)
        self.assertTrue(any("owner_decision" in p for p in problems))

    def test_bad_digest_is_rejected(self):
        problems = validate_summary(good_summary(diff_sha256="not-a-digest"))
        self.assertTrue(any("diff_sha256" in p for p in problems))

    def test_contract_error_carries_problems(self):
        with self.assertRaises(ContractError) as ctx:
            assert_valid(good_summary(schema_version="wrong"))
        self.assertTrue(ctx.exception.problems)

    def test_contract_version_is_stable(self):
        self.assertEqual(CONTRACT_VERSION, "dev-run-summary/1")


if __name__ == "__main__":
    unittest.main()
