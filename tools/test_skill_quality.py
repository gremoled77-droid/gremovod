"""Offline unit tests for the project skill quality checker.

The checker validates the skills that live under ``.minimax/skills/`` in this
repository: their frontmatter, their name, the sections the quality gate
requires, and the repository rules that must not be broken (Aider-specific
commands, placeholder text, broken formatting).

Everything here is offline: fixtures are written to a temporary directory and
the checker is called in-process. The one test that touches the repository
checks the real GremoVOD gate skill against the real checker, so the checker
cannot be weakened without that test failing.
"""
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.check_skill_quality import (
    FORBIDDEN_TOKENS,
    NAME_PATTERN,
    REQUIRED_SECTIONS,
    ROOT,
    check_skill_file,
    main,
    parse_frontmatter,
    split_frontmatter,
)

VALID_FRONTMATTER = """---
name: demo-skill
description: |
  Демонстрационный скилл для юнит-тестов валидатора качества скиллов.
---

# Демо

## 1. Preflight

Проверить состояние репозитория.

## 2. Red → Green

Сначала тест, потом исправление.
"""


def write_skill(root: Path, name: str, frontmatter: str = VALID_FRONTMATTER,
                body: str = "", directory: str = None) -> Path:
    """Create ``<root>/.minimax/skills/<name>/SKILL.md`` and return its path."""
    directory = directory or name
    skill_dir = root / ".minimax" / "skills" / directory
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / "SKILL.md"
    path.write_text(frontmatter + body, encoding="utf-8")
    return path


class FrontmatterParsingTests(unittest.TestCase):
    def test_valid_frontmatter_is_split_from_the_body(self):
        raw, body, error = split_frontmatter(VALID_FRONTMATTER)
        self.assertIsNone(error)
        self.assertIn("name: demo-skill", raw)
        self.assertIn("# Демо", body)

    def test_missing_frontmatter_is_reported(self):
        raw, _body, error = split_frontmatter("# просто текст\n")
        self.assertIsNone(raw)
        self.assertIsNotNone(error)

    def test_unterminated_frontmatter_is_reported(self):
        raw, _body, error = split_frontmatter("---\nname: demo-skill\n")
        self.assertIsNone(raw)
        self.assertIsNotNone(error)

    def test_block_scalar_is_read_as_one_string(self):
        data, problems = parse_frontmatter(
            "name: demo-skill\ndescription: |\n  первая строка\n  вторая строка\n"
        )
        self.assertEqual(problems, [])
        self.assertEqual(data["name"], "demo-skill")
        self.assertIn("первая строка", data["description"])
        self.assertIn("вторая строка", data["description"])

    def test_duplicate_key_is_reported(self):
        data, problems = parse_frontmatter("name: a\nname: b\n")
        self.assertTrue(problems)
        self.assertTrue(any("дублирующий" in problem for problem in problems))

    def test_line_without_colon_is_reported(self):
        _data, problems = parse_frontmatter("name demo-skill\n")
        self.assertTrue(problems)

    def test_unexpected_indent_is_reported(self):
        _data, problems = parse_frontmatter("name: demo-skill\n  случайный отступ\n")
        self.assertTrue(problems)


class SkillFileChecksTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_valid_skill_has_no_problems(self):
        path = write_skill(self.root, "demo-skill")
        self.assertEqual(check_skill_file(path), [])

    def test_missing_frontmatter_is_reported(self):
        path = write_skill(self.root, "demo-skill", frontmatter="# без frontmatter\n")
        problems = check_skill_file(path)
        self.assertTrue(any("frontmatter" in problem for problem in problems))

    def test_name_must_match_the_directory(self):
        path = write_skill(self.root, "demo-skill", directory="other-dir")
        problems = check_skill_file(path)
        self.assertTrue(any("имя каталога" in problem for problem in problems))

    def test_invalid_name_is_reported(self):
        path = write_skill(self.root, "demo-skill", frontmatter=VALID_FRONTMATTER.replace(
            "name: demo-skill", "name: Demo Skill"))
        problems = check_skill_file(path)
        self.assertTrue(
            any("Demo Skill" in problem for problem in problems),
            msg=f"некорректное имя не найдено в нарушениях: {problems}",
        )

    def test_missing_description_is_reported(self):
        frontmatter = "---\nname: demo-skill\n---\n\n# Демо\n"
        path = write_skill(self.root, "demo-skill", frontmatter=frontmatter)
        problems = check_skill_file(path)
        self.assertTrue(any("description" in problem for problem in problems))

    def test_short_description_is_reported(self):
        frontmatter = "---\nname: demo-skill\ndescription: коротко\n---\n\n# Демо\n"
        path = write_skill(self.root, "demo-skill", frontmatter=frontmatter)
        problems = check_skill_file(path)
        self.assertTrue(any("description" in problem for problem in problems))

    def test_missing_required_section_is_reported(self):
        path = write_skill(self.root, "demo-skill")
        problems = check_skill_file(path, required_sections=("## 4. CI must be green",))
        self.assertTrue(any("CI must be green" in problem for problem in problems))

    def test_aider_specific_command_is_reported(self):
        for token in FORBIDDEN_TOKENS:
            with self.subTest(token=token):
                path = write_skill(
                    self.root, "demo-skill", body=f"\nИспользуй {token} блок.\n")
                problems = check_skill_file(path)
                self.assertTrue(
                    any(token in problem for problem in problems),
                    msg=f"токен {token!r} не найден в нарушениях: {problems}",
                )

    def test_placeholder_marker_is_reported(self):
        path = write_skill(self.root, "demo-skill", body="\nTODO: дописать раздел.\n")
        problems = check_skill_file(path)
        self.assertTrue(any("placeholder" in problem for problem in problems))

    def test_tab_character_is_reported(self):
        path = write_skill(self.root, "demo-skill", body="\n\tс табуляцией\n")
        problems = check_skill_file(path)
        self.assertTrue(any("табуляц" in problem for problem in problems))

    def test_unbalanced_code_fence_is_reported(self):
        path = write_skill(self.root, "demo-skill", body="\n```python\nx = 1\n")
        problems = check_skill_file(path)
        self.assertTrue(any("ограждени" in problem for problem in problems))


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def run_main(self, argv):
        """Run the checker in-process and capture its report."""
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = main(argv)
        return code, buffer.getvalue()

    def test_exit_code_zero_for_a_valid_skill(self):
        write_skill(self.root, "demo-skill")
        code, report = self.run_main(["--root", str(self.root)])
        self.assertEqual(code, 0, msg=report)
        self.assertIn("SKILL_QUALITY: OK", report)

    def test_exit_code_one_for_a_broken_skill(self):
        write_skill(self.root, "demo-skill", frontmatter="# без frontmatter\n")
        code, report = self.run_main(["--root", str(self.root)])
        self.assertEqual(code, 1, msg=report)
        self.assertIn("SKILL_QUALITY: FAIL", report)

    def test_missing_skill_root_is_an_error(self):
        code, report = self.run_main(["--root", str(self.root / "empty")])
        self.assertEqual(code, 1, msg=report)
        self.assertIn("скиллы не найдены", report)

    def test_explicit_path_is_checked(self):
        path = write_skill(self.root, "demo-skill")
        code, report = self.run_main([str(path)])
        self.assertEqual(code, 0, msg=report)

    def test_explicit_missing_path_is_an_error(self):
        code, report = self.run_main([str(self.root / "нет" / "SKILL.md")])
        self.assertEqual(code, 1, msg=report)
        self.assertIn("файла нет", report)

    def test_module_runs_as_a_script(self):
        result = subprocess.run(
            [sys.executable, "-X", "utf8", str(ROOT / "tools" / "check_skill_quality.py")],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("SKILL_QUALITY: OK", result.stdout)


class ProjectSkillTests(unittest.TestCase):
    """The real GremoVOD gate skill must pass the real checker."""

    def setUp(self):
        self.path = (ROOT / ".minimax" / "skills" / "gremovod-code-quality" / "SKILL.md")
        self.assertTrue(
            self.path.is_file(),
            msg=f"скилл не найден: {self.path}",
        )

    def test_project_skill_passes_the_checker(self):
        problems = check_skill_file(
            self.path, required_sections=REQUIRED_SECTIONS.get("gremovod-code-quality", ()))
        self.assertEqual(problems, [])

    def test_checker_requires_the_owner_mandated_sections(self):
        required = REQUIRED_SECTIONS.get("gremovod-code-quality", ())
        for section in (
            "## 1. Preflight",
            "## 2. Red → Green",
            "## 3. Проверка противоположных сценариев",
            "## 4. CI must be green",
        ):
            self.assertIn(section, required)

    def test_name_pattern_accepts_the_project_skill(self):
        self.assertTrue(NAME_PATTERN.match("gremovod-code-quality"))


if __name__ == "__main__":
    unittest.main()
