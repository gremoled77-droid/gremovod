# Независимая приёмка и повторная проверка

**PARTIAL.** Кодовая база: `57cac59ca790d380d8e68f2f6db82674ca142e92`. Среда: Windows, Python 3.13.14, Node 24.16.0; fastapi 0.143.1, starlette 1.8.0, httpx 0.28.1, pydantic 2.14.1, Pillow 12.3.0. Использованы существующие зависимости, установки не было.

## Текущие результаты — только этот аудит

| Проверка | Результат | Предел доказательства |
|---|---|---|
| Backend full loader: 58 test modules / 487 test IDs | первый рабочий прогон: 457 PASS, 0 assertion failures, 30 environment errors, 188.982 s | audit hook блокировал subprocess из-за Windows argv representation; один тест требует DNS |
| Повтор 29 media/FFmpeg test IDs | 29 PASS, 0 fail/error, 31.736 s | разрешены только ffmpeg/ffprobe, сеть/production DB всё ещё запрещены |
| Итог backend по объединению ID | **486 PASS / 1 BLOCKED**, уникальных IDs загружено 487 | не заявляется 487 зелёных и не суммируются повторные тесты |
| Единственный BLOCKED | test_smoke.StudioSmokeTests.test_downloads_reject_private_network_and_invalid_images | audit hook запретил socket.getaddrinfo; продуктовый дефект из этого не выводится |
| Frontend npm-equivalent node test | **120 PASS / 0 fail**, 9.406 s | во временной копии с существующими node_modules и STUDIO_PYTHON; pure unit/bundled state tests |
| TypeScript | tsc --noEmit, exit 0 | не browser QA |
| Production frontend build | Vite build --configLoader runner, exit 0, 8.13 s | config runner обошёл filesystem denial esbuild default-loader; bundle warning >500 KB, не blocker |
| Coordination/scope | 14 PASS | механические contracts, не процесс утверждения человеком |
| Node P0 + QA aggregator | 23 PASS (7 SQLite wrappers + 16 aggregator cases) | 7 backend-тестов здесь повторяются; к 486 не прибавлялись |
| Browser E2E / console | **NOT_RUN** | audit clone не запускался как сайт, чужие 8000/5173 не трогались |
| CapCut import/render | **NOT_RUN** | нет выбранного пилотного проекта и ручного действия в CapCut |
| Live n8n state/worker | **NOT_RUN** | только source exports/manifests/runbooks; никакой cloud mutation |
| Paid APIs/current real prices | **NOT_RUN** | прямой запрет задания; registry parity не равна provider billing |
| Real production DB / backup restore | **NOT_RUN** | реальные SQLite не открывались и миграции не запускались |
| Реальный пилот/канон/права/художественная приёмка | **NOT_RUN** | нет выбранного владельцем acceptance-snapshot |

Первичные неудачи стенда: unittest top_level_dir требовал importable package, затем отсутствовал cwd в sys.path; результаты этих запусков отброшены. Полный запрет sockets сначала мешал Windows asyncio socketpair; допущено только создание локального служебного socketpair стандартной библиотекой, внешние подключения по-прежнему блокировались. Frontend без deps дал module-not-found; после временного подключения существующих deps и копирования backend catalogue tsc/build прошли. Единственный оставшийся frontend esbuild filesystem-denial исчез при повторе вне sandbox; исходники тестов не менялись. Эти проблемы не включены в P0/P1/P2 приложения.

## Контрольные отрицательные пробы

| Проба на временной базе | Наблюдение |
|---|---|
| POST /api/llm/tasks, настоящий lifecycle без helper patches | NameError: task_identity is not defined |
| Та же подготовка с временным helper stub, synthetic signed permit; execute | OperationalError: llm_calls has 11 columns but 10 values were supplied; provider call count 0 |
| Task handler после синтетического корректного reserve и in-memory helper/reserve stubs; TimeoutError | status=failed, usd=0.0, estimated_usd=0.1; **условный** путь, не сквозное исполнение через сломанный API |
| Agents run, три mock success без usage | HTTP 200; 3 calls; estimate=0.000843; cost_usd=0.0 |
| Chat, mock usage(-1000000,-1000000) | HTTP 200; cost_usd=-0.14 |
| Remote login, 7 неверных паролей с разным XFF | [401,401,401,401,401,401,401] |

