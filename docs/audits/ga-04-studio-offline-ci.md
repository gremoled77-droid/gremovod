# GA-04 · Полноценный offline CI кандидата

**Дата:** 2026-10-21
**Ветка:** `minimax/ga-04-studio-offline-ci`
**База:** `origin/mavis/work` @ `57cac59`
**Worktree:** `.worktrees/ga-04-ci`
**Статус:** реализовано, ожидает независимого ревью Codex. Runtime-код приложения не тронут.

---

## 1. Итог

Кандидат теперь получает воспроизводимую offline-проверку: backend-тесты на временной
SQLite, frontend-тесты, TypeScript, production-сборка Vite, контракты CI и скан
секретов. Scope guard расширен на task-ветки `minimax/**` и `mavis/**` — без поломки
исторических PR.

**Важное различие, которое GA-04 просит отчётливо разделить:**

| Утверждение | Состояние |
|---|---|
| «Workflow существует и запускается на PR» | **Да.** `studio-offline-ci.yml` в этой ветке |
| «Branch protection требует этот check» | **Нет.** Настройки репозитория и required checks не менялись — это отдельное решение владельца (D7) |

Пока check не внесён в branch protection, красный CI **не блокирует** слияние.
Это осознанно: GA-04 прямо запрещает менять настройки репозитория без отдельного
решения владельца.

---

## 2. Что изменено

| Файл | Изменение |
|---|---|
| `.github/workflows/studio-offline-ci.yml` | **новый** — тяжёлые проверки: `backend-unit`, `backend-media`, `frontend-unit`, `frontend-typecheck-build`; фильтр путей на триггере |
| `.github/workflows/studio-ci-contract.yml` | **новый** — проверки, которые выполняются **всегда**: `ci-contract`, `secret-scan`; без фильтра путей |
| `.github/workflows/agent-scope-guard.yml` | predicate `if:` дополнен префиксами `minimax/` и `mavis/` |
| `.github/workflows/agent-coordination.yml` | в `paths:` добавлены новый workflow и новые `tools/*`, чтобы правки CI проходили координационную проверку |
| `tools/minimax_task_scopes.json` | **новый** — явный allowlist областей для task-веток (`ga-01`…`ga-05`) |
| `tools/check_agent_scope.py` | добавлены `task_key_for_branch()`, `validate_manifest()`, `load_manifest()`; `forbidden_files(branch, paths)` → `forbidden_files(branch, paths, manifest=None)` |
| `tools/test_agent_scope.py` | +13 тестов на task-scope (все 6 прежних сохранены без изменений) |
| `tools/check_ci_contracts.py` | **новый** — проверка workflow-файлов, контракта кандидатного workflow и соответствия lock-файла |
| `tools/test_ci_contracts.py` | **новый** — 14 тестов |
| `tools/check_no_secrets.py` | **новый** — скан секретов по добавленным строкам изменения |
| `tools/test_no_secrets.py` | **новый** — 12 тестов, включая интеграционный на временном git-репозитории |
| `.gitignore` | убрана строка `tools/` — она молча скрывала новые исходники `tools/*.py` и манифест от `git add`; локальные payloads остаются исключены через `tools/downloads/` и `tools/ffmpeg/` |
| `docs/audits/ga-04-studio-offline-ci.md` | **новый** — этот handoff |

Runtime-модули приложения (`backend/main.py`, `backend/llm_guard.py`,
`backend/spend_ledger.py`, `frontend/src/**`) **не изменялись**.

---

## 3. Как устроен CI

Два workflow:

```
studio-ci-contract.yml   без фильтра путей   ci-contract + secret-scan   (всегда)
studio-offline-ci.yml    фильтр на триггере  backend-unit, backend-media,
                                             frontend-unit, frontend-typecheck-build
```

### Почему два, а не один

Первая версия была одним workflow с фильтрами путей **на уровне job**. Так делать
нельзя: **`paths` не является допустимым ключом job в схеме Actions.** YAML это
принимает, но GitHub отвергает весь файл — прогон падает за 0 секунд с «workflow
file issue» и нулём jobs. Это поймал настоящий прогон Actions, а не локальная
проверка: первая версия `check_ci_contracts.py` проверяла только синтаксис YAML и
пропустила несуществующий ключ.

Отсюда две правки, обе в этом PR:

1. **Фильтры путей живут на триггере** (`on.pull_request.paths`), где они и
   допустимы. Тяжёлые проверки запускаются только когда изменение их касается.
2. **`check_ci_contracts.py` теперь проверяет ключи по схеме Actions**, а не только
   синтаксис YAML: допустимые ключи workflow / job / step перечислены явно, любое
   другое имя — находка. Это ловит целый класс ошибок, а не только `paths`.

