# Handoff для Codex — этап P1 (MiniMax-ревьюер), 19.10.2026

Источник: Issue [#27](https://github.com/gremoled77-droid/gremovod/issues/27)
(временное расширение от 19.10.2026), Issue [#28](https://github.com/gremoled77-droid/gremovod/issues/28).

Ветка: `experiment/minimax-observability-20261020` (база — `origin/main`).
Ветка не запушена. Draft PR не открыт.

## Что сделано

- Единый контракт `dev-run-summary/1` и один интерфейс `Reviewer` для `mock` / `minimax` / `argon`.
- Адаптер MiniMax-M3.1-Flash через официальный OpenAI-совместимый API
  (`POST https://api.minimax.io/v1/chat/completions`), с `thinking: adaptive`,
  `reasoning_effort: low`, без автоповторов.
- Охранник квоты M Plan: остаток проверяется **до** запроса, не подтверждён → стоп;
  окно M Plan закрывается 2026-10-25 00:00 (+03:00).
- 83 офлайн-теста, ноль сетевых вызовов.
- n8n-черновик `GremoVOD Dev Observability — MOCK (MiniMax Reviewer)`,
  13 узлов, не активен, без credential: <https://gremovod.app.n8n.cloud/workflow/XInjy5I69fd11iLv>
- CI `minimax-review-summary.yml`: только ручной запуск и push в свою ветку, только MOCK.

## Что НЕ сделано (и почему)

- **Живого запроса к MiniMax не было.** Требуется согласие владельца, `MINIMAX_SUBSCRIPTION_KEY`
  и подтверждённый остаток квоты.
- **Ветка не запушена, Draft PR не открыт** — это действие владельца.
- **n8n-черновик не опубликован**, узлы 07 и 11 выключены и без credential.
- **Существующие n8n-воркфлоу не тронуты**, `main` не тронут.

## Что сделать дальше

1. Проверить офлайн-набор на своей машине:

   ```powershell
   python -X utf8 -m unittest discover -s tests -p "test_review_*.py" -v
   ```

2. Прогнать MOCK-ревью ветки и приложить отчёт:

   ```powershell
   python -X utf8 -m tools.ai_review.cli review --repo . --base origin/main --head HEAD `
     --scope "..." --provider mock --mode MOCK --tests-status PASS --out-dir artifacts/ai-review
   ```

3. Запушить ветку и открыть **Draft** PR с отчётом MOCK в описании.
   Draft обязателен: этап экспериментальный, решение владельца ещё не принято.

4. Дальше — по отдельному согласию владельца: ключ, проверка остатка (`cli quota`),
   первый живой запрос (одна штука), затем — включение узлов 07/11 в n8n.

## Важное для любого, кто продолжит

- Единственное место, где живёт «MiniMax или Argon» — узел 06 n8n и `adapters/` в Python.
  Не дублируйте логику провайдера ещё где-нибудь.
- Локальные охранники (лимиты диффа, поиск секретов, `allowed_paths`) — общие
  для MiniMax и Argon, менять их в двух местах нельзя.
- `tools/` в `.gitignore` — новые файлы там добавляются через `git add -f`
  (так же сделан PR #22).
- Не изменять `main`, не активировать workflow, не публиковать n8n-воркфлоу без решения владельца.

Документы: `docs/experiments/MINIMAX_N8N_OBSERVABILITY_RU.md`,
`docs/experiments/MINIMAX_REVIEWER_ADAPTER_RU.md`.
