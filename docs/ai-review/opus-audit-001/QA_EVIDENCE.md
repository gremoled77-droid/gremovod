# QA_EVIDENCE — независимые критики A6 / A7 / A8

> **Важная поправка к исходной постановке задачи.** Реализация A6/A7/A8 находится
> **не в PR #29, #34, #35**, а в отдельной ветке `feature/qa-text-audit-fixes-20261019`
> @ `3979390` — это **PR #8** («[DRAFT] QA TEXT_PRECHECK: audit fixes, isolated FastAPI
> tests, secure A6/A7 connection gate», base `integration/n8n@ce23d7e`, 10 файлов,
> +1343/−1). Ниже это отражено. Файл
> `integrations/n8n/QA_A6_A7_SECURE_CONNECTION_GATE_2026-10-19.md` **не входит в PR #29** —
> проверено: в `pr/29` каталог `integrations/n8n/` содержит ровно два файла
> (`WF_00_WF_06_MANIFEST.json`, `pilot_state_sqlite.py`).

---

## D-00. Карта веток и PR: четыре независимых цепочки

Это не «три PR», а **четыре независимые цепочки PR** плюс `main`:

| PR | Draft | Base | Head | Содержание |
|---|---|---|---|---|
| #8 | да | `integration/n8n@ce23d7e` | `feature/qa-text-audit-fixes-20261019@3979390` | **Реальная реализация A6/A7**, пакеты, вердикты, гейт |
| #17 | да | `codex/n8n-full-production-spec-20261019@cafcbc6` | `feature/n8n-astra-contract-hardening-20261019@cb3f1dc` | Усиление контрактов Astra (18 файлов, +3710/−46) |
| #18 | да | `feature/n8n-astra-contract-hardening-20261019@cb3f1dc` | `feature/p0-studio-foundation-20261019@5206dcc` | P0 + 7 WF (26 файлов, +1751/−4) |
| **#29** | да | `codex/p0-fixes-20261019@fc05caf` | `minimax/p0-budget-authz@c082829` | Единый бюджет, capability, запрет второй БД |
| **#34** | да | `experiment/minimax-kie-argon-bridge-20261019@0ac4e91` | `…impl-20261020@b3183d2` | Бюджетный шлюз → KIE Argon |
| **#35** | да | `main@82adb2d` | `experiment/minimax-observability-20261020@051ab3a` | Временный ревьюер MiniMax (P1, MOCK) |

Всего в репозитории **22 открытых PR, из них 21 — Draft**.

> **Вывод для аудита:** `main` и PR #34/#35 **не содержат ни одного упоминания
> A6/A7/A8** (проверено `git grep -E "\bA[678]\b"` — единственные совпадения в обоих
> случаях — ложные в HTML-файле `docs/official-prompts/wan3-prompting.html`).
> То есть ветка PR #29 — единственная из «трёх», где A6/A7/A8 упомянуты, и там они
> упомянуты **только как спецификация**.

---

## D-01. Где определены A6, A7, A8

### 1.1 Семейство определений A — n8n-манифест и навыки

Ветка `origin/feature/qa-text-audit-fixes-20261019` (и идентичные blob'ы в
`origin/feature/qa-text-precheck-sandbox-20261019`, `origin/integration/n8n`).

**Записи агентов** — `integrations/n8n/agent-manifest.json` (проверено чтением):

| Роль | `key` | `id` | `name` | `model` | `published` | `enabled` |
|---|---|---|---|---|---|---|
| A6 | `"A6"` (`:449`) | `nkmWNxBdJcFEXSMF` (`:450`) | GremoVOD A6 — Независимый критик ТЗ (`:451`) | `anthropic/claude-haiku-5-5` (`:452`) | `false` (`:453`) | `true` (`:475`) |
| A7 | `"A7"` (`:483`) | `NRWXr5AY2MXAFhcH` (`:484`) | GremoVOD A7 — Независимый критик системы и канона (`:485`) | `anthropic/claude-sonnet-5-5` (`:486`) | `false` | `true` (`:525`) |
| A8 | `"A8"` (`:533`) | `s7IIGiioapxre90t` (`:534`) | GremoVOD A8 — Независимый критик ремесла (`:535`) | `anthropic/claude-opus-5-5` (`:536`) | `false` | `true` (`:587`) |

