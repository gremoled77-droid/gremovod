"""Inventory of outbound PAID call sites in the Studio backend.

The GPT-6 Astra review (P0 finding 1) asks for one thing about the money
boundary: every outgoing PAID call must pass the P0 gate, not only the
image/video ones. This script does not decide anything - it produces the
evidence the decision needs: every place in backend/ that can reach a paid
provider, the function it lives in, and whether that function mentions the P0
gate at all.

Read-only: it imports nothing from the Studio and calls nothing.
Usage:  python scripts/p0_paid_dispatch_audit.py [--markdown]
"""
from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"

# Hosts that cost money. A call to any of them is a paid call.
PAID_HOSTS = (
    "api.piapi.ai",
    "piapi.ai",
    "api.kie.ai",
    "api.openai.com",
    "api.anthropic.com",
    "api.minimax.io",
    "api.minimaxi.com",
)

# Names of the helper functions that actually put money on the wire.
SUBMIT_HINTS = (
    "create_task",
    "submit",
    "generate",
    "dispatch",
    "start_generation",
    "text2video",
    "text2image",
    "image2video",
)

GATE_MARKERS = ("p0_control", "p0_authz", "authorize", "spend_ledger")


def paid_calls(path: Path):
    """Yield (lineno, function, snippet) for lines that can reach a paid host."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for number, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        host = any(host in low for host in PAID_HOSTS)
        post = ".post(" in line or ".post (" in line
        submit = any(hint in low for hint in SUBMIT_HINTS) and (
            "(" in line and "=" not in line.split("(")[0].strip()[-1:][:1] or "(" in line)
        if not (host or post or submit):
            continue
        if re.search(r"@app\.(post|get)|@router\.(post|get)", line):
            continue  # a route declaration is not an outgoing call
        if re.search(r"^\s*#", line):
            continue  # a comment is not a call either
        if host and not post and not submit and "http" in low and "=" in line:
            continue  # a constant with a docs URL
        yield number, line.strip()


def enclosing_functions(path: Path):
    """Map line number -> enclosing function name for a module."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return {}
    found = {}

    def walk(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}{child.name}"
                for line in range(child.lineno, (child.end_lineno or child.lineno) + 1):
                    found[line] = name
                walk(child, name + ".")
            else:
                walk(child, prefix)

    walk(tree)
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--out", help="write the report to this file (UTF-8)")
    args = parser.parse_args()

    rows = []
    for path in sorted(BACKEND.glob("*.py")):
        if path.name.startswith("test_"):
            continue
        funcs = enclosing_functions(path)
        for number, snippet in paid_calls(path):
            func = funcs.get(number, "<module level>")
            gated = any(marker in func for marker in GATE_MARKERS)
            rows.append((path.name, number, func, gated, snippet[:110]))

    if args.markdown:
        lines = []
        lines.append("# Инвентарь исходящих платных вызовов (backend/)")
        lines.append("")
        lines.append("Сгенерировано `scripts/p0_paid_dispatch_audit.py`. Только чтение, "
                     "ничего не вызывается.")
        lines.append("")
        lines.append("| Файл:строка | Функция | За P0-шлюзом | Строки |")
        lines.append("|---|---|---|---|")
        for name, number, func, gated, snippet in rows:
            mark = "да" if gated else "**нет**"
            lines.append(f"| `{name}:{number}` | `{func}` | {mark} | {snippet} |")
        lines.append("")
        lines.append(f"Всего мест: {len(rows)}; за шлюзом: "
                     f"{sum(1 for r in rows if r[3])}; вне шлюза: "
                     f"{sum(1 for r in rows if not r[3])}.")
        report = "\n".join(lines) + "\n"
    else:
        out = []
        for name, number, func, gated, snippet in rows:
            mark = "GATED" if gated else "BYPASS"
            out.append(f"{mark:7} {name}:{number}  {func}  |  {snippet}")
        out.append("")
        out.append(f"total={len(rows)} gated={sum(1 for r in rows if r[3])} "
                   f"bypass={sum(1 for r in rows if not r[3])}")
        report = "\n".join(out) + "\n"

    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"written: {args.out}")
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
