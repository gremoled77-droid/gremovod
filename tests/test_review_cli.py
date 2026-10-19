"""Офлайн-проверки CLI: сквозной MOCK-прогон в временном git-репозитории."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.ai_review.cli import main  # noqa: E402
from tools.ai_review.contract import validate_summary  # noqa: E402


def git(path, *args):
    return subprocess.run(
        ["git", "-C", str(path), *args], check=True, capture_output=True, encoding="utf-8"
    )


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "user.email", "test@example.org")
        (self.repo / "code.py").write_text("x = 1\n", encoding="utf-8")
        git(self.repo, "add", "code.py")
        git(self.repo, "commit", "-qm", "base")

    def commit_change(self, text):
        (self.repo / "code.py").write_text(text, encoding="utf-8")
        git(self.repo, "add", "code.py")
        git(self.repo, "commit", "-qm", "change")

    def test_mock_run_produces_valid_summary_and_report(self):
        self.commit_change("import subprocess\nsubprocess.run(cmd, shell=True)\n")
        out_dir = Path(self.tmp.name) / "artifacts"
        rc = main(
            [
                "review",
                "--repo",
                str(self.repo),
                "--base",
                "HEAD~1",
                "--head",
                "HEAD",
                "--scope",
                "Проверить безопасность запуска команд",
                "--provider",
                "mock",
                "--mode",
                "MOCK",
                "--tests-status",
                "PASS",
                "--task-id",
                "T-27",
                "--run-id",
                "R-27",
                "--out-dir",
                str(out_dir),
            ]
        )
        self.assertEqual(rc, 0)

        summary_path = out_dir / "R-27" / "summary.json"
        report_path = out_dir / "R-27" / "report.md"
        self.assertTrue(summary_path.exists())
        self.assertTrue(report_path.exists())

        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(validate_summary(summary), [])
        self.assertEqual(summary["mode"], "MOCK")
        self.assertEqual(summary["provider"], "mock")
        self.assertEqual(summary["review_status"], "FINDINGS")
        self.assertEqual(summary["findings"][0]["severity"], "P1")
        self.assertIsNone(summary["provider_usage"])
        self.assertIsNone(summary["actual_cost"])

        report = report_path.read_text(encoding="utf-8")
        self.assertIn("Отчёт прогона", report)
        self.assertIn("НЕ ПОДТВЕРЖДЕНО", report)
        self.assertIn("P1", report)

    def test_validate_subcommand_accepts_generated_summary(self):
        self.commit_change("x = 2\n")
        out_dir = Path(self.tmp.name) / "artifacts"
        main(
            [
                "review",
                "--repo",
                str(self.repo),
                "--base",
                "HEAD~1",
                "--head",
                "HEAD",
                "--scope",
                "Проверить изменение",
                "--out-dir",
                str(out_dir),
            ]
        )
        summary_path = out_dir / "R" if False else next(out_dir.rglob("summary.json"))
        self.assertEqual(main(["validate", str(summary_path)]), 0)

    def test_review_does_not_modify_repository(self):
        self.commit_change("x = 2\n")
        before = git(self.repo, "status", "--porcelain").stdout
        main(
            [
                "review",
                "--repo",
                str(self.repo),
                "--base",
                "HEAD~1",
                "--head",
                "HEAD",
                "--scope",
                "Проверить изменение",
                "--out-dir",
                str(Path(self.tmp.name) / "artifacts"),
            ]
        )
        self.assertEqual(before, git(self.repo, "status", "--porcelain").stdout)


if __name__ == "__main__":
    unittest.main()
