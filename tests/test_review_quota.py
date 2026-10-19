"""Офлайн-проверки охранника квоты M Plan и отсечки 25.10.2026.

Сеть не используется: transport остатка квоты подменяется заглушкой.
"""

import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.ai_review import quota  # noqa: E402


def snapshot_with(remaining_5h=100.0, remaining_week=1000.0, recognized=True):
    return quota.QuotaSnapshot(
        source=quota.MINIMAX_QUOTA_URL,
        checked_at="2026-10-20T10:00:00+00:00",
        window_5h_remaining=remaining_5h,
        window_5h_limit=200.0,
        weekly_remaining=remaining_week,
        weekly_limit=2000.0,
        recognized=recognized,
    )


class ExpiryTest(unittest.TestCase):
    def test_before_deadline_is_allowed(self):
        now = dt.datetime(2026, 10, 20, 12, 0, tzinfo=dt.timezone.utc)
        decision = quota.check_expiry(now=now)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.code, quota.STOP_OK)

    def test_after_deadline_is_blocked(self):
        now = dt.datetime(2026, 10, 25, 0, 0, tzinfo=dt.timezone.utc)
        decision = quota.check_expiry(now=now)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, quota.STOP_EXPIRED)

    def test_deadline_matches_issue_27(self):
        self.assertEqual(quota.MINIMAX_SUBSCRIPTION_EXPIRES_AT, "2026-10-25T00:00:00+03:00")


class QuotaParseTest(unittest.TestCase):
    def test_recognizes_known_shape(self):
        payload = {
            "plan": "M Plan",
            "remains": [{"model": "MiniMax-M3.1-Flash", "remain_5h": 42, "remain_week": 4200}],
        }
        snapshot = quota.parse_quota_payload(payload)
        self.assertTrue(snapshot.recognized)
        self.assertEqual(snapshot.window_5h_remaining, 42.0)
        self.assertEqual(snapshot.weekly_remaining, 4200.0)

    def test_unrecognized_shape_fails_closed(self):
        snapshot = quota.parse_quota_payload({"something": "else"})
        self.assertFalse(snapshot.recognized)

    def test_non_object_payload_fails_closed(self):
        snapshot = quota.parse_quota_payload(["unexpected"])
        self.assertFalse(snapshot.recognized)

    def test_fetch_quota_uses_injected_transport(self):
        calls = []

        def transport(url, key):
            calls.append((url, key))
            return {"remain_5h": 10, "remain_week": 100}

        snapshot = quota.fetch_quota("test-key", transport=transport)
        self.assertTrue(snapshot.recognized)
        self.assertEqual(calls[0][0], quota.MINIMAX_QUOTA_URL)

    def test_fetch_quota_transport_error_is_unknown(self):
        def transport(url, key):
            raise OSError("network down")

        snapshot = quota.fetch_quota("test-key", transport=transport)
        self.assertFalse(snapshot.recognized)
        self.assertEqual(snapshot.window_5h_remaining, None)


class QuotaEvaluationTest(unittest.TestCase):
    def test_exhausted_five_hour_window_blocks(self):
        decision = quota.evaluate_quota(snapshot_with(remaining_5h=0))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, quota.STOP_QUOTA_EXHAUSTED)

    def test_exhausted_weekly_window_blocks(self):
        decision = quota.evaluate_quota(snapshot_with(remaining_week=0))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, quota.STOP_QUOTA_EXHAUSTED)

    def test_unknown_shape_blocks(self):
        decision = quota.evaluate_quota(snapshot_with(recognized=False))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, quota.STOP_QUOTA_UNKNOWN)

    def test_healthy_quota_allows(self):
        decision = quota.evaluate_quota(snapshot_with())
        self.assertTrue(decision.allowed)


class PreflightTest(unittest.TestCase):
    """Порядок проверок закрыт по умолчанию: любое сомнение = стоп."""

    def base(self, **overrides):
        kwargs = dict(
            mode="LIVE",
            provider="minimax",
            consent=True,
            credential_present=True,
            now=dt.datetime(2026, 10, 20, 12, 0, tzinfo=dt.timezone.utc),
            quota=snapshot_with(),
        )
        kwargs.update(overrides)
        return quota.preflight(**kwargs)

    def test_all_gates_pass(self):
        decision = self.base()
        self.assertTrue(decision.allowed)

    def test_expired_blocks_first(self):
        decision = self.base(now=dt.datetime(2026, 10, 26, 0, 0, tzinfo=dt.timezone.utc))
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, quota.STOP_EXPIRED)

    def test_missing_consent_blocks(self):
        decision = self.base(consent=False)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, quota.STOP_NO_CONSENT)

    def test_mock_mode_blocks_network(self):
        decision = self.base(mode="MOCK")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, quota.STOP_WRONG_MODE)

    def test_missing_credential_blocks(self):
        decision = self.base(credential_present=False)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, quota.STOP_CREDENTIAL_MISSING)

    def test_missing_quota_blocks(self):
        decision = self.base(quota=None)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, quota.STOP_QUOTA_UNKNOWN)

    def test_unknown_provider_blocks(self):
        decision = self.base(provider="something-else")
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.code, quota.STOP_PROVIDER_NOT_ALLOWED)


if __name__ == "__main__":
    unittest.main()
