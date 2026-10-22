# Запрос на согласование области задачи MM-CAPCUT-02 (CapCut handoff v1)

**Кто просит:** MiniMax Code, ветка `minimax/capcut-02-retest` (база — HEAD PR #71
`experiment/capcut-handoff-v1`, `8ea6cbb36c41f88b5872d7e861346f7894908454`).

**Что просят:** внести в `tools/minimax_task_scopes.json` задачу `capcut-02`, чтобы scope guard
проверял эту область, и положить в базу PR #90 до его слияния.

## Почему это нужно

`tools/minimax_task_scopes.json` сейчас содержит задачи `ga-01` … `ga-05`. Задачи `capcut-02`
в нём нет, и ни в одной ветке репозитория упоминания `capcut-02` нет:

```
$ git grep -l "capcut-02" $(git branch -r --format='%(refname:short)')
(пусто)
```

Как это выглядит для guard'а:

| Состояние базы PR | Поведение guard'а |
|---|---|
| База без манифеста (сейчас: HEAD PR #71 — манифеста в цепочке нет) | `NO_SCOPE_MANIFEST` → `LEGACY_BRANCH_NOT_ENFORCED`, exit 0. Проверка фактически не выполняется: ветка `minimax/*` не входит в список префиксов, которые guard знает в этой цепочке |
| База с манифестом (после PR #87 или PR #62) | `task_key_for_branch('minimax/capcut-02-retest')` → `capcut-02`; такой задачи в манифесте нет → `UNKNOWN_TASK_SCOPE`, guard работает «fail closed»: весь набор изменённых путей считается неразрешённым, exit 1 |

То есть сейчас CI зелёный, но проверки области фактически нет; после того как манифест попадёт
в базу, тот же PR станет красным — и это правильно, потому что область задачи не была
согласована.

## Что именно нужно добавить

Ровно одна запись в `tasks` манифеста `tools/minimax_task_scopes.json`:

```json
"capcut-02": {
  "summary": "Проверка и укрепление офлайн-экспорта GremoVOD → CapCut: пакет материалов для ручного монтажа.",
  "allow": [
    "tools/capcut_handoff.py",
    "tools/test_capcut_handoff.py",
    "docs/capcut-handoff/"
  ]
}
```

Ключ `capcut-02` соответствует шаблону `task_key_pattern` (`^[a-z]+-[0-9]+$`), префикс ветки
`minimax/` входит в `branch_prefixes`. Проверяемые файлы PR #90:

| Файл | В списке `allow` |
|---|---|
| `tools/capcut_handoff.py` | да |
| `tools/test_capcut_handoff.py` | да |
| `docs/capcut-handoff/README.md` | да (`docs/capcut-handoff/`) |
| `docs/capcut-handoff/SCOPE-REQUEST.md` | да (`docs/capcut-handoff/`) |

Файлы `backend/`, `frontend/` и любые другие в этот PR не попадают.

## Чего этот PR не делает

- `tools/minimax_task_scopes.json` в PR #90 **не** меняется: манифест — control-файл guard'а,
  и ветка задачи не должна расширять собственную область тем же PR. Это ровно то, от чего
  защищает guard («a task branch cannot widen its own scope in the same pull request»).
- `backend/` и `frontend/` не меняются.
- Ветка PR #71 `experiment/capcut-handoff-v1` не меняется.

## Кто и когда должен внести

Согласование области — ревьюируемое изменение, поэтому его должен внести владелец или
Claude Code отдельным PR, который **встаёт в базу раньше** PR #86/PR #90. Практический порядок:

1. PR #87 (`build/claude/ga-03-scope-ext`) — расширение области `ga-03` — уже согласован;
   при его слиянии в базу guard начинает проверять ветки `minimax/*` по манифесту.
2. Отдельным изменением в тот же манифест добавляется запись `capcut-02` (патч выше).
3. После этого PR #90 проходит scope-проверку по записи `capcut-02`, а не вхолостую.

Если владелец решит, что область `capcut-02` не нужна, альтернатива та же: merge PR #90
только после того, как guard перестанет его отклонять, либо после перевода PR #90 в
независимую экспериментальную ветку вне guard'а.
