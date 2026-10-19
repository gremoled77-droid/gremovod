#!/usr/bin/env python3
"""Отправка пакета AUDIT на KIE (Claude Opus 5.5) с вложениями.

Почему вложения в формате .txt, а не .md/.json
------------------------------------------------
KIE (Anthropic-совместимый Messages API) принимает вложения, но отвергает
типы .md (text/markdown) и .json (application/json) — неподдерживаемые
media_type. Поддерживаются application/pdf и text/plain.

Поэтому каждый документ отдаётся в двух эквивалентных виде:
  * .txt  — те же байты, media_type text/plain. Основной путь: код и JSON
            читаются точно, токенизация дешёвая.
  * .pdf  — media_type application/pdf. Запасной путь, если инструмент
            владельца принимает только PDF.

Вложение в сообщение отправляется блоком:
  {"type":"document","source":{"type":"text","media_type":"text/plain","data":"<текст>"}}

Запуск:
    python packages/send_audit.py AUDIT-001A
    python packages/send_audit.py AUDIT-001A --pdf
    python packages/send_audit.py AUDIT-001A --dry-run

Ключ берётся из переменной окружения KIE_API_KEY.
Ответ автоматических повторов НЕ делает (правило проекта: неоднозначный исход —
не повторять молча).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAYLOADS = ROOT / "packages" / "payloads"
RESPONSES = ROOT / "responses"

API_URL = "https://api.kie.ai/claude/v1/messages"
MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000

# Документы каждого пакета: (метка, файл-источник в пакете)
DOCS: dict[str, list[tuple[str, str]]] = {
    "AUDIT-001A": [
        ("PROJECT_CONTEXT.md", "PROJECT_CONTEXT.md"),
        ("ARCHITECTURE_MAP.md", "ARCHITECTURE_MAP.md"),
        ("P0_EVIDENCE.md", "P0_EVIDENCE.md"),
        ("TEST_RESULTS.md", "TEST_RESULTS.md"),
    ],
    "AUDIT-001B": [
        ("PROJECT_CONTEXT.md", "PROJECT_CONTEXT.md"),
        ("ARCHITECTURE_MAP.md", "ARCHITECTURE_MAP.md"),
        ("WORKFLOW_EVIDENCE.md", "WORKFLOW_EVIDENCE.md"),
        ("P0_EVIDENCE.md", "P0_EVIDENCE.md"),
    ],
    "AUDIT-001C": [
        ("PROJECT_CONTEXT.md", "PROJECT_CONTEXT.md"),
        ("QA_EVIDENCE.md", "QA_EVIDENCE.md"),
        ("TEST_RESULTS.md", "TEST_RESULTS.md"),
        ("OPEN_ISSUES.md", "OPEN_ISSUES.md"),
    ],
}

SYSTEM_MARK = "## Текст system prompt"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8").strip()


def system_prompt() -> str:
    md = read("OPUS_SYSTEM_PROMPT.md")
    part = md.split(SYSTEM_MARK, 1)[1]
    m = __import__("re").search(r"```(?:text)?\n(.*?)\n```", part, __import__("re").S)
    if not m:
        raise SystemExit("OPUS_SYSTEM_PROMPT.md: не найден блок с system prompt")
    return m.group(1).strip()


def request_text(pkg: str) -> str:
    import re

    if pkg == "AUDIT-001A":
        md = read("OPUS_FIRST_REQUEST.md")
        part = md.split("## Текст запроса (копируется целиком)", 1)[1]
    else:
        md = (ROOT / "packages" / f"{pkg}.md").read_text(encoding="utf-8")
        part = md
    blocks = re.findall(r"```\n(.*?)\n```", part, re.S)
    if not blocks:
        raise SystemExit(f"{pkg}: не найден блок с текстом запроса")
    text = max(blocks, key=len).strip()
    if len(text) < 800:
        raise SystemExit(f"{pkg}: подозрительно короткий текст запроса")
    return text


def attachments(pkg: str) -> list[dict]:
    """Собрать document-блоки из реальных файлов пакета."""
    out: list[dict] = []
    for label, rel in DOCS[pkg]:
        path = ROOT / rel
        if not path.exists():
            raise SystemExit(f"нет файла: {rel}")
        data = path.read_text(encoding="utf-8")
        out.append({
            "type": "document",
            "source": {
                "type": "text",
                "media_type": "text/plain",
                "data": f"=== FILE: {label} ===\n{data}",
            },
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("package", choices=sorted(DOCS))
    ap.add_argument("--dry-run", action="store_true", help="собрать запрос и показать, не отправляя")
    ap.add_argument("--out", default=None, help="куда сохранить сырой ответ")
    args = ap.parse_args()

    key = os.environ.get("KIE_API_KEY", "").strip()
    if not key and not args.dry_run:
        raise SystemExit("не задана переменная окружения KIE_API_KEY")

    body = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "stream": False,
        "messages": [{
            "role": "user",
            "content": attachments(args.package) + [{
                "type": "text",
                "text": request_text(args.package),
            }],
        }],
    }
    payload = {
        "model": body["model"],
        "max_tokens": body["max_tokens"],
        "system": system_prompt(),
        "messages": body["messages"],
    }

    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    print(f"Пакет           : {args.package}")
    print(f"Модель          : {MODEL}")
    print(f"Вложений        : {len(DOCS[args.package])} (media_type=text/plain)")
    print(f"System prompt   : {len(system_prompt()):,} символов")
    print(f"Тело запроса    : {len(request_text(args.package)):,} символов")
    print(f"JSON тела       : {len(raw):,} байт")
    print(f"URL             : {API_URL}")

    if args.dry_run:
        print("\n--dry-run: запрос не отправлен.")
        return 0

    req = urllib.request.Request(
        API_URL,
        data=raw,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    print("\nОтправка…")
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        print(f"\nHTTP {exc.code} от KIE:\n{detail[:2000]}")
        print("\nПовтор НЕ выполняется: неоднозначный исход. Проверьте баланс и логи вручную.")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"\nСбой запроса: {exc}")
        print("Повтор НЕ выполняется: неоднозначный исход. Проверьте логи KIE вручную.")
        return 2

    elapsed = time.time() - started
    RESPONSES.mkdir(parents=True, exist_ok=True)
    out = Path(args.out) if args.out else RESPONSES / f"{args.package}.response.json"
    out.write_bytes(data)

    parsed = json.loads(data)
    usage = parsed.get("usage", {})
    print(f"\nОтвет за {elapsed:.1f} с → {out}")
    print(f"model       : {parsed.get('model')}")
    print(f"stop_reason : {parsed.get('stop_reason')}")
    print(f"usage       : {usage}")
    if usage:
        cost = (usage.get("input_tokens", 0) / 1e6 * 320
                + usage.get("output_tokens", 0) / 1e6 * 1600)
        print(f"оценка      : {cost:.1f} кредитов (≈ ${cost * 0.005:.3f})")
    text = "".join(b.get("text", "") for b in parsed.get("content", []) if b.get("type") == "text")
    if text:
        md = out.with_suffix(".md")
        md.write_text(text, encoding="utf-8")
        print(f"текст ответа: {md}  ({len(text):,} символов)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
