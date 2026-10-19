"""Проверка соответствия импортируемого JSON тому, что реально создано в n8n.

Эталон — содержимое workflow `GremoVOD Dev Observability — MOCK (MiniMax Reviewer)`,
созданного через n8n SDK (13 узлов, узлы 07 и 11 выключены, 0 credential).

Запуск:  python -X utf8 scripts/verify_n8n_workflow_export.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "workflows" / "WF_07_MiniMax_Reviewer_MOCK.json"

EXPECTED_NODES = [
    "00 Ручной запуск MOCK",
    "01 Нормализация входа",
    "02 Дедупликация run_id",
    "03 Локальные бесплатные проверки",
    "04 Квота M Plan и отсечка",
    "05 Сборка материала ревью",
    "06 Выбор ревьюера",
    "07 HTTP запрос провайдеру",
    "08 Валидация ответа",
    "09 Сборка summary",
    "10 Отчёт в n8n",
    "11 GitHub Draft PR summary",
]

#: Маркеры, которые обязаны присутствовать в jsCode конкретного узла.
EXPECTED_MARKERS = {
    "01 Нормализация входа": [
        "throw new Error('BLOCKED: отсутствуют поля контракта: '",
        "consent: payload.consent === true,",
    ],
    "03 Локальные бесплатные проверки": [
        "SECRET.test(run.diff || '')",
        "DIFF_TOO_LARGE",
        "BASE_SHA_EQUALS_HEAD_SHA",
    ],
    "04 Квота M Plan и отсечка": [
        "new Date('2026-10-25T00:00:00+03:00')",
        "QUOTA_UNKNOWN",
        "CONSENT_REQUIRED",
        "SUBSCRIPTION_EXPIRED",
    ],
    "05 Сборка материала ревью": ["const messages = ["],
    "06 Выбор ревьюера": [
        "https://api.minimax.io/v1/chat/completions",
        "https://api.kie.ai/gemini-4-argon-openai/v1/chat/completions",
        "model: 'MiniMax-M3.1-Flash'",
        "thinking: { type: 'adaptive' }",
        "reasoning_effort: 'low'",
    ],
    "08 Валидация ответа": [
        "PROVIDER_RESPONSE_NOT_STRICT_JSON",
        "$('06 Выбор ревьюера').first().json",
        "STALE_REVIEW",
    ],
    "09 Сборка summary": [
        "schema_version: 'dev-run-summary/1'",
        "owner_decision: 'PENDING'",
        "provider_usage: run.mode === 'LIVE'",
    ],
    "10 Отчёт в n8n": [
        "$('09 Сборка summary').first().json",
        "report_md",
    ],
}

#: Регулярные выражения и переводы строк должны остаться экранированными как в n8n.
EXPECTED_LITERALS = {
    "03 Локальные бесплатные проверки": [r"\b(?:ghp_|github_pat_|sk-)[A-Za-z0-9_\-]{12,}"],
    "06 Выбор ревьюера": [r"/shell\s*=\s*True/", r"/except\s*:\s*(pass|\.\.\.)/"],
    "10 Отчёт в n8n": [r".replace(/\|/g, '\\|')", r".join('\n')"],
}


def main() -> int:
    workflow = json.loads(TARGET.read_text(encoding="utf-8"))
    problems: list[str] = []

    nodes = workflow.get("nodes") or []
    names = [n["name"] for n in nodes]
    for expected in EXPECTED_NODES:
        if expected not in names:
            problems.append(f"missing node: {expected}")

    code = {n["name"]: n.get("parameters", {}).get("jsCode", "") for n in nodes}
    for node, markers in EXPECTED_MARKERS.items():
        body = code.get(node, "")
        if not body:
            problems.append(f"no jsCode: {node}")
            continue
        for marker in markers:
            if marker not in body:
                problems.append(f"missing marker in {node}: {marker}")

    for node, literals in EXPECTED_LITERALS.items():
        body = code.get(node, "")
        for literal in literals:
            if literal not in body:
                problems.append(f"broken literal in {node}: {literal}")

    for node in nodes:
        if node.get("type") == "n8n-nodes-base.httpRequest":
            if not node.get("disabled"):
                problems.append(f"HTTP node must stay disabled: {node['name']}")
            if node.get("credentials"):
                problems.append(f"HTTP node must have no credentials: {node['name']}")

    if workflow.get("active"):
        problems.append("workflow must be inactive in the export")

    chain_nodes = [n for n in nodes if n["name"] != "Sticky Note MOCK-режим"]
    for index, node in enumerate(chain_nodes):
        connection = (workflow.get("connections") or {}).get(node["name"])
        if connection is None:
            problems.append(f"no connection entry: {node['name']}")
            continue
        targets = connection.get("main", [[]])[0]
        if not targets and index != len(chain_nodes) - 1:
            problems.append(f"dangling connection: {node['name']}")
        if targets and index == len(chain_nodes) - 1:
            problems.append(f"terminal node must not have a target: {node['name']}")

    leaked = re.findall(r"\$\{[A-Z_]+\}", json.dumps(workflow, ensure_ascii=False))
    if leaked:
        problems.append(f"unresolved SDK constants: {sorted(set(leaked))}")

    if problems:
        print(f"[FAIL] {len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("[OK] export matches the n8n workflow structure")
    print(f"  nodes: {len(nodes)} ({len(EXPECTED_NODES)} + sticky)")
    print("  live HTTP nodes: 07, 11 — disabled, no credentials")
    print("  workflow inactive, no unresolved constants, connections complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
