# Claude Code — компактная конфигурация агента ( claude-config-20261022 )

- **Сделано:** `CLAUDE.md` сокращён до компактной точки входа с импортом `@AGENTS.md`;
  тематические правила вынесены в `.claude/rules/`; повторяемые процедуры — в
  `.claude/skills/`; спроектированы и протестированы три хука `PreToolUse` (Git,
  секреты и данные, платные вызовы). По ревью Codex (MM-CLAUDE-02, CHANGES_REQUESTED)
  переработан гард Git (разделены источник и цель), усилены файловые ограничения
  (канонизация, границы worktree, временные каталоги), переработан платный гард
  (прямой вызов провайдера не открывается никаким переключателем), в общий контракт
  добавлены критерии качества разработки и цель беты со ссылками на D1–D4 и #54.
  По ревью MM-CLAUDE-03 исправлены: исключение `--dry-run` в платном гарде теперь
  привязано к отдельному вызову, перекрыты массовые варианты отмены изменений
  (`checkout .`, `restore` по дереву, `stash clear`), статус D1–D4 исправлен на
  OWNER_APPROVED с разделением утверждения решений и приёмки реализации.
- **Файлы:** `CLAUDE.md`, `AGENTS.md`, `docs/GIT_WORKFLOW.md`, `.gitignore`,
  `scripts/check_git_files.py`, `.claude/settings.json`, `.claude/hooks/guard_git.py`,
  `.claude/hooks/guard_files.py`, `.claude/hooks/guard_paid.py`, `.claude/rules/*` (6),
  `.claude/skills/*` (3), `tests/test_claude_hooks.py`.
- **Следующий шаг:** независимое ревью Codex обновлённого PR #74. Открытых пунктов,
  требующих решения, не осталось: зоны файлов, имя ветки и подключение тестов хуков в
  CI закрыты в предыдущем раунде и остаются в силе.

## MM-CLAUDE-02 — что исправлено по замечаниям ревью

### 1. `guard_git.py`: источник и цель — разные вещи

Главный дефект: `git merge origin/mavis/work` (обычная синхронизация task-ветки) был
запрещён, потому что аргумент считался целью. Теперь:

| Команда | Решение | Почему |
|---|---|---|
| `git merge origin/mavis/work` на task-ветке | разрешена | пишется task-ветка, `mavis/work` только читается |
| `git rebase origin/mavis/work`, `git cherry-pick origin/mavis/work` | разрешены | то же |
| `git merge` на самой `mavis/work` | запрещена | пишется защищённая ветка |
| `git push origin main` | запрещена | пишется удалённая защищённая ветка |
| `git push origin HEAD:main` | запрещена | смотрится **правая** часть refspec |
| `git push origin feature/main` | разрешена | обычная ветка |

Дополнительно проверено и закрыто: массовые push (`--all` с защищённой веткой в
наборе — запрещён, `--mirror` — запрещён, несколько refspec — любой защищённый
запрещает); Git с альтернативным рабочим каталогом (`git -C <path>` — проверяется
тот репозиторий, а не каталог сессии); force-push во всех формах (`-f`, `--force`,
`--force-with-lease`, кластер `-fu`); удаление ветки, занятой в чужом worktree; удаление
worktree; `git clean -f`; массовая отмена изменений (`checkout -- .`, `restore .`);
`reset --hard` при незакоммиченных правках.

### 2. Файловые ограничения

- Путь канонизируется (`resolve()`), поэтому symlink не может вывести запись за
  пределы worktree. Проверено двумя тестами: symlink наружу — запрещён, symlink во
  временный каталог — разрешён.
- Запись вне worktree и вне назначенных временных каталогов запрещена.
- Временные тестовые данные разрешены только в `tempfile.gettempdir()` и в `tmp/`
  репозитория (расширяется `GREMOVOD_TEMP_ROOTS`). Ключи, `.env` и приватные ключи
  запрещены везде, включая временные папки. Нормальный процесс тестирования не
  сломан: pytest, unittest и node-тесты пишут во временные каталоги.
- Нечитаемый payload — отказ, а не пропуск: действие, которое нельзя проверить,
  не выполняется.

### 3. `guard_paid.py`: переключатель — не авторизация

`GREMOVOD_ALLOW_PAID=1` больше не авторизует оплату и вообще не читается. Вместо
него `GREMOVOD_ALLOW_GATED_PAID=1`, и он открывает **только** путь через локальную
Studio (`scripts/watch_hunyuan_test.py`), где бюджет, разрешение владельца и
idempotency решает сервер. Прямой вызов провайдера (`api.piapi.ai`,
`api.openai.com`, …), `scripts/live_piapi_test.py` и флаги `--paid`/`--spend`
запрещены всегда — они обходят гейт Studio, и никакая переменная его не открывает.

Проверены составные команды и непрямые вызовы: хост внутри `bash -c`, внутри
`cmd /c`, после `&&`, в сегменте конвейера и в присваивании переменной окружения — все
отклоняются. Границы покрытия описаны явно: хук видит только командную строку, не
видит, что скрипт делает внутри, и не знает, одобрил бы Studio запрос.

