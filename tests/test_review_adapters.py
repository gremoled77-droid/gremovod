"""Офлайн-проверки адаптеров ревьюера.

Сеть не используется: транспорт MiniMax подменяется заглушкой, которая
фиксирует, был ли отправлен запрос.
"""

import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.ai_review.adapters.argon_adapter import ArgonReviewer  # noqa: E402
from tools.ai_review.adapters.minimax_adapter import (  # noqa: E402
    CHAT_URL,
    MODEL,
    MiniMaxReviewer,
)
from tools.ai_review.adapters.mock_adapter import MockReviewer  # noqa: E402
from tools.ai_review.payload import build_payload  # noqa: E402
from tools.ai_review.reviewer import ReviewRequest, get_reviewer  # noqa: E402


def make_request(diff="--- a/x.py\n+++ b/x.py\n@@\n-x = 1\n+x = 2\n", mode="MOCK"):
    payload = build_payload(
        scope="Проверить изменение",
        files=["x.py"],
        diff=diff,
        diff_sha256="a" * 64,
        base_sha="b" * 40,
        head_sha="c" * 40,
        tests_status="PASS",
    )
    return ReviewRequest(
        task_id="T-1",
        run_id="R-1",
        scope="Проверить изменение",
        mode=mode,
        base_sha="b" * 40,
        head_sha="c" * 40,
        diff_sha256="a" * 64,
        files=["x.py"],
        diff=diff,
        tests_status="PASS",
        payload=payload,
    )


class RecordingTransport:
    """Заглушка транспорта: запоминает вызовы и возвращает заданный ответ."""

    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def __call__(self, url, body, api_key):
        self.calls.append((url, body, api_key))
        if self.error is not None:
            raise self.error
        return self.response


class MockAdapterTest(unittest.TestCase):
    def test_clean_diff_passes(self):
        outcome = MockReviewer().review(make_request())
        self.assertEqual(outcome.status, "PASS")
        self.assertEqual(outcome.findings, [])

    def test_shell_true_is_p1(self):
        diff = "--- a/x.py\n+++ b/x.py\n@@\n+subprocess.run(cmd, shell=True)\n"
        outcome = MockReviewer().review(make_request(diff=diff))
        self.assertEqual(outcome.status, "FINDINGS")
        self.assertEqual(outcome.findings[0]["severity"], "P1")

    def test_mock_never_reports_usage(self):
        outcome = MockReviewer().review(make_request())
        self.assertIsNone(outcome.usage)

    def test_mock_is_deterministic(self):
        diff = "--- a/x.py\n+++ b/x.py\n@@\n+eval(user_input)\n"
        first = MockReviewer().review(make_request(diff=diff))
        second = MockReviewer().review(make_request(diff=diff))
        self.assertEqual(first.status, second.status)
        self.assertEqual(first.findings, second.findings)


class MiniMaxGateTest(unittest.TestCase):
    """Ни один живой запрос не должен уйти без всех ворот."""

    def test_mock_mode_never_calls_transport(self):
        transport = RecordingTransport(response={})
        reviewer = MiniMaxReviewer(api_key="k", transport=transport)
        outcome = reviewer.review(make_request(mode="MOCK"))
        self.assertEqual(outcome.status, "NOT_RUN")
        self.assertEqual(transport.calls, [])

    def test_live_without_consent_is_blocked(self):
        transport = RecordingTransport(response={})
        reviewer = MiniMaxReviewer(api_key="k", consent=False, transport=transport)
        outcome = reviewer.review(make_request(mode="LIVE"))
        self.assertEqual(outcome.status, "NOT_RUN")
        self.assertEqual(transport.calls, [])

    def test_live_after_deadline_is_blocked(self):
        transport = RecordingTransport(response={})
        reviewer = MiniMaxReviewer(
            api_key="k",
            consent=True,
            transport=transport,
            now=dt.datetime(2026, 10, 26, tzinfo=dt.timezone.utc),
        )
        outcome = reviewer.review(make_request(mode="LIVE"))
        self.assertEqual(outcome.status, "NOT_RUN")
        self.assertIn("SUBSCRIPTION_EXPIRED", outcome.blocked_reason or "")
        self.assertEqual(transport.calls, [])

    def test_live_without_credential_is_blocked(self):
        transport = RecordingTransport(response={})
        reviewer = MiniMaxReviewer(api_key="", consent=True, transport=transport)
        outcome = reviewer.review(make_request(mode="LIVE"))
        self.assertEqual(outcome.status, "NOT_RUN")
        self.assertEqual(transport.calls, [])

    def test_live_without_quota_snapshot_is_blocked(self):
        transport = RecordingTransport(response={})
        reviewer = MiniMaxReviewer(api_key="k", consent=True, quota_snapshot=None, transport=transport)
        outcome = reviewer.review(make_request(mode="LIVE"))
        self.assertEqual(outcome.status, "NOT_RUN")
        self.assertEqual(transport.calls, [])


