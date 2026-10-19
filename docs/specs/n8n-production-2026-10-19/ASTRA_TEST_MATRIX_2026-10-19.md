# Протокол Astra v1.1: что проверено без MP4, что заблокировано
Дата: 2026-10-19. Branch: `feature/n8n-astra-contract-hardening-20261019`.
Draft PR: https://github.com/gremoled77-droid/gremovod/pull/17
Base: `codex/n8n-full-production-spec-20261019` (не main).

## Сделано в этом этапе

1. **Письменные решения P0/P1/P2:** [ASTRA_FIXES_V1_1.md](ASTRA_FIXES_V1_1.md) — источник pilot state и роль владельца, запрос и budget grants, UNKNOWN после submit без повторного списания, external/native sound, lip-sync dependency, image reference candidate, complete media manifest, производные файлы, независимые финальные QA, double resume, N34 только технический.
2. **Структурированная спецификация:** [nodes.json](nodes.json) — 43 N + 9 S; 32 `astra_v1_1` overrides, 13 уточнённых conditional routes; статус `SPECIFIED_NOT_EXECUTED`. Три сопроводительных раздела в README/NODES/SPECIFICATION/IMPLEMENTATION_AND_ACCEPTANCE.
3. **Машиночитаемый contract:** [contracts/runtime-v1.schema.json](contracts/runtime-v1.schema.json) — 9 видов сообщений/артефактов, *не криптографическая проверка и не одобрение*.
4. **Reference SQLite module:** [pilot_state_sqlite.py](../../../integrations/n8n/pilot_state_sqlite.py) — durable operations, atomic lease и state revision, server-authenticated grant placeholders, per-request reserve, submit UNKNOWN, idempotent callback, media manifest/snapshot and persisted trusted media round as condition for owner READY. **Не подключён к рабочему backend.**
5. **Тесты:** [backend/test_n8n_astra_pilot.py](../../../backend/test_n8n_astra_pilot.py), временные SQLite файлы. GitHub Actions: [n8n-astra-pilot.yml](../../../.github/workflows/n8n-astra-pilot.yml). Базовый CI run [39214029016](https://github.com/gremoled77-droid/gremovod/actions/runs/39214029016) = success, **17 тестов** и машинный schema check. Последующие улучшения требуют green status текущего head.
6. **Реальный n8n Cloud OFFLINE mock:** [GremoVOD Astra P0-P2 free simulation](https://gremovod.app.n8n.cloud/workflow/Qx97ayFEdpTnmsMb), execution **#34**: `18/18 SIMULATED_GATES_OK`, модельных вызовов 0, `final_release_approved=false`. Проверки — **симуляция**, не доказательство runtime concurrency.
7. **Видимое полотно:** [GremoVOD 52-stage production map (ALL BLOCKED / DRAFT)](https://gremovod.app.n8n.cloud/workflow/PmIfs9DQHHLM4eTt), execution **#35**: 52 логических ноды N01–N43/S01–S09, 9 групп по стадиям, все отдельные stage placeholders `NOT_IMPLEMENTED` и намеренно **не соединены** с реальным генератором. Выполняется только status registry + fail-closed gate: `BLOCKED_NOT_IMPLEMENTED`. Зелёный статус execution означает успешную проверку статусов, а не работающий production pipeline.
8. Уже существовавший live TEXT-only demo [workflow 2DllTVkrO6imk2IR](https://gremovod.app.n8n.cloud/workflow/2DllTVkrO6imk2IR) имел execution #33 с A1/A6/A7 в Gemini Gateway, но его синтетический текст не является media acceptance. **В этой задаче платных модельных вызовов не было.**

## Таблица закрытия Astra

| Раздел | Контракт | Автоматизированная проверка | Реальное подключение |
|---|---|---|---|
| P0 S01/S08/S09 — durable state & owner | Описан | SQLite atomic lease, stale inputs; mock | **NOT_INTEGRATED** с Studio sessions/FastAPI |
| P0 S04 — BudgetGrant + RequestAuthorization | Описан | cap, hash, expired grant, change between reserve and submit | **NOT_INTEGRATED** с payment/profile adapters |
| P0 S05 — UNKNOWN / missing provider ID | Описан | UNKNOWN holds reserve, no blind second submit | **NOT_TESTED** с реальным провайдером |
| P0 S06 — actual video/audio | Описан | only missing-media BLOCKED mocks | **BLOCKED_NO_MP4**; no model capability claim |
| P1 native/external, SFX/music, lip-sync | Описан; route table обновлён | mock branch flags | **NOT_TESTED** media generation |
| P1 missing canonical reference loop | Описан; CANDIDATE + owner gate | mock return | **NOT_TESTED** image creation |
| P1 expected slots / N32 | Описан; JSON Schema + Python | missing/duplicate slot | **NOT_TESTED** ffmpeg worker |
| P1 full snapshot / N35–N41 | Описан + Python gate | same hash+roles, stale, missing media, trusted round, idempotent owner READY | **NOT_INTEGRATED** owner interface / actual media |
| P1 derivatives & viewer access | Описан + schema | structure only | **BLOCKED_NO_MP4** |
| P2 N34 duplicate criticism | Spec corrected | mock technical-only | **NOT_TESTED** renderer |
| N07 acceptable options policy | Spec corrected (2+ distinct viable) | mock 2 vs 1 | **NOT_TESTED** real A1 |
| Agent invocation method | Execute Sub-workflow is pilot choice | none | **NOT_TESTED** live subworkflow vs Message an Agent |

**Критическое предупреждение:** `owner_authenticated` и `trusted_backend_verifier` аргументы reference module не являются HTTP-авторизацией. В доверенном backend должны выводиться только из серверных verified sessions и file inspection, а не из JSON агента.

## Чёткая остановка

Без реального MP4 невозможно честно отметить как готовые N30/N31/N35–N41, проверку lipsync/тембра/движения/стыков и доступных моделей. Никакая комбинация 52 узлов, 18 зелёных mock tests, текстовых PASS или внешней ссылки на видео не отменяет `BLOCKED_NO_REAL_MEDIA`.

## Что остаётся Codex после появления файла

1. Изучить собственные `backend/automation.py` и `backend/qa_text_precheck.py` из параллельных веток и **согласовать** с этим reference module без создания второй production DB. Завершить защищённый auth route/dispatcher, SQL concurrency и service authorization tests на временной БД.
2. Проверить реальную облачную доставку MP4, checksum, codec/audio/video streams и доступность модели на стороне n8n. Проверить выбранные video+audio critic capabilities отдельно.
3. Выбрать бюджет и модель только после подтверждения gateway или Kie credit-route; до того $0.
4. Запустить три независимых reviewers на одном frozen snapshot и owner gate, внедрить адресное исправление, проверить один дубль/аварию.
5. Затем запустить идею→сценарий→режиссуру→реальные медиа→монтаж и только по фактическому успешному пилоту проектировать Studio UI.

Нельзя автоматически merge/publish, читать или изменять реальную базу, запускать A8, выдавать READY, генерировать медиа без предварительного budget approval и анализа источников.


## Дополнение: runtime routing N34–N41

19.10.2026 добавлены [конкретная матрица классов моделей, входных форматов и причин BLOCKED](N34_N41_RUNTIME_MODEL_MATRIX.md) и [структурные JSON contracts](contracts/final-runtime-v1_2.schema.json). Машинный каталог `nodes.json` дополнен `astra_v1_2` для N34–N41 и S06/S07: N34/N39–41 = 0 LLM, N35 локальная подготовка доказательств + отдельный STT-бюджет, N36–N38 = только проверенные мультимодальные профили и авторизация. `backend.test_n8n_final_routing_spec` проверяет согласованность каталога. Реальный видео/аудио бенчмарк **не выполнялся**.

Execute Sub-workflow **действительно** вызвал child MOCK на n8n (execution #36), 0 платных запросов. Это подтверждает механизм вызова другого workflow и ожидания результата, но НЕ доказывает работоспособность saved Agent и не подтверждает ни одной медиа-модальности.
