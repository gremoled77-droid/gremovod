# Claude Code — компактная конфигурация агента ( claude-config-20261022 )

- **Сделано:** `CLAUDE.md` сокращён до компактной точки входа с импортом `@AGENTS.md`;
  тематические правила вынесены в `.claude/rules/` (5 файлов, 3 из них с `paths` —
  грузятся лениво); повторяемые процедуры вынесены в `.claude/skills/` (3 скилла);
  спроектированы и протестированы три хука `PreToolUse` (Git, секреты и данные,
  платные вызовы); исправлены устаревшие пути, ветки и команды в `AGENTS.md` и
  `docs/GIT_WORKFLOW.md`; pre-commit-хуку возвращена работоспособность
  (`git config core.hooksPath .githooks`).
- **Файлы:** `CLAUDE.md`, `AGENTS.md`, `docs/GIT_WORKFLOW.md`, `.gitignore`,
  `scripts/check_git_files.py`, `.claude/settings.json`, `.claude/hooks/guard_git.py`,
  `.claude/hooks/guard_files.py`, `.claude/hooks/guard_paid.py`, `.claude/rules/*` (5),
  `.claude/skills/*` (3), `tests/test_claude_hooks.py`.
- **Следующий шаг:** Codex — архитектурное ревью PR и решение по трём пунктам из
  раздела «Требует решения» ниже. До решения `AGENTS.md`, `CLAUDE.md` и `.claude/**`
  не объявлены ни в одной роли `tools/minimax_task_scopes.json` (PR #62) — нужно
  расширить матрицу зон.

## Что изменилось и почему

### Обязательный контекст сессии

До правки каждый агент обязан был прочитать `CLAUDE.md` (15 КБ), `AGENTS.md` (6.5 КБ),
`AGENT_BUILD_MANUAL.md` (11 КБ) и `docs/HANDOFF_CLAUDE_CODE.md` (53 КБ) — это ~85 КБ
на старте, из них большая часть — исторические отчёты, а не контракт.

После правки:

| Файл | Когда грузится | Что внутри |
|---|---|---|
| `AGENTS.md` | каждый раз | общий контракт с Codex: роли, безопасность, деньги, Git, провайдеры |
| `CLAUDE.md` | каждый раз | только Claude-специфика: конфигурация, запуск, команды проверок, указатели |
| `.claude/rules/*.md` | по `paths` | правила по зонам кода (backend, frontend, scripts/tools) и два общих (guards, knowledge-map) |
| `.claude/skills/*/SKILL.md` | по запросу | три повторяемые процедуры |

В `CLAUDE.md` осталось 60 строк вместо 80, но вес снизился с 15 КБ до 4 КБ, а
`docs/HANDOFF_CLAUDE_CODE.md` перестал быть обязательным к полному прочтению.
Фактическая экономия зависит от того, какие зоны задачи открывает сессия: правила с
`paths` не попадают в контекст, пока не открыт соответствующий файл.

### Три хука

| Хук | Событие | Отклоняет |
|---|---|---|
| `guard_git.py` | PreToolUse Bash/PowerShell | push/merge/rebase/checkout в `main`, `master`, `mavis/work`; `push --force`; `git clean -f`; удаление чужой ветки или worktree |
| `guard_files.py` | PreToolUse Write/Edit/MultiEdit | запись в `*_API_KEY.txt`, `.env*`, SQLite, `backend/media/`, `backend/library/`, `backend/character_library/`, `runtime/`, `projects/`, `.claude/settings.local.json` |
| `guard_paid.py` | PreToolUse Bash/PowerShell | `scripts/live_piapi_test.py` (кроме `--dry-run`), `scripts/watch_hunyuan_test.py`, прямые обращения к платным хостам, флаги `--paid`/`--spend` |

Правила запрещённых путей и список платных хостов **не продублированы**: хуки
используют `scripts/check_git_files.py` и `scripts/p0_paid_dispatch_audit.py`, то есть
те же источники, что и pre-commit и CI-сканер секретов.

Слои защиты не дублируют друг друга: хук ловит действие в момент его выполнения,
pre-commit — путь в staged-изменениях, CI — в diff.

## Требует решения Codex

1. **Зоны файлов.** В `tools/minimax_task_scopes.json` (PR #62) в `common_deny`
   перечислены `AGENTS.md`, `CLAUDE.md`, `AGENT_BUILD_MANUAL.md`. Ни одна роль не
   владеет `.claude/**`. Этот PR правит `AGENTS.md` и `CLAUDE.md` и добавляет
   `.claude/**`, поэтому матрица зон требует расширения, иначе следующий task-ветка
   с такой же правкой упадёт на scope guard.
2. **Имя ветки.** Конвенция `AGENT_BUILD_MANUAL.md` §2 предписывает Claude Code
   `build/claude/<этап>-<задача>`, но актуальная интеграционная ветка и все открытые
   PR сейчас живут в семействе `mavis/*` и `minimax/*`. Ветка этого PR —
   `mavis/claude-config-optimization-2026-10-22`; префикс `mavis/` не совпадает с
   шаблоном ключа задачи `^[a-z]+-[0-9]+$`, поэтому scope guard для этой ветки не
   срабатывает. Требуется решение: переименовать под `build/claude/` или дополнить
   список префиксов.
3. **Тесты хуков в CI.** `tests/test_claude_hooks.py` запускается локально
   (`python -m unittest tests.test_claude_hooks`), но в CI не попадает: файлы
   `.github/workflows/*` сейчас меняются в PR #62, и трогать их из этой ветки —
   конфликт. Одиннадцать строк в `agent-coordination.yml` (путь + имя модуля в
   `python -m unittest`) закрывают вопрос.

## Запуск официального Claude Code

Рабочий каталог — worktree агента, не корень репозитория:

```powershell
cd C:\Users\BLOWKA\Documents\Minimax\_wt\gremovod-claude-config
claude
```

Проверка, что конфигурация подхватилась (в интерактивной сессии):

```
/context          # список загруженных memory files: CLAUDE.md, AGENTS.md, .claude/rules/*
/doctor prompt-audit
```

`/context` показывает `CLAUDE.md` и `AGENTS.md`; правила с `paths` появляются в
списке, когда открыт подходящий файл. Проверить загрузку правил без интерактива:

```powershell
claude -p "Назови файлы правил, которые загружены в твой контекст, и их полные пути" --debug
```

Хуки проверяются той же командой: попросить Claude выполнить `git push origin main` —
команда должна быть отклонена с объяснением.

Ветка `mavis/claude-config-optimization-2026-10-22` не защищена scope guard'ом CI
(см. «Требует решения Codex», п. 2), поэтому включать хуки в рабочую конфигурацию
следует только после ревью.

## Запуск отдельного MiniMax

Два разных варианта, их не путать.

### Вариант A — MiniMax Code как отдельный агент (эта сессия)

MiniMax Code работает на той же ветке и в том же worktree. Правила те же:
`AGENTS.md` + `CLAUDE.md`. Скиллы MiniMax лежат в своём каталоге
(`%USERPROFILE%\.minimax\skills`), а не в `.claude/skills/`, поэтому скиллы проекта
для MiniMax доступны как файлы — путь даёт `.claude/rules/knowledge-map.md`.

Порядок запуска:

1. `git worktree list` — убедиться, что активен worktree агента, а не корень `main`.
2. `git branch --show-current` — убедиться, что ветка задачи, а не `main`.
3. Запустить MiniMax Code с каталогом этого worktree; в промпте указать цель и
   потребовать перед коммитом прогнать `python -m unittest tests.test_claude_hooks`.
4. Коммит и Draft PR делает агент ветки; `STATUS.md` не правится — результат живёт
   здесь и в PR.

Проверить, что ограничения не обойдены, из MiniMax можно тем же набором тестов:
`python -m unittest tests.test_claude_hooks -v` — 44 теста, они не обращаются к сети
и не трогают рабочие данные.

### Вариант B — Claude Code на MiniMax-совместимом бэкенде

Ключ MiniMax уже хранится локально в DPAPI-шифрованном виде:
`%USERPROFILE%\.minimax\credentials\minimax-mplan.key`
(создаётся скриптом `scripts/aider/Set-MiniMaxApiKey.ps1`, ключ никогда не печатается
и не попадает в репозиторий). Endpoint проверен: `https://api.minimax.io/anthropic`
отвечает 401 без ключа, то есть существует.

Запуск в одном окне PowerShell:

```powershell
$key = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Security.Cryptography.ProtectedData]::Unprotect(
          [System.IO.File]::ReadAllBytes("$env:USERPROFILE\.minimax\credentials\minimax-mplan.key"),
          $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser))
$env:ANTHROPIC_BASE_URL = 'https://api.minimax.io/anthropic'
$env:ANTHROPIC_AUTH_TOKEN = $key
$env:ANTHROPIC_MODEL = 'MiniMax-M3.1-Flash'
cd C:\Users\BLOWKA\Documents\Minimax\_wt\gremovod-claude-config
claude
```

Оговорка: этот вызов расходует план MiniMax владельца. В рамках этой задачи он **не
запускался** — «не запускать платные API» в задании. Запускать только по явному
желанию владельца.


## Проверки

| Команда | Результат |
|---|---|
| `python -m unittest tests.test_claude_hooks` | OK, 44 теста |
| `python -m unittest tools.test_agent_coordination tools.test_agent_scope` | OK, 14 тестов |
| `python -m pytest backend` | OK, 487 тестов + 26 subtests, 224.99 s |
| `npm test` (из `frontend/`) | OK, 120 тестов |
| `npm run build` (из `frontend/`) | OK, `tsc --noEmit && vite build` |
| `git config core.hooksPath .githooks` + `git commit` с запрещённым путём | отклонено, exit 1 |
| `.githooks/pre-commit` с чистым набором | «Git file check: OK», exit 0 |
| `claude doctor` (в worktree) | «No installation issues found» |

Платные API не вызывались, системные пакеты не устанавливались, реальная SQLite не
затрагивалась. В `frontend/` выполнен `npm ci` — это зависимости проекта, как требует
`docs/GIT_WORKFLOW.md` для нового worktree.

## Живой тест Claude Code: что подтверждено, а что осталось непроверенным

Claude Code установлен и работает: версия 2.1.302 (native, win32-x64), `claude doctor`
проходит без замечаний. **Живой модельный вызов выполнить не удалось**: аккаунт владельца
 упёрся в недельный лимит (`You've hit your weekly limit · resets 12pm (Europe/Moscow)`),
это ограничение аккаунта, а не конфигурации.

Что подтверждено без обращения к модели (debug-лог `claude --debug`, `--debug-file`):

- проектный файл `.claude/settings.json` найден и взят под наблюдение:
  `Watching for changes in setting files … \_wt\gremovod-claude-config\.claude\settings.json`;
- проектные скиллы загружены: `Loading skills from: … project=[…\.claude\skills]`;
- ошибок валидации настроек в логе нет (в `-p` режиме невалидные settings.json молча
  игнорируются — здесь этого не произошло);
- событие `hook_registered` в логе присутствует.

Что осталось непроверенным и требует живого теста после сброса лимита:

1. фактическая подстановка `.claude/rules/*.md` в системный промпт (правила грузятся при
   сборке запроса, а запрос не был отправлен);
2. фактический отказ хука в живой сессии — например, `git push origin main` должен быть
   отклонён с объяснением;
3. `/context` со списком загруженных memory files.

Пока это не сделано, **хуки не включать в рабочую конфигурацию** как единственный барьер:
`core.hooksPath .githooks` уже включён (это локальная настройка репозитория, в коммиты не
попадает), а хуки Claude Code — перекрывающий слой, который нужно подтвердить вживую.


