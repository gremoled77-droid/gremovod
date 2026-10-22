# Claude Code — доверенная policy для CI Claude и задач CapCut ( CC-SCOPE-01 )

Статус: **PASS исполнителя в офлайн-harness** (не независимая приёмка; реальный GitHub scope-check ещё не проводился). Модель: Claude Sonnet 5.5.

- Issue: #97. Ветка `build/claude/ci-capcut-scope-20261023`, Draft PR stacked на #87.
- BASE подготовки: #87 `build/claude/ga-03-scope-ext` @ `c40f8bd8633355912cf01b2af36f8b4d66bd4cdc` (сверен с origin, дрейфа нет). Конечная интеграционная база — `mavis/work` (D1), не меняется.

## Что изменено

| Файл | Правка |
|---|---|
| `tools/check_agent_scope.py` | `OWNED["claude"]` + **точный** путь `.github/workflows/studio-offline-ci.yml` (через существующий `path_allowed`, равенство) |
| `tools/minimax_task_scopes.json` | задачи `capcut-02`, `capcut-03`, `capcut-04` |
| `tools/test_agent_scope.py` | 3 новых теста; проверка правдоподобия путей учитывает новую подпапку `docs/capcut-handoff/` (существует верхний каталог `docs`) |

Task-specific списки (эффективный допуск = они + `common_allow: docs/`, который не трогал; `common_deny` выигрывает):

| Задача | allow |
|---|---|
| capcut-02 | `tools/capcut_handoff.py`, `tools/test_capcut_handoff.py`, `docs/capcut-handoff/README.md`, `docs/capcut-handoff/SCOPE-REQUEST.md`, `docs/agent_handoffs/minimax-capcut-02-` |
| capcut-03 | те же два tools-файла, README, `docs/agent_handoffs/minimax-capcut-03-` (покрывает и handoff R2) |
| capcut-04 | `tests/test_capcut_edit_list_integration.py`, README, `docs/agent_handoffs/minimax-capcut-04-`; tools и backend — только чтение |

Не менялись: workflows, AGENTS/CLAUDE, `common_allow`, `common_deny`, ga-01…ga-05, fail-closed `UNKNOWN_TASK_SCOPE`, чтение манифеста из BASE, trusted-копия guard, `CONTROL_FILES`.

## Команды и результаты

```bash
python -B -X utf8 -m unittest tools.test_agent_scope -v   # 40 тестов, OK, exit 0
```

Новые тесты: роль claude может править ровно offline-workflow, а `agent-scope-guard.yml`, `studio-ci-contract.yml`, `other.yml`, `studio-offline-ci.yml.bak`, `.github/CODEOWNERS`, AGENTS.md, canon, frontend остаются запрещены; capcut-02/03/04 пропускают свои пути и закрыты для всего остального (в т. ч. capcut-04 не может править tools; `capcut-05` не объявлен, fail-closed).

## Red/green в изолированном harness (git diff реальных веток, старые vs новые код+манифест)

| PR | Файлов | Старая policy: forbidden | Новая policy: forbidden |
|---|---|---|---|
| #94 (`build/claude/ci-media-verify-20261022`) | 4 | `.github/workflows/studio-offline-ci.yml` | нет |
| #95 (`minimax/capcut-03-manifest-verify`) | 6 | все 6 (tools, README, SCOPE-REQUEST, handoff 02/03) | нет |
| #93 (`minimax/capcut-02-retest`) | 5 | все 5 | нет |

Это не заменяет настоящий GitHub scope-check.

## Что это не меняет (порядок принятия)

- Scope-check берёт guard и манифест из **BASE** открытого PR. Control PR сам по себе доверенную базу #94/#95 не меняет: #94 остаётся красным, пока его BASE (#92) без этой policy.
- Порядок: (1) независимое ревью Codex и решение владельца по этому control PR → (2) попадание в согласованную базу (mavis/work / база #92, #95) → (3) rebase/перебазирование и **повторный scope-check на новом точном HEAD** #94 и #95.
- #95: `skipped` ≠ проверенная область. Его guard/манифест должны прийти из базы, где уже есть capcut-03; до этого scope не проверен.
- Исходные PR не объявлены merge-ready.

## Не проверено

- Реальный GitHub scope-check (CI на этом PR судит BASE #87, где нет новой policy; ожидаемо: этот PR меняет CONTROL_FILES — отчёт `CONTROL_FILE_CHANGE`, вердикт по старой политике).
- Backend/frontend/media-тесты не запускались: продуктовый код не менялся.
- Независимого ревью нет. Merge, платных вызовов, Studio 8000/5173 не было.
