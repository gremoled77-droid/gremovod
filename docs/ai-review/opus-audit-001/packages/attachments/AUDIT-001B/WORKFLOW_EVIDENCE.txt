# WORKFLOW_EVIDENCE — n8n-конвейер, контракты, маршруты, артефакты

**Ревизия:** PR #29 @ `c082829b11b968965600bdaf87c137b1485a0fa2`.
`main` **не содержит** ни `workflows/`, ни `integrations/n8n/`, ни `docs/specs/n8n-production-2026-10-19/`.

---

## C-01. Главный факт: в репозитории конвейер — MOCK

**Вердикт: MOCK (для исполняемого кода) + SPEC-ONLY (для контрактов).**

Это единственный вывод, который обязан получить аудитор из этого раздела, прежде чем
читать остальное.

### 1.1 Файлы воркфлоу

`workflows/` в PR #29 — семь JSON. Реальные размеры и структура:

| Файл | Байт | Узлов | Групп connections | `active` | `name` |
|---|---:|---:|---:|---|---|
| `WF_00_Core_Infra.json` | 7 174 | 9 | 8 | `false` | `WF_00_Core_Infra — MOCK ONLY (SOURCE EXPORT)` |
| `WF_01_Writers_Room.json` | 1 808 | 2 | 1 | `false` | `WF_01_Writers_Room — MOCK ONLY (SOURCE EXPORT)` |
| `WF_02_Canon_And_Images.json` | 1 418 | 2 | 1 | `false` | `WF_02_Canon_And_Images — MOCK ONLY (SOURCE EXPORT)` |
| `WF_03_Audio_Factory.json` | 1 460 | 2 | 1 | `false` | `WF_03_Audio_Factory — MOCK ONLY (SOURCE EXPORT)` |
| `WF_04_Video_And_LipSync.json` | 1 417 | 2 | 1 | `false` | `WF_04_Video_And_LipSync — MOCK ONLY (SOURCE EXPORT)` |
| `WF_05_Assembly_And_Critics.json` | 1 540 | 2 | 1 | `false` | `WF_05_Assembly_And_Critics — MOCK ONLY (SOURCE EXPORT)` |
| `WF_06_Repair_Router.json` | 1 614 | 2 | 1 | `false` | `WF_06_Repair_Router — MOCK ONLY (SOURCE EXPORT)` |

WF_01–WF_06 содержат **по два узла**: ручной триггер и один `n8n-nodes-base.code`.
WF_00 — девять узлов: ручной триггер, узел «Инвентаризация тестов», шесть
`executeWorkflow` (по одному на WF_01…WF_06) и узел «Проверить трубу и записать READY».

### 1.2 Код внутри узла — явный MOCK

`workflows/WF_06_Repair_Router.json` целиком (2 161 байт с BOM):

```json
{
  "name": "WF_06_Repair_Router — MOCK ONLY (SOURCE EXPORT)",
  "nodes": [
    { "id": "wf06-mock", "name": "00 · Manual MOCK only", "type": "n8n-nodes-base.manualTrigger", ... },
    {
      "id": "wf06-code",
      "name": "01 · Repair routing (MOCK)",
      "type": "n8n-nodes-base.code",
      "parameters": {
        "jsCode": "const p = $input.first().json || {};\nif (!(p.MOCK_MODE && p.review_status === 'BLOCKED_NO_REAL_MEDIA')) { throw new Error('MOCK_ONLY'); }\nreturn [{ json: { ok: true, repair_mode: 'MOCK', note: 'real repair is not implemented in this export' } }];"
      }
    }
  ],
  "connections": { "00 · Manual MOCK only": { "main": [[ { "node": "01 · Repair routing (MOCK)", ... } ]] } },
  "active": false,
  "settings": {}
}
```

Узел **бросает `Error('MOCK_ONLY')`**, если вход не соответствует
`MOCK_MODE && review_status === 'BLOCKED_NO_REAL_MEDIA'`. Это не рабочий ремонтный
маршрут — это заглушка, которая честно отказывается работать вне MOCK.