### 4. Критерии качества в общем контракте

В `AGENTS.md` добавлен раздел «Критерии качества разработки»: диагностика
первопричины, red/green-регрессия, проверка архитектурных инвариантов, реальные
проверки по типу задачи, Definition of Done, отчёт `PASS / FAIL / BLOCKED /
NOT_RUN`, независимое ревью. `CLAUDE.md` не раздут — детализация в
`.claude/rules/quality.md` (с `paths`, грузится только при работе с кодом) и в скилле
`gremovod-verify`.

### 5. Цель беты

В `AGENTS.md` добавлен раздел «Цель текущей беты»: локальный путь идея → сценарий →
раскадровка → медиа → CapCut → MP4 → N34/N35 → утверждение владельца, со ссылками на
[глобальную приёмку #54](https://github.com/gremoled77-droid/gremovod/pull/54),
реестр решений, анализ пробелов беты и разбор «сценарий, агенты и знания».
Зафиксировано: локальный стенд и ручной CapCut идут первыми, а **оптимизация Claude
Code не является поводом создавать новую систему оркестрации**. Статус D1–D4 в этом
раунде был исправлен — см. раздел MM-CLAUDE-03.

## MM-CLAUDE-03 — финальные исправления

### 1. `guard_paid.py`: исключение `--dry-run` привязано к одному вызову

Было: наличие `--dry-run` где угодно в строке снимало запрет на весь скрипт, поэтому
`live_piapi_test.py --dry-run && live_piapi_test.py` проходил. Стало: строка
разбирается на отдельные вызовы (`&&`, `||`, `;`, `|`, перенос строки), и каждый
оценивается сам; `--dry-run` разрешает только свой вызов. Прямой вызов на строке
побеждает «gated»-вызов в любом месте строки.

### 2. `guard_git.py`: массовые варианты отмены изменений

Было запрещено только `git checkout -- .`. Теперь запрещены все формы, отменяющие
изменения сразу в дереве: `checkout .`, `checkout <каталог>`, `checkout HEAD -- .`,
`restore .`, `restore <каталог>`, `restore --worktree .`, `restore` без пути и
`git stash clear`. Разрешены точечные операции: `checkout -- file.txt` и
`restore --staged .` (второе только снимает индекс, рабочие файлы не теряются).

Попутно исправлен ещё один дефект: список аргументов включал сам подкомандный
аргумент, из-за чего `git restore` без пути считался имеющим путь `restore`.

### 3. `AGENTS.md`: статус D1–D4

Было написано неверно, что D1–D4 — рекомендации реестра. Фактически владелец
утвердил их после аудита #54: статус **OWNER_APPROVED**, источник —
[PR #55](https://github.com/gremoled77-droid/gremovod/pull/55) и
[`docs/decisions/2026-10-21-beta-acceptance-D1-D4.md`](https://github.com/gremoled77-droid/gremovod/blob/decisions/beta-d1-d4-20261021/docs/decisions/2026-10-21-beta-acceptance-D1-D4.md).

Разделено ровно то, что требовалось:

- **утверждение продуктовых решений** — D1–D4 утверждены как границы первой беты;
  это разрешение рамки, а не одобрение кода, платных вызовов, слияния или релиза;
  D5–D7 открыты;
- **приёмка реализации** — остаётся частичной: глобальный аудит #54 сохраняет статус
  PARTIAL / NO GO для платной беты до подтверждённого закрытия P0 и E2E, и решение
  D1–D4 этот статус не меняет.

В `AGENTS.md` добавлена таблица утверждённых решений с их следствиями для работы.

### 4. Конфликт областей с PR #62 и предложение по CI

**Файлы:** пересечение с PR #62 — только `.gitignore`. Хунки не пересекаются: PR #62
меняет строки ~27–31 (правило `tools/`), этот PR — строки ~46 и ~71 (`/.claude/`).
Виртуальное слияние `git merge-tree --write-tree` двух веток проходит без конфликта
(exit 0), и в слитом дереве присутствуют обе правки.

**Но есть реальный риск после слияния PR #62:** обновлённый
`agent-scope-guard.yml` в PR #62 расширяет условие запуска на префиксы `minimax/` и
`mavis/`. То есть гард областей начнёт работать и для этой ветки. Сейчас ветка
проходит, потому что её имя не совпадает с шаблоном ключа задачи `^[a-z]+-[0-9]+$`
(`claude-config` не является `xxx-NN`), и гард печатает
`LEGACY_BRANCH_NOT_ENFORCED`. Если ветку переименовать под шаблон или Codex введёт
новое правило, гард потребует объявления области в `tools/minimax_task_scopes.json`,
где `AGENTS.md` и `CLAUDE.md` стоят в `common_deny`, а `.claude/**` не принадлежит
ни одной роли.

**Предложение для Codex — одно изменение в `.github/workflows/agent-coordination.yml`:**

```yaml
    paths:
      # добавить
      - 'tests/test_claude_hooks.py'
      - '.claude/hooks/**'
      - '.claude/settings.json'
      - '.claude/rules/**'
      - '.claude/skills/**'
...
      - name: Validate handoff files, role boundaries, agent guards and seven safe MOCK n8n JSON files
        run: python -m unittest -v tools.test_agent_coordination tools.test_agent_scope tests.test_claude_hooks
```

Почему именно так:

- тесты хуков офлайновые, без сети и без платных вызовов, ~20 с — они не утяжеляют
  обязательный CI;
- `tests.test_claude_hooks` импортируется как namespace-пакет, дополнительных правок
  не требует;
- путь в фильтре нужен, чтобы воркфлоу запускался при изменении самих хуков: сейчас
  правка `.claude/hooks/**` не задевает ни один обязательный check.

Изменение в `.github/workflows/**` намеренно **не сделано в этом PR**: файл уже
меняется в PR #62, и трогать его отсюда — прямой конфликт. Правка принадлежит
Codex.



Квota аккаунта была исчерпана во время первого прогона; после сброса лимита живая
сессия отработала. Claude Code 2.1.302 в worktree агента:

| Что проверялось | Результат |
|---|---|
| `CLAUDE.md` + импорт `@AGENTS.md` | модель назвала `AGENTS.md` общим контрактом всех агентов — импорт работает |
| загрузка правил | в контексте `guards.md` и `knowledge-map.md`; `quality.md` не загружен, потому что у него `paths` — ленивая загрузка работает как задумано |
| `git push origin main --dry-run` | **отклонено хуком**: «Push to the protected branch 'main' is blocked…» |
| запись `backend/studio.sqlite3` | **отклонено хуком Write**, файл не создан |
| `curl https://api.piapi.ai/v1/task` | **отклонено хуком**, запрос к хосту не ушёл |
| `python scripts/live_piapi_test.py --dry-run` | разрешено и выполнено: скрипт возвращается до сетевого запроса и печатает только оценку цены |

Не проверено вживую: реальный платный вызов (запрещён заданием), `git push` без
`--dry-run` (в живой сессии не выполнялся ни разу), browser E2E.

## Проверки

| Команда | Результат |
|---|---|
| `python -m unittest tests.test_claude_hooks` | OK, 106 тестов |
| `python -m unittest tools.test_agent_coordination tools.test_agent_scope` | OK, 14 тестов |
| `python -m pytest backend` | OK, 487 тестов + 26 subtests, 219.24 s |
| `npm test` (из `frontend/`) | OK, 120 тестов |
| `npm run build` (из `frontend/`) | OK |
| `git commit` с запрещённым путём в staged | отклонено pre-commit, exit 1 |
| `.githooks/pre-commit` с чистым набором | «Git file check: OK», exit 0 |
| сканер секретов из PR #62 против этой ветки | `SECRET_SCAN: OK` |
| `claude doctor` | «No installation issues found» |

Платные API не вызывались, системные пакеты не устанавливались, реальная SQLite не
затрагивалась. В `frontend/` выполнен `npm ci` — зависимости проекта, как требует
`docs/GIT_WORKFLOW.md` для нового worktree.

## Red/green-доказательства

1. **Раунд MM-CLAUDE-02.** Новый набор тестов против реализации раунда 1: **23
   красных** (20 failures + 3 errors) из 91. С новой реализацией — **0 красных**.
2. **Раунд MM-CLAUDE-03.** Набор из 106 тестов против реализации раунда 2
   (`dd966ed`): **11 красных** — ровно 11 новых тестов раунда, каждый закрывает
   свой дефект (массовые варианты отмены изменений, `--dry-run` вне своего вызова).
   С новой реализацией — **0 красных, 106 OK**.
3. **Тесты кусаются.** При искусственно отключённом `guard_git.check` падают 12 из
   18 Git-тестов.

## Запуск официального Claude Code

Рабочий каталог — worktree агента, не корень репозитория:

```powershell
cd C:\Users\BLOWKA\Documents\Minimax\_wt\gremovod-claude-config
claude
```

Проверка, что конфигурация подхватилась: `/context` (список загруженных memory files)
и `/doctor prompt-audit`. Без интерактива:

```powershell
claude -p "Назови файлы правил, которые загружены в твой контекст" --debug
```

Проверить, что гард работает, в живой сессии:

```powershell
claude -p "Выполни git push origin main --dry-run и приведи точную причину отказа" `
  --permission-mode bypassPermissions
```

## Запуск отдельного MiniMax

Два разных варианта, их не путать.

### Вариант A — MiniMax Code как отдельный агент

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

### Вариант B — Claude Code на MiniMax-совместимом бэкенде

Ключ MiniMax уже хранится локально в DPAPI-шифрованном виде:
`%USERPROFILE%\.minimax\credentials\minimax-mplan.key`
(создаётся скриптом `scripts/aider/Set-MiniMaxApiKey.ps1`, ключ никогда не печатается
и не попадает в репозиторий). Endpoint проверен: `https://api.minimax.io/anthropic`
отвечает 401 без ключа, то есть существует.

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

Оговорка: этот вызов расходует план MiniMax владельца. В рамках задания он **не
запускался** — «не запускать платные API». Запускать только по явному желанию владельца.
