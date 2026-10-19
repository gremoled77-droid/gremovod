"""Offline regression tests for the Argon budget gate. Never contacts KIE.

Every provider call in this file is a local fake. The gate is driven through
its injected `provider` and `credits_reader` seams, so the whole suite runs
with no key, no socket and no credits.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "ai_review"))

import argon_review  # noqa: E402
import build_review_packet as packets  # noqa: E402
import review_gate  # noqa: E402

PR_URL = "https://github.com/gremoled77-droid/gremovod/pull/999"
FAKE_KEY = "unit-test-key-not-a-real-credential"
# Built at runtime on purpose: a credential-shaped literal in this file would
# trip the secret guard on the repository's own diff.
FAKE_SECRET = "sk-" + "abcdefghijklmno123456"


def git(path, *args):
    return subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, encoding="utf-8")


class FakeProvider:
    """Stand-in for argon_review.ask_argon_detailed."""

    def __init__(self, content=None, error=None, credits=1.5, delay=0.0):
        self.content = content
        self.error = error
        self.credits = credits
        self.delay = delay
        self.calls = []
        self._lock = threading.Lock()

    def __call__(self, messages, key):
        with self._lock:
            self.calls.append({"messages": messages, "key": key})
        if self.delay:
            time.sleep(self.delay)
        if self.error is not None:
            raise self.error
        return {
            "content": self.content if self.content is not None else '{"verdict":"PASS"}',
            "credits_consumed": self.credits,
            "usage": {"total_tokens": 10},
            "http_status": 200,
            "raw": {},
        }

    @property
    def call_count(self):
        with self._lock:
            return len(self.calls)


class FakeCredits:
    """Stand-in for argon_review.fetch_credits.

    Without explicit values it starts at 100 credits and drops by `charge`
    after every read, so a normal call looks like a normal charge.
    """

    def __init__(self, *values, charge=1.5):
        self.values = list(values)
        self.charge = charge
        self.calls = 0
        self._lock = threading.Lock()

    def __call__(self, key):
        with self._lock:
            self.calls += 1
            if self.values:
                index = min(self.calls - 1, len(self.values) - 1)
                return self.values[index]
            return 100.0 - self.charge * (self.calls - 1)

    @property
    def call_count(self):
        with self._lock:
            return self.calls


class FixedCredits:
    """Balance reader that never moves. Used where thread order must not matter."""

    def __init__(self, value=100.0):
        self.value = value
        self.calls = 0
        self._lock = threading.Lock()

    def __call__(self, key):
        with self._lock:
            self.calls += 1
            return self.value

    @property
    def call_count(self):
        with self._lock:
            return self.calls


def live_policy(**overrides):
    values = dict(
        max_calls_per_pr=1,
        max_calls_per_day=2,
        max_calls_per_week=5,
        max_concurrent=1,
        max_packet_bytes=6144,
        max_packet_files=4,
        retry_count=0,
        max_kie_credits_per_day=100.0,
        max_kie_credits_per_call=10.0,
        min_kie_balance=5.0,
        credit_delta_tolerance=1.0,
    )
    values.update(overrides)
    return review_gate.Policy(**values)


class GateTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)

        self.repo = base / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "user.email", "test@example.org")
        (self.repo / "p0_authz.py").write_text("def check():\n    return True\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "base")
        self.base_sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()

        self.state = base / "state"
        self.state.mkdir()
        self.now = review_gate.dt.datetime(2026, 10, 20, 12, 0, 0, tzinfo=review_gate.dt.timezone.utc)

    def change(self, text="def check():\n    return False  # bypass\n", name="p0_authz.py"):
        (self.repo / name).write_text(text, encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "change")
        return git(self.repo, "rev-parse", "HEAD").stdout.strip()

    def approval(self, head_sha, pr=PR_URL, approved=True, name="approval.json"):
        if head_sha and len(head_sha) != 40:
            head_sha = git(self.repo, "rev-parse", head_sha).stdout.strip()
        path = self.state / name
        path.write_text(json.dumps({"approved": approved, "pr": pr, "head_sha": head_sha}),
                        encoding="utf-8")
        return path

    def run_gate(self, **overrides):
        params = dict(
            repo=self.repo,
            base=self.base_sha,
            head="HEAD",
            pr_url=PR_URL,
            task_id="P0-AUTH",
            scope="Check the capability check",
            mode="live",
            policy=live_policy(),
            state_dir=self.state,
            provider=FakeProvider(),
            credits_reader=FakeCredits(),
            api_key=FAKE_KEY,
            now=self.now,
        )
        params.update(overrides)
        return review_gate.run(**params)

    def ledger_entries(self):
        return review_gate.Ledger(self.state / "ledger.json").entries()


# --------------------------------------------------------------------------- offline


class OfflineDefaultsTest(GateTestCase):
    def test_offline_is_the_default_and_makes_no_network_call(self):
        self.change()
        provider = FakeProvider()
        credits = FakeCredits()
        outcome = review_gate.run(
            repo=self.repo, base=self.base_sha, head="HEAD", pr_url=PR_URL, task_id="T",
            scope="s", mode="offline", state_dir=self.state, provider=provider,
            credits_reader=credits, api_key=FAKE_KEY, now=self.now,
        )
        self.assertEqual(outcome["status"], review_gate.STATUS_OFFLINE)
        self.assertEqual(outcome["network_calls"], 0)
        self.assertEqual(provider.call_count, 0)
        self.assertEqual(credits.call_count, 0)
        self.assertEqual(self.ledger_entries(), [])

    def test_offline_writes_the_packet_snapshot_locally(self):
        self.change()
        review_gate.run(repo=self.repo, base=self.base_sha, head="HEAD", pr_url=PR_URL,
                        task_id="T", scope="s", mode="offline", state_dir=self.state,
                        provider=FakeProvider(), api_key=FAKE_KEY, now=self.now)
        snapshots = list((self.state / "packets").glob("*.json"))
        self.assertEqual(len(snapshots), 1)
        packet = json.loads(snapshots[0].read_text(encoding="utf-8"))
        self.assertEqual(packet["head_sha"], git(self.repo, "rev-parse", "HEAD").stdout.strip())
        self.assertTrue(packet["hunks"])

    def test_report_is_written_offline(self):
        self.change()
        outcome = review_gate.run(repo=self.repo, base=self.base_sha, head="HEAD", pr_url=PR_URL,
                                  task_id="T", scope="s", mode="offline", state_dir=self.state,
                                  provider=FakeProvider(), api_key=FAKE_KEY, now=self.now)
        report = review_gate.render_report(outcome)
        self.assertIn("Status: **OFFLINE**", report)
        self.assertNotIn("sk-", report)


# --------------------------------------------------------------------------- packet


class PacketTest(GateTestCase):
    def test_packet_is_bound_to_real_shas_and_real_hunks(self):
        head = self.change()
        packet = packets.build_packet(self.repo, self.base_sha, head, pr_url=PR_URL,
                                      task_id="T", scope="scope", summary="summary")
        self.assertEqual(packet["base_sha"], self.base_sha)
        self.assertEqual(packet["head_sha"], head)
        self.assertEqual(len(packet["diff_sha256"]), 64)
        self.assertTrue(packet["hunks"])
        patch_text = packet["hunks"][0]["patch"]
        self.assertTrue(patch_text.startswith("@@"))
        self.assertIn("p0_authz.py", packet["selection"]["files_included"])

    def test_payload_respects_the_6kib_cap(self):
        self.change()
        packet = packets.build_packet(self.repo, self.base_sha, "HEAD", pr_url=PR_URL,
                                      task_id="T", scope="scope", summary="summary")
        payload = packets.packet_user_payload(packet)
        self.assertLessEqual(len(payload.encode("utf-8")), packets.MAX_PACKET_BYTES)
        self.assertEqual(packets.packet_digest(packet),
                         __import__("hashlib").sha256(payload.encode("utf-8")).hexdigest())

    def test_a_big_new_file_can_reach_the_reviewer(self):
        """A brand new file arrives as one huge hunk that cannot fit the 6 KiB
        packet. Such a file used to be skipped entirely, so the packet carried
        only whatever small file happened to fit."""
        big = "".join(f"line_{i} = 'value {i}'\n" for i in range(400))
        self.change(text=big, name="big_module.py")
        packet = packets.build_packet(self.repo, self.base_sha, "HEAD", pr_url=PR_URL,
                                      task_id="T", scope="scope", summary="summary")
        self.assertIn("big_module.py", packet["selection"]["files_included"])
        payload = packets.packet_user_payload(packet)
        self.assertLessEqual(len(payload.encode("utf-8")), packets.MAX_PACKET_BYTES)

    def test_the_packet_covers_several_files_not_just_the_top_one(self):
        """One file must not eat the whole budget."""
        for name in ("alpha_service.py", "beta_service.py", "gamma_service.py"):
            self.change(text=f"def {name.split('_')[0]}():\n    return 1\n", name=name)
        packet = packets.build_packet(self.repo, self.base_sha, "HEAD", pr_url=PR_URL,
                                      task_id="T", scope="scope", summary="summary")
        included = packet["selection"]["files_included"]
        self.assertGreaterEqual(len(included), 2)

    def test_implementation_outranks_documentation(self):
        """A document that merely mentions 'secret' must not outrank the code."""
        (self.repo / "docs").mkdir(exist_ok=True)
        self.change(text="TOKEN = 'x'  # secret credential token\n", name="docs/notes.md")
        self.change(text="def run():\n    return 1\n", name="app_service.py")
        packet = packets.build_packet(self.repo, self.base_sha, "HEAD", pr_url=PR_URL,
                                      task_id="T", scope="scope", summary="summary")
        included = packet["selection"]["files_included"]
        self.assertIn("app_service.py", included)

    def test_path_weight_prefers_source_over_prose(self):
        self.assertGreater(packets.path_weight("tools/ai_review/review_gate.py"),
                           packets.path_weight("docs/ai-review/examples/report.example.md"))
        self.assertLess(packets.path_weight("docs/ai-review/PLAN_RU.md"),
                        packets.path_weight("backend/kie.py"))

    def test_split_hunk_keeps_valid_headers(self):
        body = [f"+line {i}\n" for i in range(200)]
        pieces = packets.split_hunk("@@ -0,0 +1,200 @@", body, max_bytes=400)
        self.assertGreater(len(pieces), 1)
        for header, chunk in pieces:
            self.assertTrue(header.startswith("@@"))
            self.assertTrue(packets.HUNK_HEADER.match(header))
            self.assertLessEqual(len(("\n".join(chunk)).encode("utf-8")), 600)
        joined = "".join("".join(chunk) for _header, chunk in pieces)
        self.assertEqual(joined.count("+line "), 200)

    def test_the_packet_carries_the_project_context(self):
        """Argon sees a diff with no history; it needs to know what the project is."""
        self.change()
        packet = packets.build_packet(self.repo, self.base_sha, "HEAD", pr_url=PR_URL,
                                      task_id="T", scope="scope", summary="summary")
        payload = packets.packet_user_payload(packet)
        self.assertIn("project_context", packet)
        self.assertTrue(packet["project_context"].strip())
        self.assertIn("project_context", payload)
        self.assertIn("GremoVOD", payload)

    def test_a_custom_project_context_replaces_the_default(self):
        self.change()
        packet = packets.build_packet(self.repo, self.base_sha, "HEAD", pr_url=PR_URL,
                                      task_id="T", scope="scope", summary="summary",
                                      project_context="Custom background for this repo.")
        self.assertEqual(packet["project_context"], "Custom background for this repo.")

    def test_oversized_packet_is_refused(self):
        self.change()
        with self.assertRaises(packets.PacketError) as ctx:
            packets.build_packet(self.repo, self.base_sha, "HEAD", pr_url=PR_URL, task_id="T",
                                 scope="s", summary="s", max_payload_bytes=200)
        self.assertEqual(ctx.exception.reason, "packet_too_large")

    def test_empty_diff_is_refused(self):
        outcome = self.run_gate(mode="live", head=self.base_sha, base=self.base_sha,
                                provider=FakeProvider())
        self.assertEqual(outcome["status"], review_gate.STATUS_BLOCKED)
        self.assertEqual(outcome["reason"], "empty_diff")

    def test_secret_in_diff_is_refused(self):
        self.change(text=f'key = "{FAKE_SECRET}"\n')
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider)
        self.assertEqual(outcome["status"], review_gate.STATUS_BLOCKED)
        self.assertEqual(outcome["reason"], "unsafe_diff")
        self.assertEqual(provider.call_count, 0)


# --------------------------------------------------------------------------- limits


class LimitTest(GateTestCase):
    def test_parallel_requests_make_at_most_one_reservation(self):
        self.change()
        provider = FakeProvider(delay=0.25, credits=0.0)
        credits = FixedCredits(100.0)
        approval = self.approval("HEAD")
        barrier = threading.Barrier(2)
        results = []

        def worker():
            barrier.wait()
            results.append(self.run_gate(provider=provider, credits_reader=credits,
                                         policy=live_policy(max_concurrent=2), approval_path=approval))

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(len(results), 2)
        statuses = sorted(r["status"] for r in results)
        self.assertEqual(statuses, [review_gate.STATUS_BLOCKED, review_gate.STATUS_PASS])
        blocked = [r for r in results if r["status"] == review_gate.STATUS_BLOCKED][0]
        self.assertTrue(blocked["reason"].startswith("no_new_call"), blocked["reason"])
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(len(self.ledger_entries()), 1)

    def test_repeated_pr_and_sha_is_no_new_call(self):
        self.change()
        provider = FakeProvider()
        approval = self.approval("HEAD")
        first = self.run_gate(provider=provider, approval_path=approval)
        self.assertEqual(first["status"], review_gate.STATUS_PASS)
        second = self.run_gate(provider=provider, approval_path=approval)
        self.assertEqual(second["status"], review_gate.STATUS_BLOCKED)
        self.assertTrue(second["reason"].startswith("no_new_call"), second["reason"])
        self.assertEqual(provider.call_count, 1)

    def test_daily_credit_ceiling_blocks_before_the_call(self):
        self.change()
        provider = FakeProvider()
        approval = self.approval("HEAD")
        policy = live_policy(max_kie_credits_per_day=11.0, max_kie_credits_per_call=10.0)
        first = self.run_gate(provider=provider, approval_path=approval, policy=policy)
        self.assertEqual(first["status"], review_gate.STATUS_PASS)
        # A second PR on purpose: the per-PR cap is 1 and cannot be raised, so
        # only a different PR can reach the daily credit ceiling.
        other_pr = PR_URL + "-second-pr"
        second = self.run_gate(provider=provider, pr_url=other_pr, policy=policy,
                               approval_path=self.approval("HEAD", pr=other_pr, name="approval2.json"))
        self.assertEqual(second["status"], review_gate.STATUS_BLOCKED)
        self.assertIn("credit ceiling", second["reason"])
        self.assertEqual(provider.call_count, 1)

    def test_emergency_stop_blocks_the_call(self):
        self.change()
        provider = FakeProvider()
        (self.state / "STOP").write_text("stop", encoding="utf-8")
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"))
        self.assertEqual(outcome["status"], review_gate.STATUS_BLOCKED)
        self.assertEqual(outcome["reason"], "emergency_stop")
        self.assertEqual(provider.call_count, 0)

    def test_the_inflight_slot_is_released_after_a_call(self):
        self.change()
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"))
        self.assertEqual(outcome["status"], review_gate.STATUS_PASS)
        self.assertEqual(list((self.state / "inflight").glob("slot-*.json")), [])

    def test_a_stale_slot_does_not_block_the_next_call_forever(self):
        self.change()
        inflight = self.state / "inflight"
        inflight.mkdir(parents=True, exist_ok=True)
        stale = inflight / "slot-0.json"
        stale.write_text("{}", encoding="utf-8")
        old = time.time() - 3600
        os.utime(stale, (old, old))
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"))
        self.assertEqual(outcome["status"], review_gate.STATUS_PASS)
        self.assertEqual(provider.call_count, 1)

    def test_a_second_live_call_while_one_is_in_flight_is_refused(self):
        self.change()
        inflight = self.state / "inflight"
        inflight.mkdir(parents=True, exist_ok=True)
        (inflight / "slot-0.json").write_text("{}", encoding="utf-8")
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"))
        self.assertEqual(outcome["status"], review_gate.STATUS_BLOCKED)
        self.assertIn("concurrency limit", outcome["reason"])
        self.assertEqual(provider.call_count, 0)

    def test_a_corrupted_ledger_fails_closed(self):
        self.change()
        (self.state / "ledger.json").write_text("{not json", encoding="utf-8")
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"))
        self.assertEqual(outcome["status"], review_gate.STATUS_BLOCKED)
        self.assertEqual(outcome["reason"], "ledger_corrupted")
        self.assertEqual(provider.call_count, 0)

    def test_a_state_dir_inside_the_repository_is_refused(self):
        self.change()
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                state_dir=self.repo / ".argon-state")
        self.assertEqual(outcome["status"], review_gate.STATUS_BLOCKED)
        self.assertEqual(outcome["reason"], "state_dir_inside_repo")
        self.assertEqual(provider.call_count, 0)

    def test_an_approval_without_a_head_sha_is_not_accepted(self):
        """The owner approves a SHA. An approval that names none must not pass."""
        self.change()
        provider = FakeProvider()
        path = self.state / "no-sha.json"
        path.write_text(json.dumps({"approved": True, "pr": PR_URL}), encoding="utf-8")
        outcome = self.run_gate(provider=provider, approval_path=path)
        self.assertEqual(outcome["status"], review_gate.STATUS_PENDING_APPROVAL)
        self.assertTrue(outcome["reason"].startswith("approval_stale"))
        self.assertEqual(provider.call_count, 0)

    def test_the_pr_url_is_canonicalised_for_the_ledger(self):
        """A trailing slash must not buy a second paid call."""
        self.change()
        provider = FakeProvider()
        approval = self.approval("HEAD")
        first = self.run_gate(provider=provider, approval_path=approval)
        self.assertEqual(first["status"], review_gate.STATUS_PASS)
        second = self.run_gate(provider=provider, approval_path=approval, pr_url=PR_URL + "/")
        self.assertEqual(second["status"], review_gate.STATUS_BLOCKED)
        self.assertTrue(second["reason"].startswith("no_new_call"), second["reason"])
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(len(self.ledger_entries()), 1)

    def test_findings_that_are_not_a_list_do_not_crash_the_gate(self):
        self.change()
        provider = FakeProvider(content=json.dumps({"verdict": "PASS", "findings": {"a": 1}}))
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 98.5))
        self.assertEqual(outcome["status"], review_gate.STATUS_HALTED_UNKNOWN)
        self.assertEqual(outcome["reason"], "response_not_json")
        self.assertEqual(provider.call_count, 1)

    def test_a_pass_verdict_with_findings_is_not_a_pass(self):
        self.change()
        content = json.dumps({"verdict": "PASS", "findings": [
            {"severity": "P0", "path": "p0_authz.py", "line": 1, "evidence": "bypass"}]})
        provider = FakeProvider(content=content)
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 98.5))
        self.assertEqual(outcome["status"], review_gate.STATUS_HALTED_UNKNOWN)
        self.assertEqual(outcome["reason"], "contradictory_verdict")
        self.assertEqual(len(outcome["findings"]), 1)

    def test_a_call_above_the_per_call_ceiling_is_flagged(self):
        self.change()
        provider = FakeProvider(credits=50.0)
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 50.0))
        self.assertEqual(outcome["credits"]["accounting"], "MISMATCH")
        self.assertEqual(outcome["status"], review_gate.STATUS_HALTED_UNKNOWN)

    def test_the_daily_ceiling_works_when_the_provider_omits_the_spend(self):
        self.change()
        provider = FakeProvider(credits=None)
        policy = live_policy(max_kie_credits_per_day=11.0, max_kie_credits_per_call=10.0)
        first = self.run_gate(provider=provider, approval_path=self.approval("HEAD"), policy=policy,
                              credits_reader=FakeCredits(100.0, 95.0))
        self.assertEqual(first["status"], review_gate.STATUS_PASS)
        self.assertEqual(first["credits"]["credits_consumed"], 5.0)
        other_pr = PR_URL + "-second-pr"
        second = self.run_gate(provider=provider, pr_url=other_pr, policy=policy,
                               approval_path=self.approval("HEAD", pr=other_pr, name="approval2.json"),
                               credits_reader=FakeCredits(95.0, 90.0))
        self.assertEqual(second["status"], review_gate.STATUS_BLOCKED)
        self.assertIn("credit ceiling", second["reason"])
        self.assertEqual(provider.call_count, 1)

    def test_a_failed_reservation_does_not_leak_the_concurrency_slot(self):
        self.change()
        (self.state / "ledger.json").write_text("{not json", encoding="utf-8")
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"))
        self.assertEqual(outcome["status"], review_gate.STATUS_BLOCKED)
        self.assertEqual(outcome["reason"], "ledger_corrupted")
        self.assertEqual(list((self.state / "inflight").glob("slot-*.json")), [])

    def test_a_failed_call_is_counted_as_a_network_call(self):
        self.change()
        provider = FakeProvider(error=argon_review.ProviderError("HTTP 429", kind="rate_limited", status=429))
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0))
        self.assertEqual(outcome["network_calls"], 1)
        self.assertEqual(outcome["status"], review_gate.STATUS_HALTED_UNKNOWN)

    def test_the_report_keeps_the_raw_answer_out(self):
        self.change()
        content = json.dumps({"verdict": "FINDINGS", "findings": [
            {"severity": "P1", "path": "p0_authz.py", "line": 2,
             "evidence": "SUPERSECRETKEY1234567890 leaked", "fix": "rotate", "test": "none"}]})
        provider = FakeProvider(content=content)
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 98.5))
        report = review_gate.render_report(outcome)
        self.assertNotIn("SUPERSECRETKEY1234567890", report)
        self.assertIn("[REDACTED]", report)
        self.assertNotIn("\"verdict\": \"FINDINGS\"", report)

    def test_the_report_keeps_git_digests_readable(self):
        self.change()
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 98.5))
        report = review_gate.render_report(outcome)
        self.assertIn(outcome["diff_sha256"], report)
        self.assertIn(outcome["payload_sha256"], report)

    def test_retries_cannot_be_enabled(self):
        with self.assertRaises(review_gate.GateError) as ctx:
            review_gate.Policy.from_env({"ARGON_RETRY_COUNT": "2"})
        self.assertEqual(ctx.exception.reason, "retry_not_allowed")

    def test_the_environment_cannot_raise_a_limit_above_the_ceiling(self):
        """An agent that exports a bigger budget must still get the ceiling."""
        policy = review_gate.Policy.from_env({
            "ARGON_MAX_CALLS_PER_PR": "50",
            "ARGON_MAX_CALLS_PER_DAY": "500",
            "ARGON_MAX_CALLS_PER_WEEK": "999",
            "ARGON_MAX_CONCURRENT": "8",
            "ARGON_MAX_PACKET_BYTES": "999999",
            "ARGON_MAX_PACKET_FILES": "80",
        })
        self.assertEqual(policy.max_calls_per_pr, review_gate.HARD_MAX_CALLS_PER_PR)
        self.assertEqual(policy.max_calls_per_day, review_gate.HARD_MAX_CALLS_PER_DAY)
        self.assertEqual(policy.max_calls_per_week, review_gate.HARD_MAX_CALLS_PER_WEEK)
        self.assertEqual(policy.max_concurrent, review_gate.HARD_MAX_CONCURRENT)
        self.assertEqual(policy.max_packet_bytes, review_gate.HARD_MAX_PACKET_BYTES)
        self.assertEqual(policy.max_packet_files, review_gate.HARD_MAX_PACKET_FILES)
        self.assertIn("max_calls_per_day", policy.clamped)
        self.assertEqual(policy.clamped["max_calls_per_day"]["requested"], 500)

    def test_the_environment_may_tighten_a_limit(self):
        policy = review_gate.Policy.from_env({"ARGON_MAX_CALLS_PER_DAY": "1"})
        self.assertEqual(policy.max_calls_per_day, 1)
        self.assertEqual(policy.clamped, {})

    def test_a_policy_built_in_python_cannot_buy_a_bigger_budget(self):
        """The ceiling is enforced where the call happens, not only where the
        policy is configured. A hand-built Policy must not raise the caps."""
        self.change()
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                policy=live_policy(max_calls_per_pr=10, max_calls_per_day=99,
                                                    max_calls_per_week=99, max_concurrent=8,
                                                    max_packet_bytes=999999))
        self.assertEqual(outcome["limits"]["max_calls_per_pr"], 1)
        self.assertEqual(outcome["limits"]["max_calls_per_day"], 2)
        self.assertEqual(outcome["limits"]["max_calls_per_week"], 5)
        self.assertEqual(outcome["limits"]["max_packet_bytes"], 6144)
        self.assertEqual(outcome["limits"]["retry_count"], 0)
        self.assertIn("max_calls_per_day", outcome["clamped"])

    def test_the_report_shows_the_limits_that_were_in_force(self):
        self.change()
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 98.5))
        report = review_gate.render_report(outcome)
        self.assertIn("## Limits in force", report)
        self.assertIn("max_calls_per_day: `2`", report)
        self.assertIn("max_calls_per_pr: `1`", report)
        self.assertIn("max_calls_per_week: `5`", report)

    def test_the_ledger_refuses_a_duplicate_reservation_under_parallel_use(self):
        """The ledger itself deduplicates, independently of the concurrency guard."""
        ledger = review_gate.Ledger(self.state / "ledger.json")
        policy = live_policy()
        record = {
            "id": "a", "ts_utc": self.now.isoformat(timespec="seconds"),
            "repo": "gremoled77-droid/gremovod", "pr": PR_URL,
            "head_sha": "a" * 40, "payload_sha256": "b" * 64,
        }
        results = []
        barrier = threading.Barrier(4)

        def worker():
            barrier.wait()
            results.append(ledger.reserve(dict(record), policy, self.now))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(len([r for r in results if r[0]]), 1)
        self.assertEqual(len(ledger.entries()), 1)

    def test_missing_key_budget_or_approval_makes_no_network_call(self):
        self.change()
        for overrides, expected_status, expected_reason in (
            ({"api_key": ""}, review_gate.STATUS_BLOCKED, "no_api_key"),
            ({"policy": live_policy(max_kie_credits_per_day=None, max_kie_credits_per_call=None,
                                    min_kie_balance=None)},
             review_gate.STATUS_BLOCKED, "no_budget_policy"),
            ({"approval_path": None}, review_gate.STATUS_PENDING_APPROVAL, "approval_missing"),
        ):
            provider = FakeProvider()
            credits = FakeCredits()
            outcome = self.run_gate(provider=provider, credits_reader=credits, **overrides)
            self.assertEqual(outcome["status"], expected_status, overrides)
            self.assertEqual(outcome["reason"], expected_reason, overrides)
            self.assertEqual(provider.call_count, 0, overrides)
            self.assertEqual(credits.call_count, 0, overrides)

    def test_stale_approval_for_another_sha_is_not_accepted(self):
        self.change()
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider, approval_path=self.approval("0" * 40))
        self.assertEqual(outcome["status"], review_gate.STATUS_PENDING_APPROVAL)
        self.assertTrue(outcome["reason"].startswith("approval_stale"))
        self.assertEqual(provider.call_count, 0)

    def test_pr_head_drift_is_a_hard_stop(self):
        self.change()
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                expected_head_sha="0" * 40)
        self.assertEqual(outcome["status"], review_gate.STATUS_BLOCKED)
        self.assertEqual(outcome["reason"], "pr_head_drift")
        self.assertEqual(provider.call_count, 0)

    def test_insufficient_balance_blocks_the_call(self):
        self.change()
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider, credits_reader=FakeCredits(6.0),
                                approval_path=self.approval("HEAD"))
        self.assertEqual(outcome["status"], review_gate.STATUS_BLOCKED)
        self.assertEqual(outcome["reason"], "insufficient_balance")
        self.assertEqual(provider.call_count, 0)


# --------------------------------------------------------------------------- provider


class ProviderTest(GateTestCase):
    def test_rate_limit_is_halted_unknown_with_zero_retry(self):
        self.change()
        provider = FakeProvider(error=argon_review.ProviderError("HTTP 429", kind="rate_limited", status=429))
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0))
        self.assertEqual(outcome["status"], review_gate.STATUS_HALTED_UNKNOWN)
        self.assertEqual(outcome["reason"], "rate_limited")
        self.assertEqual(provider.call_count, 1)
        # The request did go out, so the spend counter must say so.
        self.assertEqual(outcome["network_calls"], 1)

    def test_timeout_is_halted_unknown_with_zero_retry(self):
        self.change()
        provider = FakeProvider(error=argon_review.ProviderError("timeout", kind="timeout"))
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0))
        self.assertEqual(outcome["status"], review_gate.STATUS_HALTED_UNKNOWN)
        self.assertEqual(outcome["reason"], "timeout")
        self.assertEqual(provider.call_count, 1)

    def test_auth_failure_is_blocked(self):
        self.change()
        provider = FakeProvider(error=argon_review.ProviderError("HTTP 401", kind="auth_failed", status=401))
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0))
        self.assertEqual(outcome["status"], review_gate.STATUS_BLOCKED)
        self.assertEqual(outcome["reason"], "auth_failed")
        self.assertEqual(provider.call_count, 1)

    def test_malformed_json_is_never_pass(self):
        self.change()
        provider = FakeProvider(content="I think this looks fine, no notes.")
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 98.5))
        self.assertEqual(outcome["status"], review_gate.STATUS_HALTED_UNKNOWN)
        self.assertEqual(outcome["reason"], "response_not_json")
        self.assertEqual(provider.call_count, 1)

    def test_findings_are_reported(self):
        self.change()
        content = json.dumps({
            "verdict": "FINDINGS",
            "findings": [{"severity": "P1", "path": "p0_authz.py", "line": 2,
                           "evidence": "bypass", "fix": "compare the signature", "test": "unittest"}],
            "requested_context": [],
        })
        provider = FakeProvider(content=content)
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 98.5))
        self.assertEqual(outcome["status"], review_gate.STATUS_FINDINGS)
        self.assertEqual(len(outcome["findings"]), 1)
        self.assertEqual(outcome["findings"][0]["path"], "p0_authz.py")

    def test_need_context_does_not_trigger_a_second_call(self):
        self.change()
        content = json.dumps({"verdict": "NEED_CONTEXT",
                              "requested_context": [{"path": "p0_authz.py", "lines": "1-5",
                                                      "reason": "need the caller"}]})
        provider = FakeProvider(content=content)
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 98.5))
        self.assertEqual(outcome["status"], review_gate.STATUS_BLOCKED)
        self.assertEqual(outcome["reason"], "need_context")
        self.assertEqual(provider.call_count, 1)

    def test_unsure_is_halted_unknown(self):
        self.change()
        provider = FakeProvider(content=json.dumps({"verdict": "UNSURE"}))
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 98.5))
        self.assertEqual(outcome["status"], review_gate.STATUS_HALTED_UNKNOWN)


# --------------------------------------------------------------------------- accounting


class AccountingTest(GateTestCase):
    def test_credits_are_recorded_and_never_converted_to_usd(self):
        self.change()
        provider = FakeProvider(credits=1.5)
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 98.5))
        credits = outcome["credits"]
        self.assertEqual(credits["credits_before"], 100.0)
        self.assertEqual(credits["credits_after"], 98.5)
        self.assertEqual(credits["credits_consumed"], 1.5)
        self.assertIsNone(credits["usd_amount"])
        self.assertEqual(credits["accounting"], "OK")
        entry = self.ledger_entries()[0]
        self.assertEqual(entry["state"], "COMPLETED")
        self.assertEqual(entry["status"], review_gate.STATUS_PASS)
        self.assertIsNone(entry["usd_amount"])

    def test_balance_jump_is_flagged_and_does_not_report_pass(self):
        self.change()
        provider = FakeProvider(credits=1.5)
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 150.0))
        self.assertEqual(outcome["credits"]["accounting"], "MISMATCH")
        self.assertEqual(outcome["status"], review_gate.STATUS_HALTED_UNKNOWN)
        self.assertEqual(outcome["reason"], "credit_accounting_mismatch")

    def test_reported_spend_that_disagrees_with_the_balance_is_flagged(self):
        self.change()
        provider = FakeProvider(credits=40.0)
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 98.5))
        self.assertEqual(outcome["credits"]["accounting"], "MISMATCH")
        self.assertEqual(outcome["status"], review_gate.STATUS_HALTED_UNKNOWN)

    def test_daily_credit_spend_is_summed_from_the_ledger(self):
        self.change()
        provider = FakeProvider(credits=2.0)
        self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                     policy=live_policy(max_calls_per_pr=1, max_calls_per_day=5),
                     credits_reader=FakeCredits(100.0, 98.0))
        spent = review_gate.Ledger(self.state / "ledger.json").credits_spent_today(self.now)
        self.assertEqual(spent, 2.0)


# --------------------------------------------------------------------------- report


class ReportTest(GateTestCase):
    def test_contaminated_provider_answer_is_redacted_from_the_report(self):
        self.change()
        content = json.dumps({
            "verdict": "FINDINGS",
            "findings": [{"severity": "P1", "path": "p0_authz.py", "line": 2,
                           "evidence": f"leaked {FAKE_SECRET} here",
                           "fix": "rotate", "test": "none"}],
        })
        provider = FakeProvider(content=content)
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 98.5))
        report = review_gate.render_report(outcome)
        self.assertNotIn(FAKE_SECRET, report)
        self.assertIn("[REDACTED]", report)

    def test_report_contains_no_key_and_no_diff_body(self):
        self.change()
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 98.5))
        report = review_gate.render_report(outcome)
        self.assertNotIn(FAKE_KEY, report)
        self.assertNotIn("bypass", report)
        self.assertIn("Argon PASS is not a test PASS", report)

    def test_report_states_the_status_and_the_sha(self):
        self.change()
        head = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 98.5))
        report = review_gate.render_report(outcome)
        self.assertIn("Status: **PASS**", report)
        self.assertIn(head, report)


# --------------------------------------------------------------------------- read only


class ReadOnlyTest(GateTestCase):
    def test_the_gate_never_writes_to_the_repository(self):
        self.change()
        before_status = git(self.repo, "status", "--porcelain").stdout
        before_head = git(self.repo, "rev-parse", "HEAD").stdout
        before_refs = git(self.repo, "show-ref").stdout
        before_files = sorted(p.name for p in self.repo.iterdir())

        provider = FakeProvider()
        self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                     credits_reader=FakeCredits(100.0, 98.5))

        self.assertEqual(git(self.repo, "status", "--porcelain").stdout, before_status)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD").stdout, before_head)
        self.assertEqual(git(self.repo, "show-ref").stdout, before_refs)
        self.assertEqual(sorted(p.name for p in self.repo.iterdir()), before_files)
        self.assertFalse((self.repo / "ledger.json").exists())

    def test_the_gate_does_not_touch_the_working_tree(self):
        self.change()
        (self.repo / "untracked.txt").write_text("scratch", encoding="utf-8")
        provider = FakeProvider()
        outcome = self.run_gate(provider=provider, approval_path=self.approval("HEAD"),
                                credits_reader=FakeCredits(100.0, 98.5))
        self.assertEqual(outcome["status"], review_gate.STATUS_PASS)
        self.assertTrue((self.repo / "untracked.txt").exists())


# --------------------------------------------------------------------------- legacy contract


class LegacyContractTest(unittest.TestCase):
    def test_ask_argon_keeps_its_old_return_shape(self):
        payload = {"choices": [{"message": {"content": "PASS"}}], "credits_consumed": 3}
        with mock.patch.object(argon_review, "_post_chat", return_value=(payload, 200)):
            content, credits = argon_review.ask_argon([{"role": "user", "content": "x"}], "key")
        self.assertEqual(content, "PASS")
        self.assertEqual(credits, 3)

    def test_ask_argon_keeps_the_not_provided_default(self):
        payload = {"choices": [{"message": {"content": "PASS"}}]}
        with mock.patch.object(argon_review, "_post_chat", return_value=(payload, 200)):
            content, credits = argon_review.ask_argon([{"role": "user", "content": "x"}], "key")
        self.assertEqual(credits, "not provided")

    def test_snapshot_keeps_its_size_ceiling(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-q")
            git(repo, "config", "user.name", "Test")
            git(repo, "config", "user.email", "test@example.org")
            (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "base")
            (repo / "a.py").write_text("x = 2\n", encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "change")
            files, diff, digest = argon_review.snapshot(repo, "HEAD~1", "HEAD")
            self.assertEqual(files, ["a.py"])
            self.assertEqual(len(digest), 64)
            self.assertIn("+x = 2", diff)

    def test_a_diff_mentioning_the_binary_markers_is_not_binary(self):
        """The guard must key on git's own markers, not on the words themselves."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-q")
            git(repo, "config", "user.name", "Test")
            git(repo, "config", "user.email", "test@example.org")
            (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "base")
            (repo / "a.py").write_text(
                'if "Binary files " in diff or "GIT binary patch" in diff:\n    raise ValueError\n',
                encoding="utf-8")
            git(repo, "add", "-A")
            git(repo, "commit", "-qm", "mention the markers")
            files, diff, _digest = argon_review.snapshot(repo, "HEAD~1", "HEAD")
            self.assertEqual(files, ["a.py"])
            self.assertIn("Binary files ", diff)
            self.assertFalse(argon_review.has_binary_patch(diff))

    def test_a_real_binary_marker_is_still_detected(self):
        self.assertTrue(argon_review.has_binary_patch(
            "diff --git a/x.png b/x.png\nBinary files a/x.png and b/x.png differ\n"))
        self.assertTrue(argon_review.has_binary_patch("GIT binary patch\nliteral 7z\n"))
        self.assertFalse(argon_review.has_binary_patch("+Binary files a/x and b/x differ\n"))
        self.assertFalse(argon_review.has_binary_patch(" context mentioning GIT binary patch\n"))


