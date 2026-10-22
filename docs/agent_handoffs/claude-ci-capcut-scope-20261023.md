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

## Статусы проверок (AGENTS.md, «Критерии качества», п. 6)

| Проверка | Статус |
|---|---|
| `unittest tools.test_agent_scope` (40 тестов), локально | PASS |
| red/green harness: #94 (1), #95 (6), #93 (5) файлов, старая → новая policy | PASS (FAIL → PASS по политике; не GitHub-проверка) |
| GitHub checks на #98: contracts, hooks, secrets, `check-agent-scope`, handoff | PASS |
| `check-agent-scope` на #94 с новой policy | NOT_RUN: его BASE (#92) без policy, нужен порядок принятия |
| `check-agent-scope` на #95 | NOT_RUN: до включения capcut-02/03/04 в доверенный манифест он `skipped`, а не проверен |
| Backend / frontend / media-тесты | NOT_RUN: продуктовый код не менялся |
| Независимое ревью Codex, решение владельца | NOT_RUN |

## Сверка с AGENTS.md и docs/HANDOFF_CLAUDE_CODE.md

Прочитаны после выполнения (AGENTS.md целиком; HANDOFF — по теме scope/workflow/CapCut, как велит AGENTS.md: файл исторический).

- Сходится: `canon/**`, `skills/`, `AGENTS.md`, `CLAUDE.md` остаются в `common_deny` и всегда побеждают; решение D1 (`mavis/work` — конечная база) не заменено, #87 только база подготовки; `mavis/work`/`main` не трогались; `git add` по точным путям; CapCut как монтаж и приёмка вне студии (D4, решение владельца) согласуется с задачами capcut-02/03/04; новых слоёв оркестрации нет.
- В HANDOFF_CLAUDE_CODE.md о scope guard, ролях OWNED и `.github/workflows` ничего нет: сверять не с чем, противоречий нет.
- Расхождение процесса (исправлено этим коммитом): первая версия handoff не использовала словарь статусов PASS/FAIL/BLOCKED/NOT_RUN и не содержала вопросов ревьюеру. Добавлено выше и ниже.
- Сознательное отступление: AGENTS.md п. 1 («перед задачей `git merge origin/mavis/work`») не выполнялся — Issue #97 требует ветку от #87 `c40f8bd` без merge в неё.

## Вопросы ревьюеру (Codex)

1. Допустимо ли закреплять в `OWNED["claude"]` точное имя `studio-offline-ci.yml`, или нужен отдельный механизм для control-файлов роли?
2. `capcut-03` и `capcut-04` делят README и не пересекаются по tools — достаточно ли этого, или `capcut-04` должен лишиться README?
3. Верно ли описан порядок принятия (control → согласованная база → повторный scope-check #94/#95)?

## Не проверено

- Реальный GitHub scope-check (CI на этом PR судит BASE #87, где нет новой policy; ожидаемо: этот PR меняет CONTROL_FILES — отчёт `CONTROL_FILE_CHANGE`, вердикт по старой политике).
- Backend/frontend/media-тесты не запускались: продуктовый код не менялся.
- Независимого ревью нет. Merge, платных вызовов, Studio 8000/5173 не было.
