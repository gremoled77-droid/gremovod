# GremoVOD — локальный диспетчер Codex ↔ MiniMax (эксперимент, v2)

**Статус:** DRAFT / v2 поверх [PR #57](https://github.com/gremoled77-droid/gremovod/pull/57).
Не включать unattended-раунды до приёмки Codex и явного согласия владельца на расход квоты MiniMax.

**Проверенные версии:** MiniMax Code **0.6.12**, Codex CLI **0.160.0** (app-server 0.163.0), `gh` 2.102.0, Python 3.13.14, VS Code 1.142.0.

## Что изменилось в v2 (по итогам диагностики CLI)

| # | Было | Стало |
|---|---|---|
| 1 | `--permission auto` (не существует в CLI, exit 2) | `--permission smart` — публичное имя того же внутреннего режима `auto` |
| 2 | `subprocess.run(["mcode", …])` → `FileNotFoundError` на Windows | `node <npm-global>/node_modules/@minimax-ai/code/cli.js exec …`; npm-шим `mcode.cmd` без shell не запускается |
| 3 | нет машинно-читаемого результата | `--output-format json` + `-o <файл>` + `--output-schema`; код возврата читается явно |
| 4 | только внешний `timeout=3600` (kill) | `--timeout 3480s` внутри команды → чистый код возврата |
| 5 | без лимитов | `--max-steps 40`, `--prompt-mode coding`, `--effort`, `--model` доступны |
| 6 | риск `bypassPermissions` | `--permission full` не используется никогда; фикс-фаза только `smart` |
| 7 | цикл не замыкался | `commit`/`push` за отдельными разрешениями, только по allowlist путей, без `git add -A`, максимум 3 раунда, повторное ревью того же SHA запрещено |
| 8 | Codex только через GitHub-бота | независимое локальное ревью `codex exec … review` в отдельной detached-worktree, read-only |
| 9 | следующая задача проверялась по флагу `merged` | accept-запись `{merge_sha, at}` в state.json + явный маркер Codex |
| 11 | тесты покрывали только чистые функции | 27 offline-тестов: argv обеих CLI, таймауты, не нулевой exit, повторный запуск, устаревший SHA, неподтверждённый переход, лимит циклов, allowlist путей |

**Пункт 10 (необязательный, без глобальной установки).** Диспетчер запускает Codex по абсолютному пути к vendor-бинарнику, поэтому PATH менять не требуется. Но MCP-плагин `codex-local` (скилл `codex:codex-cli-runtime`) запускает `codex` по bare-имени и падает с `spawn codex ENOENT`. Минимальное изменение — добавить vendor-bin в пользовательский PATH:

```powershell
$vendor = "$env:APPDATA\Roaming\npm-global\node_modules\@openai\codex\node_modules\@openai\codex-win32-x64\vendor\x86_64-pc-windows-msvc\bin"
# только на текущую сессию:
$env:Path += ";$vendor"
# постоянно для пользователя (без глобальной установки пакетов):
[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path","User") + ";$vendor", "User")
```

Копию `C:\Users\BLOWKA\AppData\Local\OpenAI\Codex\bin\<hash>\codex.exe` в PATH **не добавлять**: это 0.159.0-alpha.12.1, старее vendor 0.160.0.

## Проверенные параметры CLI

**`mcode exec` (0.6.12)** — задание без интерактива: позиционный `prompt`, `--input -` (stdin), `--file`; результат: `--output-format text|json|stream-json`, `-o/--output-last-message`, `--output-schema`; директория: `--cwd`; права: `--permission smart|full|off` (`ask` — только TUI/ACP), `--mode`, `--prompt-mode`, `--timeout`, `--max-steps`.

**`codex exec` (0.160.0)** — задание без интерактива: позиционный `PROMPT` или `-` (stdin); результат: `--json` (JSONL), `-o/--output-last-message`, `--output-schema`; директория: `-C/--cd`, `--add-dir`; права: `-s/--sandbox read-only|workspace-write|danger-full-access`, `--approve-for-me`, `--ignore-rules`, `--ignore-user-config`, `--ephemeral`, `--worktree`.

**Важно о порядке флагов:** `-C`, `-s`, `--approve-for-me` — флаги уровня `codex exec`, поэтому они ставятся **до** подкоманды `review`. У `codex exec review` собственных `-C` и `-s` нет. У верхнего уровня `codex review` нет ни `-C`, ни `--worktree`, ни `-o`, ни `--json` — для автоматизации использовать только `codex exec … review`.

## Флаги диспетчера

| Флаг | Смысл |
|---|---|
| `--pr N` | числовой номер GitHub PR (обязателен) |
| `--worktree PATH` | worktree MiniMax (по умолчанию `C:\AI_Workflow_Studio\.worktrees\minimax`) |
| `--codex-worktree PATH` | worktree Codex, **detached** на head SHA PR (по умолчанию `…\.worktrees\codex-review`) |
| `--execute` | разрешает один headless-раунд MiniMax (расход квоты) |
| `--allow-commit` | разрешает staging+commit разрешённых путей |
| `--allow-push` | разрешает push (требует `--allow-commit`) |
| `--codex-review` | разрешает независимое локальное ревью Codex (расход квоты) |
| `--max-cycles N` | максимум раундов на задачу, 1..3, по умолчанию 3 |
| `--dry-run` | печатает план действий, ничего не запускает и не меняет |
| `--watch` | опрос раз в час |

## Безопасный запуск

```powershell
cd C:\AI_Workflow_Studio
python -m unittest discover -s scripts\agent-handoff -p "test_dispatcher.py" -v
```

1. **Прочитать состояние, ничего не запуская** (сетевые вызовы GitHub — да, модели — нет):

```powershell
python scripts\agent-handoff\dispatcher.py --pr 58
```

2. **Прогнать план без изменений**:

```powershell
python scripts\agent-handoff\dispatcher.py --pr 58 --execute --dry-run
```

3. **Независимое ревью Codex в отдельной worktree** (создаётся один раз вручную, detached на head SHA PR):

```powershell
git -C C:\AI_Workflow_Studio worktree add --detach C:\AI_Workflow_Studio\.worktrees\codex-review 9b6a610
python scripts\agent-handoff\dispatcher.py --pr 58 --codex-review --codex-worktree C:\AI_Workflow_Studio\.worktrees\codex-review
```

4. **Раунд исправлений MiniMax без записи в git** (только правит файлы, коммит и push — отдельные разрешения):

```powershell
python scripts\agent-handoff\dispatcher.py --pr 58 --execute --worktree C:\AI_Workflow_Studio\.worktrees\minimax
```

5. **Раунд с коммитом и пушем** (публикует только разрешённые пути, затем сам просит ревью Codex через `@codex review`):

```powershell
python scripts\agent-handoff\dispatcher.py --pr 58 --execute --allow-commit --allow-push --worktree C:\AI_Workflow_Studio\.worktrees\minimax
```

## Цикл GA-01 → GA-02

| Переход | Кто | Условие |
|---|---|---|
| `DRAFT → CHANGES_REQUESTED` | Codex-бот | маркер `codex-review-state:v1` на точном head SHA |
| `CHANGES_REQUESTED → FIX_PUSHED` | MiniMax (`mcode exec`) | чистая worktree, ветка = head PR, один запуск на `PR:SHA:status`, ≤ 3 раундов |
| `FIX_PUSHED → CHANGES_REQUESTED` | MiniMax → `gh pr comment "@codex review"` | новый SHA, ранее не ревьюившийся |
| `CHANGES_REQUESTED → REVIEW_CLEAR` | Codex-бот | `has_unresolved_findings=false` на текущем SHA |
| `REVIEW_CLEAR → MERGED` | **только человек** | у диспетчера нет права merge |
| `MERGED → NEXT_AUTHORIZED` | accept-запись + маркер `GREMOVOD_NEXT_TASK: GA-02` | обе части |
| `NEXT_AUTHORIZED → GA-02 STARTED` | владелец | новая ветка/worktree из `mavis/work` — по-прежнему вручную |

## Правила публикации (пункт 7)

* `git add -A` **не используется**: staging идёт поштучно, `git add -- <path>`.
* Allowlist путей: `backend/`, `frontend/`, `docs/`, `scripts/`, `tests/`, `tools/`. Всё остальное отклоняется с `REFUSED_PATH`.
* Отклоняются: абсолютные пути, `..`, `.git/**`, `.env*`, `id_rsa`, `credentials.json`, симлинки наружу из worktree.
* Перед коммитом сверяется набор проиндексированных файлов с allowlist — при расхождении коммит не выполняется.
* `--allow-commit` и `--allow-push` — независимые разрешения; `--allow-push` без `--allow-commit` блокируется.
* Повторный запрос ревью для уже ревьюившегося SHA не отправляется.

## Пределы безопасности

* Диспетчер локальный: gh + mcode + codex, без n8n, без API-ключей моделей, без сервера.
* Merge, force-push, `git reset`, `git checkout`, production SQLite, чтение секретов и платные генерации GremoVOD не выполняются.
* GitHub-комментарии считаются недоверенными данными: они кладутся в Markdown-файл, а не исполняются; prompt injection остаётся возможным.
* `--permission full` (= `bypassPermissions`) не используется; в фикс-фазе только `smart`.
* Автоповтор запрещён: после `LAUNCHED`, `TIMEOUT` или `FAILED` тот же `PR:SHA:status` повторно не запускается без нового SHA.
* Модель получает запрет на `git add/commit/push` — публикацией занимается диспетчер.
* `--watch` требует открытой PowerShell-сессии; для фоновой работы нужен планировщик Windows.

## Приёмка Codex

Проверить: изоляцию worktree, mock внешних `gh/mcode/codex`, маркер review и точное совпадение SHA, пагинацию комментариев, чистую worktree, allowlist путей, отсутствие `git add -A`, dedupe, таймауты и аварийные коды возврата, ровно один запуск на `PR:SHA:status`, лимит трёх раундов, запрет повторного ревью того же SHA, отсутствие перехода GA-01 → GA-02 без accept-записи и маркера. Затем один реальный GA-PR **без `--execute`**.

Связанные PR: [#54](https://github.com/gremoled77-droid/gremovod/pull/54), [#56](https://github.com/gremoled77-droid/gremovod/pull/56), [#57](https://github.com/gremoled77-droid/gremovod/pull/57).