class SelfReviewTest(unittest.TestCase):
    """The bridge must be able to review its own repository.

    A credential-shaped literal in the sources makes the secret guard reject the
    repository's OWN diff. The tool then refuses to review the very code that
    implements it, with a confusing "Potential secret in diff" message.
    """

    def test_the_repository_sources_do_not_trip_the_secret_guard(self):
        root = ROOT
        offenders = []
        # Python AND the prose: a credential-shaped literal written into a
        # report or an example lands in the diff just as firmly as one in code,
        # and the guard rejects the whole diff either way.
        suffixes = (".py", ".md", ".json")
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            parts = set(path.parts)
            if ".git" in parts or "node_modules" in parts or "__pycache__" in parts:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            match = argon_review.SECRET.search(text)
            if match:
                offenders.append(f"{path.relative_to(root)}: {match.group(0)[:40]}")
        self.assertEqual(offenders, [], "credential-shaped literals in sources:\n" + "\n".join(offenders))

    def test_a_secret_literal_written_in_one_piece_is_detected(self):
        """The guard still catches a real secret; the sources only avoid writing one."""
        one_piece = "sk-" + "abcdefghijklmno123456"
        repo_diff = '+key = "%s"\n' % one_piece
        self.assertTrue(argon_review.SECRET.search(repo_diff))
        split = '+FAKE_SECRET = "sk-" + "abcdefghijklmno123456"\n'
        self.assertIsNone(argon_review.SECRET.search(split))


