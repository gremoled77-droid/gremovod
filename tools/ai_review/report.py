"""Рендер отчёта по прогону из JSON-контракта `dev-run-summary/1`.

Формат — русский Markdown, как принято в GremoVOD. Важное правило Issue #27:
неизвестное значение пишется как «НЕ УКАЗАНО» / «НЕ ПОДТВЕРЖДЕНО», а не как
нулевое или «успешно». Отчёт — это единственный источник правды для владельца,
GitHub и n8n, поэтому он не приукрашивает.
"""

from __future__ import annotations

from typing import Any

NOT_SPECIFIED = "НЕ УКАЗАНО"
NOT_CONFIRMED = "НЕ ПОДТВЕРЖДЕНО"

_STATUS_LABELS = {
    "PASS": "PASS — замечаний нет",
    "FINDINGS": "FINDINGS — есть замечания",
    "UNCERTAIN": "UNCERTAIN — данных недостаточно",
    "API_ERROR": "API_ERROR — ошибка провайдера",
    "QUOTA_EXHAUSTED": "QUOTA_EXHAUSTED — квота M Plan исчерпана",
    "STALE_REVIEW": "STALE_REVIEW — ревью устарело (SHA разошлись)",
    "NOT_RUN": "NOT_RUN — ревью не выполнялось",
}

_TESTS_LABELS = {
    "PASS": "PASS",
    "FAIL": "FAIL",
    "NOT_RUN": "NOT_RUN (не запускались)",
    "UNKNOWN": "UNKNOWN (нет данных)",
}

_SEVERITY_LABELS = {"P1": "P1 — критично", "P2": "P2 — существенно", "P3": "P3 — мелочь"}


def _text(value: Any, fallback: str = NOT_SPECIFIED) -> str:
    if value is None:
        return fallback
    if isinstance(value, str) and not value.strip():
        return fallback
    return str(value)


