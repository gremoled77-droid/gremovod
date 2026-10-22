# Claude Code — проверка установки FFmpeg на runner ( CC-CI-VERIFY-01 )

Статус: **PASS исполнителя** (не независимая приёмка). Один известный красный check —
scope guard, см. «Открыто». Модель: Claude Opus 5.5, effort high.

- Ветка: `build/claude/ci-media-verify-20261022`, Draft PR #94, stacked на #92.
- База: #92 `claude/ffmpeg-ci-timeout-fix-31ceac` @ `92ded3695a1e365b436d1f28a3fcf0719c5e5b77`.
  Пины на 22.10.2026 сверены с origin: `mavis/work` @ `57cac59c…`, #75
  `mavis/ci-final-2026-10-22` @ `bfb57631…`, #92 @ `92ded369…` — совпадают.
- Worktree: `C:/Users/BLOWKA/ci-media-verify`. Ветки #92, #75, MiniMax и корень не трогались.

## Что изменено

| Файл | Правка |
|---|---|
| `.github/workflows/studio-offline-ci.yml` | `paths` у `pull_request` и `push` включает сам `studio-offline-ci.yml`; таймауты apt перенесены в `env` шага; `timeout-minutes` шага 8 → 10; пауза только между попытками; новый шаг `ffmpeg/ffprobe -version` |
| `tools/check_ci_contracts.py` | контракт: path-filter `pull_request` обязан покрывать `.github/workflows/studio-offline-ci.yml` |
| `tools/test_ci_contracts.py` | тест триггера (отрицательный и положительный); `FfmpegInstallStepTests`: шаг установки с подставным `sudo`; проверка бюджета времени |

Не добавлено: `continue-on-error`, `pull_request_target`, секреты, пропуск медиа-тестов.

## Бюджет времени

На #92 худший случай: 3 × (150 + 150) + 3 × 10 = 930 с при лимите шага 480 с,
то есть третья попытка не помещалась, а при зависании и вторая не доходила до конца.
Теперь: 3 × (60 update + 120 install) + 2 × 10 пауза = **560 с ≤ 600 с** (`timeout-minutes: 10`).
Это проверяет `test_every_attempt_fits_in_the_step_timeout`, числа он берёт из `env` шага.
Лимит джобы 20 мин: в реальном прогоне шаг установки занял ~17 с, вся джоба 40 с.

## Тесты шага установки (подставные команды, без apt и sudo)

Тест берёт `run` шага из YAML и запускает его в `bash --noprofile --norc -eo pipefail`
(те же флаги, что у GitHub). Первым в `PATH` стоит подставной `sudo`: он только пишет
вызов в журнал и разыгрывает сценарий. `timeout` настоящий (coreutils). На Windows
выполняется только Git Bash; лаунчер WSL из `System32` пропускается.

| Сценарий | Ожидание | Результат |
|---|---|---|
| успех с первой попытки | код 0, 1 update + 1 install, без warning | ok |
| update падает 1 раз | код 0, 2 update + 1 install, `::warning::apt attempt 1 of 3` | ok |
| install падает всегда | код ≠ 0, 3 + 3 вызова, `::error::…after 3 attempts` | ok |
| update висит 30 с, таймаут 1 с | код ≠ 0, 3 update, 0 install, всё за < 30 с | ok |

## Red / green

Команды (из корня worktree):

```bash
python tools/check_ci_contracts.py
python -X utf8 -m unittest tools.test_ci_contracts tools.test_no_secrets tools.test_agent_scope tools.test_agent_coordination
```

- **Red** — новые тесты и контракт на workflow из #92 (Windows, Git Bash):
  `check_ci_contracts.py` → `CI_CONTRACT: FAILED`, код 1:
  `the pull_request path filter does not cover '.github/workflows/studio-offline-ci.yml'`.
  `tools.test_ci_contracts`: 34 теста, failures=2, errors=1 — `test_candidate_workflow_keeps_its_contract`
  (триггер), `test_a_hanging_apt_is_cut_by_the_timeout…` (захардкоженные 150 с не режут зависание),
  `test_every_attempt_fits_in_the_step_timeout` (нет бюджета в `env`; 930 > 480).
- **Green** — после правки: `CI_CONTRACT: OK`; 91 тест tools — OK (локально);
  на runner `CI contracts and tool tests` — OK, все 5 `FfmpegInstallStepTests` выполнены, не skipped.

## Реальные прогоны GitHub Actions, HEAD `ae801bbf63c251d95119c874d932f0faddf55013`

| Workflow | Run | Итог |
|---|---|---|
| GremoVOD Studio offline CI | [39851415581](https://github.com/gremoled77-droid/gremovod/actions/runs/39851415581) | success |
| ↳ Backend media and QC tests | [job 120078315327](https://github.com/gremoled77-droid/gremovod/actions/runs/39851415581/job/120078315327) | success, 40 с |
| ↳ Backend unit tests | job 120078315218 | success |
| ↳ Frontend unit tests | job 120078315380 | success |
| ↳ Frontend TypeScript and production build | job 120078315940 | success |
| GremoVOD CI contracts | [39851415498](https://github.com/gremoled77-droid/gremovod/actions/runs/39851415498) | success (contracts, secrets, claude-hooks) |
| Agent handoff and workflow export checks | 39851415399 | success |
| Agent ownership boundaries (new task branches) | [39851415430](https://github.com/gremoled77-droid/gremovod/actions/runs/39851415430) | **failure** — см. ниже |

Лог media-job: установка с первой попытки, без `::warning::apt`; `/usr/bin/ffmpeg`, `/usr/bin/ffprobe`,
`ffmpeg version 6.1.1-3ubuntu5`, `ffprobe version 6.1.1-3ubuntu5`;
`backend.test_media_qc backend.test_n35_freeze` — `Ran 32 tests … OK`.
Сам запуск этого workflow на PR, в котором из его путей изменён только он сам, и есть
доказательство, что триггер исправлен (на #92 этот workflow не запускался).

`gh run list` подписывает run путём файла: workflow ещё нет в default branch. API отдаёт
`name: GremoVOD Studio offline CI`.

Коммит с этим handoff меняет только `docs/`, но path filter у `pull_request` смотрит на весь
diff PR, поэтому offline CI запускается ещё раз уже на финальном HEAD. Ссылка на этот прогон —
в комментарии к PR #94.

## Открыто

- **Scope guard красный**: `CROSS_OWNER_CHANGE: .github/workflows/studio-offline-ci.yml`
  (у роли `claude` нет прав на `.github/workflows/`). В задании workflow назван shared/controlled
  областью именно этого задания; manifest менять запрещено. Нужно решение координатора/владельца:
  принять handoff или выдать область в manifest. Обходить guard не стал.
- Не проверено: реальный отказ apt на runner и срабатывание `timeout-minutes` самого Actions
  (покрыто только арифметикой бюджета и подставными командами).
- Риск: если `timeout` убьёт `apt-get install` в середине dpkg, следующая попытка может упасть
  на `dpkg was interrupted`. Тогда шаг честно красный, но повтор не помогает. `dpkg --configure -a`
  не добавлял — это вне задания.
- Локально не запускались backend pytest и frontend (продуктовый код не менялся; на runner зелёные).
- Независимый review и приёмка владельцем — не проводились. STATUS.md не трогал (за координатором).
  GA-02 не начинал. Merge, платных вызовов, Studio на 8000/5173 не было.
