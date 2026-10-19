"""BETA Gateway-only workflow security smoke; no network/API calls."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent
W=json.loads((ROOT/"workflows/BETA_001_Gateway_Gemini.json").read_text(encoding="utf8"))
POLICY=json.loads((ROOT/"BUDGET_POLICY.json").read_text(encoding="utf8"))


class BetaSafety(unittest.TestCase):
    def test_one_manual_trigger_one_gateway_model(self):
        nodes=W["nodes"]
        types=[x["type"] for x in nodes]
        self.assertFalse(W["active"])
        self.assertEqual(len(nodes),4)
        self.assertEqual(types.count("n8n-nodes-base.manualTrigger"),1)
        self.assertEqual(types.count("@n8n/n8n-nodes-langchain.googleGemini"),1)
        self.assertEqual(types.count("n8n-nodes-base.code"),2)
        self.assertEqual(len(set(x["name"] for x in nodes)),4)

    def test_no_provider_credentials_or_external_network_nodes(self):
        self.assertTrue(all("credentials" not in n for n in W["nodes"]))
        self.assertFalse(any(n["type"] in ("n8n-nodes-base.httpRequest","n8n-nodes-base.scheduleTrigger") for n in W["nodes"]))
        self.assertFalse(W.get("pinData"))

    def test_manual_balance_check_blocks_by_default(self):
        gate=next(n for n in W["nodes"] if n["name"].startswith("01"))
        code=gate["parameters"]["jsCode"]
        self.assertIn("observedGatewayBalanceUsd=null",code)
        self.assertIn("BETA_PRE_FLIGHT_BLOCKED",code)
        self.assertIn("BETA_STOP_GATEWAY_CREDIT_RESERVE",code)
        self.assertIn("observedBalanceTime=null",code)
        self.assertIn("minReserveUsd=1",code)
        self.assertIn("safetyMarginUsd=0.25",code)
        self.assertIn("perCallBudgetCeilingUsd=0.10",code)

    def test_gateway_model_is_bounded(self):
        m=next(n for n in W["nodes"] if "googleGemini" in n["type"])
        self.assertEqual(m["parameters"]["modelId"]["value"],"models/gemini-3-flash-preview")
        self.assertLessEqual(m["parameters"]["options"]["maxOutputTokens"],256)
        self.assertEqual(m["parameters"]["options"]["thinkingBudget"],0)
        self.assertFalse(m["parameters"]["builtInTools"]["googleSearch"])
        self.assertFalse(m["parameters"]["builtInTools"]["urlContext"])

    def test_budget_keeps_dollar_and_requires_manual_balance(self):
        self.assertEqual(POLICY["min_target_reserve_usd"],1)
        self.assertEqual(POLICY["recommended_stop_threshold_usd"],1.25)
        self.assertIsNone(POLICY["current_verified_gateway_balance_usd"])
        self.assertTrue(POLICY["manual_balance_verification_required"])
        self.assertFalse(POLICY["automatic_switch_to_own_api"])
        self.assertFalse(POLICY["external_credentials_allowed"])
        self.assertFalse(POLICY["auto_retry"])
        self.assertFalse(POLICY["auto_top_up"])


if __name__=="__main__":
    unittest.main()
