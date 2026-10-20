#!/usr/bin/env python3
"""Проверка платного вызова GPT-6 Astra (KIE) с файлами пакета AUDIT-001.

Маршрут: POST https://api.kie.ai/openai/v1/responses  (Responses-совместимый)
Модель: gpt-6-astra
Файлы:  пакеты Tier 1 пакета AUDIT-001A как input_file (text/plain, base64)

Ключ: переменная окружения KIE_API_KEY. Баланс меряется до и после.
Автоматических повторов НЕТ (неоднозначный исход — не повторять).
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://api.kie.ai/openai/v1/responses"
CREDIT_URL = "https://api.kie.ai/api/v1/chat/credit"
MODEL = "gpt-6-astra"

FILES = [
    "PROJECT_CONTEXT.md",
    "ARCHITECTURE_MAP.md",
    "P0_EVIDENCE.md",
    "TEST_RESULTS.md",
]

QUESTION = """Ты получил четыре документа проекта GremoVOD во вложениях (input_file).

Ответь ТОЛЬКО на один вопрос и ответь по фактам из вложений:

Какой документ содержит перечень ПРОВЕРЕННЫХ, а не предполагаемых, результатов
тестов, и какое конкретно число тестов в нём указано для ветки PR #29
(c082829b11b968965600bdaf87c137b1485a0fa2)?

Требуемый формат ответа (не более 120 слов):
- Документ: <имя файла>
- Число тестов PR #29: <число>
- Подтверждение: <цитата из вложения>
- Прочитаны ли все четыре вложения: да/нет, перечисли имена файлов, которые ты видел

Если во вложениях нет ответа — скажи прямо «нет в материалах», не додумывай."""


def credits(key: str) -> float:
    req = urllib.request.Request(CREDIT_URL, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return float(json.loads(r.read())["data"])


def b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def main() -> int:
    key = os.environ.get("KIE_API_KEY", "").strip()
    if not key:
        raise SystemExit("не задана KIE_API_KEY")

    out_dir = ROOT / "responses"
    out_dir.mkdir(parents=True, exist_ok=True)

    before = credits(key)
    print(f"баланс до      : {before:.2f} кредита")

    parts: list[dict] = []
    for name in FILES:
        p = ROOT / name
        if not p.exists():
            raise SystemExit(f"нет файла: {p}")
        raw = p.read_bytes()
        parts.append({
            "type": "input_file",
            "filename": name,
            "file_data": "data:text/plain;base64," + b64(p),
        })
        print(f"  вложение: {name:<26} {len(raw):>7,} байт")

    parts.append({"type": "input_text", "text": QUESTION})

    instructions = (
        "Ты — независимый архитектурный аудитор GremoVOD. Отвечай по фактам из "
        "приложенных файлов, ссылайся на файл и строки. Не додумывай: если в материалах "
        "нет ответа — так и напиши. Отвечай на заданный вопрос, не пересказывай проект."
    )

    # В Responses API `input` — массив ИТОКОВ (message/reasoning/...), а части
    # контента (input_text / input_file) лежат внутри item типа message.
    body = {
        "model": MODEL,
        "instructions": instructions,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": parts,
            }
        ],
        "max_output_tokens": 900,
        "stream": False,
    }
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
    print(f"\nтело запроса   : {len(raw):,} байт")
    print(f"URL            : {URL}")
    print("\nотправка…")
    t0 = time.time()
    try:
        req = urllib.request.Request(
            URL, data=raw, method="POST",
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json; charset=utf-8"})
        with urllib.request.urlopen(req, timeout=900) as r:
            data = r.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        print(f"HTTP {exc.code}: {detail[:1200]}")
        print("Повтор НЕ выполняется: неоднозначный исход.")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"сбой: {exc}")
        print("Повтор НЕ выполняется: неоднозначный исход.")
        return 2

    elapsed = time.time() - t0
    after = credits(key)
    spent = before - after

    path = out_dir / "GPT-ASTRA-AUDIT-001A.filecheck.json"
    path.write_bytes(data)
    parsed = json.loads(data)

    print(f"\nответ за {elapsed:.1f} с -> {path}")
    print(f"баланс после   : {after:.2f}  (израсходовано {spent:.4f} кредита)")

    usage = parsed.get("usage") or (parsed.get("response") or {}).get("usage") or {}
    if usage:
        print(f"usage          : {json.dumps(usage, ensure_ascii=False)}")

    # извлечь текст
    text = ""
    for item in parsed.get("output", []) or (parsed.get("response") or {}).get("output", []) or []:
        for c in item.get("content", []) or []:
            if c.get("type") in ("output_text", "text"):
                text += c.get("text", "")
    if not text:
        for c in parsed.get("output_text", []) or []:
            text += c.get("text", "") if isinstance(c, dict) else str(c)
    if not text:
        text = parsed.get("output_text") or ""
    if isinstance(text, list):
        text = "".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in text)

    if text:
        md = out_dir / "GPT-ASTRA-AUDIT-001A.filecheck.md"
        md.write_text(text, encoding="utf-8")
        print(f"текст ответа   : {md}  ({len(text):,} символов)")
        print("\n--- ОТВЕТ МОДЕЛИ ---\n" + text[:2000])
    else:
        print("\n--- ключи ответа ---")
        print(json.dumps(list(parsed.keys()), ensure_ascii=False))
        print((parsed.get("response") or {}).get("status"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
