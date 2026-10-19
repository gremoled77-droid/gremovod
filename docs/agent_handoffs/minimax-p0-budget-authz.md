# MiniMax Code — P0: единый бюджет, серверные права, одна БД

**Дата:** 19.10.2026 · **Статус:** `READY_FOR_ARGON_REVIEW` (не `PRODUCTION_READY`)

**База:** `origin/codex/p0-fixes-20261019` = `fc05cafee9e835cbbc49aff73e50520ba638420e`
(цепочка PR #17 → #18 → #19 плюс уже закрытые R-01…R-03)
**Ветка:** `minimax/p0-budget-authz`
**Diff для ревью:** `fc05cafee9e835cbbc49aff73e50520ba638420e...HEAD`

Работа велась в отдельном worktree `C:\Users\BLOWKA\Documents\Minimax\gremovod-minimax`.
`C:\AI_Workflow_Studio`, рабочая SQLite, медиа, канон и GPT-6 Sol Proxy v2 не изменялись;
venv студии использован только как интерпретатор для тестов, ничего в нём не менялось.

## Матрица: что уже было, что частично, чего нет

| Область | Состояние до | Что сделано | Состояние после |
|---|---|---|---|
| P0-DB: единственный источник истины | **partial** — `p0_*` живут в Studio SQLite, но `pilot_state_sqlite.connect()` и `migrate()` открывали любой файл; вторая writable-БД не запрещена | `backend/studio_db.py`: путь Studio как в `backend/main.py`; `open_db`/`migrate`/`pilot.connect` отказывают второй БД, если не сказано `allow_disposable=True` | **implemented** (fail-closed) |
| P0-AUTH: доверие к телу запроса (R-05) | **missing** — `trusted_studio_owner`, `trusted_studio_request_authorization`, `provider_evidence_verified` принимались как обычные параметры | `backend/p0_authz.py`: серверные capability-токены (HMAC) вместо булевых; legacy-поля отклоняются явно; provider-evidence проверяет серверный callable | **implemented** |
| P0-MONEY: один счётчик расходов (R-04) | **partial** — Studio считал `generation_approvals`/`jobs`, P0 считал `p0_budget_envelopes`; два лимита → второй слой тратит то, что первый ещё разрешает | `backend/spend_ledger.py`: единый счётчик (legacy + P0), `security.py` делегирует ему; `authorize` проверяет общий cap в той же транзакции | **implemented** |
| P0-MANIFEST: полный expected manifest (R-02) | **implemented** в `codex/p0-fixes` | не трогал | implemented |
| Миграция без потери данных (R-03) | **implemented** в `codex/p0-fixes` | добавлен запрет мигрировать не-Studio БД | implemented |
| UNKNOWN после submit, второй POST (R-01) | **implemented** в `codex/p0-fixes` | не трогал | implemented |
| Транспорт медиа Windows→Cloud→Windows (P0-MEDIA) | **missing** | не начат: вне 2–3 P0-дефектов первого этапа | missing |
| HTTP-маршруты P0 и владелец capability (S09) | **missing** | маршрутов нет и не добавлялось: привязка capability требует решения владельца по выдаче capability | missing |
| N34 технический отдельно от N35–N41 (P1-QA) | **partial** | не начат | partial |
| Семь физических WF_00..WF_06 | **partial** — экспорты есть, наполнены mock-нодами | не начат (роль Argon по матрице) | partial |
| Реальный MP4 и художественная приёмка A6/A7/A8 | **blocked** | нет MP4 у владельца | blocked |

## Исправленные дефекты

### 1. R-05 / P0-AUTH — права больше не приходят из тела запроса

Было: `create_envelope(..., trusted_studio_owner=True)` — любой вызывающий мог передать `True`
и получить бюджетное разрешение владельца.

Стало: `backend/p0_authz.py` выдаёт capability (HMAC-SHA256) с привязкой к конкретному
envelope / job / request hash / сумме и сроком жизни. Ledger сам проверяет подпись, срок и
привязку. Поля `trusted_*` из внешнего тела отклоняются с явной ошибкой, а не игнорируются.
Provider-evidence подтверждается серверным callable, а не булевым.

### 2. R-04 / P0-MONEY — один счётчик расходов вместо двух

Было: Studio считал `generation_approvals`/`jobs` по лимитам проекта и суток, P0-конверты
считали свой `cap_cents`. Подключение второго слоя обходило общий лимит.

Стало: `backend/spend_ledger.py` складывает legacy-одобрения и резервы P0-конвертов
(включая деньги, удерживаемые за UNKNOWN) и проверяет общий лимит проекта и суток.
`security.budget_state`/`check_budget` теперь считают через тот же модуль — дублирования нет.
`p0_control.authorize` проверяет общий cap в той же транзакции, что и резерв.

### 3. P0-DB — вторая writable-БД запрещена

Было: `p0_control.open_db()`, `scripts/p0_migrate.py` и reference-пилот открывали любой файл.

Стало: `backend/studio_db.py` — единственный путь Studio (`STUDIO_DATA_DIR`/`backend/studio.sqlite3`,
как в `backend/main.py`). Открыть другую БД можно только явным `allow_disposable=True`
(тесты и одноразовые копии). Reference-пилот дополнительно запрещён в самой Studio SQLite:
его таблицы не должны появляться рядом с пятью `p0_*`.

## Зоны ответственности (межзонное изменение — требует внимания Argon)

`integrations/n8n/pilot_state_sqlite.py` принадлежит зоне Argon по матрице ролей. Изменение
в нём сделано намеренно: это прямой «shadow-state», который ревью R-04 требует удержать
в статусе reference-only (решение №1 в `CODEX_REVIEW_2026-10-19.md`). Правка только убирает
возможность: `connect()` больше не может создать таблицы пилота в Studio SQLite и требует
явного `allow_disposable=True`. Логика пилота не менялась. Файл требует отдельного ревью Argon.

## Проверки (бесплатные, локальные, без провайдеров)

```
python -X utf8 -m unittest backend.test_p0_budget_authz            -> Ran 18 tests, OK
python -X utf8 -m unittest <9 модулей CI из n8n-astra-pilot.yml>    -> Ran 103 tests, OK
python -X utf8 -m unittest discover -s backend -p "test_*.py"      -> Ran 345 tests, OK
node --test tests/test_p0_state.js                                 -> 7 pass, 0 fail
```

Интерпретатор venv студии использован только для чтения; `STUDIO_DATA_DIR` не подменялся на
рабочую базу, тесты работали на временных копиях. Платных вызовов: 0.

## Что НЕ сделано намеренно

- Argon не запускался: LIVE-вызов — только по отдельному подтверждению владельца.
- `main` не тронут, merge не выполнялся, force-push не использовался.
- `STATUS.md` не редактировался: по правилу самого репозитория состояние агента пишется в
  `docs/agent_handoffs/<role>-<task>.md`, чтобы не конфликтовать с координатором.
- `backend/automation.py` не переносился из `codex/n8n-api-contract`: его схема заперта на
  `stage=storyboard / agent_role=A2 / model=echo / estimated_cost=0`, перенос без решения по
  ролям A6–A8 и по выдаче capability создал бы второй путь к деньгам.
- Канон, промпты, workflow-экспорты и `docs/specs/**` не изменялись (роль Argon / владельца).

## ТЗ для Argon (этап 2, отдельным решением владельца)

**Что проверить** — только мой diff, три аспекта:

1. **P0-AUTH.** Capability-токен привязан к правильной сущности и сумме; подделка, протухание
   и переиспользование под другой job/envelope/request отвергаются; legacy-поле `trusted_*`,
   переданное извне, отвергается, а не игнорируется; provider-evidence нельзя «подтвердить»
   булевым флагом.
2. **P0-MONEY.** Legacy-одобрения и резервы P0 складываются в один лимит; резерв после UNKNOWN
   продолжает удерживать деньги; проверка общего cap происходит в той же транзакции, что и резерв;
   `security.py` не дублирует логику счётчика.
3. **P0-DB.** Вторая writable-БД недостижима из production-путей; reference-пилот не может
   создать таблицы в Studio SQLite; тестовый путь требует явного `allow_disposable`.

**Границы ревью**

Полный дифф PR (13 файлов / 70 737 байт) НЕ влезает в лимиты инструмента
(12 файлов / 45 000 байт) - инструмент отказался бы отправлять такой запрос.
Поэтому ревью отправляется по ветке-носителю `minimax/p0-authz-core`:
`fc05cafee9e835cbbc49aff73e50520ba638420e...556f406dfafdfdf1fed602024c4352af3668c6f8`
- 8 файлов / 40 741 байт: ядро доверия, единого бюджета и запрета второй БД плюс новый
  регрессионный набор. Содержимое файлов побайтно совпадает с PR #29; в носителе нет только
  механических правок вызовов в существующих тестах и этого handoff-документа.

- base SHA: `fc05cafee9e835cbbc49aff73e50520ba638420e`
- head SHA (payload): `556f406dfafdfdf1fed602024c4352af3668c6f8`
- SHA-256 диффа: `aa1d8c0baec4040b5ede1cfb4328eb572081e02665de69acf664b1ceab92b938`
- команда: `git diff --unified=3 fc05cafee9e835cbbc49aff73e50520ba638420e...HEAD`
- лимиты: дифф ≤ 45 КБ, ≤ 12 изменённых файлов, без бинарников, без подозрения на секрет
- предварительно: офлайн-предпросмотр и SHA-256 диффа, затем **один** запрос к Argon с ручным
  подтверждением, без retry
- ожидаемый формат ответа: `PROCEED` либо список проблем с приоритетом, доказательством и
  минимальным исправлением; «неуверенно» — если данных не хватает

**Инструмент:** `tools/ai_review/argon_review.py` (ветка `experiment/manual-argon-review-20261019`),
OFFLINE по умолчанию, LIVE требует `--live` + подтверждения + `KIE_API_KEY`.

**Ожидание по деньгам:** ни одного платного вызова не выполнено; до отдельного разрешения
владельца Argon не вызывается.
