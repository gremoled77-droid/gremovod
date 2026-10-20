# P0_EVIDENCE — деньги, авторизация, SQLite, состояния, восстановление

**Ревизия:** PR #29, head `c082829b11b968965600bdaf87c137b1485a0fa2`
(ветка `minimax/p0-budget-authz`), base `codex/p0-fixes-20261019` @ `fc05cafe9…`.
**НЕ в `main`.** Все строки ниже — из этого ref, проверено чтением файла.
Ничего из PR #34/#35 сюда не подмешано.

Коммиты PR #29 поверх base:
```
c082829 docs(p0): зафиксировать модель подключения Argon (KIE, chat only, разовый diff-review)
baad79c docs(p0): уточнить диапазон ревью Argon под лимиты инструмента
cc9204f P0: единый бюджет, серверные capability-власти и запрет второй БД
```
> Замечание к гигиене PR: тело PR #29 в поле «Head SHA» указывает `cc9204f1…`, тогда как
> фактический head — `c082829b…` (на два коммита впереди). `cc9204f` — реальный предок,
> то есть расхождение — устаревший текст описания, а не расхождение кода. OI-09.

---

## B-01. Авторизация платных операций

**Вердикт: IMPLEMENTED (в PR #29), отсутствует в `main`.**

### Что было сломано (дефект R-05)

Ledger принимал поля доверия **из тела запроса**. `backend/p0_authz.py:29-37`:

```python
# Legacy trust parameters that used to be accepted by the ledger. They are
# ...
LEGACY_TRUST_FIELDS = (
    "trusted_studio_owner",
    "trusted_studio_request_authorization",
    ...
)
```

### Как исправлено

Вместо доверия телу запроса — **серверная HMAC-подписанная capability** с TTL и привязкой
к конкретному запросу. `backend/p0_authz.py:67-101`:

```python
def mint(purpose: str, binding: dict, *, ttl_ms: int = 120_000) -> str:
    ...
    body = json.dumps({"purpose": purpose, "binding": binding,
                       "exp_ms": now_ms() + int(ttl_ms)}, sort_keys=True, separators=(",", ":"))
    signature = _b64(hmac.new(signing_key(), body.encode("utf-8"), hashlib.sha256).digest())
    return f"{_b64(body.encode('utf-8'))}.{signature}"


def verify(token: str, *, purpose: str, binding: dict) -> dict:
    ...
    expected = _b64(hmac.new(signing_key(), body.encode("utf-8"), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise AuthzError("capability signature is not valid")
    ...
    if payload["purpose"] != purpose:
        raise AuthzError("capability was issued for a different purpose")
    if payload["exp_ms"] < now_ms():
        raise AuthzError("capability is expired")
    if payload["binding"] != binding:
        raise AuthzError("capability is bound to a different request")
```

Свойства, которые видны из кода:
- **HMAC-SHA256**, сравнение через `hmac.compare_digest` (защита от timing-атак).
- **TTL по умолчанию 120 000 мс** (2 минуты) — `p0_authz.py:67`, `:104`, `:116`.
- **Привязка к purpose** — capability, выданная на одну операцию, не принимается для другой.
- **Привязка к binding** — не принимается для другого запроса/run/envelope.
- Два типа capability: `mint_owner_capability(run_id, envelope_id, cap_cents, stage, provider, model)`
  (`:103`) и `mint_request_capability(job_id, request_sha, upper_cents)` (`:115`).

### Fail-closed на легаси-поля

`backend/p0_authz.py:124-131`:

```python
def reject_legacy_trust(extra: dict) -> None:
    ...
    offending = sorted(set(extra) & set(LEGACY_TRUST_FIELDS))
    if offending:
        raise AuthzError(
            ...
```

Вызывается из `p0_control.finish_verified` (`p0_control.py:340-343`) — то есть путь
«клиент прислал `provider_evidence_verified: true`» блокируется на входе.

### Открытый вопрос для аудита

`signing_key()` (`p0_authz.py:47`) — как именно выводится ключ? Аудитор должен проверить,
что ключ не попадает в репозиторий и что его отсутствие приводит к отказу, а не к
«работе без подписи».

---

## B-02. Единый бюджет и резервы

**Вердикт: IMPLEMENTED (в PR #29), отсутствует в `main`.**

### Два слоя бюджета

1. **Legacy-слой** — `backend/spend_ledger.py`, USD-флаты, лимиты проекта и дня.
2. **P0-слой** — `backend/p0_control.py` + таблицы `p0_budget_envelopes` / `p0_jobs`.
   На **входе** суммы целочисленные центы. Но `check_cents()` сразу приводит их
   к float через `cost_cents / 100` (`backend/spend_ledger.py:122-126`), и дальше
   сравнение идёт в float-арифметике.
   **Правка после аудита GPT-6 Astra:** прежняя формулировка «целые центы,
   никогда не float» была **неверной**.

`spend_ledger.py:113-126`:

```python
def check(db, project_id: str, cost_usd: float) -> None:
    """Raise BudgetExceeded when the combined ledger would pass a cap."""
    value = state(db, project_id)
    if value["project_reserved_usd"] + cost_usd > value["project_limit_usd"] + 1e-9:
        raise BudgetExceeded("Превышен серверный бюджет проекта. Измени лимит в разделе «Экономика».")
    if value["daily_reserved_usd"] + cost_usd > value["daily_limit_usd"] + 1e-9:
        raise BudgetExceeded("Превышен дневной серверный бюджет. Измени лимит в разделе «Экономика».")


def check_cents(db, project_id: str, cost_cents: int) -> None:
    """Cent-precise variant for the P0 ledger, which never handles floats."""
    if type(cost_cents) is not int or cost_cents < 0:
        raise BudgetExceeded("cost in integer cents is required")
    check(db, project_id, cost_cents / 100)
```

### Сведение двух слоёв

`spend_ledger.py:89-110` — `state()` складывает legacy и P0:

```python
    p0_project = sum((r["reserved_cents"] + r["spent_cents"]) / 100 ...)
    p0_daily   = sum((r["reserved_cents"] + r["spent_cents"]) / 100 ...)
    ...
    "project_reserved_usd": round(legacy_project + p0_project, 6),
    "daily_reserved_usd":   round(legacy_daily + p0_daily, 6),
    "legacy_reserved_usd":  round(legacy_project, 6),
    "p0_reserved_usd":      round(p0_project, 6),
```

То есть **общий лимит считается по объединённой сумме** — P0 не может потратить сверх
капа, обходя legacy-учёт. Это ключевое свойство, и оно выглядит корректно.

### Резерв как отдельная сущность

Резерв отражается в `p0_budget_envelopes.reserved_cents` и списывается **только**
подтверждённым терминальным событием (`p0_control.py:364-366`):

```python
db.execute("""UPDATE p0_budget_envelopes SET reserved_cents=reserved_cents-?,
      spent_cents=spent_cents+? WHERE envelope_id=?""",
      (j["reserve_cents"], charged_cents, j["envelope_id"]))
```

### Потолок резерва

`p0_control.py:359-363`:

```python
if charged_cents > j["reserve_cents"]:
    raise Blocked("provider cost exceeds reserved ceiling, manual reconciliation")
e = _one(db, "SELECT * FROM p0_budget_envelopes WHERE envelope_id=?", (j["envelope_id"],))
if e["reserved_cents"] < j["reserve_cents"]:
    raise Conflict("reserve missing")
```

Провайдер не может списать больше, чем зарезервировано; превышение → ручная сверка,
а не тихое списание.

---

## B-03. Идемпотентность, состояние UNKNOWN, восстановление

**Вердикт: IMPLEMENTED (в PR #29). Это самая сильная часть контура.**

### Машина состояний задачи

`backend/p0_control.py` — состояния `p0_jobs.state`:

```
INTENT_CREATED ──authorize()──► AUTHORIZED ──begin_submit()──► SUBMITTING
                                                                    │
                              ┌─────────────────────┬───────────────┘
                              ▼                     ▼
                       accept_provider_id()   mark_unknown()
                              │                     │
                              ▼                     ▼
                          SUBMITTED              UNKNOWN
                              │                    (терминально, не возобновляемо)
                    finish_verified() ─────────────┘
                        │              │
                        ▼              ▼
                   COMPLETED        FAILED
```

### UNKNOWN — «потерянный ack»

`p0_control.py:308-316`:

```python
def mark_unknown(db, *, job_id):
    """Lost acknowledgement: NEVER re-send, NEVER free reserved money without proof."""
    with atomic(db):
        j = _one(db, "SELECT state FROM p0_jobs WHERE job_id=?", (job_id,))
        if j["state"] != "SUBMITTING":
            raise Conflict("ambiguous submit only after SUBMITTING")
        db.execute("""UPDATE p0_jobs SET state='UNKNOWN',possible_charge=1,
            lease_owner=NULL,lease_until_ms=NULL,state_version=state_version+1,
            updated_at_ms=? WHERE job_id=?""", (now_ms(), job_id))
```

Три свойства:
1. **Никогда не переотправляется.** `claim_job` (`p0_control.py:272-284`) требует
   `state == "AUTHORIZED"`; UNKNOWN туда не попадает:
   ```python
   if j["state"] != "AUTHORIZED" or j["state_version"] != expected_version:
       raise Conflict("job not safe to claim (UNKNOWN is NEVER resumable)")
   ```
2. **Деньги не освобождаются без доказательства.** Резерв остаётся зарезервированным;
   освобождает его только верифицированное терминальное событие.
3. **Блокирует новые попытки по слоту.** `p0_control.py:194-202`:
   ```python
   def _block_unresolved_attempt(db, job):
       ... AND (state IN ('AUTHORIZED','SUBMITTING','SUBMITTED','UNKNOWN','CANCEL_REQUESTED')
   ```
   То есть после UNKNOWN по тому же `run_id`/`slot_id`/`kind` новая попытка не создаётся.

### Дедупликация терминальных колбэков

`p0_control.py:331-372`:

```python
def finish_verified(db, *, job_id, event_id, event_body, charged_cents,
                    provider_success, verify_evidence=None, **legacy):
    """Backend checks provider authenticity; duplicated terminal callbacks do not recharge.

    `verify_evidence` is a server-side callable that authenticates the
    provider event. The ledger never accepts a boolean that says "this event is
    genuine": a caller could simply set it. Legacy
    `provider_evidence_verified` is refused.
    """
```

Ключевое:
- `verify_evidence` — **обязательный серверный callable** (`:344-347`):
  ```python
  if not callable(verify_evidence):
      raise Blocked("server-side provider evidence verification is required")
  if verify_evidence(event_body) is not True:
      raise Blocked("provider evidence not verified by backend")
  ```
- Повтор с тем же `event_id` → `return False`, повторного списания нет (`:353-356`).
- **Тот же `event_id` с другим payload → `Conflict("event ID reused with changed payload")`** (`:355`).
- Финальная стоимость не может превысить резерв (`:359`).

### Атомарность

`p0_control.py:104-105`:

```python
def atomic(db):
    db.execute("BEGIN IMMEDIATE")
```

`BEGIN IMMEDIATE` — общий патч-лок на запись, снимает read-modify-write гонку на
счётчиках бюджета. Соединение открывается с `isolation_level=None`
(`p0_control.py:59`), то есть autocommit-режим — транзакции явные.

---

## B-04. Параллельные задачи и гонки

**Вердикт: IMPLEMENTED с оговоркой (см. «Что осталось открытым»).**

### Оптимистичная блокировка по версии

`state_version` инкрементируется на каждое изменение состояния
(`p0_control.py:250-251`, `:266-267`, `:282-283`, `:304-305`, `:314-316`, `:326-328`, `:367-371`).
Проверка версии — в `claim_run` / `claim_job` / `begin_submit`.

### Лиза с владельцем и сроком

`p0_control.py:255-270` (`claim_run`) и `:272-286` (`claim_job`):

```python
if r["state_version"] != expected_version or r["status"] not in ("CREATED","RUNNING","PAUSED"):
    raise Conflict(...)
if r["lease_owner"] and r["lease_until_ms"] and r["lease_until_ms"] > t:
    raise Conflict("job lease already owned")
```

`lease_ms=120000` по умолчанию. Истечение лизы → `lease_until_ms <= t` → лиза берётся заново.

### Защита от повторной отправки

`p0_control.py:288-306` (`begin_submit`):

```python
"""Transition persisted to SUBMITTING before HTTP POST; caller makes at most one POST."""
...
if (j["state"] != "AUTHORIZED" or j["state_version"] != expected_version or
        j["lease_owner"] != worker or (j["lease_until_ms"] or 0) <= t or j["submit_count"] != 0):
    raise Conflict("not authorized, lease expired or already submitted")
...
db.execute("""UPDATE p0_jobs SET state='SUBMITTING',submit_count=1, ...""")
```

`submit_count` выставляется в 1 **до** HTTP POST. Это и есть «не более одного POST»:
состояние `SUBMITTING` персистится раньше, чем провайдер увидел запрос.

### Что осталось открытым (вопрос аудитору)

1. **Лиза на 2 минуты может истечь, пока провайдер «думает».** Тогда `begin_submit`
   для этого же job упадёт на `lease_until_ms <= t`, но **уже после** того, как первый
   POST ушёл. Идемпотентность на стороне провайдера в контуре не прослеживается.
   Нужен ли провайдерский idempotency-key?
2. **`claim_run` и `claim_job` — разные лизы.** `claim_run` берёт лизу на run, `claim_job`
   — на job. Не проверяется ли, что владелец job-лизы согласован с владельцем run-лизы.
3. **Окно между `submit_count=1` и реальным POST.** Если процесс умирает после
   `begin_submit`, но до POST — задача навсегда в `SUBMITTING`/`UNKNOWN`, и деньги
   зарезервированы, хотя провайдер их не списал. Требуется процедура сверки
   (`provider_job_id` пуст, `possible_charge=1`).

---

## B-05. Запрет второй рабочей SQLite

**Вердикт: IMPLEMENTED (в PR #29).**

### Единая точка правды о пути

`backend/studio_db.py:1-10` (докстринг):

> Single source of truth for the Studio SQLite path. … The Studio database is the one
> database; every other path is … The Studio path mirrors backend/main.py:
> `(STUDIO_DATA_DIR or backend/) / "studio.sqlite3"`

`backend/studio_db.py:24-32`:

```python
def studio_db_path() -> Path:
    ...
    base = Path(data).resolve() if data else ROOT
    return (base / "studio.sqlite3").resolve()

def is_studio_db(path: Path | str) -> bool:
    ...
    return Path(path).resolve() == studio_db_path()
```

### Fail-closed проверка

`backend/studio_db.py:37-51`:

```python
def resolve(path: Path | str, *, allow_disposable: bool = False) -> Path:
    """Return the resolved database path or refuse a shadow state.

    `allow_disposable` exists for tests and for explicitly disposable copies
    of the Studio database. It must never be set on a production code path.
    """
    resolved = Path(path).resolve()
    ...
    if allow_disposable:
        return resolved
    raise ShadowState(
        ...
        f"({studio_db_path()}); a second writable database is not allowed: {resolved}"
    )
```

И обёртка, превращающая отказ в `Blocked` — `backend/p0_control.py:49-63`:

```python
def open_db(path: Path | str, *, allow_disposable: bool = False) -> sqlite3.Connection:
    """Open the Studio SQLite. A second writable database is refused.
    ...
    """
    try:
        resolved = studio_db.resolve(path, allow_disposable=allow_disposable)
    except studio_db.ShadowState as exc:
        raise Blocked(str(exc)) from None
    db = sqlite3.connect(str(resolved), timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=10000")
    return db
```

### Аудит escape hatch

Проверено по всему `pr/29`: `allow_disposable=True` встречается **только** в
тест-файлах и в `scripts/p0_migrate.py` (который требует бэкап). В боевом пути
`p0_control.open_db` флаг не выставляется. Проверка выполнена поиском по
`backend/*.py`, `integrations/n8n/*.py`, `scripts/*.py`.

### Согласованность с n8n-пилотом

`integrations/n8n/pilot_state_sqlite.py` (изменён в PR #29, +21 строка) использует тот же
`studio_db.resolve(...)` и отказывается открывать не-Sstudio БД. Именно это требование
зафиксировано в `docs/agent_handoffs/minimax-p0-budget-authz.md:89`:

> ролям A6–A8 и по выдаче capability создал бы второй путь к деньгам.

---

## B-06. Защита от повторного платного запроса

**Вердикт: IMPLEMENTED на уровне контура PR #29; на `main` — отсутствует.**

Собранные вместе меры:

| Мера | Где | Что даёт |
|---|---|---|
| Capability с TTL 120 c | `p0_authz.py:67-101` | Клиентская подпись не бессрочна |
| Capability привязана к `request_sha` | `p0_authz.py:115-121` | Нельзя переиспользовать на другой payload |
| Legacy-поля доверия отвергаются | `p0_authz.py:124-131` | Клиент не может сам объявить себя доверенным |
| `submit_count` = 1 до POST | `p0_control.py:296-305` | Не более одного HTTP POST на задачу |
| `state != INTENT_CREATED` → Conflict | `p0_control.py:228-229` | Повторная авторизация невозможна |
| Запрет второй попытки по слоту | `p0_control.py:244-249` | Не более одного платного задания на слот |
| UNKNOWN блокирует новые попытки | `p0_control.py:194-202` | После неопределённого исхода — стоп |
| Дедупликация по `event_id` | `p0_control.py:353-356` | Повторный колбэк не списывает дважды |
| `event_id` с другим payload → Conflict | `p0_control.py:355` | Защита от подмены |
| Резерв выше потолка → Blocked | `p0_control.py:359-360` | Локальный ledger **не примет** сумму выше резерва. **Это не значит, что провайдер не спишет больше** — это лишь отказ локально учесть долг. Реальное превышение остаётся на балансе провайдера, а в ledger возникает расхождение |

> ⚠️ **Второй путь к деньгам.** На `main` платные вызовы идут через
> `adapters` + `main.py:460-472`, минуя весь P0-контур. То есть перечисленные меры
> защищают **только** путь PR #29. Пока P0 не в `main`, `main` не защищён.
> Это главный вопрос аудита: **как гарантируется, что P0-контур не будет обойдён**
> после мержа? `p0_provider_dispatch.py` (PR #29) — вероятный кандидат на единый шлюз;
> аудитору нужно проверить, что он действительно закрывает `main`-путь.

---

## B-07. Заморозка плана и манифеста

**Вердикт: IMPLEMENTED (в PR #29).**

`p0_control.py:375-407` (`freeze_manifest`) — полный доверенный план замораживается
**до** того, как существуют задачи или поставки медиа:

- список слотов валидируется: `{'slot_id','kind','required'}`, `kind` из закрытого набора
  `{'shot','voice','sfx','music','ambience','title','reference','other'}`, `required` — строго `bool`;
- дубликаты `slot_id` запрещены (`:388-389`);
- `source_revision` должен совпасть, иначе `Conflict("stale manifest source")` (`:393-394`);
- манифест **иммутабелен** для данного source (`:397-400`);
- заморозка запрещена, если уже есть задачи или сцены (`:401-405`).

> Аудитору: стоит проверить, покрывает ли `freeze_manifest` тот случай, когда
> владелец меняет канон **после** заморозки, но **до** завершения задач —
> `p0_jobs` привязан к `source_revision`, но не видно, что делает `finish_verified`
> с задачей, чей source устарел.
>
> **Уточнение GPT-6 Astra:** финансовое завершение задачи и приёмка артефакта по
> текущему канону должны быть **независимы** — оплаченный старый результат может
> быть непригоден к новому канону, и это не обязано быть ошибкой оплаты.

---

## B-08. Сводка P0-компонентов

| Компонент | Статус | Тест |
|---|---|---|
| HMAC capability, TTL, привязка, fail-closed | IMPLEMENTED | `backend/test_p0_budget_authz.py` |
| Отвержение legacy-полей доверия (R-05) | IMPLEMENTED | `backend/test_p0_budget_authz.py` |
| Единый бюджет (legacy + P0, USD + центы) | IMPLEMENTED | `backend/test_p0_budget_authz.py`, `backend/test_budget_release.py` |
| Резерв / списание / потолок | IMPLEMENTED | `backend/test_p0_budget_authz.py` |
| Идемпотентность, дедуп по `event_id` | IMPLEMENTED | `backend/test_p0_regressions.py` |
| UNKNOWN: нет переотправки, нет освобождения | IMPLEMENTED | `backend/test_p0_control.py`, `backend/test_p0_regressions.py` |
| `submit_count` — не более одного POST | IMPLEMENTED | `tests/test_p0_state.js` |
| Запрет второй БД (`studio_db.resolve`) | IMPLEMENTED | `backend/test_p0_migrate.py` |
| Лиза + `state_version` | IMPLEMENTED | `backend/test_p0_control.py` |
| `BEGIN IMMEDIATE` (атомарность) | IMPLEMENTED | косвенно, во всех тестах |
| Заморозка манифеста | IMPLEMENTED | `backend/test_p0_control.py` |
| Сведение P0 с `main`-путём к провайдерам | **MISSING** | — |
| Провайдерский idempotency-key | **MISSING** | — |
| Процедура сверки «зависших» в SUBMITTING/UNKNOWN | **MISSING** | — |
| Ключ подписи capability: происхождение и отсутствие → отказ | **не проверено** | — |
| Происхождение capability (кто и с каким полномочием выдаёт) | **не проверено** | — |
| Связь verified event с `job_id`/стоимостью/успехом | **не проверено** | — |
| Транспортные retry ниже state machine | **не исследовано** | — |
| Переход через полночь: дневная семантика лимита | **не раскрыта** | — |

> Последние четыре строки — **вопросы к аудитору**, а не утверждения об отсутствии
> (код не изучался настолько детально, чтобы утверждать). Первые три строки
> «MISSING» получены из факта отсутствия соответствующих символов в `pr/29`
> (`grep` по `p0_control.py`, `p0_authz.py`, `spend_ledger.py`).
