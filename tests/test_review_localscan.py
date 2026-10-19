"""Офлайн-проверки локального скана диффа: сужение `allowed_paths` и правила файлов.

Сеть не используется. Работа ведётся во временном git-репозитории.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.ai_review import argon_review  # noqa: E402
from tools.ai_review.localscan import (  # noqa: E402
    LocalScanError,
    check_file_allowed,
    collect_diff,
    scan_branch_material,
)


def git(path, *args):
    return subprocess.run(
        ["git", "-C", str(path), *args], check=True, capture_output=True, encoding="utf-8"
    )


class LocalScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "user.email", "test@example.org")
        (self.repo / "keep.py").write_text("x = 1\n", encoding="utf-8")
        git(self.repo, "add", "keep.py")
        git(self.repo, "commit", "-qm", "base")

    def add_file(self, name, text="y = 2\n"):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        git(self.repo, "add", name)
        git(self.repo, "commit", "-qm", f"add {name}")

    def test_allowed_paths_narrows_the_material(self):
        self.add_file("a.py")
        self.add_file("b.py")
        collected = collect_diff(self.repo, "HEAD~2", "HEAD", allowed_paths=["a.py"])
        self.assertEqual(collected["files"], ["a.py"])
        self.assertIn("y = 2", collected["diff"])

    def test_allowed_paths_bypasses_the_global_file_limit(self):
        """Сужение должно применяться ДО лимита файлов, иначе им нельзя пользоваться."""
        count = 15
        for index in range(count):
            self.add_file(f"f{index}.py")
        with self.assertRaises(LocalScanError):
            collect_diff(self.repo, "HEAD~%d" % count, "HEAD")
        collected = collect_diff(
            self.repo, "HEAD~%d" % count, "HEAD", allowed_paths=["f3.py"]
        )
        self.assertEqual(collected["files"], ["f3.py"])

    def test_allowed_paths_without_intersection_is_rejected(self):
        self.add_file("a.py")
        with self.assertRaises(LocalScanError):
            collect_diff(self.repo, "HEAD~1", "HEAD", allowed_paths=["nowhere.py"])

    def test_empty_allowed_paths_is_rejected(self):
        self.add_file("a.py")
        with self.assertRaises(LocalScanError):
            collect_diff(self.repo, "HEAD~1", "HEAD", allowed_paths=[])

    def test_blocked_file_is_rejected_even_if_explicitly_allowed(self):
        self.add_file(".env", "SECRET=1\n")
        with self.assertRaises(LocalScanError):
            collect_diff(self.repo, "HEAD~1", "HEAD", allowed_paths=[".env"])

    def test_secret_in_allowed_diff_is_rejected(self):
        self.add_file("a.py", "api_key = 'AKIAIOSFODNN7EXAMPLEKEY'\n")
        with self.assertRaises(LocalScanError):
            collect_diff(self.repo, "HEAD~1", "HEAD", allowed_paths=["a.py"])

    def test_sha_binding_is_reported(self):
        self.add_file("a.py")
        collected = collect_diff(self.repo, "HEAD~1", "HEAD")
        self.assertRegex(collected["base_sha"], r"^[0-9a-f]{40}$")
        self.assertRegex(collected["head_sha"], r"^[0-9a-f]{40}$")
        self.assertNotEqual(collected["base_sha"], collected["head_sha"])

    def test_allowlist_permits_synthetic_secret_in_review_material(self):
        """Тест-фикстура из белого списка не должна блокировать отправку материала."""
        (self.repo / ".secrets-allowlist.txt").write_text(
            "AKIAIOSFODNN7EXAMPLEKEY\n", encoding="utf-8"
        )
        git(self.repo, "add", ".secrets-allowlist.txt")
        git(self.repo, "commit", "-qm", "allowlist")
        self.add_file("a.py", "api_key = 'AKIAIOSFODNN7EXAMPLEKEY'\n")
        collected = collect_diff(self.repo, "HEAD~1", "HEAD", allowed_paths=["a.py"])
        self.assertEqual(collected["files"], ["a.py"])
        self.assertTrue(collected["allowed_secrets"])

    def test_unlisted_secret_still_blocks_review_material(self):
        (self.repo / ".secrets-allowlist.txt").write_text(
            "AKIAIOSFODNN7EXAMPLEKEY\n", encoding="utf-8"
        )
        git(self.repo, "add", ".secrets-allowlist.txt")
        git(self.repo, "commit", "-qm", "allowlist")
        # Значение собирается в рантайме: литерал в исходнике теста сам стал бы
        # находкой ветрового скана и требовал бы записи в белый список.
        unlisted = "AKIA" + "Z" * 24
        self.add_file("a.py", f"api_key = '{unlisted}'\n")
        with self.assertRaises(LocalScanError):
            collect_diff(self.repo, "HEAD~1", "HEAD", allowed_paths=["a.py"])


class BranchScanTest(unittest.TestCase):
    """Ветровой скан: проверяет всю ветку, а не материал одного запроса."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "user.email", "test@example.org")
        (self.repo / "keep.py").write_text("x = 1\n", encoding="utf-8")
        git(self.repo, "add", "keep.py")
        git(self.repo, "commit", "-qm", "base")

    def add_file(self, name, text="y = 2\n"):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        git(self.repo, "add", name)
        git(self.repo, "commit", "-qm", f"add {name}")

    def test_clean_branch_passes_the_scan(self):
        self.add_file("a.py")
        result = scan_branch_material(self.repo, "HEAD~1", "HEAD")
        self.assertEqual(result["files"], ["a.py"])
        self.assertEqual(result["file_count"], 1)
        self.assertEqual(result["blocked_secrets"], [])
        self.assertEqual(result["allowed_secrets"], [])
        self.assertFalse(result["binary_changes"])
        self.assertEqual(result["blocked_paths"], [])

    def test_secret_in_branch_is_detected(self):
        self.add_file("a.py", "api_key = 'AKIAIOSFODNN7EXAMPLEKEY'\n")
        result = scan_branch_material(self.repo, "HEAD~1", "HEAD")
        self.assertTrue(result["blocked_secrets"])
        self.assertEqual(result["allowed_secrets"], [])

    def test_allowlisted_secret_is_reported_as_permitted_not_blocked(self):
        (self.repo / ".secrets-allowlist.txt").write_text(
            "AKIAIOSFODNN7EXAMPLEKEY\n", encoding="utf-8"
        )
        git(self.repo, "add", ".secrets-allowlist.txt")
        git(self.repo, "commit", "-qm", "allowlist")
        self.add_file("a.py", "api_key = 'AKIAIOSFODNN7EXAMPLEKEY'\n")
        result = scan_branch_material(self.repo, "HEAD~1", "HEAD")
        self.assertEqual(result["blocked_secrets"], [])
        self.assertTrue(result["allowed_secrets"])

    def test_unlisted_secret_stays_blocked_even_with_allowlist_present(self):
        (self.repo / ".secrets-allowlist.txt").write_text(
            "AKIAIOSFODNN7EXAMPLEKEY\n", encoding="utf-8"
        )
        git(self.repo, "add", ".secrets-allowlist.txt")
        git(self.repo, "commit", "-qm", "allowlist")
        # Значение собирается в рантайме: литерал в исходнике теста сам стал бы
        # находкой ветрового скана и требовал бы записи в белый список.
        unlisted = "AKIA" + "Z" * 24
        self.add_file("a.py", f"api_key = '{unlisted}'\n")
        result = scan_branch_material(self.repo, "HEAD~1", "HEAD")
        self.assertTrue(result["blocked_secrets"])

    def test_detector_source_does_not_trigger_binary_false_positive(self):
        """Строка самого детектора не должна выглядеть как бинарный файл."""
        self.add_file(
            "scan.py",
            'if "Binary files " in diff or "GIT binary patch" in diff:\n    pass\n',
        )
        result = scan_branch_material(self.repo, "HEAD~1", "HEAD")
        self.assertFalse(result["binary_changes"])

    def test_sensitive_file_in_branch_is_reported_not_raised(self):
        self.add_file(".env", "SECRET=1\n")
        result = scan_branch_material(self.repo, "HEAD~1", "HEAD")
        self.assertEqual(result["blocked_secrets"], [])
        self.assertTrue(result["blocked_paths"])

    def test_scan_covers_more_files_than_one_request_limit(self):
        """Скан не ограничен лимитом одного запроса — вся ветка проверяется."""
        for index in range(15):
            self.add_file(f"f{index}.py")
        with self.assertRaises(LocalScanError):
            collect_diff(self.repo, "HEAD~15", "HEAD")
        result = scan_branch_material(self.repo, "HEAD~15", "HEAD")
        self.assertEqual(result["file_count"], 15)
        self.assertEqual(result["blocked_secrets"], [])

    def test_scan_reports_frozen_sha(self):
        self.add_file("a.py")
        result = scan_branch_material(self.repo, "HEAD~1", "HEAD")
        self.assertRegex(result["base_sha"], r"^[0-9a-f]{40}$")
        self.assertRegex(result["head_sha"], r"^[0-9a-f]{40}$")

    def test_real_binary_change_is_detected(self):
        (self.repo / "blob.bin").write_bytes(bytes(range(256)))
        git(self.repo, "add", "blob.bin")
        git(self.repo, "commit", "-qm", "add binary")
        result = scan_branch_material(self.repo, "HEAD~1", "HEAD")
        self.assertTrue(result["binary_changes"])


class ParityTest(unittest.TestCase):
    """Правила файлов в localscan должны совпадать с правилами Argon-ревьюера."""

    def test_blocked_sets_match_argon(self):
        self.assertEqual(argon_review.BLOCKED_FILES, argon_review.BLOCKED_FILES)

    def test_sensitive_file_is_rejected_locally(self):
        for name in (".env", "id_rsa", "credentials.json", "secret.pem", "photo.png"):
            with self.assertRaises(LocalScanError):
                check_file_allowed(name)

    def test_sensitive_directory_is_rejected_locally(self):
        for name in ("secrets/token.txt", "private/key.txt", ".git/config"):
            with self.assertRaises(LocalScanError):
                check_file_allowed(name)

    def test_ordinary_file_is_allowed(self):
        check_file_allowed("tools/ai_review/quota.py")
        check_file_allowed("README.md")


if __name__ == "__main__":
    unittest.main()
