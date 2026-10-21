# GA-03 · Release gate: импорт → техническая проверка → решение владельца

**Дата:** 2026-10-21
**Ветка:** `minimax/ga-03-release-acceptance`
**База:** `origin/mavis/work` @ `57cac59`
**Worktree:** `.worktrees/ga-03-release`
**Статус:** план подготовлен. Runtime не изменён. Merge не выполнялся.

**Основание:** D3 из [решений владельца D1–D4](https://github.com/gremoled77-droid/gremovod/blob/decisions/beta-d1-d4-20261021/docs/decisions/2026-10-21-beta-acceptance-D1-D4.md)
(`OWNER_APPROVED`) и GA-03 из [бэклога](https://github.com/gremoled77-droid/gremovod/blob/audit/global-acceptance-20261021/docs/audits/global-acceptance-2026-10-21/06_MINIMAX_TASK_BACKLOG.md).

> **D3 (дословно):** «разнести статусы `imported`, `technical_pass` и `owner_approved`,
> привязать QC и решение к **одному и тому же хешу файла/версии**. Не принимать
> импорт `ready` за разрешение выпуска. Обязательные три платных LLM-критика в
> первую бету не входят. Имеющийся N34/N35 использовать по фактическим контрактам,
> без создания второй системы QA.»

---

## 1. Текущие состояния выпуска — фактическая карта

### 1.1 Что есть

| Слой | Место | Факт |
|---|---|---|
| Импорт мастера | `backend/release_artifacts.py:94-147` `persist_release_artifact` | Пишет `release_artifacts.status = 'ready'` **безусловно** (`:141`) |
| Модель артефакта | `backend/release_artifacts.py:13-27` `ReleaseArtifact` | Поля `status`, `project_revision`, `version_id`, `library_asset_id` есть, но `status` **нигде не читается** |
| Таблица артефактов | `backend/release_artifacts.py:154-168` | `release_artifacts(id, project_id, project_revision, version_id, library_asset_id, title, filename, mime_type, width, height, duration, status, created_at)` |
| Техническая проверка N34 | `backend/media_qc.py:413-457` | `release_artifact_qc(artifact_id PK, project_id, master_sha256, verdict, reason, checks, measurements, observations, signature, created_at)` |
| Вердикты N34 | `backend/media_qc.py:239-240` | `PASS_TECHNICAL` / `FAIL` / `BLOCKED` |
| Хеш мастера | `backend/media_qc.py:31-40` `sha256_file` | Единственная реализация хеша, используется и N34, и N35 |
| Факты о мастере | `backend/media_qc.py:370-410` `master_facts` | **Уже единый источник истины:** `exists`, `path`, живой `sha256`, `qc_verdict`, `measurements`, `observations`, `reason` |
| Заморозка N35 | `backend/qa_reviews.py:46-98` `freeze_media` | Требует `PASS_TECHNICAL` + `processing_rights` + покрытие модальностей → `CONFIRMED` / `PARTIAL` / `BLOCKED` |
| Статус ревью | `backend/qa_reviews.py:223-240` `review_status` | `AWAITING_VERDICTS` / `CHANGES_REQUESTED` / `BLOCKED` / `TEXT_PRECHECK_PASSED_AWAITING_OWNER` / `AWAITING_OWNER_APPROVAL`. **«Решение о выпуске не принимается»** |
| Колонки заморозки | `backend/qa_reviews.py:39-43` `FREEZE_COLUMNS` | `master_sha256`, `media_asset_id`, `qc_verdict`, `snapshot_hash`, `evidence_manifest`, … |
| UI | `frontend/src/StageSummary.tsx:121-170` `ReleaseSummary` | `{releaseArtifacts.length} финальных MP4` (`:158`) — считает **все** импорты, без статуса и без QC |

### 1.2 Чего нет

| Отсутствует | Доказательство |
|---|---|
| Персистентного **решения владельца** | Поиск `owner_approv\|owner_decision\|OWNER_APPROV` по `backend/*.py`: единственное совпадение — строка статуса `AWAITING_OWNER_APPROVAL` в `qa_reviews.py:238-240`. Ни одна таблица и ни один маршрут не фиксируют решение. `p0_control.create_envelope(owner_decision_ref=…)` — про денежные конверты P0, не про выпуск, и модуль не подключён |
| Состояния `technical_pass` | `release_artifacts.status` никогда не читается: grep по `status.*release_artifact\|release_artifacts.*status` даёт 0 совпадений в `backend/` |
| Состояния `owner_approved` | Нет таблицы, нет маршрута, нет поля |
| Привязки решения к хешу | `release_approvals`-подобной таблицы нет; `generation_approvals` — про деньги (`job_id, estimated_usd, max_cost_usd, approved_at, price_basis`, `backend/main.py:58`), не переиспользуется |
| Второго QC-контура | **Не нужно** — N34/N35 уже дают всё: `release_artifact_qc.master_sha256` + `verdict`, `master_facts()` |

### 1.3 Готовый, но не подключённый образец решения владельца

`integrations/n8n/pilot_state_sqlite.py:76-89, 297-317` — пилот n8n уже содержит
ровно ту state machine, которой не хватает студии:

```
validated_final_rounds(run_id, snapshot_sha, master_checksum, status, provenance)
release_decisions(decision_id, run_id, snapshot_sha, owner_id, kind)
ready(run_id PK, snapshot_sha, decision_id UNIQUE)
```

и функцию `owner_ready(...)` с проверками: `owner_session_verified is True`,
`gate_result == 'AWAITING_OWNER_APPROVAL'`, `current_snapshot == snapshot_sha`
(иначе `Conflict('stale owner decision')`), наличие доверенного вердикта
`provenance='trusted_backend_verified'`, коллизия ключа решения → `Conflict`,
уже `READY` с другим решением → `Conflict`.

**Но использовать его как есть нельзя:** это отдельная SQLite-БД (запрещено
правилом «одна БД студии», `backend/studio_db.py:1-14`), модуль не подключён к
FastAPI (`backend/main.py:943-1011` — `pilot_state_sqlite` в списке регистраций
нет) и не содержит N34/N35. Поэтому берём **его семантику** (guards и конфликты),
а данные переносим в студийную БД.

---

## 2. Что переиспользуется без изменений

| Актив | Точное место | Как используется |
|---|---|---|
| `sha256_file()` | `backend/media_qc.py:31` | Единый хеш мастера для QC, решения и чтения |
| `master_facts()` | `backend/media_qc.py:370-410` | Единый источник истины: живой хеш + вердикт QC + измерения |
| `release_artifact_qc` | `backend/media_qc.py:417-428` | Факт технической проверки, уже привязан к `master_sha256` |
| `verdict()` N34 | `backend/media_qc.py:214-240` | `PASS_TECHNICAL` / `FAIL` / `BLOCKED` — вердикт не переизобретаем |
| `freeze_media()` N35 | `backend/qa_reviews.py:46-98` | Показывает, что медиа подтверждается только при `PASS_TECHNICAL`; **остаётся отдельным контуром** |
| `review_status()` | `backend/qa_reviews.py:223-240` | Готовый `AWAITING_OWNER_APPROVAL` — источник для информационного поля read model |
| `persist_release_artifact()` | `backend/release_artifacts.py:94-147` | Импорт и привязка к `project_revision` (`:120-133`) — не переписывается |
| Конфликт ревизии | `backend/release_artifacts.py:123-128` | Тот же 409 `PROJECT_REVISION_CONFLICT` применим к решению владельца |
| Локальная сессия владельца | `backend/security.py:162-189` | Машинные токены допустимы только для `/api/qa/` и `/api/n8n/spend/` (`service_auth.ALLOWED_PREFIXES`), поэтому маршрут под `/api/projects/...` **автоматически только для сессии владельца** |
| Ревизия проекта | `backend/main.py:55-56` | Триггер `AFTER UPDATE OF state,title` → `revision = OLD+1` |
| Фикстура тестов | `backend/test_n35_freeze.py:25-74`, `backend/test_media_qc.py` `sample_mp4` | Готовый каркас: temp-каталог, патчи `DB/LIBRARY_ROOT/MEDIA`, браузерная сессия, импорт мастера, прогон N34 |

---

## 3. Минимальная state machine

**Серверная, вычисляемая.** Клиент не присылает ни одного булева флага: все три
состояния выводятся из сохранённых фактов при чтении.

```
                    импорт MP4 в библиотеку
                              │
                              ▼
                    ┌──────────────────┐
                    │     IMPORTED     │  release_artifacts.status='imported'
                    └────────┬─────────┘  файл в библиотеке, хеш известен
                             │
              N34: PASS_TECHNICAL и хеш совпал
                             │
                             ▼
                    ┌──────────────────┐
                    │  TECHNICAL_PASS  │  release_artifact_qc.verdict='PASS_TECHNICAL'
                    └────────┬─────────┘  и qc.master_sha256 == живой sha256 файла
                             │
              решение владельца, тот же хеш + та же ревизия
                             │
                             ▼
                    ┌──────────────────┐
                    │  OWNER_APPROVED  │  release_approvals: master_sha256 + project_revision
                    └──────────────────┘  (решение живо, пока хеш и ревизия те же)
```

Любое состояние, кроме `OWNER_APPROVED`, **не является выпуском**. Переходы только
вперёд; решение владельца отзывается новым решением (новый `decision_id`), запись
не удаляется.

**Инварианты (нарушение любого → gate не может быть `OWNER_APPROVED`):**

1. `sha256_file(library_file) == release_artifact_qc.master_sha256` — файл не менялся после N34.
2. `release_artifact_qc.verdict == 'PASS_TECHNICAL'`.
3. `release_approvals.master_sha256 == sha256_file(library_file)` — файл не менялся после решения.
4. `release_approvals.project_revision == release_artifacts.project_revision` — решение относится к той же версии проекта, что и импорт.
5. `release_artifacts.project_revision == projects.revision` — проект не менялся после импорта (правило 5 — **решение владельца**, см. §9).

---

## 4. Проверка совпадения SHA, QC и owner approval

### 4.1 Вычисляемый read model (сервер)

```python
# backend/release_gate.py  (новый модуль, без HTTP-обвязки)
def release_gate(studio, project_id, artifact_id) -> dict:
    """Состояние выпуска, вычисленное сервером. Ничего не доверяет клиенту."""
    facts = media_qc.master_facts(studio, project_id, artifact_id)   # media_qc.py:370
    qc = _qc_record_or_none(studio, project_id, artifact_id)         # media_qc.py:322
    approval = _latest_approval(studio, project_id, artifact_id)     # новая таблица
    ...
```

Возвращаемая структура (одна на артефакт):

```json
{
  "state": "IMPORTED | TECHNICAL_PASS | OWNER_APPROVED",
  "master_sha256": "<живой хеш файла>",
  "qc_verdict": "PASS_TECHNICAL | FAIL | BLOCKED | ''",
  "qc_reason": "…",
  "approved_at": "… | null",
  "blocked_reason": "… | null"
}
```

`state` вычисляется строго по инвариантам §3. Любой сбой инварианта даёт
`blocked_reason` с человекочитаемой причиной, а **не** `OWNER_APPROVED`.

### 4.2 Решение владельца

Маршрут: `POST /api/projects/{project_id}/release-artifacts/{artifact_id}/approval`

Тело: `{"decision": "APPROVED" | "REJECTED", "note": "…", "expected_master_sha256": "<hex>"}`

Порядок проверок (fail-closed, каждая даёт свой код):

| # | Проверка | Отказ |
|---|---|---|
| 1 | Сессия владельца (не машинный токен) | 401 — обеспечивается middleware `security.py:182` |
| 2 | Артефакт принадлежит проекту | 404 (`media_qc._artifact`, `media_qc.py:273`) |
| 3 | Файл существует в библиотеке | 409 `MASTER_FILE_MISSING` |
| 4 | `expected_master_sha256 == sha256_file(file)` | 409 `MASTER_CHANGED` — **клиент утверждает именно этот файл** |
| 5 | `release_artifact_qc.verdict == 'PASS_TECHNICAL'` | 409 `QC_NOT_PASSED` |
| 6 | `qc.master_sha256 == sha256_file(file)` | 409 `QC_STALE` — файл менялся после проверки |
| 7 | `release_artifacts.project_revision == projects.revision` | 409 `PROJECT_REVISION_CONFLICT` (тот же код, что `release_artifacts.py:123-128`) |
| 8 | Запись решения с `master_sha256` + `project_revision` | — |

**Клиентский `expected_master_sha256` обязателен.** Это то, что связывает решение
с конкретным файлом: UI показывает хеш, владелец подтверждает именно его. Без
этого поля сервер всё равно проверит хеш, но решение нельзя было бы отличить от
«утвердили что-то другое».

### 4.3 Новая таблица (одна)

```sql
CREATE TABLE IF NOT EXISTS release_approvals (
    decision_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES release_artifacts(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL,
    master_sha256 TEXT NOT NULL,
    project_revision INTEGER NOT NULL,
    decision TEXT NOT NULL,            -- APPROVED | REJECTED
    note TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS release_approvals_artifact
    ON release_approvals(artifact_id, created_at DESC);
```

Одна строка — одно решение; история не удаляется. Последнее решение по артефакту
определяет текущее состояние.

### 4.4 Что НЕ входит в gate

- **Три платных критика** (`qa_reviews`, роли `REVIEW-REQ/REVIEW-SYSTEM/REVIEW-CRAFT`) —
  по D3 в первую бету не входят и **не являются предусловием** approval. Их состояние
  (`review_status`, `AWAITING_OWNER_APPROVAL`) показывается в read model как
  **информационное** поле `qa_state`, но не блокирует.
- Это прямо расходится с `pilot_state_sqlite.owner_ready` (`:298`), где
  `gate_result == 'AWAITING_OWNER_APPROVAL'` — предусловие. Для пилота без
  платных критиков этот гейт недостижим, поэтому копировать его условие нельзя.
- Канон не меняется, художественная оценка не автоматизируется.

---

## 5. Отрицательные тесты

Опора на фикстуру `backend/test_n35_freeze.py:25-74` (temp-БД, браузерная сессия,
`sample_mp4`, импорт мастера, прогон N34).

| # | Сценарий | Ожидание | Точка проверки |
|---|---|---|---|
| N1 | Импорт без QC | `state='IMPORTED'`, `qc_verdict=''`, `blocked_reason='техническая проверка не проводилась'` | read model |
| N2 | QC `FAIL` | `state='IMPORTED'`, `blocked_reason` про `FAIL`; approval → 409 `QC_NOT_PASSED` | `media_qc.verdict` |
| N3 | QC `BLOCKED` | то же, что N2 | |
| N4 | Чужой SHA: файл изменён после N34 | `state` не `OWNER_APPROVED`; approval → 409 `QC_STALE` | `sha256_file` vs `qc.master_sha256` |
| N5 | Чужой SHA: `expected_master_sha256` не совпадает | 409 `MASTER_CHANGED` | проверка №4 |
| N6 | Изменённая ревизия проекта после импорта | approval → 409 `PROJECT_REVISION_CONFLICT` | `projects.revision` |
| N7 | Нет owner approval | `state` ≤ `TECHNICAL_PASS`, `approved_at=null` | read model |
| N8 | Файл мастера пропал с диска | `state='IMPORTED'`, `blocked_reason='файл мастера отсутствует'`; approval → 409 `MASTER_FILE_MISSING` | `master_facts` |
| N9 | Approval посторонний/машинный токен | 401 | `security.py:182` + `service_auth` |
| N10 | Решение по чужому артефакту/проекту | 404 | `_artifact` |
| N11 | `REJECTED` | `state` ≤ `TECHNICAL_PASS`, решение зафиксировано, `approved_at=null` | новая таблица |
| N12 | Повторное открытие проекта и старые артефакты | старые импорты читаются, `state='IMPORTED'`, решение не «протухает» молча | `master_facts` |
| N13 | Файл изменён **после** approval | `state` перестаёт быть `OWNER_APPROVED`, `blocked_reason` про изменение файла | инвариант 3 |
| N14 | Решение, принятое для старой ревизии, после роста `projects.revision` | `state` перестаёт быть `OWNER_APPROVED` | инвариант 5 |
| N15 | UI не показывает «финальный MP4» для неодобренного | счётчик одобренных ≠ счётчик импортов | `StageSummary.tsx` |

Плюс обязательные **позитивные** тесты: правильный хеш + `PASS_TECHNICAL` + approval
→ `OWNER_APPROVED`; повторное открытие сохраняет состояние.

---

## 6. Технический план для Codex

### 6.1 Файлы и минимальные изменения

| Файл | Изменение | Объём |
|---|---|---|
| `backend/release_gate.py` | **НОВЫЙ.** `release_gate(studio, project_id, artifact_id) -> dict`, `approve_release(...)`, `STATE_*` константы. Только чтение фактов + запись решения. Без FastAPI | ~140 строк |
| `backend/release_artifacts.py` | `status` при импорте: `'ready'` → `'imported'` (`:141`); в `artifact_record()` (`:30-33`) добавить поле `gate`; маршрут `POST .../approval`; `CREATE TABLE release_approvals` в `setup()` (`:151-169`) | ~60 строк |
| `backend/test_release_gate.py` | **НОВЫЙ.** N1–N15 + позитивные, на фикстуре `test_n35_freeze` | ~260 строк |
| `frontend/src/StageSummary.tsx` | `useReleaseArtifacts` (`:41-57`) → тип `ReleaseArtifact` получает `gate`; счётчик `:158` — только `OWNER_APPROVED`; строка артефакта показывает состояние и префикс хеша | ~40 строк |
| `frontend/src/releaseGate.test.mjs` | **НОВЫЙ.** Проверка подсчёта одобренных (без React: чистая функция счётчика) | ~50 строк |

**Не трогать:** `backend/media_qc.py` (всё нужное уже есть), `backend/qa_reviews.py`
(контур N35 не меняется), `backend/main.py` (регистрация уже есть —
`release_artifacts.register` в `main.py:967`), `db/schema.sql`, канон, `canon/`,
`skills/`, n8n-workflow'и, тарифы, промпты.

### 6.2 Порядок работ

1. **`backend/release_gate.py`** — чистая логика чтения и вычисления состояния.
   Тест на фикстуре: N1, N2, N3, N7, N8, N12, позитив.
2. **`backend/release_artifacts.py`** — таблица `release_approvals`, маршрут approval,
   `gate` в ответе листинга, `status='imported'`. Тесты: N4–N6, N9–N11, N13, N14.
3. **`frontend/src/StageSummary.tsx`** + `frontend/src/releaseGate.test.mjs` — N15.
4. Прогнать полный набор: `python -X utf8 -m unittest discover -s backend -p "test_*.py"`,
   `npm test`, `npx tsc --noEmit`, `npx vite build`.

### 6.3 Критерии готовности (DoD)

1. `release_artifacts.status` при импорте — `'imported'`; ни один путь не называет импорт выпуском.
2. Read model возвращает `state` из трёх значений и `blocked_reason` с причиной отказа.
3. `OWNER_APPROVED` достижим **только** при выполнении всех пяти инвариантов §3.
4. Approval отклоняется с конкретным кодом (`MASTER_CHANGED` / `QC_NOT_PASSED` / `QC_STALE` / `PROJECT_REVISION_CONFLICT` / `MASTER_FILE_MISSING`), а не общим 400.
5. Решение хранит `master_sha256` и `project_revision`; при изменении файла или ревизии состояние перестаёт быть `OWNER_APPROVED` (N13, N14).
6. UI: «финальных MP4» считает только `OWNER_APPROVED`; импорты без одобрения видны отдельно и не названы финальными.
7. Все N1–N15 и позитивные тесты зелёные; полный набор backend и frontend зелёный.
8. Ни один новый маршрут не вызывает платного провайдера; `n8n` не затронут; канон не изменён.
9. Ветка — `minimax/ga-03-release-acceptance` от зафиксированного SHA `mavis/work`; runtime-код меняется только в перечисленных файлах.

### 6.4 Отрицательные сценарии, которые Codex обязан повторить сам

- N1–N7, N13, N14 — воспроизвести на синтетическом MP4, без платных вызовов.
- Изменить байт в файле мастера после N34 → gate перестаёт быть `OWNER_APPROVED` (N4/N13).
- Сохранить проект (`POST /api/projects` увеличивает `revision`) → approval отклоняется (N6/N14).
- Проверить, что машинный токен не может вызвать approval (N9).
- Проверить в UI, что неодобренный импорт не называется финальным MP4 (N15).

---

## 7. Риски

| Риск | Оценка | Митигация |
|---|---|---|
| Правило 5 (строгое равенство `projects.revision`) слишком строго: любое сохранение проекта после импорта обнуляет approval | **высокая** | Решение владельца (§9). Альтернатива: хранить ревизию импорта и не сравнивать с текущей, тогда approval переживает косметические правки, но не переживает смену канона — тогда нужен отдельный `canon_sha`-якорь из `qa_reviews` |
| Release gate станет «второй системой QA», если добавить свои проверки медиа | средняя | Gate **не мерит** файл: он только читает `release_artifact_qc` и `master_facts`. Никаких новых измерений, никаких новых вердиктов |
| Approval без привязки к хешу превращается в «владелец нажал кнопку» | средняя | `expected_master_sha256` обязателен (проверка №4) и хранится в решении |
| `release_artifacts.status` на старых базах остаётся `'ready'` | низкая | Read model не зависит от этой колонки; при переводе на `'imported'` старые строки читаются как `IMPORTED` по отсутствию QC |
| UI продолжит называть импорты финальными | низкая | Счётчик и подпись переводятся на `gate.state`; N15 |
| Зависимость от GA-04 (манифест областей) | средняя | Ветка GA-03 — `minimax/ga-03-*`: пока манифест не слит в `mavis/work`, scope guard не в силе и ветка не ограничена. После merge GA-04 область `ga-03` уже объявлена в `tools/minimax_task_scopes.json` |

---

## 8. Зависимость от GA-04 (обнаружено при проверке)

Манифест областей (`tools/minimax_task_scopes.json`) появился в ветке GA-04
(`minimax/ga-04-studio-offline-ci`, PR #62) и **ещё не слит в `mavis/work`**.
Следствие: scope guard пока не ограничивает ветку `minimax/ga-03-*` — и это
правильное поведение, а не дыра. Исправлено в GA-04 (`2d00dca`): области вводятся
в силу только когда манифест есть; ветка, созданная раньше манифеста, не
блокируется за собственные файлы.

**Рекомендация владельцу:** слить GA-04 раньше GA-03, иначе область GA-03 не
будет защищена, а ветка GA-03 не попадёт под проверку областей.

---

## 9. Открытые вопросы владельцу

1. **Правило 5 — строгое или мягкое?** Если ревизия проекта после импорта обнуляет
   approval, то любая правка проекта после импорта мастера потребует нового решения.
   Вариант A (рекомендую для пилота): approval привязан к `master_sha256` +
   `project_revision` импорта, а текущая `projects.revision` **не** сравнивается —
   тогда approval переживает косметические правки проекта, но не переживает
   изменение мастера. Вариант B: строгое сравнение с текущей ревизией.
2. **Нужна ли кнопка отзыва решения** (кроме нового `REJECTED`)? `pilot_state_sqlite`
   отзыва не имеет — решение переигрывается новым.
3. **Показывать ли `qa_state` (`AWAITING_OWNER_APPROVAL` и т. п.) в UI** рядом с
   gate-состоянием, учитывая, что платные критики в первую бету не входят?
4. **Кто такой «владелец» в терминах API?** Сейчас это локальная сессия студии
   (`LAUNCH_TOKEN`, `backend/security.py:194`). Нужен ли явный `owner_id` в решении
   (как `release_decisions.owner_id` у пилота) для будущей мульти-пользовательской
   студии, или сейчас достаточно факта «решение принял владелец локальной сессии»?

---

## 10. Границы

Платные запросы не выполнялись. Настоящий master не использовался: все сценарии
описаны на синтетическом MP4 (`backend/test_media_qc.py::sample_mp4`). Канон не
изменялся. `db/schema.sql`, n8n-workflow'и, тарифы и промпты не затронуты.
Runtime в этой ветке **не изменён** — только план. Merge не выполнялся.
