# GremoVOD — локальный диспетчер Codex → MiniMax (эксперимент)

**Статус:** DRAFT / NOT LIVE-TESTED ON WINDOWS. Не включать unattended-модельные вызовы до тестов и явного согласия владельца на расход квоты MiniMax.

## Что добавлено

`scripts/agent-handoff/dispatcher.py` — независимый от n8n минимальный локальный Python 3.13 скрипт, требующий `gh` и, только для запуска модели, `mcode`. Он читает GitHub API и не требует API-ключа Codex. Использует существующий GitHub PR handoff из [PR #56](https://github.com/gremoled77-droid/gremovod/pull/56); новый параллельный backend/ledger не создаётся.

* Проверяет только PR из `minimax/ga-01..05` в `mavis/work` и только из доверенного репозитория.
* Сверяет **Codex Review Summary с точным текущим head SHA**. Старое ревью или running — WAITING_FOR_CODEX.
* Если есть замечания, собирает GitHub reviews + inline + PR comments со **всех страниц**, сохраняет локальный Markdown в `%LOCALAPPDATA%/GremoVOD/agent-dispatcher`; исходники не трогает.
* **По умолчанию НЕ запускает агента.** `--execute` разрешает максимум один headless `mcode exec` на уникальный `PR:SHA:status`, только когда Codex завершил ревью с замечаниями. Проверяет ветку и чистоту worktree; фиксирует запуск до вызова модели. Не делает merge или платных генераций GremoVOD; однако само исполнение MiniMax **расходует квоту Token Plan**.
* Следующее задание GA-N+1 показывается только после **человеческого merge предыдущего PR** и точного сообщения от официального Codex GitHub bot `GREMOVOD_NEXT_TASK: GA-02` (и только для статической разрешённой очереди). На этом этапе диспетчер **ещё не запускает следующую задачу автоматически**: новая отдельная worktree/ветка и проверка зависимостей требуют интеграционного шага; это осознанный fail-closed барьер.

## Установка/первичная проверка (после review/merge экспериментальной ветки)

В PowerShell VS Code:

```powershell
cd C:\AI_Workflow_Studio
gh auth status
mcode --version
python -m unittest scripts/agent-handoff/test_dispatcher.py
```

Для Git worktree команда может быть запущена с точным путём к файлу через `python C:\AI_Workflow_Studio\.worktrees\minimax\scripts\agent-handoff\dispatcher.py`; сначала нужно перенести в неё принятый диспетчер, не overwriting dirty files.

Ручная проверка состояния (НЕ запускает MiniMax):

```powershell
python scripts/agent-handoff/dispatcher.py --pr 1234
```

Номер 1234 — пример. Укажи **реальный числовой GA-PR**, а не `GA-01` или PR #56 (у #56 другая branch).

Часовой local watch (PowerShell остаётся открытым):

```powershell
python scripts/agent-handoff/dispatcher.py --pr 1234 --watch
```

Только после теста и согласия владельца на расход Token Plan:

```powershell
python scripts/agent-handoff/dispatcher.py --pr 1234 --watch --execute
```

Перед `--execute` закрой интерактивный MiniMax TUI в **этой же** worktree. Запрещено одновременно иметь два писателя. `--watch` не означает работу, когда PC выключен/спит: для настоящего фонового процесса потребуется Windows Task Scheduler + учёт состояния + ограничение времени работы.

## Пределы безопасности

- Это **локальный прототип диспетчера**, не SaaS и не n8n Cloud worker.
- Нет `merge`, `push`, `git reset`, `git checkout`, файлов production SQLite, чтения secrets или запуска Codex API. Публикация PR делается самим MiniMax по отдельному ограниченному заданию.
- GitHub comments недоверенные; в модельном prompt они передаются как путь к локальному Markdown для проверки, а не исполняются как команды, но prompt injection по-прежнему возможен. Для автоматического `--execute` нужен дополнительный security review.
- Если MiniMax аварийно завершился после отметки `LAUNCHED`, автоматический повтор **запрещён**: потребуются ручная сверка, новый SHA или контролируемый reset. Это защищает от дублирования операций.
- Ограничения: timeout `mcode exec` 1 час; GitHub CLI API timeout 45 секунд на вызов; ограничение строк отчёта. Невыполнение Windows smoke явно отмечено.
- Текущая очередь не запускается самопроизвольно: GA-01 остаётся активной интерактивной задачей, а код-ревью Codex не является approval к слиянию.
- Диспетчер мониторит один PR за запуск. Массовая очередь нескольких PR, автоматическое создание worktree под следующую задачу, heartbeat на sleep/reboot и подтверждение Codex для GA-02+ требуют второго этапа после пилотного теста.

## Приёмка Codex

Проверь изоляцию, mock внешних `gh/mcode`, маркер Code Review bot, SHA, pagination, чистую worktree, dedupe, поведение crash/timeout, ровно один запуск на PR/sha/status, отсутствие запуска следующей задачи после обычного комментария или непринятого merge; затем протестировать один реальный GA-PR **без `--execute`**. Никаких production migrations/paid provider API.

Связанные решения: [#54](https://github.com/gremoled77-droid/gremovod/pull/54), [#55](https://github.com/gremoled77-droid/gremovod/pull/55), [#56](https://github.com/gremoled77-droid/gremovod/pull/56).
