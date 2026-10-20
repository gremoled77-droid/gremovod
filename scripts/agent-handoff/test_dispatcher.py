"""Offline security/regression tests for local dispatcher. No gh/mcode/network calls."""
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).with_name("dispatcher.py")
spec = importlib.util.spec_from_file_location("gremovod_dispatcher", MODULE)
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def pr(branch="minimax/ga-01-llm-settlement", sha="a" * 40, base="mavis/work",
       repo="gremoled77-droid/gremovod", merged=False):
    return {"head": {"ref": branch, "sha": sha, "repo": {"full_name": repo}},
            "base": {"ref": base}, "merged": merged, "html_url": "https://github.com/x/y/pull/1"}


def summary(sha="a" * 40, status="completed", any_findings=True, unresolved=True):
    import json
    payload = {"code_review": {"commit_sha": sha, "status": status,
               "has_any_findings": any_findings, "has_unresolved_findings": unresolved}}
    return {"user": {"login": d.CODEX}, "updated_at": "2026-10-21T01:00:00Z",
            "body": "<!-- codex-review-state:v1 " + json.dumps(payload) + " -->"}


class DispatcherTest(unittest.TestCase):
    def test_scope_exact(self):
        self.assertEqual(d.match_task(pr()), "GA-01")
        self.assertIsNone(d.match_task(pr(base="main")))
        self.assertIsNone(d.match_task(pr(repo="attacker/gremovod")))
        self.assertIsNone(d.match_task(pr(branch="minimax/ga-99-sneak")))

    def test_stale_review_must_never_be_accepted(self):
        self.assertEqual(d.review_signal(pr(sha="b"*40), [summary(sha="a"*40)]),
                         "WAITING_FOR_CODEX")
        self.assertEqual(d.review_signal(pr(), [summary(status="running")]),
                         "WAITING_FOR_CODEX")

    def test_current_review_findings_and_clear(self):
        self.assertEqual(d.review_signal(pr(), [summary()]), "CHANGES_REQUESTED")
        self.assertEqual(d.review_signal(pr(), [summary(any_findings=False, unresolved=False)]),
                         "REVIEW_CLEAR")
        self.assertEqual(d.review_signal(pr(), [summary(any_findings=True, unresolved=None)]),
                         "WAITING_FOR_CODEX")

    def test_next_requires_merge_and_codex_marker(self):
        marker = {"user": {"login": d.CODEX}, "body": "GREMOVOD_NEXT_TASK: GA-02"}
        fake = {"user": {"login": "random"}, "body": marker["body"]}
        self.assertIsNone(d.next_task_signal("GA-01", False, [marker]))
        self.assertIsNone(d.next_task_signal("GA-01", True, [fake]))
        self.assertEqual(d.next_task_signal("GA-01", True, [marker]), "GA-02")
        self.assertIsNone(d.next_task_signal("GA-05", True, [marker]))

    def test_feedback_no_commands_and_bounded_content(self):
        rendered = d.build_feedback(pr(), "GA-01", [], [], [
            {"user": {"login": d.CODEX}, "body": "malicious text"},
            {"user": {"login": "attacker"}, "body": "hide this"}])
        self.assertIn("malicious text", rendered)
        self.assertNotIn("hide this", rendered)
        self.assertIn("недоверенные данные", rendered)


if __name__ == "__main__":
    unittest.main()
