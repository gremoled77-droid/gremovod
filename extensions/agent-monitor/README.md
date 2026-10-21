# GremoVOD Agent Monitor v1

Устанавливаемое VS Code extension: **GremoVOD: Open Agent Monitor**. Панель наблюдает за GitHub, существующим Python dispatcher v2 и локальной Git worktree. Backend Studio, n8n, Python-процесс и модельные API для работы монитора не нужны.

## Установка и запуск

Требуются VS Code ≥ 1.95, установленный GitHub CLI `gh` с доступом к `gremoled77-droid/gremovod`, Git. Авторизацию `gh` выполняет владелец обычным способом; extension не читает файлы credentials и не получает токен через `gh auth token`.

1. В этом каталоге: `npm ci`, `npm test`, `npm run package` (Node.js ≥ 22 для dev tools).
2. VS Code → Extensions → меню `…` → **Install from VSIX…** → `gremovod-agent-monitor-0.1.0.vsix`.
3. Откройте доверенную локальную папку проекта. `Ctrl+Shift+P` → **GremoVOD: Open Agent Monitor**.
4. В Settings найдите **GremoVOD Agent Monitor**. PR по умолчанию: **58, 59**, можно выбрать до 10 числовых PR. Репозиторий фиксирован.

Для разработки откройте сам каталог `extensions/agent-monitor`, выполните `npm ci` и `npm run build`, затем F5. В новом Extension Development Host вызовите команду открытия монитора. Расширение не меняет открываемую worktree.

Настройки:

| Настройка | Значение |
| --- | --- |
| `gremovodAgentMonitor.pullRequests` | `[58,59]`; наблюдаемые PR, а не разрешение на исполнение |
| `gremovodAgentMonitor.dispatcherDirectory` | Machine scope. Пусто → `%LOCALAPPDATA%/GremoVOD/agent-dispatcher` на Windows; после изменения переоткройте панель |
| `gremovodAgentMonitor.pollSeconds` | 120 секунд, минимум 60; ошибка удваивает интервал, максимум час |

**Refresh** обновляет локальные данные сразу. GitHub обновляется вручную не чаще раза в 15 секунд и сохраняет паузу после ошибок. Локальные `state.json` / `PR-*.md` / `PR-*.json` отслеживаются watcher; резервный локальный опрос — 30 секунд. Время последнего успешного GitHub-запроса и следующего разрешённого опроса видно в панели.

## Архитектура и границы read-only

```text
GitHub REST через gh api ─┐
dispatcher state/reports ─┼─ adapters → AgentEvent → append-only JSONL → Webview
Git branch/HEAD/status ───┘                    ↳ ID dedupe / filters / Handoff
```

- `src/events.ts`: контракт, проверка, фильтры, скрытие типовых секретов, JSONL.
- `src/sources.ts`: адаптер GitHub, dispatcher v1/v2, отчёты, Git; только `gh api` GET и Git branch/rev-parse/log/status. `GIT_OPTIONAL_LOCKS=0`.
- `src/extension.ts`: команда, жизненный цикл панели, watcher, опрос/backoff, журнал в VS Code globalStorage, проверенные действия.
- `media/monitor.js` и `.css`: интерфейс без UI framework и runtime npm dependencies.
- `test/`: фикстуры, unit/adapter checks, реальный VS Code Extension Host и Webview UI.

Extension записывает только свой журнал/метаданные VS Code, не `state.json`, отчёты, исходники, ветки или SQLite. Копирование изменяет clipboard; открытие локального отчёта создаёт **редактированный текстовый снимок** в untitled editor. Ни одной команды запуска MiniMax/Codex, push, merge или переключения веток в панели нет.

## Источники и честность состояний

GitHub PR, discussion, reviews, inline findings, commits, имена изменённых файлов и GitHub Actions загружаются из REST. Для комментариев, reviews, commits и files используется `--paginate --slurp`. Ограничение API GitHub на список файлов отмечается предупреждением; Actions ограничены 100 последними runs текущего head SHA и предупреждают при превышении. GitHub Actions ≠ доказательство локального запуска pytest; текст в PR/отчёте ≠ независимая проверка тестов.

**Codex GitHub** — только события официального `chatgpt-codex-connector[bot]`; **Codex CLI** — отдельно наблюдаемые локальные `PR-N-codex-review.md`. Вердикт берётся из `codex-review-state:v1` официального бота и только на **точном head SHA**. Если SHA сменился, показывается **Stale SHA**; running, отсутствующий или повреждённый marker не считается clear. Findings P0/P1/P2 считаются только для текущего SHA; это число записанных findings, **не** число открытых discussions. После второго чтения PR смена head в ходе обновления также инвалидирует вердикт.

Dispatcher v2 `state.json`: `{version:2,runs:{"PR:SHA:STATUS":{status,at,round}},tasks:{"GA-01":{rounds,reviewed_shas,accepted}}}`. Поддерживается старый flat `runs` формат. `accepted` показывается как существующая запись, не новое разрешение. Следующая GA-задача не запускается; GitHub merge + официальный marker показываются только как наблюдения, dispatcher acceptance не выдумывается.

Существующий dispatcher **не пишет JSONL и heartbeat**, не записывает worktree процесса, текущую команду, фазу тестирования и подтверждённую активность процесса. `LAUNCHED` значит только «запуск записан тогда-то». При закрытом терминале монитор сохраняет последнее известное наблюдение с временем и **current activity Unknown**. Изменённые файлы относятся к **открытой наблюдаемой worktree**, а не автоматически к MiniMax.

