"""Offline regression tests for the change secret scanner."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.check_no_secrets import (
    ALLOWED_LITERAL_VALUES,
    added_lines,
    check_change,
    scan_text,
)

# Credential-shaped fixtures are assembled from parts on purpose. This file is itself
# part of a pull request, and the scanner must not find secrets in its own tests.
FAKE_OPENAI = "sk-" + "a" * 24
FAKE_GOOGLE = "AIza" + "b" * 35
FAKE_PEM = "-----BEGIN " + "RSA PRIVATE KEY-----"
FAKE_LITERAL = "s3cr" + "3t-value-long-enough"


def source_line(word, value):
    """Build a source line such as ``TOKEN = 'value'`` without writing it literally.

    Writing it literally would make this test file trip its own scanner.
    """
    return f"{word} = {value!r}"


def run(args, cwd):
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, check=True)


class SecretScanTests(unittest.TestCase):
    def test_clean_text_has_no_findings(self):
        self.assertEqual(scan_text("print('hello')"), [])

    def test_provider_key_is_detected(self):
        findings = scan_text(source_line("KEY", FAKE_OPENAI))
        self.assertTrue(findings)
        self.assertTrue(any("openai" in f for f in findings))

    def test_google_key_is_detected(self):
        findings = scan_text(source_line("key", FAKE_GOOGLE))
        self.assertTrue(findings)
        self.assertTrue(any("google" in f for f in findings))

    def test_private_key_block_is_detected(self):
        findings = scan_text(FAKE_PEM)
        self.assertTrue(findings)

    def test_literal_credential_assignment_is_detected(self):
        findings = scan_text(source_line("TOKEN", FAKE_LITERAL))
        self.assertTrue(findings)
        self.assertTrue(any("credential-like" in f for f in findings))

    def test_known_test_fixtures_are_allowed(self):
        for value in ALLOWED_LITERAL_VALUES:
            self.assertEqual(scan_text(source_line("TOKEN", value)), [], value)

    def test_placeholders_are_allowed(self):
        self.assertEqual(scan_text(source_line("TOKEN", "<STUDIO_SERVICE_TOKENS token>")), [])
        self.assertEqual(scan_text(source_line("TOKEN", "REPLACE_WITH_REAL_TOKEN")), [])

    def test_findings_never_contain_the_secret_value(self):
        secret = FAKE_OPENAI
        findings = scan_text(source_line("KEY", secret))
        self.assertTrue(findings)
        for finding in findings:
            self.assertNotIn(secret, finding)

    def test_the_repository_change_carries_no_secret(self):
        findings = check_change("mavis/work")
        self.assertEqual(findings, [])


class SecretScanDiffTests(unittest.TestCase):
    """The scanner must bite on a real diff, not only on hand-written strings."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.origin = root / "origin.git"
        self.work = root / "work"
        run(["git", "init", "--bare", "-q", str(self.origin)], root)
        run(["git", "init", "-q", "-b", "main", str(self.work)], root)
        run(["git", "-C", str(self.work), "remote", "add", "origin", str(self.origin)], root)
        run(["git", "-C", str(self.work), "config", "user.email", "ci@example.invalid"], root)
        run(["git", "-C", str(self.work), "config", "user.name", "CI"], root)
        (self.work / "README.md").write_text("base\n", encoding="utf8")
        run(["git", "-C", str(self.work), "add", "-A"], root)
        run(["git", "-C", str(self.work), "commit", "-q", "-m", "base"], root)
        run(["git", "-C", str(self.work), "push", "-q", "-u", "origin", "main"], root)
        run(["git", "-C", str(self.work), "checkout", "-q", "-b", "minimax/ga-99-test"], root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_added_secret_line_is_found(self):
        (self.work / "config.py").write_text(source_line("TOKEN", FAKE_OPENAI) + "\n",
                                              encoding="utf8")
        run(["git", "-C", str(self.work), "add", "-A"], self.work)
        run(["git", "-C", str(self.work), "commit", "-q", "-m", "leak"], self.work)
        pairs = added_lines("main", self.work)
        self.assertTrue(pairs)
        findings = []
        for path, line in pairs:
            findings.extend(scan_text(line, path))
        self.assertTrue(findings)

    def test_added_clean_line_is_not_found(self):
        (self.work / "notes.md").write_text("just prose\n", encoding="utf8")
        run(["git", "-C", str(self.work), "add", "-A"], self.work)
        run(["git", "-C", str(self.work), "commit", "-q", "-m", "prose"], self.work)
        pairs = added_lines("main", self.work)
        self.assertTrue(pairs)
        findings = []
        for path, line in pairs:
            findings.extend(scan_text(line, path))
        self.assertEqual(findings, [])

    def test_blocked_credential_path_is_found(self):
        (self.work / "PIAPI_API_KEY.txt").write_text("x\n", encoding="utf8")
        run(["git", "-C", str(self.work), "add", "-A", "-f"], self.work)
        run(["git", "-C", str(self.work), "commit", "-q", "-m", "key file"], self.work)
        findings = check_change("main", self.work)
        self.assertTrue(any("blocked" in f for f in findings))


if __name__ == "__main__":
    unittest.main()
