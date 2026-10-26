# Blender: результат offline-этапа 26.10.2026

## 1. Результат

Подготовлены строгие manifests, семантическая проверка, offline planner, исходник
синтетической сцены, mock-tested process primitive, QC adapter, reference binding,
dry-run проверки установки, собственный skill и Windows CI. Это **частичное
выполнение P0**, а не принятый render pipeline. G1 запрещает запуск Blender/MCP
без подтверждённой изолированной среды без секретов. Реальный рендер, reopen,
MP4, visual acceptance и оптимизация не выполнены. Следующий шаг — предоставить
среду и реализовать/проверить isolated launcher; receipt сам по себе недостаточен.

## 2. Git и файлы

Base: `codex/blender-previz-research-20261024`, SHA
`921b0f5f0f74add2d87bd0c939120de2ad9fb837`. Ветка:
`codex/blender-integration-p0-20261026`; worktree:
`C:\AI_Workflow_Studio\.worktrees\codex-blender-p0`.
Точный итоговый HEAD и Draft PR URL приводятся в сообщении сдачи; этот отчёт входит
в сам commit. PR направлен на исследовательскую ветку, поэтому зависит от неё.
Root checkout и main не изменялись в ходе реализации.

Изменения: `scripts/blender/`, `schemas/blender/`, шесть
`tests/test_blender_*.py`, два requirements-файла, workflow
`blender-offline.yml`, `.gitignore`, этот комплект `docs/blender/`, собственный
`skills/gremovod-blender-consistency/SKILL.md` и project discovery copy `.agents`. Идентичная локальная `.claude` copy
сохранена на диске, но исключена из Git по запрету project commit hook.
Медиа, база, credentials, vendor-код и runtime в commit не включаются.

## 3. Установка

Полная матрица версий/путей/ограничений — в
[THIRD_PARTY_SKILLS_MATRIX.md](THIRD_PARTY_SKILLS_MATRIX.md).
Инвентарь 25 навыков / 107 файлов и SHA —
[SKILL_INSTALL_INVENTORY.json](SKILL_INSTALL_INVENTORY.json).
Сопоставленные файлы `.agents` и `.claude` совпадают. EL4CTEO: 22 навыка,
commit `71d031dab8bc6729504d11a78cbe91945401045f`, MIT.
Expert: только router, previs-storyboard и hard-surface; provenance/license
UNKNOWN, остальные специалисты не устанавливались. Версионная совместимость
навыков, ориентированных на 5.2, с доступным 4.5.15 не доказана.
BAS уже установлен 0.6.4. MustardSimplify 2026.3.1, Model Optimizer 2.1.0 и
Asset Validator 1.0.0 обнаружены установленными; это не render acceptance.
Live MCP не активирован. Новый собственный skill валиден, но фактическое
обнаружение/вызов из нового сеанса Codex/Claude/MiniMax не проверялись.

## 4. Среда

Blender executable:
`C:\AI_Workflow_Studio\tools\blender\blender-4.5.15-windows-x64\blender.exe`.
Ранее проверена версия 4.5.15 LTS / build `5afeabba6097`; в offline preflight
бинарник только хешируется, `actual_version=NOT_EXECUTED`.
GTX 950 2 GiB; i7-6700K; RAM около 63.9 GiB; FFmpeg/ffprobe 9.0.2.
Полные значения — [ENVIRONMENT_AUDIT.md](ENVIRONMENT_AUDIT.md).
Реальные время рендера, peak RAM/VRAM и размер медиа UNKNOWN.

## 5. P0 demonstration

`scene_build.py` — подготовленный, **не исполненный в Blender** исходник:
семиметровый neutral proxy, физический левый борт +Y, камера на 192 кадра / 24 fps.
Это не канонический ВАЗ/лимузин и не подтверждение композиции.
JSON fixtures обеих ориентаций 960×540 и 540×960 прошли schema/semantic checks.
Их `asset_bytes_verified=false`; пример hash не относится к существующей модели.
`.blend`, first/mid/last PNG, MP4 и measured QC отсутствуют;
master geometry SHA = null, human state = PENDING, visibility = UNVERIFIED.
QC unit fixtures не являются измерением видео.

## 6. Безопасность

Planner не запускает subprocess и не создаёт attempt directory. Проверены
траверсал, ownership/version/hash при переданном trusted registry, JSON/ID,
camera bounds и reference binding. CLI не подключён к реальному owner lookup.
В отдельном primitive проверены shell=False, timeout и подавление stdio, но это
не OS sandbox. Нет launcher pinning, memory/disk/process-tree enforcement,
immutable-master copy/reopen orchestration. Эти ограничения явно сохранены
как незавершённые. Windows ACL и firewall не менялись. Контрольный запуск CLI
показал BLOCKED_G1, render_executed=false, attempt_exists=false.
Provider transport отсутствует; offline reference preview всегда BLOCKED_P1,
без dispatch/upload/hold. Платных вызовов и загрузки медиа в ходе работ не было;
это утверждение о выполненных действиях, не аудит внешнего billing.

## 7. Benchmark

NOT_MEASURED: baseline/optimized elapsed, peak memory, geometry SHA и speedup =
null. Workbench/Cycles CPU × два аспекта — лишь шаблон четырёх строк; Cycles
preset не реализован. Сравнение разных engines не доказывает ускорение addon.
Протокол будущего сравнения — [OPTIMIZATION_BENCHMARK.md](OPTIMIZATION_BENCHMARK.md).

## 8. Проверки

Команда в [BLENDER_P0_RUNBOOK.md](BLENDER_P0_RUNBOOK.md): шесть явных pytest
файлов, **45 passed**. Реальные Blender/process/provider вызовы в тестах не
выполнялись: процессные проверки используют injected mock. Проверка собственного
skill через `quick_validate.py` с `-X utf8`: Skill is valid.
Offline CLI: stage/shot/portrait PASS_SCHEMA_SEMANTIC;
preflight exit 0 / BLOCKED_G1; planner exit 2 / BLOCKED_G1 и без attempt;
benchmark exit 0 / NOT_MEASURED. Exit 0 отчёта не означает принятие рендера.
Локальная venv использует system-site-packages; чистая установка не проверена.
Удалённый CI, полный suite, UI, Blender API, кодеки, рендер, skill discovery,
лицензионная неопределённость Expert/Optimizer и paid A/B не проверены.

## 9. Следующие карточки

Исполнители, зависимости и DoD девяти карточек —
[BLENDER_P1_P2_PLAN.md](BLENDER_P1_P2_PLAN.md): изоляция/launcher → diagnostic
и reopen → immutable master/две ориентации/MP4/QC → измеренный optimization →
owner-backed registry и existing budget binding → разрешённый provider transport →
frontend review → n8n RFC. P1 transport нельзя принимать до локального P0.
Текущий quote hash — offline contract, не confirm token существующего бюджета.

## 10. Блокирующие входы владельца

Нужна подтверждённая VM/учётная запись без секретов с ограничениями файловой
системы, сети и ресурсов. Для канонического пилота нужна утверждённая модель
и размеры/версия; до этого допустим только NON_CANONICAL_PROXY.
Платные тесты/внешние uploads остаются закрыты; когда до них дойдёт очередь,
нужно отдельное разрешение с provider/model, стоимостью и пределом. Сейчас
такое разрешение не запрашивается: сначала требуется завершить локальный P0.