Читаются только отчёты с именами `PR-N[-12hex]-feedback.md`, `PR-N[-12hex]-feedback-result.json`, `PR-N-codex-review.md` внутри настроенного каталога, после realpath-проверки. Произвольные CLI-логи и внутреннее хранилище чатов не читаются. Ответы/задания доступны в Handoff как текст источника; их содержание не исполняется.

## AgentEvent / история

Каждая JSONL-строка содержит:

`event_id, timestamp, source, agent, task_id, pr_number, commit_sha, event_type, severity, status, summary, payload_ref, correlation_id`.

Недоступные task/PR/SHA — `null`, в UI `Unknown`. Время создания/изменения GitHub берётся из API; `report_observed` использует **mtime файла**, что подписано как наблюдение. Некоторые события не имеют SHA: у discussion/создания PR нет достоверной привязки к конкретному commit. SHA не подставляется задним числом.

`event_id` — SHA-256 от источника и стабильного upstream identity + revision (например comment ID/updated_at). Обновление комментария — новая версия события; одинаковый poll не создаёт повтор. `correlation_id` объединяет task/PR/SHA, не является разрешением на действия.

Журнал: `<VS Code globalStorage>/gremovod.gremovod-agent-monitor/<workspace-hash>/events.jsonl`. В нём только краткие очищенные summaries и проверенные GitHub ссылки, **без полных тел отчётов/комментариев, stderr и credentials**. Полный редактированный текст текущих источников хранится в памяти и заново загружается при открытии. Поэтому старое событие может иметь только summary и ссылку, когда исходного текста уже нет.

История переживает переоткрытие панели/VS Code. Файл никогда не ротируется/удаляется автоматически. Чтение потоковое; oversized/corrupt/оборванные строки пропускаются с предупреждением. В UI сохраняется окно **5000 последних событий по времени**, с постраничным выводом 200; полный JSONL остаётся на диске. Dedupe ID индекс содержит всю историю; память индекса растёт с числом уникальных событий. При необходимости полного старого архива откройте JSONL вручную. Локальный state ≤4 MiB, отчёт ≤256 KiB, максимум 200 файлов; превышения явно обозначаются.

## Безопасность

CSP: `default-src 'none'`, nonce для скрипта, локальный stylesheet, запрет connect/img/form/base; resources только в `media`. Нет `innerHTML`, Markdown renderer, remote images или command URI. Все внешние данные — `textContent`. Webview передаёт только allowlisted типы сообщений и event ID; extension находит событие в своём журнале. Произвольные пути/URL/команды от Webview не принимаются. Открываются только HTTPS ссылки внутри точного GitHub repo без credentials/query и проверенные локальные отчёты.

Перед выводом/копированием и записью summaries скрываются распространённые token/key форматы, credential assignments, auth headers, private keys и URL credentials/query. Секретные файлы не читаются. **Эвристическая redaction не может распознать произвольный неразмеченный секрет в чужом тексте**; владельцу нельзя помещать секреты в GitHub comments или агентские отчёты. Скриншоты/журнал перед публикацией проверяются отдельно. Доверенная workspace обязательна; remote/virtual workspace не поддерживается.

## Проверки

```powershell
npm ci
npm test
# Отдельный тестовый профиль, живой read-only PR 58, без моделей:
$env:VSCODE_EXECUTABLE_PATH = 'C:\Users\BLOWKA\AppData\Local\Programs\Microsoft VS Code\Code.exe'
npm run test:host
npm run package
```

Host runner без `VSCODE_EXECUTABLE_PATH` использует загрузку VS Code из `@vscode/test-electron`. UI проверяется Playwright через loopback CDP **только в тестовом профиле** (порт 19358); обычная установка не открывает debug-порт. Если он занят, тест не следует запускать до выбора другого порта в обоих test scripts. Тест не трогает профиль рабочего VS Code. Нет платных моделей. Сетевой отказ/смена SHA тестируются mock-адаптерами; сетевой интерфейс компьютера не отключается.

Текущие результаты и скриншот — в [evidence](evidence/). Модульные тесты не заменяют приёмку владельцем. Перед ней: установить VSIX в рабочий VS Code, открыть нужную worktree, сверить данные PR/ревью, источник и clipboard, указать реальный dispatcher directory при его наличии. Live модельный цикл не запускался и для проверки UI не нужен.

## База Draft PR

На 21.10.2026 PR #54–59 не слиты. Цепочка: **#56 → #57 → #59 → этот PR**; база реализации — `experiment/codex-minimax-local-dispatcher-20261021-v2@ba078cb`. Выбрана для проверки точного контракта v2 и обзора отдельного additive diff. Это **не** функциональность `mavis/work`. Расширение автономно по runtime: читает файлы, не импортирует/не запускает Python dispatcher и не требует слияния экспериментальных workflows для GitHub-наблюдения. Main не подмешивается: пользователь задал конкретную экспериментальную цепочку и отдельный review; посторонние изменения main не входят в этот PR.

Dispatcher, его tests, `.vscode/tasks.json`, GA-01, Studio backend/frontend, main, SQLite и канон этим PR не изменяются. Merge не выполняется; Marketplace не публикуется.
