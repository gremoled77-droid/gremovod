"""Сборка импортируемого n8n JSON из SDK-исходника.

Нужен, чтобы файл `workflows/WF_07_MiniMax_Reviewer_MOCK.json` в репозитории
и workflow в n8n Cloud были одним и тем же объектом, а не двумя руками
написанными копиями.

Запуск:  python -X utf8 scripts/export_n8n_workflow.py
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "workflows" / "WF_07_MiniMax_Reviewer_MOCK.ts"
TARGET = ROOT / "workflows" / "WF_07_MiniMax_Reviewer_MOCK.json"

WORKFLOW_NAME = "GremoVOD Dev Observability — MOCK (MiniMax Reviewer)"
WORKFLOW_ID = "wf07-minimax-reviewer-mock"

MINIMAX_URL = "https://api.minimax.io/v1/chat/completions"
ARGON_URL = "https://api.kie.ai/gemini-4-argon-openai/v1/chat/completions"

#: Узлы HTTP собираются вручную: их параметры выражениями не читаются из SDK-исходника
#: автоматически, и их мало.
HTTP_NODES = {
    "07 HTTP запрос провайдеру": {
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.3,
        "disabled": True,
        "notes": (
            "ВЫКЛЮЧЕН по умолчанию. Перед включением: назначить credential Header Auth "
            "(Authorization: Bearer <MiniMax Subscription Key>), проверить остаток квоты M Plan "
            "и получить согласие владельца."
        ),
        "parameters": {
            "method": "POST",
            "url": "={{ $json.request_url }}",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ $json.request_body }}",
            "options": {"timeout": 90000},
        },
    },
    "11 GitHub Draft PR summary": {
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.3,
        "disabled": True,
        "notes": (
            "ВЫКЛЮЧЕН по умолчанию. Перед включением: назначить credential GitHub "
            "(комментарий в Draft PR, read-only по правам токена)."
        ),
        "parameters": {
            "method": "POST",
            "url": (
                "=https://api.github.com/repos/{{ $json.repo_owner }}/{{ $json.repo_name }}"
                "/pulls/{{ $json.pr_number }}/comments"
            ),
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ { body: $json.report_md } }}",
            "options": {"timeout": 30000},
        },
    },
}

STICKY = {
    "name": "Sticky Note MOCK-режим",
    "type": "n8n-nodes-base.stickyNote",
    "typeVersion": 1,
    "position": [1744, 208],
    "parameters": {
        "content": (
            "## MOCK-режим (этап P1, Issue #27)\n\n"
            "Живые узлы 07 и 11 выключены и не имеют credential.\n\n"
            "Узел 04 закрывает доступ после 2026-10-25 00:00 (+03:00) и при неподтверждённой "
            "квоте M Plan.\n\n"
            "Смена MiniMax на Argon не меняет архитектуру: меняется только provider на входе "
            "узла 01.\n\n"
            "В MOCK узел 07 обходится, сеть не затрагивается, request_url пуст."
        ),
        "color": 4,
        "width": 1040,
        "height": 224,
    },
}

#: Константы SDK-исходника: TypeScript подставляет их в шаблонные строки `jsCode`,
#: а в готовом workflow это должны быть уже готовые значения.
SDK_CONSTANTS = {
    "CONTRACT_VERSION": "dev-run-summary/1",
    "EXPIRES_AT": "2026-10-25T00:00:00+03:00",
    "MINIMAX_URL": MINIMAX_URL,
    "ARGON_URL": ARGON_URL,
}


def resolve_constants(text: str) -> str:
    """Подставить значения констант SDK вида ${NAME}."""
    for name, value in SDK_CONSTANTS.items():
        text = text.replace("${" + name + "}", value)
    return text


def unescape_template(text: str) -> str:
    """Развернуть escape-последовательности шаблонной строки TypeScript."""
    out: list[str] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            nxt = text[index + 1]
            mapping = {"\\": "\\", "n": "\n", "t": "\t", "`": "`", "$": "$"}
            if nxt in mapping:
                out.append(mapping[nxt])
                index += 2
                continue
        out.append(char)
        index += 1
    return "".join(out)


def parse_source(source: str) -> list[dict]:
    """Вытащить узлы из SDK-исходника.

    Разбивать исходник по `const` нельзя: внутри `jsCode` есть собственные `const`.
    Поэтому узлы ищутся по имени (`name: '...'` — такой строки в коде узлов нет),
    а тело `jsCode` берётся из сегмента до следующего имени.
    """
    markers = [(m.group(1), m.end()) for m in re.finditer(r"name:\s*'([^']+)'", source)]
    nodes: list[dict] = []

    for index, (name, start) in enumerate(markers):
        end = markers[index + 1][1] if index + 1 < len(markers) else len(source)
        segment = source[start:end]
        position_match = re.search(r"position:\s*\[(-?\d+),\s*(-?\d+)\]", segment)
        if not position_match:
            continue
        position = [int(position_match.group(1)), int(position_match.group(2))]

        if name in HTTP_NODES:
            spec = HTTP_NODES[name]
            nodes.append(
                {
                    "parameters": spec["parameters"],
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "type": spec["type"],
                    "typeVersion": spec["typeVersion"],
                    "position": position,
                    "disabled": spec["disabled"],
                    "notes": spec["notes"],
                }
            )
            continue

        code_match = re.search(r"jsCode:\s*`(.*?)`,", segment, re.DOTALL)
        if code_match:
            js_code = resolve_constants(unescape_template(code_match.group(1)))
            nodes.append(
                {
                    "parameters": {
                        "mode": "runOnceForAllItems",
                        "jsCode": js_code,
                    },
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "type": "n8n-nodes-base.code",
                    "typeVersion": 2,
                    "position": position,
                }
            )
            continue

        nodes.append(
            {
                "parameters": {},
                "id": str(uuid.uuid4()),
                "name": name,
                "type": "n8n-nodes-base.manualTrigger",
                "typeVersion": 1,
                "position": position,
            }
        )
    return nodes


def build_connections(nodes: list[dict]) -> dict:
    """Линейная цепочка узлов в порядке объявления."""
    connections: dict[str, dict] = {}
    for index, node in enumerate(nodes):
        if index + 1 < len(nodes):
            connections[node["name"]] = {
                "main": [[{"node": nodes[index + 1]["name"], "type": "main", "index": 0}]]
            }
        else:
            connections[node["name"]] = {"main": [[]]}
    return connections


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    nodes = parse_source(source)

    sticky = dict(STICKY)
    sticky["id"] = str(uuid.uuid4())

    workflow = {
        "name": WORKFLOW_NAME,
        "nodes": nodes + [sticky],
        "connections": build_connections(nodes),
        "settings": {"executionOrder": "v1"},
        "pinData": {},
        "active": False,
        "id": WORKFLOW_ID,
        "meta": {"instanceId": "gremovod-local-export"},
        "tags": [],
    }

    TARGET.write_text(
        json.dumps(workflow, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    code_nodes = [n for n in workflow["nodes"] if n["type"] == "n8n-nodes-base.code"]
    print(f"written: {TARGET.relative_to(ROOT)}")
    print(f"nodes: {len(workflow['nodes'])} (code: {len(code_nodes)}, sticky: 1)")
    print(f"active: {workflow['active']}")
    for node in workflow["nodes"]:
        if node.get("disabled"):
            print(f"disabled: {node['name']}")
    for node in code_nodes:
        if not node["parameters"]["jsCode"].strip():
            print(f"ERROR: empty jsCode in {node['name']}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
