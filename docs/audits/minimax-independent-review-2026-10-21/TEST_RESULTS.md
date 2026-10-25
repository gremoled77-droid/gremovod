# Результаты и воспроизведение offline-проверок

Версии тестирования зафиксированы в reviewed_refs.json. Во время публикации #58 обновился до `c634c0c915a1afbf3d75df5bc897f75ef5b723ea`; этот SHA не тестировался здесь. Runner по умолчанию продолжает воспроизводить проверенный `5c47ace...`, не подменяя его live branch HEAD.

## 1. Независимое исходное ревью

Все backend/SQLite/media проверки выполнялись на изолированных snapshot/temp данных. Ключи — синтетические; платных submit не было.

| Проверка | Реальный результат | Scope |
|---|---|---|
| GA-01 профильный pytest | **82 PASS**, 38.68s | test_llm_settlement, test_llm_guard, test_money_boundary, test_unified_budget, test_n8n_spend, test_budget_release |
| Новый авторский test_llm_settlement.py на HEAD #58 | Все **30** тестов входят в 82 | 9 LlmSettlement + 5 AgentsSettlement + 8 AgentsReconcile + 6 TaskSettlement + 2 UsageValidator |
| GA-04 tool pytest после настройки Git refs | **63 PASS, 7 subtests PASS**, 2.60s | ci_contracts/no_secrets/agent_scope/coordination |
| GA-05 remote_access pytest | **20 PASS**, 14.39s | bare ASGI/Host/Origin/cookie/proxy fixtures |
| Combined GA-04+GA-01+GA-05, весь backend | **530 PASS, 26 subtests PASS**, 219.78s | exact reviewed snapshots; fresh temporary SQLite; media/FFmpeg tests included |
| diff --check всех четырёх исходных PR | Exit 0 | реальные base...head |
| Дополнительные независимые пробы | Находки воспроизведены | source scripts и структурированные наблюдения сохранены здесь |

82 и 20 — подмножества combined 530; повторные прогоны не прибавляются к уникальным тестам. Старые числа MiniMax 20 новых/506 full backend и 62 tools не выдаются за текущие результаты. Первоначальный архивный GA-04 запуск не имел origin/mavis/work: 62 PASS + 1 infrastructure error; после отдельного git checkout/ref получено 63 PASS.

Среда исходного ревью: Windows, Python 3.13.14, Uvicorn 0.54.0, FastAPI 0.143.1, Pydantic 2.14.1, pytest 9.1.1, Node 24.16.0; доступный FFmpeg/ffprobe. Новые зависимости не устанавливались. Существующий venv использовался только как интерпретатор/библиотеки, без записи рабочих данных Studio.

## 2. GitHub CI на точном GA-04 SHA

HEAD `08213fdc271dcef7f203e7cedb866b2588e55257`: все восемь jobs success, полные логи прочитаны.