Не делались изменения функций на диске: для обхода предварительных поломок в двух диагностических пробах использован только unittest.mock в отдельном процессе. Пробы не являются реализацией исправлений. В task-repro нельзя скрывать эти предусловия.

## Как воспроизвести безопасный backend-прогон

Только в **отдельной копии** фиксированного SHA. Запуск из её корня через существующий Python, `-X utf8 -B`; scratch под системным TEMP. Не запускать обычный suite на production DB и не наследовать provider keys.

Аудит использовал следующий принцип runner (сохранить во временный файл, не в backend). Он создаёт данные только в clone/TEMP и блокирует реальные соединения. На Windows аргументы subprocess из audit event приходят строкой, что учтено ниже.

```python
import os, sys, pathlib, tempfile, unittest, shlex
root = pathlib.Path.cwd().resolve()
sys.path.insert(0, str(root))
scratch = pathlib.Path(tempfile.mkdtemp(prefix="gremovod-audit-"))
temp = pathlib.Path(tempfile.gettempdir()).resolve()
os.environ["STUDIO_DATA_DIR"] = str(scratch / "studio")
for key in list(os.environ):
    if any(x in key.upper() for x in (
        "API_KEY", "SERVICE_TOKENS", "SIGNING_KEY",
        "STUDIO_REMOTE", "STUDIO_PUBLIC"
    )):
        os.environ.pop(key, None)

def safe(value):
    if value is None or isinstance(value, int):
        return True
    p = pathlib.Path(os.fsdecode(value)).resolve()
    return any(p == a or a in p.parents for a in (root, temp))

def audit(event, args):
    if event == "socket.getaddrinfo":
        raise RuntimeError("AUDIT network disabled")
    if event == "socket.connect":
        caller = sys._getframe(1)
        if (caller.f_code.co_name != "_fallback_socketpair"
                or pathlib.Path(caller.f_code.co_filename).name != "socket.py"):
            raise RuntimeError("AUDIT network disabled")
    if (event == "sqlite3.connect" and args[0] not in (":memory:", "")
            and not safe(args[0])):
        raise RuntimeError("AUDIT production DB denied")
    if event == "open" and isinstance(args[0], (str, bytes)) and not safe(args[0]):
        name, mode, flags = args
        if ((mode and any(c in mode for c in "wax+"))
                or (flags and flags & (
                    os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))):
            raise RuntimeError("AUDIT write denied")
        leaf = os.path.basename(os.fsdecode(name)).lower()
        if leaf.startswith(".env") or leaf.endswith("_api_key.txt") or leaf == "mini.env":
            raise RuntimeError("AUDIT credential read denied")
    if event in ("os.remove", "os.rmdir", "os.mkdir") and not safe(args[0]):
        raise RuntimeError("AUDIT mutation denied")
    if event in ("os.rename", "os.replace") and not (safe(args[0]) and safe(args[1])):
        raise RuntimeError("AUDIT move denied")
    if event == "subprocess.Popen":
        argv = args[1]
        first = argv[0] if isinstance(argv, (list, tuple)) else shlex.split(argv, posix=False)[0].strip('"')
        exe = os.path.basename(str(args[0] or first)).lower()
        if exe not in ("ffmpeg", "ffmpeg.exe", "ffprobe", "ffprobe.exe"):
            raise RuntimeError("AUDIT subprocess denied")

sys.addaudithook(audit)
names = ["backend." + p.stem for p in sorted(pathlib.Path("backend").glob("test_*.py"))]
result = unittest.TextTestRunner(verbosity=2).run(
    unittest.defaultTestLoader.loadTestsFromNames(names))
raise SystemExit(not result.wasSuccessful())
```

Один DNS-зависимый тест этим runner намеренно блокируется; разрешение внешнего DNS ради зелёного результата не выдавалось. Для отдельного targeted retest использовать исходные test IDs из error summary, сохраняя тот же audit hook.

Frontend повторялся в TEMP-копии frontend + backend, с junction node_modules на уже установленную папку mavis frontend (без npm ci), `STUDIO_PYTHON=C:/AI_Workflow_Studio/.venv/Scripts/python.exe`. Команды: `node --experimental-strip-types --test`, `tsc --noEmit`, `vite build --configLoader runner`. Поэтому это проверка текущего источника с доступными локальными dependencies, не воспроизводимость чистой lockfile-install.

