#!/usr/bin/env python3
"""Проверка: влияет ли расширение файла (.md / .json) на приём в GPT-6 Astra.

Маршрут: POST https://api.kie.ai/openai/v1/responses
Вложения: input_file с data:<media_type>;base64,... и filename с нужным расширением.

Запуск: python -X utf8 packages/gpt_astra_extcheck.py
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://api.kie.ai/openai/v1/responses"
CREDIT_URL = "https://api.kie.ai/api/v1/chat/credit"
MODEL = "gpt-6-astra"

# (имя файла, которое видит модель, исходник в репозитории)
CASES = [
    ("evidence.md", "P0_EVIDENCE.md", "text/plain"),
    ("manifest.json", "EVIDENCE_MANIFEST.json", "application/json"),
]

QUESTION = (
    "Во вложениях два файла. Ответь одной строкой в формате:\n"
    "FILE1: <имя файла, который ты видишь> | FIRSTLINE: <первая строка его содержимого>\n"
    "FILE2: <имя файла, который ты видишь> | FIRSTLINE: <первая строка его содержимого>\n"
    "Если вложение не было принято — напиши ОТСУТСТВУЕТ: <имя>."
)


def credits(key: str) -> float:
    req = urllib.request.Request(CREDIT_URL, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return float(json.loads(r.read())["data"])


def main() -> int:
    key = os.environ.get("KIE_API_KEY", "").strip()
    if not key:
        raise SystemExit("не задана KIE_API_KEY")
    before = credits(key)
    print(f"баланс до: {before:.2f}")

    content: list[dict] = []
    for shown, src, media in CASES:
        raw = (ROOT / src).read_bytes()
        content.append({
            "type": "input_file",
            "filename": shown,
            "file_data": f"data:{media};base64," + base64.b64encode(raw).decode("ascii"),
        })
        print(f"  {shown:<16} <- {src} ({len(raw):,} байт, media_type={media})")
    content.append({"type": "input_text", "text": QUESTION})

    body = {
        "model": MODEL,
        "instructions": "Отвечай кратко и только по фактам из вложений.",
        "input": [{"type": "message", "role": "user", "content": content}],
        "max_output_tokens": 300,
        "stream": False,
    }
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    print(f"\nтело: {len(raw):,} байт")

    t0 = time.time()
    try:
        req = urllib.request.Request(
            URL, data=raw, method="POST",
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=600) as r:
            data = r.read()
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8','replace')[:600]}")
        print("Повтор НЕ выполняется.")
        return 2

    p = json.loads(data)
    after = credits(key)
    usage = p.get("usage", {})
    print(f"\nстатус : {p.get('status')}   модель: {p.get('model')}   {time.time()-t0:.1f} с")
    print(f"usage  : in={usage.get('input_tokens')} out={usage.get('output_tokens')} "
          f"total={usage.get('total_tokens')}")
    print(f"credits_consumed (в ответе): {p.get('credits_consumed')}")
    print(f"баланс: {before:.2f} -> {after:.2f}  (списано {before-after:.4f})")

    # В Responses API поле `text` — это КОНФИГ формата вывода, а не сам ответ.
    # Ответ лежит в output[].content[].text
    chunks: list[str] = []
    for item in p.get("output", []) or []:
        for c in item.get("content", []) or []:
            if c.get("type") in ("output_text", "text"):
                chunks.append(c.get("text", ""))
    text = "".join(chunks)
    if not text:
        raw_text = p.get("text")
        text = raw_text if isinstance(raw_text, str) else json.dumps(raw_text, ensure_ascii=False)
    print("\n--- ОТВЕТ ---\n" + (text[:1500] if text else "(текст не извлечён)"))
    print("\n--- структура output ---")
    for item in (p.get("output") or []):
        print("  item.type =", item.get("type"), "| content types:",
              [c.get("type") for c in item.get("content", [])])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
