"""Origin of the signing key (P0-ASTRA finding 2).

The audit asked for one thing here: the origin of the key, the authority that
issues a capability and the binding to the actual request must be traceable,
and a missing key must block BOTH issuing and execution.

Only a temporary SQLite! No real Studio DB, n8n workflow or paid API call.
"""
import os
import unittest
from unittest.mock import patch

from backend import p0_authz


KEY_A = "test-signing-key-a"
KEY_B = "test-signing-key-b"


class SigningKeyOriginTests(unittest.TestCase):
    def test_missing_key_blocks_issuing_and_execution(self):
        """Without a key there is no capability at all - not a weaker one."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop(p0_authz.ENV_KEY, None)
            os.environ.pop(p0_authz.ENV_ALLOW_EPHEMERAL, None)
            with self.assertRaises(p0_authz.AuthzError) as ctx:
                p0_authz.mint("envelope", {"run_id": "r1"})
            self.assertIn(p0_authz.ENV_KEY, str(ctx.exception))
            # execution is blocked as well: there is nothing to verify against
            with self.assertRaises(p0_authz.AuthzError):
                p0_authz.verify("body.signature", purpose="envelope", binding={"run_id": "r1"})

    def test_ephemeral_mode_must_be_requested_explicitly(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop(p0_authz.ENV_KEY, None)
            os.environ.pop(p0_authz.ENV_ALLOW_EPHEMERAL, None)
            with self.assertRaises(p0_authz.AuthzError):
                p0_authz.mint("envelope", {"run_id": "r1"})
            p0_authz.allow_ephemeral_key()
            token = p0_authz.mint("envelope", {"run_id": "r1"})
            self.assertTrue(p0_authz.verify(token, purpose="envelope", binding={"run_id": "r1"}))

    def test_capability_carries_the_key_that_issued_it(self):
        with patch.dict(os.environ, {p0_authz.ENV_KEY: KEY_A}, clear=True):
            token = p0_authz.mint("envelope", {"run_id": "r1"})
            payload = p0_authz.verify(token, purpose="envelope", binding={"run_id": "r1"})
            self.assertEqual(payload["kid"], p0_authz.key_id())

    def test_a_capability_from_another_key_is_a_deployment_fault_not_a_forgery(self):
        """A worker must not look like an attacker when the key is not shared."""
        with patch.dict(os.environ, {p0_authz.ENV_KEY: KEY_A}, clear=True):
            token = p0_authz.mint("envelope", {"run_id": "r1"})
        with patch.dict(os.environ, {p0_authz.ENV_KEY: KEY_B}, clear=True):
            with self.assertRaises(p0_authz.AuthzError) as ctx:
                p0_authz.verify(token, purpose="envelope", binding={"run_id": "r1"})
            message = str(ctx.exception)
            self.assertIn("different signing key", message)
            self.assertNotIn("signature is not valid", message)

    def test_binding_and_purpose_still_apply_with_a_shared_key(self):
        with patch.dict(os.environ, {p0_authz.ENV_KEY: KEY_A}, clear=True):
            token = p0_authz.mint("request", {"job_id": "j1", "request_sha": "sha"})
            with self.assertRaises(p0_authz.AuthzError):
                p0_authz.verify(token, purpose="envelope", binding={"job_id": "j1", "request_sha": "sha"})
            with self.assertRaises(p0_authz.AuthzError):
                p0_authz.verify(token, purpose="request", binding={"job_id": "j2", "request_sha": "sha"})

    def test_settlement_facts_are_refused_from_the_caller(self):
        p0_authz.reject_caller_settlement({})
        for field in ("charged_cents", "provider_success", "provider_job_id"):
            with self.assertRaises(p0_authz.AuthzError) as ctx:
                p0_authz.reject_caller_settlement({field: 1})
            self.assertIn(field, str(ctx.exception))

    def test_reconcile_capability_is_bound_to_one_obligation(self):
        with patch.dict(os.environ, {p0_authz.ENV_KEY: KEY_A}, clear=True):
            token = p0_authz.mint_reconcile_capability("j1", obligation_id="j1:event1")
            p0_authz.verify(token, purpose="reconcile",
                            binding={"job_id": "j1", "obligation_id": "j1:event1"})
            with self.assertRaises(p0_authz.AuthzError):
                p0_authz.verify(token, purpose="reconcile",
                                binding={"job_id": "j1", "obligation_id": "j1:event2"})


if __name__ == "__main__":
    unittest.main()
