"""Проверка качества проектных скиллов MiniMax Code (GremoVOD).

Валидатор проверяет скиллы, которые лежат в репозитории по пути
``.minimax/skills/<name>/SKILL.md``:

* корректный frontmatter с полями ``name`` и ``description``;
* имя скилла соответствует шаблону и совпадает с именем каталога — так его
  находит загрузчик скиллов;
* обязательные разделы скилла присутствуют (для скилла гейта качества это
  четыре правила владельца);
* в тексте нет Aider-специфичных команд и placeholder-заглушек;
* файл технически цел: без табуляций, с парными ограждениями кодовых блоков.

Скрипт работает офлайн, без внешних сервисов и без зависимостей. Он не
проверяет код приложения и ничего не меняет на диске.

Запуск: ``python tools/check_skill_quality.py [--root ROOT] [path ...]``.
Код возврата 0 — все проверенные скиллы корректны, 1 — есть нарушения.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = Path(".minimax") / "skills"
SKILL_FILE = "SKILL.md"

# Имя скилла — это идентификатор каталога: строчные буквы, цифры и дефис.
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Описание должно объяснять, когда скилл применяется, а не быть пустым ярлыком.
MIN_DESCRIPTION_LENGTH = 40

# Aider-специфичные команды в проектных скиллах MiniMax Code не переносятся:
# они описывают другой инструмент и в этом репозитории не работают.
FORBIDDEN_TOKENS = (
    "SEARCH/REPLACE",
    "/read-only",
    "Repo Map",
    "[IMPACT]",
)

# Заглушки вместо содержания: такой файл читается как готовая работа.
PLACEHOLDER_MARKERS = (
    "TODO",
    "FIXME",
    "XXX",
    "... existing code",
    "остальной код",
    "<placeholder>",
    "ЗАПОЛНИТЬ",
)

# Обязательные разделы по скиллам. Список для gremovod-code-quality повторяет
# четыре правила владельца задачи GA-06 и разделы точности/границ/чек-листа;
# проверка не даёт скиллу потерять их при правках.
REQUIRED_SECTIONS = {
    "gremovod-code-quality": (
        "## 1. Preflight",
        "## 2. Red → Green",
        "## 3. Проверка противоположных сценариев",
        "## 4. CI must be green",
        "## 5. Точность заявлений и handoff",
        "## 6. Границы",
        "## 7. Чек-лист перед публикацией",
    ),
}


def split_frontmatter(text):
    """Split ``---`` frontmatter from the body.

    Returns ``(raw_frontmatter, body, error)``. ``raw_frontmatter`` is None and
    ``error`` is set when the file has no closed frontmatter block.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text, "нет YAML frontmatter: первая строка не '---'"
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1:]), None
    return None, text, "нет YAML frontmatter: закрывающий '---' не найден"


def parse_frontmatter(raw):
    """Parse the small YAML subset that skill frontmatter actually uses.

    Supported: ``key: value`` and block scalars (``key: |`` and ``key: >``).
    Anything else is reported as a problem instead of being guessed, because a
    silent guess would hide a broken file.
    """
    data = {}
    problems = []
    lines = raw.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line[:1].isspace():
            problems.append(f"frontmatter: неожиданный отступ ({line.strip()!r})")
            continue
        if ":" not in line:
            problems.append(f"frontmatter: строка без 'ключ: значение' ({line.strip()!r})")
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key in data:
            problems.append(f"frontmatter: дублирующий ключ {key!r}")
        if value in ("|", ">", "|-", ">-", "|+", ">+"):
            block = []
            while index < len(lines) and (
                not lines[index].strip() or lines[index][:1].isspace()
            ):
                block.append(lines[index].strip())
                index += 1
            data[key] = "\n".join(part for part in block if part).strip()
        else:
            data[key] = value.strip("\"'")
    return data, problems


def check_skill_file(path, required_sections=()):
    """Return the list of problems of one skill file. Empty list means valid."""
    problems = []
    text = path.read_text(encoding="utf-8")
    raw, body, error = split_frontmatter(text)
    if error:
        problems.append(error)
        data = {}
    else:
        data, front_problems = parse_frontmatter(raw)
        problems.extend(front_problems)

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append("frontmatter: нет поля name")
    else:
        if not NAME_PATTERN.match(name):
            problems.append(
                f"frontmatter: имя {name!r} не соответствует {NAME_PATTERN.pattern}")
        if name != path.parent.name:
            problems.append(
                f"frontmatter: имя {name!r} != имя каталога {path.parent.name!r}")

    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        problems.append("frontmatter: нет непустого поля description")
    elif len(description.strip()) < MIN_DESCRIPTION_LENGTH:
        problems.append(
            f"frontmatter: description короче {MIN_DESCRIPTION_LENGTH} символов "
            f"({len(description.strip())})")

    for section in required_sections:
        if section not in body:
            problems.append(f"нет обязательного раздела: {section}")

    for token in FORBIDDEN_TOKENS:
        if token in text:
            problems.append(f"Aider-специфичная команда в тексте: {token}")

    for marker in PLACEHOLDER_MARKERS:
        if marker in text:
            problems.append(f"placeholder-заглушка в тексте: {marker}")

    if "\t" in text:
        problems.append("в файле есть табуляции")
    if body.count("```") % 2 != 0:
        problems.append("нечётное число ограждений кодовых блоков")

    return problems


def iter_skill_files(root):
    """Return the skill files of a project root, sorted by path."""
    base = root / SKILL_ROOT
    if not base.is_dir():
        return []
    return sorted(path for path in base.glob(f"*/{SKILL_FILE}") if path.is_file())


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Проверить качество проектных скиллов MiniMax Code.")
    parser.add_argument(
        "--root", default=str(ROOT),
        help="корень репозитория (по умолчанию корень этого файла)")
    parser.add_argument(
        "paths", nargs="*",
        help="явные файлы скиллов; по умолчанию проверяются все скиллы проекта")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if args.paths:
        targets = [Path(item).resolve() for item in args.paths]
    else:
        targets = iter_skill_files(root)

    if not targets:
        print(f"SKILL_QUALITY: FAIL — скиллы не найдены в {root / SKILL_ROOT}")
        return 1

    failed = 0
    for path in targets:
        if not path.is_file():
            print(f"SKILL_QUALITY: FAIL — файла нет: {path}")
            failed += 1
            continue
        required = REQUIRED_SECTIONS.get(path.parent.name, ())
        problems = check_skill_file(path, required)
        if problems:
            failed += 1
            print(f"SKILL_QUALITY: FAIL — {path} ({len(problems)} нарушений)")
            for item in problems:
                print(f"  - {item}")
        else:
            print(f"SKILL_QUALITY: OK — {path}")

    if failed:
        print(f"SKILL_QUALITY: FAIL — файлов с нарушениями: {failed} из {len(targets)}")
        return 1
    print(f"SKILL_QUALITY: OK — проверено скиллов: {len(targets)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