def _lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def render_report(summary: dict[str, Any]) -> str:
    """Собрать Markdown-отчёт по summary."""
    out: list[str] = []

    out.append(f"# Отчёт прогона: {_text(summary.get('task_id'))}")
    out.append("")
    out.append(f"**Режим:** `{_text(summary.get('mode'))}` · **Провайдер:** `{_text(summary.get('provider'))}`")
    out.append(f"**Модель ревьюера:** {_text(summary.get('reviewer_model'))}")
    out.append("")

    out.append("## 1. Задача")
    out.append("")
    out.append(_text(summary.get("scope")))
    out.append("")

    out.append("## 2. Что менялось")
    out.append("")
    changes = _lines(summary.get("code_changes"))
    if changes:
        out.extend(f"- {item}" for item in changes)
    else:
        out.append("- (список файлов не передан)")
    out.append("")
    out.append(f"- Ветка: `{_text(summary.get('branch'))}`")
    out.append(f"- base_sha: `{_text(summary.get('base_sha'))}`")
    out.append(f"- head_sha: `{_text(summary.get('head_sha'))}`")
    out.append(f"- diff_sha256: `{_text(summary.get('diff_sha256'))}`")
    out.append("")

    out.append("## 3. Тесты")
    out.append("")
    status = _text(summary.get("tests_status"), "UNKNOWN")
    out.append(f"**Итог:** {_TESTS_LABELS.get(status, status)}")
    out.append("")

    out.append("## 4. Результат ревью")
    out.append("")
    review_status = _text(summary.get("review_status"))
    out.append(f"**Итог:** {_STATUS_LABELS.get(review_status, review_status)}")
    out.append("")
    blocked = summary.get("blocked_reason")
    if blocked:
        out.append(f"**Причина остановки:** {_text(blocked)}")
        out.append("")

    findings = summary.get("findings") or []
    if findings:
        out.append("### Замечания")
        out.append("")
        for index, finding in enumerate(findings, start=1):
            if not isinstance(finding, dict):
                continue
            severity = _text(finding.get("severity"))
            out.append(
                f"#### {index}. [{_SEVERITY_LABELS.get(severity, severity)}] "
                f"{_text(finding.get('file'))}"
            )
            if finding.get("line") is not None:
                out.append(f"- Строка: {finding.get('line')}")
            out.append(f"- Доказательство: {_text(finding.get('evidence'))}")
            out.append(f"- Воспроизведение: {_text(finding.get('reproduction'))}")
            out.append(f"- Исправление: {_text(finding.get('fix'))}")
            out.append("")
    else:
        out.append("Замечаний нет.")
        out.append("")

    out.append("## 5. Квота и расход")
    out.append("")
    quota = summary.get("quota")
    if isinstance(quota, dict):
        out.append(f"- Источник проверки: `{_text(quota.get('source'))}`")
        out.append(f"- Остаток 5-часового окна: {_text(quota.get('window_5h_remaining'), NOT_CONFIRMED)}")
        out.append(f"- Остаток недельного окна: {_text(quota.get('weekly_remaining'), NOT_CONFIRMED)}")
        out.append(f"- Проверено в: {_text(quota.get('checked_at'))}")
    else:
        out.append(f"- Остаток квоты M Plan: {NOT_CONFIRMED}")
    out.append("")

    cost = summary.get("actual_cost")
    if isinstance(cost, dict):
        out.append(
            f"- Фактический расход: {cost.get('amount')} {cost.get('currency')} "
            f"(источник: {_text(cost.get('source'))})"
        )
    else:
        out.append(f"- Фактический расход: {NOT_CONFIRMED}")
    usage = summary.get("provider_usage")
    if isinstance(usage, dict):
        out.append(
            f"- Токены: prompt={usage.get('prompt_tokens')}, "
            f"completion={usage.get('completion_tokens')}, total={usage.get('total_tokens')}"
        )
    else:
        out.append(f"- Токены провайдера: {NOT_CONFIRMED}")
    out.append("")

    out.append("## 6. Ссылки")
    out.append("")
    for label, key in (
        ("GitHub Issue", "pr_url"),
        ("GitHub Actions run", "actions_run_url"),
        ("n8n execution", "n8n_execution_url"),
    ):
        value = summary.get(key)
        out.append(f"- {label}: {_text(value)}")
    out.append("")

    out.append("## 7. Решение владельца")
    out.append("")
    out.append(f"**{_text(summary.get('owner_decision'), 'PENDING')}**")
    out.append("")

    out.append("---")
    out.append("")
    out.append(
        "Отчёт описывает состояние прогона кода. Изменение кода в репозитории "
        "**не означает**, что рабочий процесс n8n обновлён: обновление n8n — отдельная задача."
    )
    out.append("")

    return "\n".join(out)


def render_short_summary(summary: dict[str, Any], limit: int = 5) -> str:
    """Короткая сводка для комментария в GitHub Draft PR / job summary."""
    findings = summary.get("findings") or []
    lines = [
        f"**Режим:** `{_text(summary.get('mode'))}` · **Провайдер:** `{_text(summary.get('provider'))}`",
        f"**Тесты:** {_TESTS_LABELS.get(_text(summary.get('tests_status')), _text(summary.get('tests_status')))}",
        f"**Ревью:** {_STATUS_LABELS.get(_text(summary.get('review_status')), _text(summary.get('review_status')))}",
        f"**Задача:** {_text(summary.get('task_id'))}",
    ]
    if findings:
        lines.append("")
        lines.append("| Severity | Файл | Доказательство |")
        lines.append("| --- | --- | --- |")
        for finding in findings[:limit]:
            if not isinstance(finding, dict):
                continue
            severity = _text(finding.get("severity"))
            evidence = _text(finding.get("evidence")).replace("|", "\\|")
            lines.append(f"| {severity} | {_text(finding.get('file'))} | {evidence[:160]} |")
        if len(findings) > limit:
            lines.append(f"| … | … | ещё {len(findings) - limit} замечаний |")
    blocked = summary.get("blocked_reason")
    if blocked:
        lines.append("")
        lines.append(f"**Причина остановки:** {_text(blocked)}")
    return "\n".join(lines)