| Run | Job | Подтверждение |
|---|---|---|
| [39600260621](https://github.com/gremoled77-droid/gremovod/actions/runs/39600260621) | 119222660585 backend-unit | 455 tests OK |
| тот же | 119222661186 backend-media | 32 tests OK |
| тот же | 119222660987 frontend-unit | 120 tests / 120 pass |
| тот же | 119222661213 frontend-typecheck-build | tsc --noEmit и Vite build success |
| [39600260691](https://github.com/gremoled77-droid/gremovod/actions/runs/39600260691) | 119222661463 ci-contract | CI_CONTRACT OK; 63 tests OK |
| тот же | 119222661670 secret-scan | SECRET_SCAN OK |
| [39600260706](https://github.com/gremoled77-droid/gremovod/actions/runs/39600260706) | 119222661259 scope | bootstrap; changed=14, forbidden=0 |
| [39600260836](https://github.com/gremoled77-droid/gremovod/actions/runs/39600260836) | 119222660810 coordination | 32 tests OK |

На exact heads #58, #63, #64 — только skipped scope-check, полного GitHub CI нет. Старые deliberate-failure Actions из MiniMax handoff заново не запускались и отдельно не приняты по локальному рассказу. Данная публикационная ветка основана на mavis/work и не включает GA-04 workflow: её собственный статус CI не является повтором восьми jobs GA-04.

CI success и branch protection — разные факты. Required checks/D7 не утверждены, effective settings в этом ревью не подтверждены.

## 3. Проверка опубликованного тестового пакета

Три сохранённых reproduce-скрипта повторно выполнены через новый временный runner на точных SHA: каждый exit 0, ошибки воспроизведены. SHA-256 исходных файлов/логов находятся в evidence; production runtime не менялся.

При подготовке публикации через упакованный runner заново выполнен ga01 --existing: **82 PASS**, 40.08s, exit 0. Это повтор исходного subset, а не ещё 82 уникальных теста. В reproduce-фикстурах нормализованы только безопасные синтетические литералы для отсутствия ложных secret-scan срабатываний: пароль взят из уже разрешённого offline fixture, fake secret assignment собирается из именованного синтетического значения. Все сценарии сохранены, runtime не менялся.

Семнадцать новых contract tests утверждают **безопасное поведение**, поэтому текущие reviewed heads остаются красными:

| Target | Методов | Результат на reviewed head |
|---|---:|---|
| ga01 | 8 | 1 PASS, 4 failures, 3 errors; exit 1 |
| ga04 | 4 | 2 PASS; 2 метода с ошибочными условиями дают 3 failure records из-за subtests; exit 1 |
| ga05 | 5 | 5 методов дают 7 failure records из-за subtests; exit 1 |

Errors GA-01 — наблюдаемые TypeError миграции/nonfinite и NameError настоящего GA-02 prepare. Это диагностические regression results, не ошибка установки зависимостей. GA-02 case обозначен отдельно в имени и не объявляет Task API частью завершённого GA-01.

Первая упаковочная проверка выявила Windows cleanup issue в новом runner: нельзя удалить текущий cwd внутри TemporaryDirectory. Исправлено только в тестовом runner (возврат cwd перед cleanup), затем все шесть запусков reproduce/contracts повторены. Ошибка не относится к приложению и не скрыта в финальных числах.

## 4. Запуск в отдельном checkout

Требуются Git, Python 3.13 с существующими pinned backend dependencies; pytest для --existing и PyYAML для ga04. Никаких real credentials или запущенной Studio не требуется. Не использовать production checkout; клонировать опубликованную audit-ветку в отдельный каталог.

Из отдельного checkout сначала получить объекты проверенных PR (не обновляет существующие ветки MiniMax):

```powershell
git fetch --no-tags origin refs/pull/58/head refs/pull/62/head refs/pull/63/head refs/pull/64/head
$py = 'C:\path\to\existing-review-venv\Scripts\python.exe'
$runner = 'docs/audits/minimax-independent-review-2026-10-21/tests/run_offline.py'
& $py -X utf8 $runner ga01 --reproduce
& $py -X utf8 $runner ga04 --reproduce
& $py -X utf8 $runner ga05 --reproduce
```

Reproduce = characterization исходных ошибок. Exit 0 не является продуктовым PASS. На исправленном SHA эти исторические assertions могут перестать выполняться — использовать contract mode:

```powershell
& $py -X utf8 $runner ga01
& $py -X utf8 $runner ga04
& $py -X utf8 $runner ga05
# После отдельного fetch нового candidate SHA:
& $py -X utf8 $runner ga01 --ref '<полный-40-символьный-SHA>'
```

--ref не скачивает ничего и не переключает checkout: принимает только полный SHA уже доступного commit. Указанный код всё равно должен быть предварительно просмотрен; runner не является sandbox для произвольного вредоносного candidate.

Нужный subset существующих тестов и весь совместный backend:

```powershell
& $py -X utf8 $runner ga01 --existing
& $py -X utf8 $runner ga05 --existing
& $py -X utf8 $runner combined --existing
```

Для 63 existing GA-04 tests необходим настоящий отдельный Git checkout HEAD #62 и `origin/mavis/work` на base SHA: repository-diff scanner намеренно не работает на tar-архиве. В этом checkout установить временный STUDIO_DATA_DIR и выполнить:

```powershell
& $py -X utf8 -m pytest tools/test_ci_contracts.py tools/test_no_secrets.py tools/test_agent_scope.py tools/test_agent_coordination.py -q
```

Runner combined извлекает GA-04 и накладывает только непересекающиеся изменения GA-01/GA-05 из Git objects. Нет git merge, веток с production/runtime fixes или соединения с пользовательской БД. Python network audit hook блокирует внешние socket.connect текущего процесса; локальные asyncio socketpair разрешены. Это не OS-level firewall и не распространяется автоматически на любой будущий subprocess. Изученные subprocess в фикстурах — только локальный Git.

Особенности повторной приёмки: GA04 adversarial test сейчас вызывает текущий CLI workflow. После исправления trusted entrypoint тест должен запускать новую реальную границу; не объявлять замену теста на вызов head-script доказательством защиты. Ga05 stack tests читают JSON CMD Dockerfile и эмулируют его proxy middleware; это не живой Docker/Caddy E2E. Ga03 N1–N15 остаются планом до реализации gate.

## 5. Непроверенное

Browser/mobile E2E, живой Caddy/network isolation, настоящий CapCut/MP4/human review, production migrations/backup/restore, live n8n и billing провайдеров не выполнялись. Локальный frontend build в исходном ревью не повторялся — проверены GitHub logs. Полные локальные журналы не публикуются; опубликованы проверяемые сводки и SHA-256. Никаких действительных credentials или session tokens в evidence не переносить.

Официальные документы, сверенные через Context7 в исходном ревью: [GitHub pull_request workflow trust](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target), [skipped workflows](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/skip-workflow-runs), [Uvicorn settings](https://github.com/kludex/uvicorn/blob/main/docs/settings.md). Локальная проба Uvicorn использовала фактически установленную версию 0.54.0, а не только документацию main.
