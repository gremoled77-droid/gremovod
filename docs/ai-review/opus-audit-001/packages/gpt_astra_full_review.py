#!/usr/bin/env python3
"""Полный разбор GremoVOD в GPT-6 Astra (KIE) — платный вызов.

Маршрут: POST https://api.kie.ai/openai/v1/responses
Модель: gpt-6-astra
Вложения: 7 документов пакета AUDIT-001 (text/plain, .md принимаются)
Задание: packages/GPT_ASTRA_TASK.md

Ключ: KIE_API_KEY из окружения. Баланс меряется до и после.
Автоматических повторов НЕТ.

Запуск: python -X utf8 packages/gpt_astra_full_review.py
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
MAX_OUTPUT = 12000

FILES = [
    "PROJECT_CONTEXT.md",
    "ARCHITECTURE_MAP.md",
    "P0_EVIDENCE.md",
    "WORKFLOW_EVIDENCE.md",
    "QA_EVIDENCE.md",
    "TEST_RESULTS.md",
    "OPEN_ISSUES.md",
]

SYSTEM = """Ты — независимый архитектурный аудитор GremoVOD. Работаешь как senior-архитектор, \
который 15+ лет ревьюил production-системы, где утечка бюджета или гонка данных стоили \
реальных денег.

Ты не автор кода и не имеешь доступа к репозиторию. Единственный источник фактов — \
приложенные документы. Каждое утверждение о поведении системы подкрепляй ссылкой на \
файл и строки; если код не проверен — пиши «не проверено».

Различай четыре зрелости и всегда указывай, к какой относишь вывод: IMPLEMENTED \
(исполняемый код это делает) / PARTIAL (код есть, но не весь случай) / SPEC-ONLY \
(описано в спецификации, исполнения нет) / MOCK (заглушка).

Зелёный тест — не доказательство отсутствия дефекта, а свидетельство, что заявленный \
сценарий не сломался. Тест, проверяющий заглушку, доказывает только, что заглушка работает.

В проекте намеренный fail-closed (нет доказательства = BLOCKED, а не «пройдено»). \
Это сильное решение: оценивай, соответствует ли оно заявленной цели, а не то, что оно есть.

Проектируй как владелец денег: цена вопроса — сколько реальных кредитов может уйти мимо \
учёта, при каких гонках и кто может это вызвать.

Правило ответа на текущий вопрос: каждое сообщение — новая точка отсчёта. Отвечай на ТОТ \
вопрос, который задан сейчас. Не начинай с «как я уже говорил», не продолжай начатое ранее \
рассуждение, не возвращайся к предыдущему ответу, пока владелец прямо не попросит, не укажет \
на ошибку или не сошлётся на него. Каждый ответ пригоден как самостоятельный документ: \
называй предмет (файл, раздел, ревизию) явно, без отсылок «выше».

Не хвали ради объёма и не пересказывай проект. Если узкое место не найдено — так и скажи."""


def credits(key: str) -> float:
    req = urllib.request.Request(CREDIT_URL, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return float(json.loads(r.read())["data"])


def main() -> int:
    key = os.environ.get("KIE_API_KEY", "").strip()
    if not key:
        raise SystemExit("не задана KIE_API_KEY")

    out = ROOT / "responses"
    out.mkdir(parents=True, exist_ok=True)

    task = (ROOT / "packages" / "GPT_ASTRA_TASK.md").read_text(encoding="utf-8")
    content: list[dict] = []
    for name in FILES:
        p = ROOT / name
        if not p.exists():
            raise SystemExit(f"нет файла: {p}")
        raw = p.read_bytes()
        content.append({
            "type": "input_file",
            "filename": name,
            "file_data": "data:text/plain;base64," + base64.b64encode(raw).decode("ascii"),
        })
        print(f"  вложение {name:<26} {len(raw):>7,} байт")
    content.append({"type": "input_text", "text": task})

    body = {
        "model": MODEL,
        "instructions": SYSTEM,
        "input": [{"type": "message", "role": "user", "content": content}],
        "max_output_tokens": MAX_OUTPUT,
        # stream=true обязателен для больших ответов: нестриминговый ответ на
        # этом маршруте упирается в Cloudflare 524 (edge-таймаут) — генерация
        # убивается на границе, и деньги списываются лишь частично (0.09).
        # SSE отдаёт байты сразу, соединение живёт.
        "stream": True,
    }
    raw = json.dumps(body, ensure_ascii=False).encode("utf-8")

    before = credits(key)
    print(f"\nбаланс до : {before:.2f} кредита")
    print(f"тело      : {len(raw):,} байт   max_output_tokens={MAX_OUTPUT}   stream=true")
    print(f"URL       : {URL}\n\nотправка…")
    t0 = time.time()
    try:
        req = urllib.request.Request(
            URL, data=raw, method="POST",
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json; charset=utf-8",
                     "Accept": "text/event-stream"})
        with urllib.request.urlopen(req, timeout=1800) as r:
            # читаем SSE до конца
            chunks: list[str] = []
            final: dict = {}
            for raw_line in r:
                line = raw_line.decode("utf-8", "replace").rstrip("\r\n")
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    ev = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                etype = ev.get("type", "")
                if etype == "response.output_text.delta":
                    chunks.append(ev.get("delta", ""))
                elif etype == "response.completed":
                    final = ev.get("response") or {}
                elif etype == "response.incomplete" or etype == "response.failed":
                    final = final or ev
            text = "".join(chunks)
            if not text and final:
                for item in final.get("output", []) or []:
                    for c in item.get("content", []) or []:
                        if c.get("type") in ("output_text", "text"):
                            text += c.get("text", "")
            data = json.dumps(final, ensure_ascii=False).encode("utf-8")
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8','replace')[:1200]}")
        print("Повтор НЕ выполняется: неоднозначный исход.")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"сбой: {exc}")
        print("Повтор НЕ выполняется: неоднозначный исход.")
        return 2

    elapsed = time.time() - t0
    after = credits(key)
    p = json.loads(data) if data else {}
    (out / "GPT-ASTRA-FULL-REVIEW.response.json").write_bytes(data)

    usage = p.get("usage", {}) if p else {}
    print(f"\nответ за {elapsed:.1f} с")
    print(f"status  : {p.get('status')}   model: {p.get('model')}")
    print(f"usage   : in={usage.get('input_tokens')} out={usage.get('output_tokens')} "
          f"total={usage.get('total_tokens')}")
    print(f"credits : в ответе {p.get('credits_consumed')}   баланс {before:.2f} -> {after:.2f} "
          f"(списано {before - after:.4f})")

    if text:
        (out / "GPT-ASTRA-FULL-REVIEW.md").write_text(text, encoding="utf-8")
        print(f"текст   : responses/GPT-ASTRA-FULL-REVIEW.md ({len(text):,} символов)")
    else:
        print("текст не извлечён; ключи: " + ", ".join(p.keys()) if p else "нет ответа")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