> ⚠️ **`published: false` у всех трёх.** Ни один из «независимых критиков» не
> опубликован в n8n Cloud. Это не мелочь: A8 уже настроен на **Claude Opus 5.5** —
> то есть ровно на той модели, для которой готовится этот аудит. Прямая
> смысловая связь: владелец уже заложил Opus 5.5 как ремесленного критика.
>
> ⚠️ Отдельная запись в блоке `useWhen` (`:74-88`) для A8 содержит
> `"enabled": false` (`:87`) и формулировку «FINISH REVIEW ONLY, DISABLED UNTIL
> TRUSTED EXPERT APPROVAL». То есть A8 отключён **дважды**: как опубликованный агент
> и как разрешённый субагент.

**Навыки-критерии** — по одному на роль (блоб-хэши `7aa2419…` / `b283d1b…` /
`7444844…` одинаковы во всех трёх ветках):

- `skills/gremovod-review-requirements/SKILL.md` (A6)
- `skills/gremovod-review-system/SKILL.md` (A7)
- `skills/gremovod-review-craft/SKILL.md` (A8)

**Формат вердикта** — `PASS | FAIL | BLOCKED`, одинаково во всех трёх навыках,
в `integrations/n8n/THREE_CRITICS_LOOP.md:71` («BLOCKED не считается PASS») и
`integrations/n8n/QA_EVIDENCE_POLICY.md:23`.

**Изоляция как требование** — `SPECIFICATION.md:92` (pr/29):
> «Для всех режимов: критик получает только артефакт, свою часть требований/канона/bar
> и минимальные ID; не получает историю изготовления, самооценку автора и вердикт
> другого критика. … Три финальных пакета ссылаются на одинаковый checksum файла.»

### 1.2 Семейство определений B — спецификация production (pr/29)

`docs/specs/n8n-production-2026-10-19/SPECIFICATION.md:25-27`:
> `| A6 | Независимое соответствие заданию | Не судит по вкусу и не чинит собственноручно |`
> `| A7 | Независимая согласованность мира, образов и непрерывности | Не дописывает канон ради оправдания результата |`
> `| A8 | Независимое ремесло по явным критериям и доступному материалу | Не объявляет просмотр по описанию; не получает бюджет сам от себя |`

`NODES.md:357-385` — узлы N36/N37/N38. У всех трёх:
> `- **Реализация:** ROLE_ONLY.`

Это прямая пометка автора: **в спецификации эти узлы — роли, а не реализация.**

### 1.3 Проверка гипотезы «A8 не определён»

Гипотеза **опровергнута**: A8 определён в двух независимых местах (n8n-навык +
production-спецификация). Чего у A8 нет — это **реализации**, а не определения.

---

## D-02. Что критик реально получает

### 2.1 Реальная точка сборки пакета

