#!/usr/bin/env python3
"""Решающий тест: принимает ли GPT-6 Astra файлы с разными media_type и расширениями.

Каждому вложению — свой уникальный SENTINEL. Модель должна назвать файл и
эхо-нуть его сентинел. Если вложение не принято — «ОТСУТСТВУЕТ».

Запуск: python -X utf8 packages/gpt_astra_mediacheck.py
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://api.kie.ai/openai/v1/responses"
CREDIT_URL = "https://api.kie.ai/api/v1/chat/credit"
MODEL = "gpt-6-astra"

# (filename, media_type, sentinel)
CASES = [
    ("alpha.md", "text/plain", "SENTINEL-ALPHA-7Q1"),
    ("beta.json", "application/json", "SENTINEL-BETA-3M9"),
    ("gamma.md", "text/markdown", "SENTINEL-GAMMA-5K2"),
    ("delta.txt", "text/plain", "SENTINEL-DELTA-8R4"),
]

QUESTION = (
    "К каждому вложению добавлена уникальная строка-метка вида SENTINEL-XXXX-NNN, "
    "где XXXX — любые буквы, NNN — любые цифры (длина не важна).\n"
    "Для каждого из четырёх вложений выведи ровно одну строку:\n"
    "  <имя файла, как ты его видишь> | <его строка-метка SENTINEL из содержимого>\n"
    "Если вложение не было принято или его метки нет в содержимом — выведи:\n"
    "  <имя файла> | ОТСУТСТВУЕТ\n"
    "Ничего не додумывай: метку нужно скопировать из содержимого вложения."
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
    for shown, media, sentinel in CASES:
        payload = f"{sentinel}\n" + (f"Обычный текст для проверки вложения {shown}.\n" * 3)
        content.append({
            "type": "input_file",
            "filename": shown,
            "file_data": f"data:{media};base64," + base64.b64encode(payload.encode()).decode(),
        })
        print(f"  {shown:<12} media_type={media:<18} {sentinel}")
    content.append({"type": "input_text", "text": QUESTION})

    body = {
        "model": MODEL,
        "instructions": "Отвечай только по содержимому вложений. Ничего не додумывай.",
        "input": [{"type": "message", "role": "user", "content": content}],
        "max_output_tokens": 400,
        "stream": False,
    }
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    print(f"\nтело: {len(raw):,} байт")

    try:
        req = urllib.request.Request(
            URL, data=raw, method="POST",
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=600) as r:
            data = r.read()
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8','replace')[:800]}")
        return 2

    p = json.loads(data)
    after = credits(key)
    usage = p.get("usage", {})
    print(f"\nстатус: {p.get('status')}  модель: {p.get('model')}")
    print(f"usage : in={usage.get('input_tokens')} out={usage.get('output_tokens')}")
    print(f"credits_consumed: {p.get('credits_consumed')}   баланс {before:.2f} -> {after:.2f}")

    chunks: list[str] = []
    for item in p.get("output", []) or []:
        for c in item.get("content", []) or []:
            if c.get("type") in ("output_text", "text"):
                chunks.append(c.get("text", ""))
    print("\n--- ОТВЕТ ---\n" + ("".join(chunks)[:2000] or "(нет)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