# --------------------------------------------------------------------------- single money path


class StandaloneScriptTest(GateTestCase):
    """argon_review.py --live must spend through the gate, not around it.

    A second money path would let a caller spend outside the per-PR, daily,
    weekly and credit limits, and without the owner's approval file.
    """

    def _argv(self, live=False, **extra):
        args = ["--repo", str(self.repo), "--base", self.base_sha, "--head", "HEAD",
                "--scope", "scope", "--out", str(self.state / "standalone.md")]
        if live:
            args.append("--live")
        for key, value in extra.items():
            args += [f"--{key.replace('_', '-')}", str(value)]
        return args

    def _confirm(self):
        _files, _diff, digest = argon_review.snapshot(self.repo, self.base_sha, "HEAD")
        return f"REVIEW {digest[:12]}"

    def test_the_standalone_live_path_makes_no_call_without_a_budget_policy(self):
        self.change()
        provider = FakeProvider()
        with mock.patch.dict(os.environ, {"KIE_API_KEY": FAKE_KEY}, clear=False), \
             mock.patch.object(argon_review, "ask_argon_detailed", provider), \
             mock.patch.object(argon_review, "fetch_credits", FakeCredits()), \
             mock.patch("builtins.input", return_value=self._confirm()):
            code = argon_review.main(self._argv(live=True, state_dir=self.state))
        self.assertEqual(code, 2)
        self.assertEqual(provider.call_count, 0)
        report = (self.state / "standalone.md").read_text(encoding="utf-8")
        self.assertNotIn("Status: **PASS**", report)
        self.assertEqual(self.ledger_entries(), [])

    def test_the_standalone_live_path_spends_only_through_the_gate(self):
        """With an approval and a budget, the standalone path now reaches the
        provider - and the ledger records it exactly like any other call."""
        self.change()
        provider = FakeProvider()
        approval = self.approval("HEAD")
        env = {
            "KIE_API_KEY": FAKE_KEY,
            "ARGON_MAX_KIE_CREDITS_PER_DAY": "100",
            "ARGON_MAX_KIE_CREDITS_PER_CALL": "10",
            "ARGON_MIN_KIE_BALANCE": "5",
        }
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(argon_review, "ask_argon_detailed", provider), \
             mock.patch.object(argon_review, "fetch_credits", FakeCredits()), \
             mock.patch("builtins.input", return_value=self._confirm()):
            code = argon_review.main(self._argv(live=True, state_dir=self.state, pr_url=PR_URL,
                                                approval=approval))
        self.assertEqual(code, 0)
        self.assertEqual(provider.call_count, 1)
        entries = self.ledger_entries()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["pr"], PR_URL)
        report = (self.state / "standalone.md").read_text(encoding="utf-8")
        self.assertIn("Status: **PASS**", report)
        self.assertIn("## Limits in force", report)

    def test_the_standalone_live_path_refuses_a_second_call_on_the_same_pr(self):
        self.change()
        provider = FakeProvider()
        approval = self.approval("HEAD")
        env = {
            "KIE_API_KEY": FAKE_KEY,
            "ARGON_MAX_KIE_CREDITS_PER_DAY": "100",
            "ARGON_MAX_KIE_CREDITS_PER_CALL": "10",
            "ARGON_MIN_KIE_BALANCE": "5",
        }
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(argon_review, "ask_argon_detailed", provider), \
             mock.patch.object(argon_review, "fetch_credits", FakeCredits()), \
             mock.patch("builtins.input", return_value=self._confirm()):
            first = argon_review.main(self._argv(live=True, state_dir=self.state, pr_url=PR_URL,
                                                 approval=approval))
            second = argon_review.main(self._argv(live=True, state_dir=self.state, pr_url=PR_URL,
                                                  approval=approval))
        self.assertEqual(first, 0)
        self.assertEqual(second, 2)
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(len(self.ledger_entries()), 1)


if __name__ == "__main__":
    unittest.main()