Контракты: `python -m unittest tools.test_agent_coordination tools.test_agent_scope`, `node --test tests/test_p0_state.js integrations/n8n/tests/qa-orchestrator-aggregator.test.mjs` (Python для Node wrappers доступен через PATH).

## Локальные полные журналы и SHA-256

Полные журналы сохранены в системном TEMP машины этого аудита, не в GitHub: не гарантируется долговременное хранение. Ниже контрольные суммы и результаты позволяют идентифицировать конкретные прогоны; для независимой приёмки их надо выполнить заново. Огромные старые логи не копируются в отчёт.

| Файл в %TEMP% | Байтов | SHA-256 |
|---|---|---|
| `gremovod-acceptance-tests-20261021.txt` | 174140 | `c399f905a867384a3364234002ed5c202bd8549048dcc8157cd0428904ed5f17` |
| `gremovod-acceptance-retest-20261021.txt` | 4206 | `91575fd851b18916ee52546aa6d38fda562e7ee0380a97181feb9b8ddc0d6bcb` |
| `gremovod-frontend-elevated-20261021.txt` | 12742 | `3f81dce6e3471dde05de2034801f66b19a87109238db3a4099401c52d7616a2d` |
| `gremovod-tsc-final-20261021.txt` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `gremovod-build-final-20261021.txt` | 1200 | `7d19e56b4a11a26f4675d2d79c53e5049887bee04b02f2955c8172fc831105c3` |
| `gremovod-coordination-20261021.txt` | 2098 | `9728c99527e6fd4b16f7f16de6a0d0dbe0128147991330da11b015a74298b3f9` |
| `gremovod-node-contracts-20261021.txt` | 2270 | `1840a82232c7e7fce9478c9b894791e06378f1c0539259f036997e3b28d93341` |

## Приёмка исправлений MiniMax

1. До тестов: взять PR head SHA; проверить diff against согласованной базы и allowlist из GA-задачи. Вне scope или чужой dirty файл → отдельное выяснение, без auto-merge.
2. GA-01: повторить missing/negative usage и partial-agent-run, inspect ledger до/после. UNKNOWN не освобождается, подтверждённый факт учитывается полностью и один раз. Цена не может стать отрицательной.
3. GA-02: полный реальный task endpoint lifecycle без helper/reserve patches. Проверить duplicate request_id, changed spec/revision, permit expiry, concurrency, startup schema и reopened DB; mock provider count ≤1.
4. GA-03: upload без QC/approval не является verified release; FAIL/BLOCKED/stale hash не дают approval. Синтетический MP4 проходит N34 и выбранное owner-решение; исходник не переписывается.
5. GA-04: Actions на точном candidate SHA, frontend+backend и отрицательный fixture scope guard; список required checks отдельно сверить с владельцем settings.
6. GA-05: changing XFF от недоверенного peer не обходит лимит, trusted proxy contract явно проверен; Host/Origin/session regressions остаются.
7. После адресных tests один раз выполнить совместный offline regression и frontend build. Не гонять их бесконечно без новых изменений.
8. Пройти один бесплатный browser E2E на отдельном стенде с собственным STUDIO_DATA_DIR: project→canon refs→Producer mock→manual StoryPlan preview/apply→board→mock media→audio import→edit-list→master import→N34→owner decision. Capture exact SHA, screen/console/API и ошибки.
9. На настоящем выбранном master: CapCut import/render, ffprobe/full decode, звук/паузы/синхронность, frame/canon/rights review, restore копии проекта и hashes. Не применять миграции к исходной рабочей базе.
10. Только после принятия денежных границ и отдельного разрешения владельца — один конкретный paid smoke с известными provider/model/request hash/ценой/потолком. После unknown не повторять submit.

## Точная точка продолжения PARTIAL

Начать с review/исправления **GA-01**, затем GA-02, если D2 оставляет task API в бете. Исходная база `57cac59`; незакоммиченные локальные helpers сверить отдельно, не переносить автоматически. Принять D1–D5, затем выполнить пункты 8–10 выше в разрешённом объёме.

Не завершено: полная семантическая дедупликация всех веток, browser usability/console, реальный пилот/CapCut, live n8n worker transport/skills, effective branch protection, production backup/restore и provider billing. Это обязательные явные ограничения текущего акта.

После сохранения/публикации этого аудита работа останавливается. Кодовые исправления, интеграция, запуск новых агентов, paid smoke и merge не начинаются автоматически.