class MiniMaxResponseTest(unittest.TestCase):
    def make(self, response=None, error=None, quota_remaining=50.0):
        from tools.ai_review import quota

        snapshot = quota.QuotaSnapshot(
            source=quota.MINIMAX_QUOTA_URL,
            checked_at="2026-10-20T10:00:00+00:00",
            window_5h_remaining=quota_remaining,
            window_5h_limit=100.0,
            weekly_remaining=500.0,
            weekly_limit=1000.0,
            recognized=True,
        )
        transport = RecordingTransport(response=response, error=error)
        reviewer = MiniMaxReviewer(
            api_key="k",
            consent=True,
            quota_snapshot=snapshot,
            transport=transport,
            now=dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc),
        )
        return reviewer, transport

    def test_valid_pass_response(self):
        response = {
            "choices": [{"message": {"content": '{"status":"PASS","findings":[]}'}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        reviewer, transport = self.make(response)
        outcome = reviewer.review(make_request(mode="LIVE"))
        self.assertEqual(outcome.status, "PASS")
        self.assertEqual(outcome.usage["total_tokens"], 15)
        self.assertEqual(len(transport.calls), 1)
        url, body, key = transport.calls[0]
        self.assertEqual(url, CHAT_URL)
        self.assertEqual(body["model"], MODEL)
        self.assertEqual(body["thinking"], {"type": "adaptive"})
        self.assertEqual(body["stream"], False)
        self.assertEqual(key, "k")

    def test_findings_response(self):
        raw = (
            '{"status":"FINDINGS","findings":[{"severity":"P2","file":"x.py","line":1,'
            '"evidence":"e","reproduction":"r","fix":"f"}]}'
        )
        reviewer, _transport = self.make({"choices": [{"message": {"content": raw}}]})
        outcome = reviewer.review(make_request(mode="LIVE"))
        self.assertEqual(outcome.status, "FINDINGS")
        self.assertEqual(outcome.findings[0]["file"], "x.py")

    def test_unparsable_content_is_uncertain(self):
        reviewer, _transport = self.make({"choices": [{"message": {"content": "просто текст"}}]})
        outcome = reviewer.review(make_request(mode="LIVE"))
        self.assertEqual(outcome.status, "UNCERTAIN")

    def test_insufficient_balance_maps_to_quota_exhausted(self):
        reviewer, _transport = self.make({"base_resp": {"status_code": 1008, "status_msg": "no balance"}})
        outcome = reviewer.review(make_request(mode="LIVE"))
        self.assertEqual(outcome.status, "QUOTA_EXHAUSTED")

    def test_rate_limit_maps_to_api_error(self):
        reviewer, _transport = self.make({"base_resp": {"status_code": 1002, "status_msg": "rate limit"}})
        outcome = reviewer.review(make_request(mode="LIVE"))
        self.assertEqual(outcome.status, "API_ERROR")

    def test_transport_failure_maps_to_api_error_without_retry(self):
        reviewer, transport = self.make(error=OSError("network down"))
        outcome = reviewer.review(make_request(mode="LIVE"))
        self.assertEqual(outcome.status, "API_ERROR")
        self.assertEqual(len(transport.calls), 1)

    def test_exhausted_quota_blocks_before_transport(self):
        from tools.ai_review import quota

        snapshot = quota.QuotaSnapshot(
            source=quota.MINIMAX_QUOTA_URL,
            checked_at="2026-10-20T10:00:00+00:00",
            window_5h_remaining=0.0,
            window_5h_limit=100.0,
            weekly_remaining=500.0,
            weekly_limit=1000.0,
            recognized=True,
        )
        transport = RecordingTransport(response={})
        reviewer = MiniMaxReviewer(
            api_key="k",
            consent=True,
            quota_snapshot=snapshot,
            transport=transport,
            now=dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc),
        )
        outcome = reviewer.review(make_request(mode="LIVE"))
        self.assertEqual(outcome.status, "QUOTA_EXHAUSTED")
        self.assertEqual(transport.calls, [])


class ArgonAdapterTest(unittest.TestCase):
    def test_mock_mode_is_not_run(self):
        outcome = ArgonReviewer(api_key="k").review(make_request(mode="MOCK"))
        self.assertEqual(outcome.status, "NOT_RUN")

    def test_live_requires_consent(self):
        outcome = ArgonReviewer(api_key="k", consent=False, live=True).review(make_request(mode="LIVE"))
        self.assertEqual(outcome.status, "NOT_RUN")


class RegistryTest(unittest.TestCase):
    def test_registry_maps_names(self):
        self.assertEqual(get_reviewer("mock").name, "mock")
        self.assertEqual(get_reviewer("minimax").name, "minimax")
        self.assertEqual(get_reviewer("argon").name, "argon")

    def test_unknown_provider_raises(self):
        with self.assertRaises(ValueError):
            get_reviewer("unknown")

    def test_registry_is_case_insensitive(self):
        self.assertEqual(get_reviewer("MOCK").name, "mock")


if __name__ == "__main__":
    unittest.main()