`backend/qa_text_precheck.py` (только в ветке PR #8). Проверено чтением:

```python
ROLES = ('REVIEW-REQ', 'REVIEW-SYSTEM')
ROLE_MODELS = {'REVIEW-REQ': 'mock-a6-v1', 'REVIEW-SYSTEM': 'mock-a7-v1'}
```

```python
def role_package(snapshot, job, role):
    common = {'task_id': job['id'], 'project_id': job['project_id'],
              'artifact_id': snapshot['artifact_id'], 'artifact_revision': snapshot['artifact_revision'],
              'review_round': 1, 'review_phase': 'TEXT_PRECHECK', 'requested_scopes': ['TEXT'],
              'artifact_text': snapshot['artifact_text'], 'text_sha256': snapshot['text_sha256'],
              'model': ROLE_MODELS[role], 'mock_only': True, 'quality_claim': False,
              'source_provenance': snapshot['source_provenance']}
    if role == 'REVIEW-REQ':
        return {**common, 'role': role, 'approved_requirements': snapshot['requirements'],
                'brief_revision': snapshot['brief_revision']}
    return {**common, 'role': role, 'approved_canon': snapshot['canon'],
            'canon_revision': snapshot['canon_revision']}
```

Четыре свойства, видимые прямо в коде:
1. `mock_only: True` — пакет **сам декларирует**, что модель моковая.
2. `quality_claim: False` — пакет не претендует на подтверждение качества.
3. `requested_scopes: ['TEXT']` — **только текст**.
4. A6 получает `approved_requirements`, A7 получает `approved_canon` — **роли разведены
   на уровне данных**, чужой материал в пакет не попадает.

### 2.2 Что входит в снимок

`context()` собирает: `artifact_text` (текст текущих сцен), `requirements`
(карточки story-plan + исходная идея), `canon` (текст `projects.state.characters[].identity`),
и четыре хэша: `artifact_revision`, `brief_revision`, `canon_revision`, `text_sha256`.

Проверено: в снимке жёстко зашито
```python
'canon_images_reviewed': False
```
и стоит защита от раздувания:
```python
if any(len(snapshot[k]) > 150000 for k in ('artifact_text', 'requirements', 'canon')):
    raise HTTPException(422, 'QA text snapshot is too large')
```

### 2.3 Таблица «заявлено vs реализовано»

| # | Заявлено (цитата) | Реализовано (цитата) | Разрыв |
|---|---|---|---|
| 1 | `SPECIFICATION.md:92` — «критик получает только артефакт, свою часть требований/канона/bar и минимальные ID» | `role_package()` — `artifact_text` + (`approved_requirements` **или** `approved_canon`) + 4 хэша + `mock_only`/`quality_claim` | **СОВПАДАЕТ** для A6/A7 в TEXT. `bar` отсутствует. A8 — пакета нет |
| 2 | A7 `SKILL.md:10` — «реквизит, одежду, цвет, географию кадра, continuity» | В пакете **нет ни кадра, ни изображения, ни URL**; `canon_images_reviewed: False` | **НЕВОЗМОЖНО** проверить визуальные критерии |
| 3 | A7 `SKILL.md:19` — канон должен иметь серверные `approved=true`, `canon_revision`; «не принимать свободный текст как окончательное изменение канона» | `canon` = `state['characters'][*]['identity']` — **свободный текст**, редактируемый пользователем, без флага `approved` | **ПРОТИВОРЕЧИТ** собственной спецификации |
| 4 | A8 `SKILL.md:13` — «При отсутствии исходного рендера, bar.md, нужных кадров/таймкодов — вернуть BLOCKED» | A8 не имеет роли в `ROLES`, не имеет модели, `Verdict.role` его не принимает; n8n-узел A8 жёстко отдаёт `verdict:'BLOCKED'` | **ОТСУТСТВУЕТ** полностью |
| 5 | `SPECIFICATION.md:92` — «Три финальных пакета ссылаются на одинаковый checksum файла» | `pr/29:workflows/WF_05_Assembly_And_Critics.json:30` — `reviewers:['A6','A7','A8'].map(role=>({role,verdict:'BLOCKED',reason:'MOCK_MEDIA_NOT_REAL'}))` | **MOCK** — ни checksum, ни пакета, ни критика |
| 6 | `THREE_CRITICS_LOOP.md:7` — «три логически независимых критика» | FastAPI агрегирует **2** вердикта (`len(reviews) == 2`); n8n требует 2 для TEXT_PRECHECK, 3 для FINAL_MEDIA | **ПРОТИВОРЕЧИЕ** — бэкенд сводит двойку, спека требует тройку |
| 7 | `QA_EVIDENCE_POLICY.md:16` — «`PASS(TEXT)` никогда не повышает статус `IMAGE`/`VIDEO` до `PASS`» | `requested_scopes: tuple[Literal['TEXT']]`, `checked_scopes: list[Literal['TEXT']]`, `verify_verdict` — «Only TEXT scope is supported» | **СОВПАДАЕТ** — реально обеспечено типами |
| 8 | Гейт `:47` — «Machine-check JSON schema и точные цитаты против замороженного серверного текста» | `verify_verdict` перепроверяет `source[ev.start:ev.end] != ev.quote` → 422 | **РЕАЛИЗОВАНО** — сильнейший контроль в проекте |

### 2.4 Второй путь: жёстко зашитые BLOCKED

| Файл:строка | Что делает |
|---|---|
| `pr/29:workflows/WF_05_Assembly_And_Critics.json:30` | `reviewers:['A6','A7','A8'].map(role=>({role,verdict:'BLOCKED',reason:'MOCK_MEDIA_NOT_REAL'}))` — проверено чтением |
| `pr/29:tools/mock_evidence.py:60` | `"role_reviews":[{"role":x,"verdict":"BLOCKED","reason":"NO_REAL_USER_MEDIA_OR_APPROVED_CAPABILITY"} for x in ("A6","A7","A8")]` — проверено |
| `pr/29:tools/mock_media_pilot.py:143` | `"A6_A7_A8":"BLOCKED_NOT_REAL_USER_MEDIA"` |
| `pr/29:integrations/n8n/pilot_state_sqlite.py:246` | `roles=("A6","A7","A8")` — **метки**, ни к чему не привязаны |
| `pr/29:db/schema.sql:101` | `roles_expected TEXT NOT NULL DEFAULT 'A6,A7,A8'` — **метки** |
| `pr/29:integrations/n8n/WF_00_WF_06_MANIFEST.json:145` | ключ `"A6_A7_A8"` |

**Проверка через тест (главное доказательство):**
`pr/29:backend/test_mock_evidence.py:29-30`:

```python
self.assertEqual({r["role"] for r in evidence["role_reviews"]},{"A6","A7","A8"})
self.assertTrue(all(r["verdict"]=="BLOCKED" for r in evidence["role_reviews"]))
```

Тот же тест фиксирует `motion_evaluated: False`, `final_release_approved: False`,
`stt: "BLOCKED_STT_NOT_AVAILABLE"`.

> **Вывод: единственный исполняемый путь, порождающий вердикты A6/A7/A8, выдаёт
> BLOCKED по всем трём ролям. Механизма, способного выдать PASS или FAIL
> для A6/A7/A8 по медиа-критериям, в репозитории нет.**

---

## D-03. Может ли критик технически проверить свой критерий

| Роль | Критерий | Что реально в пакете | Вердикт |
|---|---|---|---|
| **A6** (ТЗ) | «Для каждого критерия указать наблюдаемое подтверждение из фактического артефакта… PASS только при доказанном выполнении всех обязательных критериев» | полный `artifact_text` + `approved_requirements` + ревизии; цитаты перепроверяются по байтам | **ЧАСТИЧНО** — текстовые требования проверить может; требования к длительности/формату/lip-sync/порядку событий в артефакте — нет (нет медиа) |
| **A7** (канон) | «идентичность, ВАЗ-2106, ракурсы и ориентация дверей, реквизит, одежда, цвет, географию кадра, continuity»; «Если визуальная проверка нужна, но кадр не предоставлен, BLOCKED» | текст + `approved_canon` = **свободный текст** из состояния проекта; ни кадра, ни флага `approved`, `canon_images_reviewed: False` | **НЕ МОЖЕТ** — визуальные критерии недостижимы; и сам канон не является утверждённым набором правил |
| **A8** (ремесло) | «сравнить с открываемым образцом и утверждённым bar.md с 5–7 механиками… BLOCKED без рендера, bar.md, кадров/таймкодов» | **ничего** | **НЕ МОЖЕТ** — входного пакета не существует |

### 3.1 Особая оговорка про A7

Политика проекта (`QA_EVIDENCE_POLICY.md:3`) фиксирует ровно тот отказ, который
A7 воспроизводит в текущей реализации: «A7 сравнил тексты; никакого реального
автомобиля, кадра или видео не существовало». То есть A7, как он реализован,
делает **именно то, чего политика запрещает** — но формально это «PASS(TEXT)»,
который политика отдельно запрещает превращать в `IMAGE`/`VIDEO` PASS.

> **Вопрос аудитору:** является ли «A7 сравнил текст и выдал PASS» приемлемым
> результатом, если его собственная спецификация (`SKILL.md:19`) требует
> утверждённого серверного канона, а вход — свободный текст?

### 3.2 Следствие для «трёхкритического» гейта

Поскольку A8 не даёт **никакой** проверочной способности, а бэкенд агрегирует
**два** вердикта, фактически «трёхкритический независимый гейт» — это
**двухкритический текстовый гейт**. Он fail-closed и не пропускает ложное качество —
но это не тот гейт, который описан.

---

## D-04. Гейт безопасного соединения A6/A7

Файл `integrations/n8n/QA_A6_A7_SECURE_CONNECTION_GATE_2026-10-19.md` — **только** в
`origin/feature/qa-text-audit-fixes-20261019` (PR #8). В `pr/29` его нет.

### 4.1 Что документ утверждает

`:2` — «19.10.2026 · implementation notes · **NOT a live AI integration**».
`:13-17` — «**Hard blocker: network topology.** Cloud n8n cannot access GremoVOD's
*loopback-only* sandbox service route. Do not open the Windows FastAPI port on the
internet, do not put bearer secrets in GitHub, and do not claim the existing n8n
Cloud QA workflow is connected.»

### 4.2 Что реально обеспечено кодом

| Контроль | Где | Сила |
|---|---|---|
| Service API только с loopback | `qa_text_precheck.py` `service()` — HMAC-сравнение Bearer-токена, затем `remote_access.is_loopback(request)` → 403 | **Реально, принудительно** |
| Токен из окружения, ≥32 символов | `service()`: `secret = os.environ.get('STUDIO_QA_SANDBOX_TOKEN','')`; `if len(secret) < 32 or not project_id:` → отказ | **Реально** |
| Владелец ≠ сервис | «Bearer service credentials cannot create approvals, even if browser cookie supplied» | **Реально** |
| Отвержение устаревшей ревизии | `is_current()` → 409 `STALE_REVISION`; перепроверка при выдаче пакета и при приёме вердикта | **Реально** |
| Перепроверка цитат по байтам | `verify_verdict` — `source[ev.start:ev.end] != ev.quote` → 422 | **Реально** — ядро антифабрикации |
| Изоляция чужих цитат | «Evidence from another reviewer is forbidden» | **Реально** |
| Согласованность вердикт↔scope | `verify_verdict` | **Реально** |
| Лимит тела колбэка 32 КБ | `QACallbackBodyLimit` | **Реально** |
| Идемпотентность, один вердикт на роль | `PRIMARY KEY(job_id,role)`, `UNIQUE(job_id,event_id)` | **Реально** |
| Fail-closed агрегация | 2 ответа: FAIL ⇒ `CHANGES_REQUESTED`, BLOCKED ⇒ `BLOCKED`, иначе `SANDBOX_TEXT_PRECHECK_PASSED_AWAITING_OWNER` | **Реально** |
| **Транспорт n8n → FastAPI** | — | **НЕ реализовано** |
| **Живой вызов Agent** | — | **НЕ реализовано** |
| **Серверное разрешение стоимости** | только `Literal[0]` | **НЕ реализовано** |
| **Инспекция медиа / coverage-receipts** | — | **НЕ реализовано** |

### 4.3 Что гейт доказывает и чего не доказывает

**Доказывает:** серверная часть fail-closed QA-API — настоящая и покрыта тестами.
Удалённый вызывающий не достучится; подтверждения выдаёт только владелец; устаревшие
входы отвергаются; **выдуманные цитаты отвергаются побайтовой сверкой** с
замороженным серверным текстом. Изоляция ролей подлинна на уровне данных: A6
физически не видит канон, A7 физически не видит требования.

**Не доказывает:** по собственным словам документа (`:71-76`):
> «A successful GitHub CI run proves code compatibility in sandbox. It does not prove
> real saved Agents can be invoked or guarantee provider billing stops. A8/Opus, paid
> calls, public webhook publication, and main merge are OUT OF SCOPE until separate
> explicit authorization.»

При этом «соединительная» половина гейта не реализована вовсе: `:11` —
«`n8n-nodes-base.messageAnAgent` и его Tool-аналог помечены **deprecated/retired**;
не строить production-зависимость ни на одном из них». `QA_FASTAPI_CONNECTION_HANDOFF.md:12`:
«Не выдумывать URL /agents/{id}/chat». `QA_ORCHESTRATOR_IMPLEMENTATION.md:3`:
«**Доступ к QA через сам workflow по-прежнему отсутствует.**»

И отдельно: `QA_FASTAPI_CONNECTION_HANDOFF.md:10` — единственная попытка живого
вызова A6 **провалилась**: «A6 при одном предпринятом ручном Preview вернул
**execution_failed после 3 внутренних попыток с AI_APICallError/Internal error**.
Повтор не выполняли. **Вывод: работоспособность A6 не подтверждена.**»

> **Вывод:** гейт в названии («secure **connection**») не имеет реализации, которую
> можно было бы протестировать. Реализована и работает **серверная половина**.

---

## D-05. Карта упоминаний A6/A7/A8

### 5.1 ОПРЕДЕЛЕНИЕ (задаёт роли)

- `integrations/n8n/agent-manifest.json:449,483,533` — ключи ролей; `:452,:486,:536` — модели; `:74-88` — мандаты `useWhen`
- `skills/gremovod-review-requirements/SKILL.md` — критерии A6 + формат вердикта
- `skills/gremovod-review-system/SKILL.md` — критерии A7
- `skills/gremovod-review-craft/SKILL.md` — критерии A8
- `docs/specs/n8n-production-2026-10-19/SPECIFICATION.md:25-27, 79-86, 88-94` (pr/29)
- `docs/specs/n8n-production-2026-10-19/NODES.md:357-385` (pr/29) — с пометкой `Реализация: ROLE_ONLY`
- `docs/specs/.../contracts/final-runtime-v1_2.schema.json:319-321, 423-429, 600-602` — enum ролей и вердиктов (pr/29)
- `integrations/n8n/THREE_CRITICS_LOOP.md`, `QA_EVIDENCE_POLICY.md`, `contracts/qa-reviewer-output-v1.schema.json`

### 5.2 ВЫЗОВ (исполняет или подставляет вердикт)

- `backend/qa_text_precheck.py` — пакеты A6/A7 (`role_package`), приём вердиктов, агрегация (PR #8)
- `integrations/n8n/workflows/qa-orchestrator.safe-draft.snapshot.json` — узлы A6/A7/A8, **жёсткий BLOCKED**, LLM-узла нет
- `pr/29:workflows/WF_05_Assembly_And_Critics.json:30` — жёсткий BLOCKED
- `pr/29:tools/mock_evidence.py:60`, `tools/mock_media_pilot.py:143` — жёсткий BLOCKED
- `pr/29:integrations/n8n/pilot_state_sqlite.py:246`, `db/schema.sql:101` — **только метки**

### 5.3 ТОЛЬКО ПРОЗА (упоминание в документе без кода) — **главная находка**

**В pr/29 — 18 файлов, 40+ строк:**
`AGENT_BUILD_MANUAL.md:45,55` · `STATUS.md:23` · `db/README.md:51` ·
`docs/AUTORUN_6_STAGES_REPORT.md:24,42` · `docs/CODEX_DECISIONS.md:28,47` ·
`docs/CODEX_NEXT_ACTIONS.md:13,57` · `docs/CODEX_REVIEW_PACKET.md:34` ·
`docs/agent_handoffs/minimax-p0-budget-authz.md:28,89` ·
`docs/specs/n8n-production-2026-10-19/ASTRA_FIXES_V1_1.md:35,53,57` ·
`…/ASTRA_TEST_MATRIX_2026-10-19.md:15,48` · `…/HANDOFF.md:23,31` ·
`…/IMPLEMENTATION_AND_ACCEPTANCE.md:26,62,95` · `…/N34_N41_RUNTIME_MODEL_MATRIX.md:15,25,26,28,53` ·
`…/NODES.md:554` · `…/README.md:22,36` · `…/REVIEW_GPT_ASTRA.md:9` ·
`…/SCENARIO_SKILLS_N01_N11.md:19,35,38,68,74` · `…/SPECIFICATION.md:9,59-61,88,90,92,181,184,186` ·
`…/contracts/scenario-preprod-v1.schema.json:303-304` ·
`…/contracts/scenario-skills-routing-v1.json:97` · `…/nodes.json:111,113,162,229,316,462,596,655,770-790,850,862,1114-1116`

**Другие ветки:**
`origin/chatgpt/n8n-web-skill-sync-20261019:TODO.md:11` · `docs/TODO_N8N_WEB_SKILL_SYNC_2026-10-19.md:21,29` ·
`origin/codex/n8n-api-contract:TODO.md:11` · `integrations/n8n/README.md:48` ·
`origin/coordination/agent-roles-handoff-20261019:docs/CODEX_DECISIONS.md:27` · `docs/CODEX_NEXT_ACTIONS.md:9` ·
`origin/experiment/beta-gateway-first-20261019:beta/DECISIONS.md:7` · `beta/EXPERIMENT_PROTOCOL.md:3,14` · `beta/README.md:7,17` ·
`origin/feature/qa-text-audit-fixes-20261019:integrations/n8n/QA_A6_A7_SECURE_CONNECTION_GATE_2026-10-19.md:10,44-49` ·
`QA_ORCHESTRATOR_IMPLEMENTATION.md:41-42,51-52` · `QA_FASTAPI_CONNECTION_HANDOFF.md:7-13,17-45`

### 5.4 Три проза-упоминания, которые стоит проверить в первую очередь

1. **`SPECIFICATION.md:184`** — «E2E demo: 8 узлов, … два Gemini role prompts A6/A7,
   проверка цитат, owner gate.» + `ASTRA_TEST_MATRIX:15` — живой workflow
   `2DllTVkrO6imk2IR`, execution #33 с A1/A6/A7 в Gemini Gateway.
   **Ни workflow-JSON, ни конфигурации агента, ни кода этого пути нет ни в одной
   ветке репозитория.** Это единственное место, где настоящий A6/A7 мог реально
   отработать, — и оно **недоступно для аудита** из этого репозитория.
2. **`SPECIFICATION.md:186`** — «A8 остаётся на Sonnet» vs
   `agent-manifest.json:536` — `"model": "anthropic/claude-opus-5-5"`.
   **Прямое противоречие внутри проекта.** Что авторитетно — не определяется.
3. **`SPECIFICATION.md:92`** («три финальных пакета») vs `qa_text_precheck.py`
   (агрегация двух) — противоречие спека↔код.

---

## D-06. Контракт вердикта

Существуют **три независимых контракта вердикта. Ни один не free-text. Ни один не
интероперабелен между собой.**

### 6.1 QA reviewer output v1 — контракт A6/A7/A8

`integrations/n8n/contracts/qa-reviewer-output-v1.schema.json`:
- `role` enum `["REVIEW-REQ","REVIEW-SYSTEM","REVIEW-CRAFT"]`
- `verdict` enum `["PASS","FAIL","BLOCKED"]`
- `scope` enum `["TEXT","IMAGE","VIDEO","AUDIO"]`
- `evidence_type` enum `["text_quote","image_observation","video_frame","video_segment","audio_observation","transcript_quote","trusted_metadata"]`
- `additionalProperties: false` на верхнем уровне и на каждом evidence
- `title`: «GremoVOD QA reviewer observation v1 (**UNTRUSTED MODEL OUTPUT**)»

**Машино-ли? НЕТ.** Код, загружающий этот файл, в репозитории **отсутствует**;
`TODO.md:439` содержит незакрытый пункт «Реализовать в FastAPI … QA reviewer JSON Schema».

### 6.2 Фактически принудительный контракт — Pydantic в FastAPI

`backend/qa_text_precheck.py`:
- `role: Literal['REVIEW-REQ','REVIEW-SYSTEM']` — **REVIEW-CRAFT не принимается**
- `requested_scopes: tuple[Literal['TEXT']]`, `checked_scopes: list[Literal['TEXT']]`
- `scope_results: dict[Literal['TEXT'], Literal['PASS','FAIL','BLOCKED']]`
- `verdict: Literal['PASS','FAIL','BLOCKED']`
- `model_used: Literal['mock-a6-v1','mock-a7-v1']`
- `estimated_cost_usd: Literal[0]`, `actual_cost_usd: Literal[0]`
- `artifact_revision: str = Field(pattern=r'^[0-9a-f]{64}$')`

Плюс семантическая валидация в `verify_verdict()`: согласованность вердикт↔scope;
`PASS ⇒ evidence ∧ ¬missing_inputs`; `FAIL ⇒ evidence ∧ biggest_gap`;
`BLOCKED ⇒ missing_inputs ∧ ¬evidence`; запрет цитат из чужой роли;
перепроверка цитат; требование хотя бы одного наблюдения из самого артефакта.

**Это строгий enum + семантика — не free-text.** И он **строже и уже** JSON-схемы:
только TEXT, две роли, только mock-модели.

### 6.3 Контракт pr/29

`final-runtime-v1_2.schema.json`: `verdict` enum `["PASS","FAIL","BLOCKED"]`;
`role` enum `["A6","A7","A8"]`; `role_verdict_refs` требует все три;
`verified_by_trusted_backend`. **Только спецификация** — исполняющего кода нет,
`WF_05` жёстко отдаёт BLOCKED.

### 6.4 Контракт pr/35 `dev-run-summary/1` — **пересечения с A6/A7/A8 нет**

`tools/ai_review/contract.py` (проверено):
- `CONTRACT_VERSION = "dev-run-summary/1"`
- `MODES = ("MOCK","OFFLINE","LIVE")`
- `TEST_STATUSES = ("PASS","FAIL","NOT_RUN","UNKNOWN")`
- `REVIEW_STATUSES = ("PASS","FINDINGS","UNCERTAIN","API_ERROR","QUOTA_EXHAUSTED","STALE_REVIEW","NOT_RUN")`
- `OWNER_DECISIONS = ("PENDING","APPROVED","REJECTED")`, `SEVERITIES = ("P1","P2","P3")`
- Проверка enum через `_check_enum`, валидация `validate_summary`, семантика
  (PASS ⇒ пустые findings; тесты FAIL ⇒ review ≠ PASS; MOCK/OFFLINE ⇒ нулевая стоимость;
  STALE_REVIEW ⇒ `reviewed_sha`; NOT_RUN/QUOTA_EXHAUSTED/API_ERROR ⇒ owner PENDING)

`tools/ai_review/payload.py` — ревьюер получает **дифф git**, а не медиа:
`build_payload(scope, files, diff, diff_sha256, base_sha, head_sha, tests_status)`.

> **Контракты `dev-run-summary/1` и A6/A7/A8 — ортогональны и не пересекаются.**
> `dev-run-summary/1` не содержит `role`, `scope_results`, `evidence[]`.
> Он **не может** валидировать медиа-вердикт A6/A7/A8.

---

## D-07. Сводка по зрелости критиков

| Агент | Статус | Обоснование |
|---|---|---|
| **A6** | **PARTIAL** | Пакет строится и выдаётся (`role_package`, `GET …/packet/{role}`); enum + семантика вердикта принудительны; изоляция ролей реальна; CI есть. **Но** `model_used: Literal['mock-a6-v1','mock-a7-v1']`, `mock_only: True`; транспорта в n8n нет; единственная живая попытка A6 провалилась (`AI_APICallError` × 3). Медиа-критерии недостижимы. **Реальный, корректно fail-closed текстовый ревьюер без LLM за ним.** |
| **A7** | **PARTIAL — не может проверить собственный критерий** | Пакет и канон подаются; один ручной Preview вернул FAIL на синтетическом каноне. **Но**: в пакете нет кадра/медиа; `canon_images_reviewed: False`; канон — свободный текст, что `SKILL.md:19` прямо запрещает. **A7 в текущей реализации сравнивает два текста — ровно тот отказ, который политика писалась, чтобы пресечь.** |
| **A8** | **ABSENT (только определение)** | Нет роли в `ROLES`, нет модели, `Verdict.role` его не принимает; n8n-узел жёстко BLOCKED; `agent-manifest.json:453,486,536` — `published: false`; `NODES.md:385` — `Реализация: ROLE_ONLY`; `SPECIFICATION.md:90` — «выключен». **Определение есть, реализации ноль.** |
| **Трёхкритический гейт в целом** | **PARTIAL** | Бэкенд агрегирует **2** вердикта; спека требует **3**. С A8, не дающим ничего, «трёхкритический независимый гейт» — это **двухкритический текстовый гейт**. Fail-closed, но не тот гейт, который заявлен. |
| **Гейт безопасного соединения (серверная часть)** | **IMPLEMENTED** | loopback+токен; owner/service separation; отвержение устаревших ревизий; побайтовая сверка цитат; лимит 32 КБ; идемпотентность; fail-closed агрегация |
| **Гейт безопасного соединения (транспортная часть)** | **SPEC-ONLY** | `messageAnAgent` deprecated/retired; «Доступ к QA через сам workflow по-прежнему отсутствует» |
| **`qa-reviewer-output-v1.schema.json`** | **SPEC-ONLY** | Не загружается кодом; в `TODO.md:439` как нереализованный пункт |
| **pr/29 WF_00–WF_06 и `dev-run-summary/1`** | **MOCK / ОРТОГОНАЛЬНО** | `WF_05` жёстко BLOCKED; в `main` и pr/35 — **ноль** упоминаний A6/A7/A8; pr/35 валидирует только дифф-ревью |

---

## D-08. Что осталось неизвестным (для аудита, не для владельца)

1. **Живой путь A6/A7 в n8n Cloud невидим репозиторию.** `SPECIFICATION.md:184` +
   `ASTRA_TEST_MATRIX:15` ссылаются на workflow `2DllTVkrO6imk2IR` (execution #33,
   A1/A6/A7 в Gemini Gateway). **Ни JSON, ни конфигурации агента, ни кода в репозитории
   нет.** Это единственное место, где настоящий A6/A7 мог отработать, и оно недоступно
   для аудита из репозитория. Материальное слепое пятно.
2. **Инструкции агентов в n8n не синхронизированы с Git.** `agent-manifest.json`
   фиксирует ID и skill-ID, `syncStatus: "manual-copy"`. Текст навыка в Git может
   отличаться от задеплоенного текста инструкции.
3. **Противоречие по модели A8 не разрешено:** `SPECIFICATION.md:186` — «на Sonnet»,
   `agent-manifest.json:536` — Opus 5.5. Что авторитетно — не определяется.
4. **Живая работоспособность A6 неизвестна:** единственная попытка — 3× `AI_APICallError`;
   в `QA_FASTAPI_CONNECTION_HANDOFF.md:10` отмечено, что возможные списания по
   ошибочным попыткам неизвестны.
5. **Метки `A6,A7,A8` в `db/schema.sql:101` и `pilot_state_sqlite.py:246` — это
   метки.** Ничто их не привязывает к модели, промпту или пакету.
6. **Ни один тестовый набор PR #8 в этом пакете не запускался** (ветка вне трёх
   рассматриваемых PR). Статусы в §D-07 основаны на чтении кода, а не на прогоне.
   → Это входит в объём AUDIT-001C.

---

## D-09. Рекомендуемая следующая проверка (для владельца, не обязательна)

Единственный артефакт, которого нет больше нигде, — **серверный утверждённый
канонический регламент с настоящим `canon_revision`** плюс **media-inspection
receipt** (`source_asset_id` + таймкод), выпускаемый FastAPI. После этого
`qa_text_precheck.py` должен отказываться собирать пакет A7 без такого регламента
(и любой пакет A8 — до его появления). Пока `canon_images_reviewed` жёстко `False`,
а `checked_scopes` ограничен `['TEXT']`, A7 и A8 остаются структурными заглушками
независимо от того, сколько документов их описывает.