### Почему контрактный workflow без фильтра

Фильтр путей на уровне workflow у тяжёлых проверок и отсутствие фильтра у
контрактных дают оба нужных свойства:

1. **Docs-only PR не создаёт ложный статус полной Studio-приёмки.** Тяжёлый workflow
   просто не запускается, и видно, что именно не выполнялось.
2. **Ловушка required-checks не возникает.** Контрактный workflow выполняется на
   каждом PR, поэтому check существует всегда. Если бы фильтр стоял на обоих
   workflow'ах, required-check правило зависало бы на PR, чьи файлы не попали ни в
   один фильтр.

Контрактный workflow дополнительно пишет в `$GITHUB_STEP_SUMMARY` явное «что этот
прогон НЕ покрывает»: без production Studio, без платного провайдера, без n8n cloud,
без QC мастера выпуска, без решения по branch protection.

### Пути, которые обязаны запускать проверки

`tools/check_ci_contracts.py` проверяет, что фильтры кандидатного workflow покрывают
`backend/main.py`, `backend/llm_guard.py`, `backend/character_voice.py`,
`backend/spend_ledger.py` и `frontend/**`. Если кто-то сузит `backend/**` до
`backend/api/**` — контрактный тест упадёт. Это защита от регрессии path-фильтров,
а не декларация.

### Ограничения, соблюдённые по GA-04

- Никаких `secrets.*` в CI — это проверяется автоматически (`check_ci_contracts.py`).
- Никаких платных API, никакого провайдерского smoke.
- Никакого live-скрипта: `scripts/live_piapi_test.py` и подобные не вызываются.
- Никаких правок настроек репозитория, required checks, permissions и auto-merge.
- `permissions: contents: read` — только чтение.
- Backend работает на временной SQLite: `STUDIO_DATA_DIR` указывает на `$RUNNER_TEMP`.

---

## 4. Что уже было и НЕ продублировано

| Существующий артефакт | Что с ним сделано |
|---|---|
| `.github/workflows/n8n-astra-pilot.yml` | Оставлен как есть. Он закрывает узкий n8n-пилот и 52-узловой контраст. Новый workflow его не повторяет |
| `.github/workflows/agent-coordination.yml` | Оставлен как есть, расширен только список путей |
| `.github/workflows/agent-scope-guard.yml` | Не переписан — расширен только predicate. Логика решения «enforced / legacy» перенесена **в инструмент**, чтобы один код решал для всех префиксов |
| `tools/check_agent_scope.py` | Существующий механизм ролей (`build/*`, `codex/*`, `coordination/*`) не изменён. Добавлен второй, независимый механизм для task-веток |
| `scripts/check_git_files.py` | Не переписан. `check_no_secrets.py` **импортирует** его `blocked()`, чтобы pre-commit и CI не разошлись |
| `tools/test_agent_coordination.py` | Не изменён. Контракты n8n MOCK-экспортов и handoff-документов проверяются там же |
| `backend/requirements.lock.txt` | Не изменён. В CI добавляется ровно одна зависимость — `pyyaml==6.0.3` — и только в job `ci-contract`, явно закреплённой версией |

Зависимость `pyyaml` не входит в `backend/requirements.lock.txt` намеренно: это
CI-only инструмент, а не runtime-зависимость студии.

---

## 5. Scope guard: как расширен и почему это не ломает исторические PR

### Механизм

Ветка разбирается на ключ задачи:

```
minimax/ga-04-studio-offline-ci  ->  ga-04
mavis/ga-02-text-task-lifecycle  ->  ga-02
mavis/work                       ->  None (не task-ветка)
minimax/p0-budget-authz          ->  None (не task-ветка)
feature/*, codex/*, build/*      ->  прежний механизм ролей
```

Ключ ищется в `tools/minimax_task_scopes.json`. Если ветка — task-ветка, а ключа нет
в манифесте, проверка **падает закрыто** (`UNKNOWN_TASK_SCOPE`, exit 1): обойти
guard нельзя, объявить область надо явно. Это прямо закрывает риск «false skip»,
названный в GA-04.

### Манифест читается из base-коммита, а не из head

`load_manifest(base)` читает `origin/<base>:tools/minimax_task_scopes.json`.
Следствие: **task-ветка не может расширить свою область в том же PR** — проверяется
та область, которая была в силе на момент базы. Расширение требует отдельного
ревью и попадает в силу со следующего PR.

Единственное исключение — bootstrap-PR, который сам вводит манифест. В этом случае
печатается явное `SCOPE_BOOTSTRAP`, и проверка применяется к собственному
объявлению PR. Такой PR обязан пройти ревью.

