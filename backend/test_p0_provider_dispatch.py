"""No paid operations may become active with incomplete P0 adapter policies."""
import unittest
from backend.p0_provider_dispatch import (
    DEFAULT_PROFILES, ProviderDisabled, plan_dispatch, lip_sync_dependency
)


class ProviderStageTests(unittest.TestCase):
    def test_four_separate_provider_operations_disabled(self):
        self.assertEqual(set(DEFAULT_PROFILES),{"tts","image","video_generation","lip_sync"})
        for name,profile in DEFAULT_PROFILES.items():
            self.assertFalse(profile.enabled)
            with self.assertRaises(ProviderDisabled):
                plan_dispatch(kind=name,mock_mode=False)

    def test_mock_runs_without_any_payment(self):
        for name in DEFAULT_PROFILES:
            result=plan_dispatch(kind=name,mock_mode=True)
            self.assertEqual((result["state"],result["provider_calls"],result["estimated_cost_cents"]),
                             ("MOCK_ONLY",0,0))

    def test_flag_and_fake_approval_cannot_enable_http(self):
        for name,profile in DEFAULT_PROFILES.items():
            with self.assertRaises(ProviderDisabled):
                plan_dispatch(kind=name,mock_mode=False,
                              verified_request_grant=True,provider_capability_verified=True,
                              cost_ceiling_known=True)

    def test_lipsync_is_separate_job(self):
        with self.assertRaises(ProviderDisabled):
            lip_sync_dependency(original_video_verified=False,original_provider_job_id=None,
                                approved_new_request=False,mock_mode=False)
        mock=lip_sync_dependency(original_video_verified=False,original_provider_job_id=None,
                                 approved_new_request=False,mock_mode=True)
        self.assertFalse(mock["regenerate_source_video"])

    def test_unknown_operation_rejected(self):
        with self.assertRaises(ProviderDisabled):
            plan_dispatch(kind="publish",mock_mode=True)


if __name__=="__main__":
    unittest.main()