### 1.3 Манифест подтверждает

`integrations/n8n/WF_00_WF_06_MANIFEST.json` (201 строка, читается целиком):

```json
{
  "version": "1.0-stage-1",
  "status": "MOCK_FIRST_NOT_PUBLISHED",
  ...
  "pilot": {
    "MOCK_MODE": true,
    "native_audio_enabled": false,
    "external_tts_first": true,
    "independent_audio_tracks": ["voice", "sfx", "music"],
    "optional_track": "ambience",
    "no_auto_publish": true,
    "real_provider_enabled": false,
    "real_media_evidence_available": false
  },
  "mock_test": {
    "workflow_id": "j8Xqv8GQHjfJ5fVI",
    "execution_id": "39",
    "status": "MOCK_PIPELINE_COMPLETE_NO_REAL_APPROVAL",
    "physical_modules_executed": 7,
    "synthetic_shots": 3,
    "synthetic_audio_tracks": 3,
    "repaired_slot_id": "shot_02",
    "other_shots_reused": true,
    "paid_calls": 0,
    "real_media_verified": false,
    "production_release": false
  },
  "workflow_count": 7
}
```

Ключевое из `mock_test`: `paid_calls: 0`, `real_media_verified: false`,
`production_release: false`, `synthetic_shots: 3`, `synthetic_audio_tracks: 3`.
**Это прогон на синтетике**, а не на медиапотоке.

### 1.4 Что в MOCK-конвейере работает как настоящее

