# Claude Code — обязательный CI для хуков Claude Code ( claude-ci-final-20261022 )

- **Сделано:** интегрированы PR #62 (GA-04: offline CI, контракты CI, scope guard, скан
  секретов) и PR #74 (MM-CLAUDE-01…03: конфигурация Claude Code с тремя PreToolUse-хуками
  и 106 регрессионными тестами) в одну ветку `mavis/ci-final-2026-10-22` от
  `origin/mavis/work`; тесты хуков подключены к обязательному CI отдельным always-on
  job'ом `claude-hooks`, а сам факт наличия этого job'а сделан частью контракта CI
  (`tools/check_ci_contracts.py`), поэтому его удаление ломает проверку контрактов.
- **Файлы:** `.github/workflows/studio-ci-contract.yml` (job `claude-hooks`),
  `tools/check_ci_contracts.py` (`CLAUDE_HOOKS_JOB`, `CLAUDE_HOOKS_TESTS`,
  `check_claude_hooks_job()`), `tools/test_ci_contracts.py` (3 теста),
  `docs/agent_handoffs/claude-ci-final-20261022.md` (этот отчёт). Интегрированное
  содержимое PR: `.github/workflows/*` (4), `tools/*` (8), `.claude/*` (10),
  `tests/test_claude_hooks.py`, `AGENTS.md`, `CLAUDE.md`, `scripts/check_git_files.py`,
  `docs/GIT_WORKFLOW.md`, `docs/agent_handoffs/claude-claude-config-20261022.md`.
- **Следующий шаг:** независимое ревью Codex интеграционного PR #75. Он остаётся
  Draft. После его принятия PR #62 и #74 закрываются как поглощённые — решение
  владельца, здесь не выполняется.
- **Проверки:** локально — `tests.test_claude_hooks` 106 OK; полный набор CI
  (`tools.test_ci_contracts tools.test_no_secrets tools.test_agent_scope
  tools.test_agent_coordination tests.test_claude_hooks`) 191 OK; `tools/check_ci_contracts.py`
  → `CI_CONTRACT: OK`; scope guard → `LEGACY_BRANCH_NOT_ENFORCED`, exit 0; pre-commit →
  `Git file check: OK`. В GitHub Actions — 4 workflow, 9 job, все `success`
  (прогоны 39772893687, 39772893690, 39772893738, 39772893626). Платные API не вызывались.
- **Блокировки для Codex:** нет.

## Что и как слито

| Источник | PR | Коммиты | Merge-коммит |
|---|---|---|---|
| `origin/minimax/ga-04-studio-offline-ci` | #62 | `6898e4e` | `bec9b0a` |
| `origin/mavis/claude-config-optimization-2026-10-22` | #74 | `383d137`, `dd966ed`, `1c3c948` | `076236b` |
| подключение хуков к CI | #75 | `04b7bbf` | — |

