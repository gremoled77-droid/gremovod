# Результат аудита и минимальной реализации — 24.10.2026

## Git и область изменений

Репозиторий `gremoled77-droid/gremovod`. Изолированная ветка `codex/animios-seedance25`, worktree `.worktrees/codex-animios-seedance25`, база `origin/mavis/work` = `ea05f2cd31991c2a8533720864d539759febef83` после fetch. `origin/main` = `2f8f6554cc9ccc50e22c21bd992ddaff1a2fb9ac`. Грязные основной checkout (`fix/astra-aider-20261020`, HEAD `be9382ccc32c63aa230d6b34a1efd79462f66b47`) и прежний Codex worktree оставлены без правок. Main/mavis не изменялись, серверы не запускались и не останавливались. Итоговый commit SHA сообщается в PR и ответе, чтобы не записывать самоссылочный SHA в commit.

Прочитаны START_HERE, SPEC, входные MD/CSV/JSON, AGENTS/CLAUDE и инструкции совместной работы. Ранее приложенный `GremoVOD_AI_VIDEO_DIRECTING_GUIDE_2026-10-24.md` изучен как PROPOSED-источник; его отдельное DOC-only ТЗ MiniMax не подменяет текущий запрос пользователя на офлайн-реализацию backend.

Draft PR [#102](https://github.com/gremoled77-droid/gremovod/pull/102) проверен: открыт, не слит, base `mavis/work`, head `9a84a0b89af4c2b3fc0b5929602fd12d73b99239`, файлы `docs/blender/BLENDER_KNOWLEDGE_BASE.md` и `docs/blender/CODEX_TASK_BLENDER.md`. Это исследовательская архитектура Blender; не доказательство работающей интеграции. Здесь нет второго Blender RFC, нового MCP или второго видеоконвейера.

## Что уже было

| Область | Реально реализовано | Чего это не подтверждает |
|---|---|---|
| `backend/adapters.py`, `model_catalog.py`, `test_seedance_adapter.py` | Seedance 2.5 text/reference/edit/extend/draft; image/video/audio slots, лимиты, prompt tags, расчёт выхода и половины ставки входного video | Живую поддержку PiAPI, фактическую цену, качество; launch_enabled остаётся false |
| `production_entities.py` | Production nodes/state/revision, выбор refs/approved image | Immutable media versions и Stage Bible |
| `reference_upload.py` | Явная временная публикация изображений, HTTPS/cache/expiry | Загрузку clay video/audio или approval manifest; upload здесь не вызывался |
| `storyboard.py` | Outline/import/reorder и контроль revision | Кадровые интервалы, пространственную географию и prop ledger |
| `car_staging.py` | Текстовые ограничения канона автомобиля и физических сторон | Проверенную геометрию и сохранение меша |
| `clip_chain.py` | Извлечение последнего кадра FFmpeg | Семантическую непрерывность A→B |
| `media_qc.py` | SHA, ffprobe/decode, технические требования и verdict | Стабильность персонажа, физику и художественное approval |
| `llm_guard.py` | LLM budget/reserve/permit/reconcile | Разрешение Seedance submit или историю попыток видеогенерации |

## Добавлено

- `backend/reference_production.py`: чистый preflight пяти структур, нормализованный continuity report, read-only bridge к существующему asset registry, привязка Reference → Generation через существующий адаптер. Старая схема БД и HTTP API не менялись. Полный контракт и ограничения — в `CONTRACTS.md`.
- `backend/test_reference_production.py`: позитивные и негативные случаи, read-only SQLite snapshot и A/B/C в обоих aspect ratios.
- `scripts/reference_production_preflight.py`: воспроизводимый импорт 11 планов и сверка CSV с кадрами, отчёт и синтетические dry-run варианты. Пустой trusted registry намеренно оставляет исходные placeholders заблокированными.
- В этой папке: собственные исходные MD/CSV/JSON, `SEQUENCE_ANALYSIS.json` с зависимостями и реквизитом, `PILOT_STAGE.json`, `CONTRACTS.md`, `CONTINUITY_REPORT.json`, `GENERATION_MANIFEST.json`, `PILOT_EXPERIMENT.md`, `BACKLOG.md`, README и этот отчёт. Оригинальные MP4/JPG отсутствуют в Git.

## Фактически выполненные проверки

1. Локальный ffprobe исходного MP4: H.264, 1280×720, 24/1 fps, 760 кадров; stream 31.666667 s, container 31.718458 s. Размер 4 202 033 байта. CSV и manifest согласованы с видеопотоком с точностью опубликованных миллисекунд. Это сверка метаданных и границ, не независимая покадровая художественная приёмка каждой склейки.
2. Локальный контактный лист просмотрен: 11 подписанных планов, корабль/палуба/камбуз/пицца. Это реконструкция по финальному видео, не исходный проект автора. Удар-кандидат около кадра 672 находится внутри SH11 `[630,760)`; точный кадр удара вручную не утверждён.
3. `backend/test_seedance_adapter.py`: отдельно выполнены 13 unittest — PASS.
4. Итоговый узкий pytest: `backend/test_reference_production.py backend/test_seedance_adapter.py` — **45 passed**, 46 существующих FastAPI `on_event` deprecation warnings. Из них 32 новых и 13 существующих тестов. `STUDIO_DATA_DIR` перед импортом main задан через TemporaryDirectory, затем удалён; owner DB не открывалась. Полная suite/frontend build/UI не запускались — UI не изменялся.
5. CLI `scripts/reference_production_preflight.py --write-reports`: отчёты записаны, native exit **2**, ожидаемый status BLOCKED. 38 issues: 5 BLOCKED_UNVERIFIED_ASSET и 33 предупреждения о неизвестной географии/выходах/неутверждённой сцене. Ошибок CSV timing нет. BLOCKED не выдан за PASS production readiness.
6. A/B/C dry-run: 10 s, 480p, оба формата 16:9 и 9:16. По локальному каталогу A=$1.50, B=$1.50, C=$2.25 при 10 s входного video; итого шесть кандидатных preview, не шесть реальных заданий. actual_cost=null, attempts=[], approval=null, hold=NOT_RESERVED, execution_allowed=false. Синтетические URL используют зарезервированный `.invalid`; исходный заблокированный manifest не получает wire payload. Оплаченных вызовов — 0.

Воспроизведение тестов из worktree (venv указан абсолютным путём, поскольку сам venv не копируется в worktree):

```powershell
& C:\AI_Workflow_Studio\.venv\Scripts\python.exe -c "import os,tempfile,pytest; t=tempfile.TemporaryDirectory(prefix='gremovod-animios-'); os.environ['STUDIO_DATA_DIR']=t.name; code=pytest.main(['backend/test_reference_production.py','backend/test_seedance_adapter.py','-q','--disable-warnings']); t.cleanup(); raise SystemExit(code)"
& C:\AI_Workflow_Studio\.venv\Scripts\python.exe scripts/reference_production_preflight.py
```

CLI по умолчанию ничего не записывает. Exit 2 ожидаем до появления утверждённых исходников.

Контрольные суммы локальных медиа (только provenance; файлы не публикуются):

- MP4 SHA256 `4d58783cfef6207d840985d2f239a3e92390599c59f31a13037bc1d1dae82376`.
- JPG SHA256 `fd846193d93f814e60f627075992b4a0cc85a6fe2863e45afa5e73b1098c0364`.

## Блокировки и отдельная приёмка

| Проверка | Статус | Причина/что требуется |
|---|---|---|
| Blender graybox/clay render | BLOCKED_ENV | Blender отсутствует в PATH и проверенных обычных Program Files путях версий 3.6–4.5. Не устанавливался. Подготовлены только JSON камер/условные размеры. |
| Каноническая геометрия LIMO_2106 | BLOCKED_ASSET | Нет подтверждённого asset ID/version/SHA/пути. Размеры proxy не утверждают геометрию. |
| Character sheets, locations, pizza keyframes | BLOCKED_UNVERIFIED_ASSET | Все пять refs примера UNAVAILABLE/UNVERIFIED/null SHA. Не заменялись вымышленными авторскими файлами. |
| Registry approval persistence и UI | NOT_IMPLEMENTED | Есть read-only bridge и правила metadata; запись approval/immutable revisions и wiring в карточки — отдельный следующий этап. |
| Живой Seedance, загрузка refs и A/B/C quality comparison | NOT_RUN | Не разрешены платные вызовы; стоимость только из локального каталога. Транспорт тестирован офлайн. |
| Визуальная приёмка лимузина, персонажей, пиццы и звука | NOT_PERFORMED | Нужны реальные рендеры/клипы и ручной просмотр. Для первого пилота Грэм отсутствует. |

Для художественной приёмки отдельно просмотреть начало/середину/конец, все ключевые позы, полный кузов и двери/стойки/колёса, контакты с дорогой, отсутствие растяжения и преждевременного раскрытия. Повторить для 16:9 и 9:16. Проверить непрерывность пиццы и коробки между планами; звук прослушать. Зафиксировать owner approval на том же SHA результата после технического QC. Сейчас эти пункты не приняты.

Следующие отдельные задачи MiniMax (UI/approval bridge) и Claude Code (независимое ревью и приёмка) перечислены в `BACKLOG.md`. Сообщения другим чатам не отправлялись.