Справедливости ради: `mock_test` показывает `physical_modules_executed: 7` — то есть
**все семь физических модулей были выполнены** в n8n (execution #39), включая
переход по ремонту `shot_02` с переиспользованием остальных шотов. Сама **оркестрация**
(маршрутизация, передача пакетов, ремонт слота) работает. Не работает **продакшен-исполнение**:
нет реальных провайдеров, нет реальных медиа, нет реальной приёмки.

Это существенная разница, и её нельзя схлопывать: **конвейер как граф — работает в MOCK;
конвейер как производство — не существует.**

---

## C-02. Логическая структура: 43 узла + 9 сервисов

`VALIDATION.json` (`docs/specs/n8n-production-2026-10-19/`):

```json
{
  "status": "PASS",
  "checked_at_utc": "2026-10-19T06:43:52.195602+00:00",
  "logical_nodes": 43,
  "shared_services": 9,
  "unique_ids": 52,
  "main_nodes_reachable": 43,
  "final_review_outcomes_aggregated": true,
  "ready_requires_owner_node": true,
  "conditional_audio_routes": 3,
  "markdown_catalogue_matches_json": true,
  "local_links_checked": 6,
  "common_token_pattern_scan": "no matches; not an exhaustive secret audit",
  "scope": "documentation structure only",
  "not_tested": [
    "n8n execution",
    "provider calls",
    "media generation",
    "actual billing",
    "behavioral critic quality"
  ]
}
```

> ⚠️ **`"status": "PASS"` относится к `scope: "documentation structure only"`.**
> `not_tested` прямо перечисляет то, что не проверялось: исполнение n8n, вызовы
> провайдеров, генерация медиа, реальное списание денег и **поведенческое качество
> критиков**. Аудитору нельзя читать этот `PASS` как «конвейер проверен».

### 2.1 Раскладка по физическим воркфлоу

Источник: `NODES.md` (заголовки `## N01`…`## N43`, `## S01`…`## S09`) и
`WF_00_WF_06_MANIFEST.json`.

| WF | Логические узлы | Ответственность | `executable_gate` |
|---|---|---|---|
| WF_00 | S01–S09 | project_state, budget_reservations, leases, human_approvals, asset_registry | `BACKEND_REQUIRED_FOR_PRODUCTION` |
| WF_01 | N01–N11 | idea, concepts, scripts, skills, director_plan | `APPROVED_BRIEF_OWNER_AND_CANON_REQUIRED` |
| WF_02 | N12–N19 | canon_vault, references, image_factory | `APPROVED_ASSETS_AND_AUTHORIZED_SPEND_REQUIRED` |
| WF_03 | N20–N25 | external_tts, voice_timing, music, sfx | `AUDIO_TRACK_MANIFEST_COMPLETE` |
| WF_04 | N26–N31 | video_generation, separate_lipsync, video_inspection | `VIDEO_SOURCE_VERIFIED_BEFORE_LIPSYNC` |
| WF_05 | N32–N41 | manifest_gate, ffmpeg_assembly, N34_technical_no_llm, N35_evidence, A6_A7_A8, human_ready | `3_CURRENT_MEDIA_VERDICTS_PLUS_OWNER` |
| WF_06 | N42–N43 | targeted_repair, safe_resume, asset_cache | `REPAIR_ONLY_FAILED_SLOT` |

### 2.2 Полный перечень 43 узлов (заголовки `NODES.md`)

```
N01 — Идея автора                     N23 — Генерация речи и звуков
N02 — Проверка входов                 N24 — Получение и измерение аудио
N03 — A0: производственный бриф       N25 — Критика реального аудио
N04 — A4: исследование по необходим.  N26 — A2: согласование тайминга и движения
N05 — Фиксация брифа и критериев      N27 — A3: запросы видео
N06 — A1: варианты развития идеи     N28 — Проверка видеозапросов
N07 — Критика вариантов               N29 — Генерация видео / lip-sync
N08 — Выбор концепции                 N30 — Получение и инспекция видео
N09 — A1: сценарий и реплики          N31 — Критика реального клипа
N10 — Критика сценария                N32 — A5: монтажная сборка как план
N11 — A2: подбор персонажей и локаций N33 — Рендер итогового файла
N12 — Комплект референсов мира        N34 — Критика монтажа
N13 — A2: режиссёрская разработка     N35 — Заморозить финальный пакет
N14 — Критика режиссёрского решения   N36 — Финальный A6: соответствие заданию
N15 — A3: запросы изображений         N37 — Финальный A7: мир и непрерывность
N16 — Проверка image-запроса          N38 — Финальный A8: ремесло
N17 — Отправка генерации изображения   N39 — Свести три финальных вердикта
N18 — Получение и сохранение изобр.    N40 — Решение человека
N19 — Критика реального изображения    N41 — Отправить в Готовые
N20 — A5: план речи и звука            N42 — A0: адресный возврат
N21 — Подготовка аудиозапросов         N43 — Пауза и восстановление
N22 — Проверка аудиозапросов
```

Сервисы: `S01` хранилище и версии, `S02` выбор и загрузка навыков, `S03` профиль
модели и адаптер, `S04` разрешение расходов и резерв, `S05` жизненный цикл provider job,
`S06` подготовка доказательств, `S07` независимая критика этапа, `S08` журнал и
checkpoint, `S09` решения владельца.

Обратите внимание на ритм: каждый домен имеет **критику сразу после генерации**
(N19 после изображений, N25 после аудио, N31 после видео) — и это критика
**реального** артефакта, а не только техническая проверка.

---

## C-03. JSON-схемы и контракты

Каталог `docs/specs/n8n-production-2026-10-19/contracts/`:

| Файл | Байт | Назначение |
|---|---:|---|
| `runtime-v1.schema.json` | 15 742 | Роли, бюджет, evidence, provider job, слоты |
| `final-runtime-v1_2.schema.json` | 18 981 | Envelopes N34–N41 v1.2 |
| `scenario-preprod-v1.schema.json` | 15 239 | Границы сценариев N01–N11 |
| `scenario-skills-routing-v1.json` | 6 467 | Навыки, маршрутизация, политика стоимости |

### 3.1 Схемы сами объявляют, что они не доказывают

`runtime-v1.schema.json`:
- `title`: «GremoVOD n8n Astra runtime v1 — structure only; checksums/signatures require trusted backend»
- `description`: «Roles, budget and evidence are NOT considered trusted merely because this JSON
  validates. Owner and backend evidence verification are separate mandatory gates.»

`final-runtime-v1_2.schema.json`:
- `title`: «GremoVOD N34–N41 scoped runtime envelopes v1.2 (STRUCTURE ONLY)»
- `description`: «JSON Schema validation does not establish provenance, rights, actual media
  access, valid owner approval, token budget or authenticity. Trusted FastAPI must ver…»

`scenario-preprod-v1.schema.json`:
- `title`: «GremoVOD N01–N11 scenario draft boundaries (schema does not imply approval)»
- `description`: «S01 and owner session must validate hashes, source permission, character
  profiles and budgets before LLM. Structures alone are not evidence.»

**Это признание проекта о собственных границах — и оно сделано явно и в машинно-читаемом
виде. Для аудита это сильный сигнал: авторы не выдают схемы за доказательства.**

### 3.2 `scenario-skills-routing-v1.json` — политика стоимости и запреты

```json
{
  "spec_version": "1.0-scenario-preproduction-draft",
  "status": "SPECIFIED_NOT_INTEGRATED",
  "scenario_priority": "N01-N11_before_UI",
  "runtime_provider": "NONE_FOR_MOCK",
  "allow_real_source_without_trusted_backend": false,
  "source_context": {
    "canon_authority": "FastAPI approved source snapshot only",
    "github_skill_refs_are_instructions_not_approved_canon": true,
    "owner_auth": "Studio only, n8n never gra…"
  },
  "explicit_no_auto": ["OWNER_SELECT", "NEW_CANON", "PAID_GENERATE",
                       "REAL_MEDIA_QA", "READY", "PUBLICATION"],
  "execution_boundary": "n8n sub-workflow workers read server-frozen packets; FastAPI issues
                         approvals, budget grants and runtime revision checks",
  "cost_policy": {
    "mock_usd": 0,
    "budget_required_for_any_model": true,
    "prompt_style": "at most one initial call per creative stage under user-approved envelope",
    "deterministic_chec…"
  }
}
```

Три вещи, которые стоит проверить аудитору:
1. `explicit_no_auto` — шесть действий, которые **не могут** произойти без человека.
   Это «право вето», зашитое в спецификацию.
2. `execution_boundary` — n8n-воркфлоу **читают серверно-замороженные пакеты**;
   выдаёт approvals, budget grants и проверки ревизий — **FastAPI**. Граница проходит
   по строке «кто выдаёт разрешение».
3. `status: "SPECIFIED_NOT_INTEGRATED"` — честная пометка, что это спецификация,
   а не интегрированный код.

> ⚠️ **Проверить аудитору:** `cost_policy.prompt_style` — «at most one initial call per
> creative stage» — совпадает по смыслу с P0-контуром (`submit_count = 1`).
> Но это **спецификация**, а не исполняемый код. Соединяются ли две защиты на практике —
> отдельный вопрос.

---

## C-04. Условные маршруты

`NODES.md:528-530` (раздел «Условный маршрут нативного звука»):

> Базовые переходы выше соответствуют отдельной генерации речи. Для заранее выбранной
> стратегии `native_video_audio` действуют явные исключения: **N22 → N26** после проверки
> текста/голосовых входов; **N31 → N25** для фактической дорожки из принятого клипа;
> после её проверки **N25 → N32**. Не возвращаться в повторную видеогенерацию через N26.
> Эти условия также записаны в `conditional_routes` файла `nodes.json`.

Итого три условных аудио-маршрута — совпадает с `VALIDATION.json:
"conditional_audio_routes": 3`.

> ⚠️ **Проверить аудитору:** правило «не возвращаться в повторную видеогенерацию через N26»
> — это прямая защита от двойного списания за видео. Оно записано **в Markdown и в
> `nodes.json`**. Но исполняемый код в `workflows/WF_03…WF_06.json` — это MOCK-заглушки
> (§C-01.2), то есть **правило сейчас не исполняется ничем**. Реализация переходов
> должна появиться вместе с реальными воркфлоу.

---

## C-05. Домены медиа

| Домен | Узлы | Воркфлоу | Провайдер (по спецификации) | Зрелость в репозитории |
|---|---|---|---|---|
| Изображения | N15–N19 | WF_02 | PiAPI (`image_factory`) | MOCK в n8n; на `main` — рабочий `adapters.py` |
| Нативный звук | N20–N25 | WF_03 | `native_audio_enabled: false` в пилоте | MOCK |
| TTS | N20–N25 | WF_03 | `external_tts_first: true` (ElevenLabs/Fish) | MOCK в n8n; на `main` — `sound.py` |
| SFX | N23, N25 | WF_03 | отдельный трек `sfx` | MOCK в n8n; на `main` — `sound.py` |
| Музыка | N23, N25 | WF_03 | отдельный трек `music` | MOCK в n8n; на `main` — `sound.py` |
| Видео | N27–N31 | WF_04 | PiAPI, lip-sync отдельным маршрутом | MOCK в n8n |
| Монтаж | N32–N33 | WF_05 | ffmpeg (локально) | MOCK в n8n; на `main` — `edit_list.py` |
| Релиз | N40–N41 | WF_05 | `no_auto_publish: true` | MOCK |

Треки аудио разделены: `independent_audio_tracks: ["voice", "sfx", "music"]`,
`optional_track: "ambience"`. То есть «нативный звук» (голос+звук+музыка в одной
дорожке) и «внешний TTS» — **разные стратегии**, и пилот выбрал внешний TTS.

---

## C-06. Дефекты и ремонт (WF_06, N42–N43)

**Вердикт: SPEC-ONLY + MOCK-исполнение.**

- `N42 — A0: адресный возврат` — точечный ремонт конкретного слота.
- `N43 — Пауза и восстановление` — safe resume.
- `executable_gate` WF_06: `REPAIR_ONLY_FAILED_SLOT` — ремонтировать можно только
  упавший слот.
- Реальное поведение подтверждено MOCK-прогоном: `repaired_slot_id: "shot_02"`,
  `other_shots_reused: true`.

То есть **адресность ремонта в MOCK работает и проверена**: перегенерирован только
`shot_02`, остальные шоты переиспользованы. Это подтверждает, что «не переделывать
всё заново» — рабочая идея, а не лозунг. Но в исполняемом коде репозитория — заглушка
`Error('MOCK_ONLY')` (§C-01.2).

**Лимиты повторов.** В репозитории для ремонта **нет** ни счётчика попыток, ни
потолка на ремонт, ни автоматического ремонта по бюджету в исполняемом коде. Правило
`REPAIR_ONLY_FAILED_SLOT` — это **gate**, а не квота. Автоматический retry при
истощении бюджета в `p0_control` запрещён (`submit_count` + UNKNOWN-блокировка),
но это контур PR #29, а не WF_06. Связь между ними — открытый вопрос (см. OI-05).

---

## C-07. Сохранение артефактов и восстановление

**Вердикт: SPEC-ONLY в n8n-части; реализовано в FastAPI-части.**

| Аспект | Где реализовано | Статус |
|---|---|---|
| Медиа-файлы на диске | `backend/main.py` (медиа-эндпоинты), `backend/temp_cleanup.py` (211 стр.) | IMPLEMENTED |
| Версии и хранилище | S01 «Хранилище и версии» | SPEC-ONLY |
| Реестр артефактов | `asset_registry` (WF_00), `backend/image_assets.py` | SPEC + IMPLEMENTED |
| Точечный ремонт с переиспользованием | N42, WF_06 | MOCK (подтверждён прогоном) |
| Пауза/восстановление | N43, WF_06 `safe_resume`; P0: `claim_run`/`claim_job` с лизами | SPEC + IMPLEMENTED (PR #29) |
| Чекпойнт и журнал | S08 «Журнал и checkpoint» | SPEC-ONLY |

> **Слабое место, которое стоит проверить:** S01/S08 (хранилище, версии, журнал,
> чекпойнт) — **сервисные узлы без исполняемой реализации**. При этом `freeze_manifest`
> в P0 (`p0_control.py:375`) — это по сути **единственный** реализованный механизм
> версионирования плана, и он живёт в FastAPI, а не в n8n. То есть S01 в n8n-части
> и `freeze_manifest` в P0 — это **два разных механизма версионирования в двух разных
> подсистемах**. Их согласованность не описана и не проверена. Это сильный кандидат
> в находки.

---

## C-08. Сверка манифеста с реальными файлами

Проверено: три заявленных факта из `WF_00_WF_06_MANIFEST.json` против реальных файлов.

| Заявлено в манифесте | Реальность | Согласовано? |
|---|---|---|
| `workflow_count: 7` | В `workflows/` ровно 7 файлов `WF_0*.json` | ✅ |
| Все 7 `runtime_status: "DRAFT_MOCK_ONLY_NOT_PUBLISHED"` | Все 7 имеют `active: false` и `MOCK ONLY (SOURCE EXPORT)` в имени | ✅ |
| `logical` узлы S01–S09 / N01–N43 | `VALIDATION.json`: `logical_nodes: 43`, `shared_services: 9`; `NODES.md` содержит ровно 43 заголовка `## N..` и 9 `## S..` | ✅ |
| `pilot.real_provider_enabled: false` | `workflows/*.json` содержат `n8n-nodes-base.code` с `MOCK_ONLY`, ни одного вызова провайдера | ✅ |
| `mock_test.physical_modules_executed: 7` | Проверить нельзя без доступа к n8n-инстансу; принято как заявление репозитория | ⚠️ не проверено |
| `n8n_workflow_id` / `n8n_link` (7 штук) | Проверить нельзя без доступа к `gremovod.app.n8n.cloud`; принято как заявление | ⚠️ не проверено |

**Итог: манифест не лжёт.** Он точен в пределах того, что можно проверить офлайн, и
явно помечает MOCK-статус. Это важный вывод — в проекте нет расхождения между
заявлением и кодом по этому конкретному артефакту.

---

## C-09. Сводка по зрелости

| Компонент | Статус | Доказательство |
|---|---|---|
| 7 JSON-воркфлоу | **MOCK** | `active: false`, `MOCK ONLY (SOURCE EXPORT)`, `Error('MOCK_ONLY')` |
| Оркестрация в 7 модулях (в n8n) | **работает в MOCK** | `mock_test.execution_id: "39"`, `physical_modules_executed: 7` |
| Спецификация 43 узлов + 9 сервисов | **SPEC-ONLY** | `docs/specs/n8n-production-2026-10-19/`, `status: "SPECIFIED_NOT_INTEGRATED"` |
| JSON-схемы контрактов | **SPEC-ONLY** | все три схемы сами помечены `STRUCTURE ONLY` |
| `VALIDATION.json` | **валидирует только структуру документации** | `"scope": "documentation structure only"`, `not_tested: [...]` |
| Манифест | **точен** | сверено 4/4 проверяемых факта |
| Медиа-домены в n8n | **MOCK** | `real_provider_enabled: false`, `real_media_evidence_available: false` |
| Медиа-домены в FastAPI (`main`) | **IMPLEMENTED** | `adapters.py`, `sound.py`, `edit_list.py` — см. `ARCHITECTURE_MAP.md` §4 |
| Адресный ремонт | **работает в MOCK** | `repaired_slot_id: "shot_02"`, `other_shots_reused: true` |
| Бюджет/резерв/лизы в n8n | **SPEC-ONLY** (S04) + **IMPLEMENTED** в P0-контуре PR #29 | две реализации, вопрос их стыковки — OI-05 |
