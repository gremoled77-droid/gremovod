#!/usr/bin/env python3
"""Сборка текстовых payload'ов для KIE из файлов пакета.

KIE Claude Opus 5.5 принимает только текст: файл прикрепить нельзя.
Скрипт склеивает system prompt, материалы и текст запроса в один .txt,
который можно и отправить скриптом send_audit.ps1, и скопировать вручную.

Запуск:
    python packages/build_payloads.py            # из docs/ai-review/opus-audit-001/
    python packages/build_payloads.py --check    # только показать размеры

Файлы не изменяются, ничего не скачивается, сеть не используется.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "packages" / "payloads"

SYSTEM_MARK = "## Текст system prompt"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8").strip()


def system_prompt() -> str:
    """Достать текст system prompt из fenced-блока OPUS_SYSTEM_PROMPT.md."""
    md = read("OPUS_SYSTEM_PROMPT.md")
    part = md.split(SYSTEM_MARK, 1)[1]
    m = re.search(r"```(?:text)?\n(.*?)\n```", part, re.S)
    if not m:
        raise SystemExit("OPUS_SYSTEM_PROMPT.md: не найден fenced-блок с system prompt")
    return m.group(1).strip()


def request_text(pkg: str) -> str:
    """Достать текст запроса.

    AUDIT-001A: полный текст запроса лежит в OPUS_FIRST_REQUEST.md.
    AUDIT-001B/C: текст запроса вложен в сам пакет (fenced-блок «Раздел N»).
    """
    if pkg == "AUDIT-001A":
        md = read("OPUS_FIRST_REQUEST.md")
        part = md.split("## Текст запроса (копируется целиком)", 1)[1]
        blocks = re.findall(r"```\n(.*?)\n```", part, re.S)
        if not blocks:
            raise SystemExit("OPUS_FIRST_REQUEST.md: не найден блок с текстом запроса")
        text = max(blocks, key=len).strip()
    else:
        md = (ROOT / "packages" / f"{pkg}.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```\n(.*?)\n```", md, re.S)
        if not blocks:
            raise SystemExit(f"packages/{pkg}.md: не найден блок с текстом запроса")
        text = max(blocks, key=len).strip()

    if len(text) < 800:
        raise SystemExit(f"{pkg}: подозрительно короткий блок запроса ({len(text)} симв.)")
    if "независимый архитектурный аудитор" not in text and "Я — владелец GremoVOD" not in text:
        raise SystemExit(f"{pkg}: блок не похож на текст запроса — проверь, что выбран верный")
    return text


def section(rel: str, start: str | None = None, end: str | None = None) -> str:
    """Вырезать часть markdown-файла по заголовкам."""
    text = read(rel)
    if start:
        i = text.find(start)
        if i < 0:
            raise SystemExit(f"{rel}: не найден раздел «{start}»")
        text = text[i:]
    if end:
        j = text.find(end)
        if j < 0:
            raise SystemExit(f"{rel}: не найден раздел «{end}»")
        text = text[:j]
    return text.strip()


def file_block(rel: str, body: str | None = None) -> str:
    body = body if body is not None else read(rel)
    return f"=== FILE: {rel} ===\n{body.strip()}\n"


# --- определения пакетов -------------------------------------------------
#
# Для каждого пакета: (имя, [(метка, содержимое)], текст запроса)
# Содержимое уже готово к вставке «как есть» — без ссылок на файлы.

def build_001a() -> str:
    return "\n\n".join([
        "=== SYSTEM PROMPT (Claude Opus 5.5 / KIE) ===\n" + system_prompt(),
        file_block("PROJECT_CONTEXT.md"),
        file_block("ARCHITECTURE_MAP.md"),
        file_block("P0_EVIDENCE.md"),
        file_block("TEST_RESULTS.md"),
        "=== ЗАПРОС ===\n" + request_text("AUDIT-001A"),
    ])


def build_001b() -> str:
    ctx = section("PROJECT_CONTEXT.md", "## A. Назначение", "## F. Вопросы к владельцу")
    arch = section("ARCHITECTURE_MAP.md", "## 1. Топология рантайма", "## 3. Frontend")
    arch += "\n\n" + section("ARCHITECTURE_MAP.md", "## 4. Зрелость реализации по доменам", "## 5. Покрытие тестами")
    p0 = section("P0_EVIDENCE.md", "## B-02. Единый бюджет и резервы", "## B-03.")
    p0 += "\n\n" + section("P0_EVIDENCE.md", "## B-07. Заморозка плана и манифеста", "## B-08.")
    return "\n\n".join([
        "=== SYSTEM PROMPT (Claude Opus 5.5 / KIE) ===\n" + system_prompt(),
        file_block("PROJECT_CONTEXT.md", ctx),
        file_block("ARCHITECTURE_MAP.md", arch),
        file_block("WORKFLOW_EVIDENCE.md"),
        file_block("P0_EVIDENCE.md", p0),
        "=== ЗАПРОС ===\n" + request_text("AUDIT-001B"),
    ])


def build_001c() -> str:
    ctx = section("PROJECT_CONTEXT.md", "## A. Назначение", "## F. Вопросы к владельцу")
    return "\n\n".join([
        "=== SYSTEM PROMPT (Claude Opus 5.5 / KIE) ===\n" + system_prompt(),
        file_block("PROJECT_CONTEXT.md", ctx),
        file_block("QA_EVIDENCE.md"),
        file_block("TEST_RESULTS.md"),
        file_block("OPEN_ISSUES.md"),
        "=== ЗАПРОС ===\n" + request_text("AUDIT-001C"),
    ])


PACKAGES = {
    "AUDIT-001A": build_001a,
    "AUDIT-001B": build_001b,
    "AUDIT-001C": build_001c,
}

# Оценка токенов: русский текст и код — ~3.2-3.5 символа на токен.
CHARS_PER_TOKEN = 3.35

# --- вложения -----------------------------------------------------------
#
# KIE принимает файлы, но отвергает media_type .md (text/markdown) и
# .json (application/json). Поддерживаются application/pdf и text/plain.
# Поэтому для каждого документа делается .txt-копия с теми же байтами:
# её можно и приложить как файл, и отправить блоком document/text/plain.
#
# Список совпадает с DOCS в send_audit.py.

ATTACH = {
    "AUDIT-001A": ["PROJECT_CONTEXT.md", "ARCHITECTURE_MAP.md", "P0_EVIDENCE.md", "TEST_RESULTS.md"],
    "AUDIT-001B": ["PROJECT_CONTEXT.md", "ARCHITECTURE_MAP.md", "WORKFLOW_EVIDENCE.md", "P0_EVIDENCE.md"],
    "AUDIT-001C": ["PROJECT_CONTEXT.md", "QA_EVIDENCE.md", "TEST_RESULTS.md", "OPEN_ISSUES.md"],
}


def build_attachments() -> None:
    """Записать .txt-версии документов в packages/attachments/<PKG>/."""
    base = ROOT / "packages" / "attachments"
    for pkg, files in ATTACH.items():
        d = base / pkg
        d.mkdir(parents=True, exist_ok=True)
        for rel in files:
            src = ROOT / rel
            if not src.exists():
                raise SystemExit(f"нет файла: {rel}")
            text = src.read_text(encoding="utf-8")
            # .txt вместо .md/.json — те же байты, поддерживаемый media_type
            (d / (Path(rel).stem + ".txt")).write_text(text, encoding="utf-8", newline="\n")
        (d / "MANIFEST.txt").write_text(
            "Документы пакета " + pkg + " в формате text/plain (те же байты, что в .md/.json).\n"
            "KIE отвергает media_type text/markdown и application/json; text/plain принимает.\n\n"
            + "\n".join(f"{Path(r).stem}.txt <- {r}" for r in files) + "\n",
            encoding="utf-8", newline="\n")
        print(f"attachments/{pkg}: {len(files)} файлов + MANIFEST.txt")


def main() -> int:
    check = "--check" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"{'payload':<16}{'символов':>10}{'~токенов':>10}  файл")
    print("-" * 72)
    total = 0
    for name, fn in PACKAGES.items():
        text = fn()
        est = round(len(text) / CHARS_PER_TOKEN)
        total += est
        path = OUT / f"{name}.payload.txt"
        if not check:
            path.write_text(text, encoding="utf-8", newline="\n")
        print(f"{name:<16}{len(text):>10,}{est:>10,}  {path.name}")
    print("-" * 72)
    print(f"{'ИТОГО':<16}{'':>10}{total:>10,}")
    print()
    print("Оценка: chars/3.35. Реальное usage.input_tokens смотри в ответе KIE.")
    print(f"System prompt отдельно: {round(len(system_prompt())/CHARS_PER_TOKEN):,} токенов")
    if not check:
        print()
        build_attachments()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