### Валидатор тоже берётся из base-коммита

Манифест читать из base — половина защиты. Вторая половина: **код, который выносит
вердикт, тоже должен приходить из base**. Иначе task-ветка может в том же PR
переписать `tools/check_agent_scope.py` (например, на `sys.exit(0)`) и обойти
проверку целиком.

Поэтому workflow делает так:

1. чекаутится PR-head — там живут изменённые файлы, и `git diff` считает их;
2. из `github.event.pull_request.base.sha` материализуется **доверенная копия**
   `tools/check_agent_scope.py` и `tools/minimax_task_scopes.json` в
   `${{ runner.temp }}/scope-guard` — вне рабочего дерева PR;
3. запускается именно эта копия. Код PR не исполняется вообще: валидатор только
   читает git.

Итог: подмена валидатора в том же PR больше не влияет на вердикт этого PR.
Красный прогон этого поведения — в `tools/test_agent_scope.py`
(`TrustedControlCodeTests`), там подставляется настоящий git-репозиторий с
base-ревизией и PR-ревизией, и проигрывается протокол workflow целиком.

Дополнительно валидатор сверяет переданные `--branch`/`--base` с payload'ом
события GitHub (`GITHUB_EVENT_PATH`), который пишет сам GitHub. Расхождение —
`SCOPE_ERROR` и exit 2: подменить базу аргументом командной строки нельзя.

### Что ещё не закрыто: сам workflow

Файл `.github/workflows/agent-scope-guard.yml` на событии `pull_request` берётся
GitHub'ом **из merge-коммита PR**, а не из базовой ветки. Значит PR может изменить
workflow и выбрать, какой код запустится. Внутри репозитория это не закрывается:

- изменение control-файлов **обнаруживается**: доверенный валидатор печатает
  `CONTROL_FILE_CHANGE: <путь>` (`.github/workflows/agent-scope-guard.yml`,
  `tools/check_agent_scope.py`, `tools/minimax_task_scopes.json`);
- но если PR вырежет шаг с доверенным кодом совсем, проверка просто **не
  запустится** — и тогда нужен branch protection: обязательный check, который не
  отчитался, блокирует merge.

Именно это и есть разница между гарантией CI и гарантией branch protection:

| Что | Кто даёт |
|---|---|
| PR не может расширить свою область, подменить валидатор или манифест **для собственного вердикта** | CI (доверенный код из base) |
| PR не может удалить или ослабить саму проверку | branch protection владельца: обязательный check `check-agent-scope` + `CODEOWNERS` на `.github/workflows/` |

`pull_request_target` сознательно **не используется**: этот триггер берёт workflow
из ветки по умолчанию, а `main` (ветка по умолчанию) на 129 коммитов позади
`mavis/work` и guard туда ещё не доехал. Такая проверка молча перестала бы
запускаться. Это зафиксировано контрактом в `tools/check_ci_contracts.py`.

### Bootstrap-ветка: отдельное проверяемое поведение

Base-ревизия, которая не умеет судить PR доверенным кодом, — это отдельный
случай, а не повод молча пропустить проверку:

- base без `tools/check_agent_scope.py` → `SCOPE_CONTROL_CODE=bootstrap`;
- base со старым валидатором (без `--interface-version`) → тоже `bootstrap`;
- в обоих случаях workflow печатает `SCOPE_BOOTSTRAP`, объясняет, что проверка
  не может защитить саму себя, и запускает валидатор самого PR.

Для текущего PR #62 это ровно тот случай: в `origin/mavis/work` нет ни манифеста,
ни доверенного интерфейса. Проверка отрабатывает bootstrap-путь, применяет
собственное объявление PR и требует ревью владельца. **После merge этого PR
guard начнёт судить следующие PR доверенным кодом из base.**

### Общая часть области: `common_allow` и `common_deny`

Манифест разделён на общую часть и область каждой задачи:

```json
"common_allow": ["docs/"],
"common_deny": ["canon/", "skills/", "docs/specs/",
                "AGENTS.md", "CLAUDE.md", "AGENT_BUILD_MANUAL.md"]
```

- `common_allow` — то, что любая task-ветка может править помимо своей области.
  Сюда попал `docs/`, потому что по правилам проекта каждая задача обязана
  обновлять handoff, и без этого каждая такая правка падала бы на scope-проверке.
- `common_deny` — то, что запрещено **всем** task-веткам, и что **всегда** побеждает
  и `common_allow`, и область задачи. Это механическое закрепление общего запрета из
  бэклога: без канона, без правок существующих AGENTS/CLAUDE/SKILL, без правок
  контрактов Codex в `docs/specs/`.