Оба слияния — `--no-ff`, конфликтов не возникло. `.gitignore` после слияния сохраняет оба
изменения: bare-правило `tools/` снято (PR #62), `/.claude/` раз-игнорирован с точечными
исключениями `settings.local.json`, `*.local.json`, `worktrees/`, `projects/` (PR #74).

## Почему отдельный job, а не path-фильтрованный workflow

Тесты хуков выполнялись только локально: check'а, который обязан появиться на pull
request, у них не было. Обязательный check за path-фильтром остаётся `skipped`, а
пропущенный required-check — это ложный зелёный свет, а не защита. Поэтому job лежит в
`studio-ci-contract.yml`, у которого path-фильтра нет: check появляется на каждом PR.

Отличие от предложения, переданного Codex в MM-CLAUDE-03 (добавить пути и команду в
`agent-coordination.yml`): команда вынесена в always-on job, а в path-фильтрованном
workflow оставлена как есть. `agent-coordination.yml` и так срабатывает на этом PR — он
трогает `AGENTS.md`, `CLAUDE.md`, `docs/agent_handoffs/**`, `.github/workflows/**` и
`tools/test_ci_contracts.py`.

Контракт теперь проверяет не только наличие job'а, но и что он действительно запускает
`tests.test_claude_hooks`: job, который существует, но ничего не выполняет, — это check,
который никогда не станет красным.

## Red/green

| Шаг | Результат |
|---|---|
| До правки workflow: `python -m unittest tools.test_ci_contracts -v` | 28 тестов → **1 failure**: `missing job 'claude-hooks'` |
| До правки workflow: `python tools/check_ci_contracts.py` | **CI_CONTRACT: FAILED**, exit 1 |
| После правки workflow: `python -m unittest tools.test_ci_contracts -v` | **28 OK**, exit 0 |
| После правки workflow: `python tools/check_ci_contracts.py` | **CI_CONTRACT: OK**, exit 0 |

Негативные тесты на сам валидатор (контракт без job'а; job без запуска тестов) красные до
проверки и зелёные после неё.

## Реальные прогоны GitHub Actions (PR #75)

| Workflow | Job'ы | Итог |
|---|---|---|
| GremoVOD CI contracts (39772893738) | CI contracts and tool tests; **Claude hooks guard tests**; No secrets in this change | success |
| GremoVOD Studio offline CI (39772893687) | Backend unit tests; Backend media and QC tests; Frontend unit tests; Frontend TypeScript and production build | success |
| Agent ownership boundaries (39772893690) | check-agent-scope | success (`SCOPE_BOOTSTRAP` → `LEGACY_BRANCH_NOT_ENFORCED`) |
| Agent handoff and workflow export checks (39772893626) | validate-agent-handoff | success |

Scope guard отработал в bootstrap-режиме: в `origin/mavis/work` ещё нет
`tools/check_agent_scope.py`, поэтому валидатор взял из pull request, а решение остаётся
за ревью владельца. Имя ветки `mavis/ci-final-2026-10-22` не даёт ключ задачи по шаблону
`^[a-z]+-[0-9]+$`, поэтому области task-веток к ней не применяются — ровно как у PR #74,
но check выполняется и зелёный, а не пропущен.

## Непроверенное в этом раунде

- **Живая сессия Claude Code** не запускалась: контракт хуков подтверждён регрессионными
  тестами в реальном CI, интерактивный прогон не повторялся. Опыт раунда 3 (MM-CLAUDE-03)
  в силе: импорт `@AGENTS.md`, ленивая загрузка правил, отказы гардов.
- **Системный `python` без pytest** в этой машине: проверки шли через
  `C:\Users\BLOWKA\Documents\Minimax\.venv-audit\Scripts\python.exe` (pytest 9.1.1,
  pyyaml 6.0.3). В CI используется системный Python 3.13 раннера.
- **`STATUS.md` не менялся** — по конвенции его обновляет назначенный координатор.

## Риски

1. **Порядок слияния.** PR #62 расширяет scope guard на префиксы `minimax/` и `mavis/` и
   запрещает в `common_deny` `AGENTS.md`, `CLAUDE.md`, `AGENT_BUILD_MANUAL.md`. PR #74
   меняет `AGENTS.md` и `CLAUDE.md`. Если интеграционный PR примут раньше PR #62, эти
   изменения окажутся под общим запретом — нужно решение владельца о порядке.
2. **Имя ветки** не соответствует конвенции `build/claude/<этап>-<задача>` из
   `AGENT_BUILD_MANUAL.md` §2: используется `mavis/*`, как у остальных открытых PR.
   Вопрос открыт с прошлого раунда.
3. **Двойной источник правды о путях.** Пути worktree намеренно не зашиты в документацию;
   источник — `git worktree list`.
4. **Требование «обязательный check» — это не «branch protection требует его».** Список
   required-checks — отдельное решение владельца (D7 в GA-04), оно этим PR не меняется:
   добавлен job, который всегда даёт check, но включение его в branch protection не
   выполнено.
