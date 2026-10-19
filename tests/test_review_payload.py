"""Офлайн-проверки материала ревью: независимый контекст, разбор ответа, секреты."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.ai_review import localscan  # noqa: E402
from tools.ai_review.payload import (  # noqa: E402
    MAX_PAYLOAD_BYTES,
    build_payload,
    parse_review_response,
)


class PayloadTest(unittest.TestCase):
    def build(self, diff="--- a/x.py\n+++ b/x.py\n@@\n-x = 1\n+x = 2\n"):
        return build_payload(
            scope="Проверить арифметику",
            files=["x.py"],
            diff=diff,
            diff_sha256="a" * 64,
            base_sha="b" * 40,
            head_sha="c" * 40,
            tests_status="PASS",
        )

    def test_payload_has_system_and_user_messages(self):
        payload = self.build()
        roles = [m["role"] for m in payload["messages"]]
        self.assertEqual(roles, ["system", "user"])

    def test_payload_carries_scope_diff_and_tests(self):
        payload = self.build()
        user = payload["messages"][1]["content"]
        self.assertIn("Проверить арифметику", user)
        self.assertIn("x = 2", user)
        self.assertIn("PASS", user)

    def test_payload_has_no_tools_and_no_credentials(self):
        payload = self.build()
        blob = " ".join(m["content"] for m in payload["messages"])
        for forbidden in ("Authorization", "Bearer ", "api_key", "password", "minimax_subscription_key"):
            self.assertNotIn(forbidden, blob.lower())

    def test_payload_rejects_oversized_diff(self):
        with self.assertRaises(ValueError):
            self.build(diff="+" * (MAX_PAYLOAD_BYTES + 10))

    def test_payload_records_prompt_size(self):
        payload = self.build()
        self.assertGreater(payload["prompt_bytes"], 0)


class ResponseParsingTest(unittest.TestCase):
    def test_valid_pass(self):
        status, findings, error = parse_review_response('{"status":"PASS","findings":[]}')
        self.assertEqual(status, "PASS")
        self.assertEqual(findings, [])
        self.assertIsNone(error)

    def test_valid_findings(self):
        raw = (
            '{"status":"FINDINGS","findings":[{"severity":"P1","file":"x.py","line":3,'
            '"evidence":"e","reproduction":"r","fix":"f"}]}'
        )
        status, findings, error = parse_review_response(raw)
        self.assertEqual(status, "FINDINGS")
        self.assertEqual(findings[0]["severity"], "P1")
        self.assertIsNone(error)

    def test_markdown_fence_is_tolerated(self):
        raw = '```json\n{"status":"PASS","findings":[]}\n```'
        status, _findings, error = parse_review_response(raw)
        self.assertEqual(status, "PASS")
        self.assertIsNone(error)

    def test_invalid_json_is_uncertain(self):
        status, _findings, error = parse_review_response("не json вовсе")
        self.assertEqual(status, "UNCERTAIN")
        self.assertTrue(error)

    def test_empty_answer_is_uncertain(self):
        status, _findings, _error = parse_review_response("")
        self.assertEqual(status, "UNCERTAIN")

    def test_pass_with_findings_is_uncertain(self):
        raw = '{"status":"PASS","findings":[{"severity":"P1","file":"x.py","evidence":"e"}]}'
        status, _findings, error = parse_review_response(raw)
        self.assertEqual(status, "UNCERTAIN")
        self.assertTrue(error)

    def test_unknown_status_is_uncertain(self):
        status, _findings, _error = parse_review_response('{"status":"MAYBE","findings":[]}')
        self.assertEqual(status, "UNCERTAIN")

    def test_unknown_severity_is_uncertain(self):
        raw = '{"status":"FINDINGS","findings":[{"severity":"P9","file":"x.py","evidence":"e"}]}'
        status, _findings, _error = parse_review_response(raw)
        self.assertEqual(status, "UNCERTAIN")

    def test_findings_without_list_is_uncertain(self):
        status, _findings, _error = parse_review_response('{"status":"PASS","findings":{}}')
        self.assertEqual(status, "UNCERTAIN")


class RedactionTest(unittest.TestCase):
    def test_secret_is_masked(self):
        text = "api_key = 'AKIAIOSFODNN7EXAMPLEKEY'"
        masked = localscan.redact_secrets(text)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLEKEY", masked)
        self.assertIn("[REDACTED]", masked)

    def test_clean_text_is_untouched(self):
        text = "value = 42"
        self.assertEqual(localscan.redact_secrets(text), text)


if __name__ == "__main__":
    unittest.main()