### Как это отнесено к уже идущим задачам

Проверено симуляцией на реальных списках файлов:

| Ветка | Файлы | Результат |
|---|---|---|
| `minimax/ga-01-llm-settlement` (PR #58) | `backend/llm_guard.py`, `backend/main.py`, `backend/test_llm_settlement.py` | **ALLOWED** |
| `minimax/ga-05-trusted-proxy-throttle` (идёт параллельно) | `backend/remote_access.py`, `backend/test_remote_access.py`, `.env.cloud.example`, `docs/CLOUD_DEPLOY.md`, `docs/HANDOFF_CLAUDE_CODE.md` | **ALLOWED** |
| `minimax/ga-04-studio-offline-ci` (эта ветка) | 12 файлов этой задачи | **ALLOWED** |

Область `ga-05` расширена до `.env.cloud.example` и `docs/CLOUD_DEPLOY.md` — они
входят в задачу про доверенный proxy для login throttle, и без этого чужой PR
задачи упал бы на scope-проверке.

---

## 6. Проверки, которые прошли локально

| Проверка | Команда | Результат |
|---|---|---|
| Backend unit suite | `python -X utf8 -m unittest discover -s backend -p "test_*.py"` | **487 тестов, OK** (exit 0) |
| Backend unit suite (без медиа) | тот же набор, что и job `backend-unit` | OK |
| Инструменты CI | `python -X utf8 -m unittest tools.test_ci_contracts tools.test_no_secrets tools.test_agent_scope tools.test_agent_coordination` | **62 теста, OK** |
| Контракты CI | `python tools/check_ci_contracts.py` | `CI_CONTRACT: OK` (exit 0) |
| Скан секретов | `python tools/check_no_secrets.py --base mavis/work` | `SECRET_SCAN: OK` (exit 0) |
| Frontend unit | `npm test` | **120 passed, 0 failed** |
| TypeScript | `npx tsc --noEmit` | exit 0 |
| Production build | `npx vite build` | exit 0 (`✓ built in 5.07s`) |
| Scope guard на своей ветке | `python tools/check_agent_scope.py --branch minimax/ga-04-studio-offline-ci --base mavis/work` | exit 0 |

### Реальный прогон GitHub Actions (PR #62)

Прогон на настоящем runner'е GitHub дал то, чего локально проверить было нельзя.

**Первая версия workflow была отвергнута GitHub.** Прогон `39596575728`:
`failure`, **0 секунд, 0 jobs**, «This run likely failed because of a workflow file
issue». Причина: **`paths` не является допустимым ключом job в схеме Actions.**
Это видно и по тому, что прогон был создан на `push` в ветку, которую триггер
`push: branches: [mavis/work]` не покрывает: при невалидном файле GitHub создаёт
синтетический прогон на push, чтобы показать ошибку.

Локальная проверка этого не поймала: `check_ci_contracts.py` проверял только
синтаксис YAML. **Исправлено:** фильтры путей перенесены на триггер, а проверка
контрактов теперь сверяет ключи workflow / job / step со схемой Actions и любое
неизвестное имя считает находкой.

После исправления на реальном runner:

| Workflow | Результат | Время |
|---|---|---|
| `GremoVOD CI contracts` (`studio-ci-contract.yml`) | **success** | 15 с |
| `Agent ownership boundaries (new task branches)` | **success** | 9 с |
| `Agent handoff and workflow export checks` | **success** | 15 с |
| `GremoVOD Studio offline CI` (`studio-offline-ci.yml`) | запущен | ~4 мин |

Проверенные на реальном runner свойства:

- **Scope guard теперь вообще запускается на `minimax/**`.** До GA-04 все прогоны
  «Agent ownership boundaries» для таких веток были `skipped` — теперь `success`.
- **Существующие CI не сломаны:** coordination и scope guard зелёные.
- **Path-фильтр работает в обе стороны.** На PR, меняющем только `.github/`,
  `tools/`, `docs/` и `.gitignore`, тяжёлый workflow **не запустился** — ровно то
  поведение, которое нужно, чтобы docs-only PR не выдавал ложную полную приёмку.
  После добавления `backend/CI.md` тот же workflow **запустился**.
- **Контрактный workflow не имеет path-фильтра** и отработал на каждом PR.

### Что показал первый настоящий прогон (пошагово)

| Job | Шаг | Итог |
|---|---|---|
| Backend unit tests | Backend unit tests | **success** — все 487 тестов на ubuntu-latest |
| Frontend TypeScript and production build | TypeScript type check / Production build | **success** |
| Backend media and QC tests | Media and QC tests | **success** — FFmpeg из apt, медиа-ожидания совпали |
| Frontend unit tests | Frontend unit tests | **failure** |

**Падение фронтенда — реальная находка.** Два фронтенд-теста
(`frontend/directorState.test.mjs`) сравнивают браузерную подпись промпта с серверной
и для этого вызывают Python напрямую: `from backend.frame_composition import basis`.
На runner'е нет ни `.venv`, ни `fastapi` → `ModuleNotFoundError: No module named
'fastapi'`. Локально это проходило случайно: тест находит Python вверх по дереву
(`findVenvPython`), а в PATH лежал venv соседнего проекта с fastapi.

Исправление: в job `frontend-unit` добавлены `actions/setup-python@v5` и установка
`backend/requirements.lock.txt`, а тесту передан `STUDIO_PYTHON` — это уже
предусмотренный самим тестом хук (`process.env.STUDIO_PYTHON`).

**Медиа-джоб переведён в блокирующий.** Первый прогон дал зелёный шаг
`Media and QC tests` на реальном runner'е, то есть FFmpeg-сборка ubuntu удовлетворяет
ожиданиям по точным свойствам медиа. `continue-on-error: true` убран, и добавлено
правило в контрактный чекер: job в `studio-offline-ci.yml` не может быть
`continue-on-error`, иначе сломанный тест не покрасит CI в красный.

### Красный CI на реальном runner (проба от 12:17)

Чтобы доказать, что проверки действительно кусаются, в ветку был внесён
намеренно сломанный backend-тест (`assertEqual(status_code, 403)` → `500`) в файле
`backend/test_spend_guard.py`, который **не входит** в область `ga-04`.

| Workflow | Результат | Что показал |
|---|---|---|
| `Agent ownership boundaries (new task branches)` | **failure** | `AGENT_SCOPE: role=task:ga-04, changed=15, forbidden=1` → `CROSS_OWNER_CHANGE: backend/test_spend_guard.py` |
| `GremoVOD Studio offline CI` | **failure** | job `Backend unit tests` — падающее утверждение |
| `GremoVOD CI contracts` | success | контракты и секреты не затронуты — и не должны затронуться |
| `Agent handoff and workflow export checks` | success | существующий CI не затронут |

Проба откачена (коммит `a265ccf` удалён), тесты снова зелёные, CI снова зелёный.
Тем самым закрыты сразу два критерия приёмки: «намеренно сломанный тест приводит к
красному CI» и «изменение защищённого файла за пределами разрешённой области
блокируется» — оба подтверждены на настоящем runner'е, а не только локально.

### Доказательство «красного» поведения (red → green)

- **Scope guard.** Новые тесты `tools/test_agent_scope.py` прогоняются против
  **исходного** `tools/check_agent_scope.py` → `ImportError: cannot import name
  'ROOT'` → `FAILED (errors=1)`. Против новой реализации → `Ran 19 tests … OK`.
- **Скан секретов.** `tools/test_no_secrets.py::SecretScanDiffTests` строит временный
  git-репозиторий, делает коммит с ключом `sk-…` и требует, чтобы находка была.
  До исправления тест падал (`AssertionError: [] is not true`) — это выявило реальный
  баг: `added_lines()`/`changed_paths()` игнорировали аргумент `root` и диффили не
  тот репозиторий. Исправлено передачей `cwd` в `subprocess.run`.
- **Контракты workflow.** `test_unpinned_action_is_a_problem`, `test_secret_reference_is_a_problem`,
  `test_pull_request_target_head_checkout_is_a_problem`, `test_missing_permissions_is_a_problem`
  каждый конструирует заведомо плохой workflow во временном каталоге и требует
  найти проблему.
- **Намеренно сломанный backend-тест.** `backend/test_spend_guard.py` —
  `assertEqual(status_code, 403)` заменён на `500` → `AssertionError: 403 != 500`,
  `FAILED (failures=1)`, **exit 1**. После отката — зелёный.
- **Намеренно сломанный frontend-тест.** `frontend/n8nSpend.test.mjs` —
  `assert.equal(capUsd('0.05'), 0.05)` заменено на `0.06` → `ERR_ASSERTION`,
  **exit 1**. После отката — `120 passed, 0 failed`.
- **Скан секретов на реальном изменении.** Коммит с `API_KEY = 'sk-…'` →
  `SECRET_SCAN: FAILED (10 finding(s))`, exit 1. После отката — `SECRET_SCAN: OK`.
- **Scope guard на чужом пути.** Коммит, добавляющий `frontend/src/ga04-scope-probe.ts`
  в task-ветку → `CROSS_OWNER_CHANGE: frontend/src/ga04-scope-probe.ts`, exit 1.
  После отката — `forbidden=0`, exit 0.

### Два места, где новые инструменты нашли нарушение в этой же ветке

1. **Scope guard поймал мою же правку `.gitignore`.** Первая версия манифеста не
   объявляла `.gitignore`, и проверка честно вернула
   `CROSS_OWNER_CHANGE: .gitignore`, exit 1. Область объявлена явно; теперь
   `changed=12, forbidden=0`. Это и есть ожидаемое поведение guard'а.
2. **Скан секретов поймал собственный тестовый файл.** `tools/test_no_secrets.py`
   содержал буквальные ключи в фикстурах → скан помечал их. Фикстуры переписаны так,
   что собираются из частей (`"sk-" + "a" * 24`), и скан видит чистый файл. Теперь
   `tools/test_no_secrets.py` проходит собственный скан наравне с остальными.

---

## 7. Что осталось непроверенным

| Проверка | Состояние | Что делать |
|---|---|---|
| Реальный прогон GitHub Actions | **Проверено** на PR #62: контрактный workflow, координация, scope guard, backend-тесты, TS, сборка Vite, медиа-тесты | Дождаться финального зелёного прогона после правки фронтенд-job |
| `backend-media` на ubuntu-latest | **Проверено**: шаг `Media and QC tests` зелёный на реальном runner'е с FFmpeg из apt | Джоб переведён в блокирующий. Известный риск: при обновлении образа ubuntu версия FFmpeg может измениться и ожидания по точным свойствам медиа могут поехать — откат = одна строка `continue-on-error: true` |
| Path-фильтры в реальном Actions | **Проверено в обе стороны**: PR без backend/frontend-правок → тяжёлый workflow не запустился; PR с `backend/CI.md` → запустился | Codex может повторить на отдельном PR |
| Обязательные checks в branch protection | **Не менялось** — запрещено без отдельного решения владельца (D7) | Отдельное решение владельца |
| Аудит `permissions` и команд в журнале Actions | Требует доступа к GitHub | В задаче Codex |

---

## 8. Риски, которые остаются

1. **Медиа-джоб стал блокирующим.** Он переведён в блокирующий после зелёного
   прогона на реальном runner'е, но остаётся самым чувствительным к окружению:
   ожидания сравнивают точные свойства медиа. При обновлении образа ubuntu версия
   FFmpeg может измениться. Откат — одна строка `continue-on-error: true` в
   `studio-offline-ci.yml`; контрактный чекер немедленно это отметит.
2. **PyYAML вне lock-файла.** Единственная зависимость, добавленная в CI. Если
   владелец хочет единый источник зависимостей — её надо внести в отдельный
   `requirements-ci.txt`; сейчас она закреплена прямо в workflow.
3. **Гонка с параллельными GA-задачами.** Манифест объявляет области `ga-01`…`ga-05`
   по бэклогу и по фактическим diff'ам уже идущих веток. Если задача выйдет за
   объявленную область (например, GA-02 потребует ещё `backend/main.py`), её PR
   станет красным. Это правильное поведение, но владельцу нужно знать: расширение
   области = правка `tools/minimax_task_scopes.json` в отдельном PR, а не в том же.
4. **Покрытие backend ограничено одним PR-диффом.** `backend-unit` гоняет весь
   `backend/`, но набор модулей вычисляется в рантайме (glob), поэтому новый тест
   подхватывается автоматически. Исключены ровно два: `test_media_qc.py`,
   `test_n35_freeze.py` — они требуют FFmpeg и живут в отдельном джобе.
5. **Полное принятие выпуска не покрыто.** Никакой job не проверяет мастер-релиз,
   QC мастера и решение владельца. Это отдельная задача (GA-03) и её нельзя
   выдавать за покрытую.
6. **Скан секретов смотрит только добавленные строки.** Уже лежащие в репозитории
   секреты повторно не ловятся — это осознанно, иначе каждый PR был бы красным.
   См. §9.
7. **`.gitignore` изменён.** Строка `tools/` молча исключала новые исходники
   `tools/*.py` и манифест — без её правки новые инструменты CI невозможно было бы
   закоммитить обычным `git add`. Правка локальна по смыслу: `tools/downloads/` и
   `tools/ffmpeg/` остались исключены, а `tools/*.py` теперь отслеживаются. Но это
   общий файл — владельцу стоит подтвердить, что исключение `tools/` не было
   намеренным и более широким.
8. **Фикстуры в тестах сканера собираются из частей.** Это вынужденно: иначе скан
   находит секреты в собственном тестовом файле и красный CI возникает на первом же
   PR. Побочный эффект — читаемость фикстур чуть ниже; альтернатива (allowlist
   путей в сканере) ослабила бы саму проверку.
9. **Фронтенд-тесты зависят от Python.** `frontend/directorState.test.mjs` вызывает
   backend-модули напрямую, поэтому job `frontend-unit` ставит Python и
   backend-зависимости. Локально это проходило случайно: Python с `fastapi` находился
   в PATH от соседнего проекта. Теперь зависимость явная — через `STUDIO_PYTHON`.
10. **Workflow проверки остаётся под контролем PR.** Файл
    `.github/workflows/agent-scope-guard.yml` на `pull_request` берётся из merge-коммита
    PR, поэтому PR может его переписать. Внутри репозитория это не закрывается:
    изменение control-файлов обнаруживается (`CONTROL_FILE_CHANGE`), но если шаг с
    доверенным кодом вырезан, проверка не запустится вовсе. Закрывает это только
    branch protection владельца: обязательный check `check-agent-scope` (check, который
    не отчитался, блокирует merge) и `CODEOWNERS` на `.github/workflows/`. См. §5.
11. **Bootstrap-PR не защищён CI.** PR, который сам вводит guard, судить себя
    доверенным кодом не может: доверенного кода в base ещё нет. Такой PR проходит
    bootstrap-путь (собственное объявление + явный `SCOPE_BOOTSTRAP`) и требует
    ревью владельца и Codex. Это свойство любого «первого» внедрения, а не дефект
    реализации.

---

## 9. Найдено попутно: секреты в публичном репозитории

Скан по всему дереву (а не только по диффу) обнаружил **20 Google API-ключей
(`AIza…`) в `docs/official-prompts/`**:

| Файл | Ключей |
|---|---|
| `docs/official-prompts/banana-prompting.html` | 9 |
| `docs/official-prompts/banana21-model.html` | 9 |
| `docs/official-prompts/banana-framework.html` | 2 |

Репозиторий **публичный** (`gremoled77-droid/gremovod`, `visibility: PUBLIC`).
Ключи встроены в скопированные официальные страницы документации Google
(`devrel-devsite`/`gstatic`), то есть принадлежат документации Google, а не
проекту. Но это всё равно действующие ключи в публичном git-истории.

**Что предлагается (вне объёма GA-04, требует решения владельца):** ротировать
эти ключи у Google и вычистить их из истории. Чинить это в этом PR нельзя: GA-04 —
это CI, а переписывание истории и затрагивание `docs/official-prompts/` — отдельное
решение с отдельным ревью.

Именно поэтому скан в CI смотрит **только добавленные строки**: иначе каждый PR,
коснувшийся этих HTML, был бы красным по причине, заведомо не связанной с PR.

---

## 10. Что должен проверить Codex

1. **Diff workflow-файлов.** Права, триггеры, фильтры путей на триггере (не на
   job!), отсутствие `secrets.*`, отсутствие `pull_request_target` с checkout
   head-SHA, `timeout-minutes` у каждого job, отсутствие `continue-on-error` в
   `studio-offline-ci.yml`.
2. **Схема Actions, а не только YAML.** `tools/check_ci_contracts.py` сверяет ключи
   со схемой. Первая версия workflow падала именно из-за несуществующего ключа
   `paths` у job — это стоит проверить отдельно.
3. **Реальные job-логи** финального прогона: `backend-unit` (487 тестов),
   `backend-media`, `frontend-unit` (120), `frontend-typecheck-build`, `ci-contract`,
   `secret-scan`.
4. **Красный тест на реальном runner.** Прогнать сломанное утверждение в backend-
   и frontend-тесте и убедиться в красном check (в этом PR доказано на backend).
5. **Negative path-filter fixture.** На отдельном PR: правка `backend/main.py`,
   `backend/llm_guard.py`, `backend/character_voice.py`, `backend/spend_ledger.py` →
   тяжёлый workflow запускается; правка `frontend/src/**` → тоже (в текущей
   раскладке фильтр общий на backend и frontend, разделения по стеку нет); правка
   только `docs/**` → тяжёлый workflow не запускается, а `studio-ci-contract.yml`
   запускается.
6. **Scope guard на чужом пути.** Ветка `minimax/ga-04-*`, меняющая `frontend/src/App.tsx`
   или `canon/**`, обязана дать `CROSS_OWNER_CHANGE` и exit 1.
7. **Scope guard на `mavis/work` и `minimax/p0-*`** — должен остаться зелёным
   (`LEGACY_BRANCH_NOT_ENFORCED`), исторические PR не должны ломаться.
8. **Скан секретов.** Внести в PR ключ любого провайдера → красный `secret-scan`;
   проверить, что в выводе нет самого значения секрета.
9. **Манифест.** `common_deny` действительно блокирует `canon/`, `skills/`,
   `docs/specs/`, `AGENTS.md`, `CLAUDE.md`, `AGENT_BUILD_MANUAL.md`; область `ga-01`
   включает `backend/main.py`; область `ga-05` покрывает `.env.cloud.example` и
   `docs/CLOUD_DEPLOY.md`.
10. **Отсутствие платных вызовов.** Ни один job не должен дёргать платного
    провайдера, Studio на 8000/5173 или n8n cloud.
11. **Разделение по стеку.** Сейчас один path-фильтр покрывает и backend, и
    frontend: правка фронтенда запускает и backend-тесты. Это сознательный
    компромисс (проще и без рукописного фильтра по изменённым файлам). Если владелец
    хочет разделения — это отдельная правка, и её надо согласовать: job-level
    `paths` использовать нельзя.
12. **Доверенный валидатор.** Проверить, что вердикт выносит копия
    `tools/check_agent_scope.py` из base-ревизии, а не из PR. Проба: PR, который
    заменяет `tools/check_agent_scope.py` на `sys.exit(0)` и трогает запрещённый файл,
    обязан дать красный `check-agent-scope` с `CROSS_OWNER_CHANGE`. Проба на реальном
    Actions описана в §5 и в теле PR #62.
13. **Расхождение ветки и базы.** Валидатор сверяет `--branch`/`--base` с payload'ом
    события GitHub. Если в workflow передать чужую базу — ожидается `SCOPE_ERROR` и
    exit 2, а не зелёный вердикт.
14. **Bootstrap-путь.** Base-ревизия без доверенного интерфейса → явный
    `SCOPE_BOOTSTRAP` и запуск валидатора самого PR; такой PR требует ревью владельца.

---

## 11. Открытые вопросы владельцу

1. Включать ли `studio-offline-ci` в required checks (D7)? Обратить внимание: при
   required-check на уровне workflow path-фильтры ломают docs-only PR — поэтому
   фильтры и оформлены на уровне job.
2. Делать ли `backend-media` блокирующим после первого зелёного прогона на Linux?
3. Выносить ли `pyyaml==6.0.3` в отдельный `requirements-ci.txt`?
4. Кто и когда ротирует 20 Google-ключей из `docs/official-prompts/` и чистит историю?
5. Правильно ли объявлена область `ga-01` (включает `backend/main.py`)?
6. Оставлять ли `ga-02`…`ga-05` в манифесте до появления их веток?
7. **Какие checks сделать обязательными.** Внутри CI гарантия одна: вердикт выносит
   код из base-ревизии, поэтому PR не может расширить свою область, подменить
   валидатор или манифест. Остальное закрывает GitHub, и это отдельное решение
   владельца (сам не менял):

   | Что сделать | Зачем | Где |
   |---|---|---|
   | `check-agent-scope` → required status check на `mavis/work` | PR, вырезавший проверку, не отчитается → merge заблокирован | Branch protection rules → Required status checks |
   | `check-agent-scope` → required check на `mavis/work` **и** на `main` | то же для основной ветки | Branch protection rules |
   | `CODEOWNERS` на `.github/workflows/` | правка guard'а требует ревью владельца | `.github/CODEOWNERS` |
   | «Require review» + «Dismiss stale approvals» | правка guard'а не проходит по старому аппруву | Branch protection rules |
   | «Require status checks to pass before merging» | обязательные checks — условие merge | Branch protection rules |
   | правило «Do not allow bypassing the above settings» | админ не может в обход required checks | Branch protection rules |

   Имя check'а — `check-agent-scope` (job в `agent-scope-guard.yml`). Он появляется
   только на PR в ветки `build/claude/*`, `build/argon/*`, `codex/review-*`,
   `codex/spec-*`, `coordination/*`, `minimax/*`, `mavis/*` — из-за `if:` у job.
   **Для обычных документационных PR в `main` этот check не появляется**, поэтому
   ставить его required глобально опасно: merge начнёт ждать check'а, который не
   придёт никогда. Нужен либо required-check на уровне ruleset с «skip if the workflow
   is not triggered», либо узкий список веток, либо отдельный always-on workflow.
   Это решение владельца; сам я branch protection не менял.

   Более сильный вариант на будущее — repository ruleset с **required workflow** из
   отдельного репозитория: он выполняется из ветки по умолчанию и не может быть
   отключён PR'ом. Но для этого нужен отдельный репозиторий и решение владельца.
