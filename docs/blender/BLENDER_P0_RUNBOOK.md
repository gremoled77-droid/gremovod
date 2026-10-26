# P0: offline runbook

Состояние 26.10.2026: контракты и offline-проверки работают; render pipeline не принят.
G1 запрещает Blender/MCP execution до подтверждённой среды без секретов. Ни один
флаг текущего CLI не открывает этот gate. Нужны отдельная среда **и** реализация
проверенного isolated launcher; одного JSON receipt недостаточно.

## Подготовка

Работать в `.worktrees/codex-blender-p0`, ветка `codex/blender-integration-p0-20261026`.
Проверить `git status --short`, `git branch --show-current`, `git rev-parse HEAD`.
Для воспроизведения на чистом checkout создать собственный venv и установить
`requirements-blender-test.txt`. В этой сессии venv использует system-site-packages
существующего проектного Python; это не доказывает воспроизводимость чистой среды.

```powershell
$Python = '.\.venv\Scripts\python.exe'
& $Python -m pytest -q --basetemp .pytest-blender-final `
  tests/test_blender_manifests.py tests/test_blender_preflight.py `
  tests/test_blender_runner_security.py tests/test_blender_reference_binding.py `
  tests/test_blender_qc.py tests/test_blender_skill_install.py
```

Создать только JSON fixtures; геометрии, медиа и канонического master здесь нет:

```powershell
@'
import json
from pathlib import Path
from scripts.blender.example_manifests import examples
from scripts.blender.validate_manifests import validate
root = Path('runtime/blender-offline')
root.mkdir(parents=True, exist_ok=True)
stage, shot = examples()
for name, value in [('stage', stage), ('shot', shot)]:
    (root / (name + '.json')).write_text(json.dumps(value), encoding='utf-8')
portrait = dict(shot, aspect='9:16', resolution=[540,960])
validate(portrait, stage=stage)
(root / 'shot-portrait.json').write_text(json.dumps(portrait), encoding='utf-8')
'@ | & $Python -
& $Python scripts/blender/validate_manifests.py runtime/blender-offline/shot.json `
  --stage runtime/blender-offline/stage.json
```

`asset_bytes_verified=false` ожидаем для fixtures: их hash — пример контракта,
не SHA существующего `.blend`. Для настоящего asset caller передаёт валидатору
trusted registry mapping из существующего owner lookup, `owner` и `data_root`.
В CLI lookup отсутствует; произвольный JSON не создаёт права доступа.

```powershell
$Blender = 'C:\AI_Workflow_Studio\tools\blender\blender-4.5.15-windows-x64\blender.exe'
& $Python scripts/blender/run_preflight.py --blender $Blender `
  --output runtime/blender-offline/preflight.json
& $Python scripts/blender/render_shot.py --blender $Blender `
  --stage runtime/blender-offline/stage.json --manifest runtime/blender-offline/shot.json `
  --data-root runtime/blender-offline/data --attempt-id offline-01
& $Python scripts/blender/benchmark_render.py --output runtime/blender-offline/benchmark.json
```

Preflight/benchmark exit 0 означает, что **создан отчёт**, а не принят Blender.
Render planner exit 2 означает BLOCKED/INVALID_INPUT; он не создаёт attempt и не
вызывает subprocess. Путь attempt вычисляется через `production_folders.checked_path`.
В runtime нет доступа к рабочей SQLite или запуска backend/frontend.

## Что нужно добавить перед реальным рендером

1. Проверенная VM/учётная запись без owner-проектов, ключей и credential mounts;
   ограниченный network/filesystem, подтверждение отказа доступа к запрещённым путям.
2. Launcher с pin SHA executable/source, реальным timeout, ограничением памяти,
   диска и дерева дочерних процессов. `bounded_process` сейчас лишь отдельный
   mock-tested primitive: timeout 120 секунд, shell=False, stdio DEVNULL.
   Он не подключён к CLI и не реализует OS sandbox или disk/memory limits.
3. Review `scene_build.py` для Blender 4.5.15: env report → один диагностический PNG →
   сохранение/reopen `.blend` → first/mid/last в обеих ориентациях. Source подготовлен,
   но **не исполнялся**. Нельзя выдавать `py_compile` за совместимость Blender API.
4. Создание immutable master и отдельной копии на attempt, SHA до/после, snapshot
   mesh/transforms/landmarks. В candidate builder есть mesh/transform snapshot;
   master-copy/reopen orchestration ещё отсутствует.
5. После измеренного resource gate — 192 PNG при 24 fps, локальный FFmpeg MP4,
   media_qc.measure + полный decode и counted frames. `qc_preview.assess` переиспользует
   verdict Studio, но не запускает measurement/encode и не аутентифицирует входной dict.
6. Визуальное принятие каждого аспекта: правильный физический борт, раскрытие длины,
   видимость, клиппинг/окклюзия, последнее видимое. Human остаётся PENDING до review.

Нейтральный proxy: 7 м, X front/Y left/Z up, разные маркеры бортов, четыре условных
колеса; это не модель ВАЗ и не утверждённый LIMO_2106. Камера fixtures начинается
с передней детали и отходит к левому ракурсу; композиция не доказана без рендера.

## Навыки и rollback

Собственный skill хранится в `skills/gremovod-blender-consistency/SKILL.md` и идентичных
project discovery copies `.agents/skills/...` и `.claude/skills/...` этого worktree.
Project hook запрещает commit `.claude`: эта копия остаётся только локально.
Это не меняет root checkout или глобальные навыки. Codex/Claude discovery требует
нового сеанса в этом worktree; фактический вызов skill Claude/MiniMax не тестировался.
Сторонние 25 навыков установлены ранее в root project, а не повторно скопированы сюда.

`check_skill_install.py` выполняет только dry-run: существующие цели SKIP_EXISTING,
новые WOULD_COPY, SHA каждого исходного файла. Ничего не перезаписывает и не запускает.
`SKILL_INSTALL_INVENTORY.json` — снимок 25 навыков / 107 файлов; provenance Expert UNKNOWN.

До merge rollback — закрыть Draft PR и перестать использовать ветку. Не удалять
автоматически worktree, пользовательские данные, зависимости или установленные addons.
После согласованного merge откат кода — отдельный revert commit через review.
