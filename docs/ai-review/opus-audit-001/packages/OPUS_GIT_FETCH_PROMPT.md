# OPUS_GIT_FETCH_PROMPT — промпт для Claude Opus 5.5, который берёт материалы сам

**Назначение.** Отправить аудит Opus 5.5 **без вложений**: репозиторий публичный,
поэтому модель может взять все документы и исходники сама через `web_fetch` по
raw-ссылкам GitHub. Так не нужно ни прикреплять файлы, ни переименовывать их в `.txt`
(причина, по которой `.md`/`.json` не принимались, — в `KIE_SETUP.md` §8).

**Репозиторий:** `https://github.com/gremoled77-droid/gremovod` (public)

**Все ссылки ниже закреплены на конкретной ревизии (SHA).** Это принципиально:
ссылка на имя ветки может уехать, SHA — нет. В ответе Opus должен ссылаться на эти
же SHA, иначе его цитаты невоспроизводимы.

---

## 1. Как это работает

### 1.1 Формат raw-ссылки

```
https://raw.githubusercontent.com/gremoled77-droid/gremovod/<SHA>/<путь-в-репозитории>
```

- `<SHA>` — полный 40-символьный хеш, **не** имя ветки.
- Путь — как в репозитории, с `/`, регистр важен.
- Ответ — сырой текст, ровно то содержимое файла на этой ревизии.

### 1.2 Разрешение ссылок внутри документов

Документы пакета ссылаются друг на друга относительными путями. Правило:

| Внутри файла | Как трактовать |
|---|---|
| `[X.md](X.md)` или просто `X.md` | тот же каталог, **та же ревизия** |
| `[Y.md](../X/Y.md)` | путь вверх от каталога файла, та же ревизия |
| `backend/p0_control.py` | от корня репозитория, та же ревизия |
| ссылка на `main`, `PR #29` и т. п. | **не** открывать: у каждой ревизии свой SHA, см. §2 |

Правило «та же ревизия» критично: в `main` нет P0-контура, в PR #29 нет
реализации A6/A7. Смешивать ревизии — главный риск этого проекта (см. `README.md` §3).

### 1.3 Если инструмента веб-доступа нет

Промпт требует от модели **честно сообщить**, что она не может забрать файлы по
ссылкам, и перечислить, что именно нужно прислать. Это осознанное требование:
молча ответить «по моим сведениям» без единой цитаты — худший исход для аудита.

---

## 2. Таблица ссылок

### Пакет A — AUDIT-001A — P0: деньги, авторизация, SQLite, состояния, восстановление

**Tier 1 — прочитать обязательно**

| ref | путь | raw URL |
|---|---|---|
| `pkg` | `docs/ai-review/opus-audit-001/PROJECT_CONTEXT.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/6c905c7c3b0cb1252360c52ef6ecb035aa04a81f/docs/ai-review/opus-audit-001/PROJECT_CONTEXT.md |
| `pkg` | `docs/ai-review/opus-audit-001/ARCHITECTURE_MAP.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/6c905c7c3b0cb1252360c52ef6ecb035aa04a81f/docs/ai-review/opus-audit-001/ARCHITECTURE_MAP.md |
| `pkg` | `docs/ai-review/opus-audit-001/P0_EVIDENCE.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/6c905c7c3b0cb1252360c52ef6ecb035aa04a81f/docs/ai-review/opus-audit-001/P0_EVIDENCE.md |
| `pkg` | `docs/ai-review/opus-audit-001/TEST_RESULTS.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/6c905c7c3b0cb1252360c52ef6ecb035aa04a81f/docs/ai-review/opus-audit-001/TEST_RESULTS.md |

**Tier 2 — тянуть по мере надобности** (чтобы сверить конкретную цитату из Tier 1 с исходником)

| ref | путь | raw URL |
|---|---|---|
| `pr29` | `backend/p0_authz.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/backend/p0_authz.py |
| `pr29` | `backend/p0_control.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/backend/p0_control.py |
| `pr29` | `backend/spend_ledger.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/backend/spend_ledger.py |
| `pr29` | `backend/studio_db.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/backend/studio_db.py |
| `pr29` | `backend/p0_provider_dispatch.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/backend/p0_provider_dispatch.py |
| `main` | `backend/main.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/82adb2d28efa05bf8face168485fe07ae340e0bc/backend/main.py |
| `main` | `backend/security.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/82adb2d28efa05bf8face168485fe07ae340e0bc/backend/security.py |
| `main` | `backend/remote_access.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/82adb2d28efa05bf8face168485fe07ae340e0bc/backend/remote_access.py |
| `main` | `backend/adapters.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/82adb2d28efa05bf8face168485fe07ae340e0bc/backend/adapters.py |
| `pr29` | `backend/test_p0_budget_authz.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/backend/test_p0_budget_authz.py |
| `pr29` | `backend/test_p0_control.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/backend/test_p0_control.py |
| `pr29` | `backend/test_p0_regressions.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/backend/test_p0_regressions.py |
| `pr29` | `tests/test_p0_state.js` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/tests/test_p0_state.js |

### Пакет B — AUDIT-001B — n8n-конвейер, контракты, маршруты, артефакты

**Tier 1 — прочитать обязательно**

| ref | путь | raw URL |
|---|---|---|
| `pkg` | `docs/ai-review/opus-audit-001/PROJECT_CONTEXT.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/6c905c7c3b0cb1252360c52ef6ecb035aa04a81f/docs/ai-review/opus-audit-001/PROJECT_CONTEXT.md |
| `pkg` | `docs/ai-review/opus-audit-001/WORKFLOW_EVIDENCE.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/6c905c7c3b0cb1252360c52ef6ecb035aa04a81f/docs/ai-review/opus-audit-001/WORKFLOW_EVIDENCE.md |
| `pkg` | `docs/ai-review/opus-audit-001/P0_EVIDENCE.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/6c905c7c3b0cb1252360c52ef6ecb035aa04a81f/docs/ai-review/opus-audit-001/P0_EVIDENCE.md |

**Tier 2 — тянуть по мере надобности** (чтобы сверить конкретную цитату из Tier 1 с исходником)

| ref | путь | raw URL |
|---|---|---|
| `pr29` | `workflows/WF_00_Core_Infra.json` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/workflows/WF_00_Core_Infra.json |
| `pr29` | `workflows/WF_05_Assembly_And_Critics.json` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/workflows/WF_05_Assembly_And_Critics.json |
| `pr29` | `workflows/WF_06_Repair_Router.json` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/workflows/WF_06_Repair_Router.json |
| `pr29` | `integrations/n8n/WF_00_WF_06_MANIFEST.json` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/integrations/n8n/WF_00_WF_06_MANIFEST.json |
| `pr29` | `integrations/n8n/pilot_state_sqlite.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/integrations/n8n/pilot_state_sqlite.py |
| `pr29` | `docs/specs/n8n-production-2026-10-19/SPECIFICATION.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/docs/specs/n8n-production-2026-10-19/SPECIFICATION.md |
| `pr29` | `docs/specs/n8n-production-2026-10-19/NODES.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/docs/specs/n8n-production-2026-10-19/NODES.md |
| `pr29` | `docs/specs/n8n-production-2026-10-19/nodes.json` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/docs/specs/n8n-production-2026-10-19/nodes.json |
| `pr29` | `docs/specs/n8n-production-2026-10-19/VALIDATION.json` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/docs/specs/n8n-production-2026-10-19/VALIDATION.json |
| `pr29` | `docs/specs/n8n-production-2026-10-19/N34_N41_RUNTIME_MODEL_MATRIX.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/docs/specs/n8n-production-2026-10-19/N34_N41_RUNTIME_MODEL_MATRIX.md |
| `pr29` | `docs/specs/n8n-production-2026-10-19/contracts/final-runtime-v1_2.schema.json` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/docs/specs/n8n-production-2026-10-19/contracts/final-runtime-v1_2.schema.json |
| `pr29` | `docs/specs/n8n-production-2026-10-19/contracts/runtime-v1.schema.json` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/docs/specs/n8n-production-2026-10-19/contracts/runtime-v1.schema.json |
| `pr29` | `tools/mock_evidence.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/tools/mock_evidence.py |
| `pr29` | `db/schema.sql` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/db/schema.sql |

### Пакет C — AUDIT-001C — независимые критики, результаты проверок, согласованность

**Tier 1 — прочитать обязательно**

| ref | путь | raw URL |
|---|---|---|
| `pkg` | `docs/ai-review/opus-audit-001/PROJECT_CONTEXT.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/6c905c7c3b0cb1252360c52ef6ecb035aa04a81f/docs/ai-review/opus-audit-001/PROJECT_CONTEXT.md |
| `pkg` | `docs/ai-review/opus-audit-001/QA_EVIDENCE.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/6c905c7c3b0cb1252360c52ef6ecb035aa04a81f/docs/ai-review/opus-audit-001/QA_EVIDENCE.md |
| `pkg` | `docs/ai-review/opus-audit-001/TEST_RESULTS.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/6c905c7c3b0cb1252360c52ef6ecb035aa04a81f/docs/ai-review/opus-audit-001/TEST_RESULTS.md |
| `pkg` | `docs/ai-review/opus-audit-001/OPEN_ISSUES.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/6c905c7c3b0cb1252360c52ef6ecb035aa04a81f/docs/ai-review/opus-audit-001/OPEN_ISSUES.md |

**Tier 2 — тянуть по мере надобности** (чтобы сверить конкретную цитату из Tier 1 с исходником)

| ref | путь | raw URL |
|---|---|---|
| `pr08` | `backend/qa_text_precheck.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/3979390/backend/qa_text_precheck.py |
| `pr08` | `integrations/n8n/agent-manifest.json` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/3979390/integrations/n8n/agent-manifest.json |
| `pr08` | `integrations/n8n/QA_A6_A7_SECURE_CONNECTION_GATE_2026-10-19.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/3979390/integrations/n8n/QA_A6_A7_SECURE_CONNECTION_GATE_2026-10-19.md |
| `pr08` | `integrations/n8n/THREE_CRITICS_LOOP.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/3979390/integrations/n8n/THREE_CRITICS_LOOP.md |
| `pr08` | `integrations/n8n/QA_EVIDENCE_POLICY.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/3979390/integrations/n8n/QA_EVIDENCE_POLICY.md |
| `pr08` | `integrations/n8n/contracts/qa-reviewer-output-v1.schema.json` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/3979390/integrations/n8n/contracts/qa-reviewer-output-v1.schema.json |
| `pr08` | `skills/gremovod-review-requirements/SKILL.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/3979390/skills/gremovod-review-requirements/SKILL.md |
| `pr08` | `skills/gremovod-review-system/SKILL.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/3979390/skills/gremovod-review-system/SKILL.md |
| `pr08` | `skills/gremovod-review-craft/SKILL.md` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/3979390/skills/gremovod-review-craft/SKILL.md |
| `pr08` | `backend/test_qa_text_precheck.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/3979390/backend/test_qa_text_precheck.py |
| `pr29` | `tools/mock_evidence.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/tools/mock_evidence.py |
| `pr29` | `backend/test_mock_evidence.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/backend/test_mock_evidence.py |
| `pr29` | `backend/test_n8n_final_routing_spec.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/backend/test_n8n_final_routing_spec.py |
| `pr29` | `integrations/n8n/pilot_state_sqlite.py` | https://raw.githubusercontent.com/gremoled77-droid/gremovod/c082829b11b968965600bdaf87c137b1485a0fa2/integrations/n8n/pilot_state_sqlite.py |

---

## 3. System prompt (в поле `system`)

```
Ты — независимый архитектурный аудитор с жёстким стандартом доказательности.
Ты работаешь в роли senior-архитектора, который провёл 15+ лет ревью
production-систем, в которых утечка бюджета или гонка данных стоили реальных денег.

## Как ты получаешь материал
У тебя есть инструмент веб-доступа. Все материалы лежат в публичном GitHub-репозитории
gremoled77-droid/gremovod и доступны по raw-ссылкам, приведённым в сообщении.
Каждая ссылка закреплена на конкретной ревизии (SHA) — читай именно её, не подставляй
имя ветки. Прочитанное содержимое файлов — единственный источник фактов.

Правила получения материала:
- Прочитай все файлы Tier 1 до того, как начнёшь отвечать. Это обязательный минимум.
- Файлы Tier 2 тяни по мере надобности: когда проверяешь конкретную цитату или
  утверждение из Tier 1 — возьми соответствующий исходник и сверь. Не качай всё подряд.
- Если в документе есть ссылка на другой файл, и она тебе нужна для вывода, —
  перейди по ней, разрешив относительный путь от каталога текущего файла и сохранив
  ту же ревизию (SHA).
- Не смешивай ревизии. В main нет P0-контура, в PR #29 нет реализации A6/A7,
  в PR #8 нет спецификации конвейера. Если утверждение верно только для одной
  ревизии — так и напиши, с указанием ревизии.
- Если файл по ссылке не открылся или вернул ошибку — скажи это прямо и назови
  файл. Не восстанавливай его содержимое по памяти и не додумывай.
- Если у тебя нет инструмента веб-доступа — не притворяйся, что ты прочитал файлы.
  Напиши: «инструмент недоступен, вот что нужно прислать», и перечисли ровно те
  файлы Tier 1, которые требуются. Частичный разбор с честной оговоркой лучше
  полного разбора по памяти.

## Стандарт доказательности (обязателен)
1. Каждое утверждение о поведении системы подкрепляй ссылкой на файл и строки.
   Формат: `путь@SHA:строка`. Если код не проверен — пиши «не проверено».
2. Не достраивай отсутствующее. Нет файла — «файл не найден», нет поведения в коде —
   «поведение не найдено». Молчаливый додум — худший вид ошибки в аудите.
3. Различай четыре зрелости и всегда указывай, к какой относишь вывод:
   IMPLEMENTED (исполняемый код это делает) / PARTIAL (код есть, но не весь случай) /
   SPEC-ONLY (описано в спецификации, исполнения нет) / MOCK (заглушка).
4. Зелёный тест — не доказательство отсутствия дефекта, а свидетельство, что заявленный
   сценарий не сломался. Тест, проверяющий заглушку, доказывает только, что заглушка
   работает.
5. В проекте намеренный fail-closed (нет доказательства = BLOCKED, а не «пройдено»).
   Это сильное решение; оценивай, соответствует ли оно цели, а не то, что это есть.
6. Проектируй как владелец денег: цена вопроса — сколько реальных кредитов может уйти
   мимо учёта, при каких гонках и кто может это вызвать.

## Правило ответа на текущий вопрос (обязательно, приоритетно)
Каждое входящее сообщение — новая точка отсчёта. Отвечай на ТОТ вопрос, который
задан сейчас, а не на тот, который ты разбирал в прошлый раз.
1. Определи, о чём спрашивают, и ответь на это; на не заданное не перескакивай.
2. Не начинай с «как я уже говорил», «как отмечал выше». Предыдущий ответ — не вводная.
3. Не продолжай начатое ранее рассуждение. Каждый ответ считай написанным с нуля.
4. Прежний ответ не является ни основанием, ни контекстом по умолчанию. Факты бери
   из материалов, а не из памяти о диалоге. Нет в материалах — «в материалах нет».
5. Возвращаться к предыдущему ответу можно только если: (а) владелец прямо попросил;
   (б) владелец указал на ошибку; (в) текущий вопрос прямо на него ссылается.
6. Если текущий вопрос противоречит твоему прежнему ответу — не защищай прежний вывод,
   пересчитай и прямо скажи: «это меняет мой прежний вывод, потому что…».
7. Каждый ответ пригоден как самостоятельный документ: предмет (файл, узел, PR, SHA)
   называй заново, без отсылок «выше».
8. Общие выводы прошлого раунда, если верны, приводи заново с обоснованием.

## Формат ответа
По каждому пункту вопросов:
- Вердикт одной строкой: IMPLEMENTED / PARTIAL / SPEC-ONLY / MOCK / MISSING / RISK
  + одно предложение-обоснование.
- Доказательства: `путь@SHA:строка` и минимальные верные фрагменты кода. Если кода
  нет — приведи текст спецификации, который его заменяет, и пометь это.
- Что осталось открытым: что именно ты не смог проверить и почему.
- Рекомендация: одна-две строки, начинающиеся с «Исправить:» или «Проверить:».

Чего не делать: не писать вводных абзацев, не пересказывать проект, не хвалить ради
объёма, не выдумывать имена файлов, номера строк и результаты тестов, не считать
количество страниц мерой качества.

## Ограничение по расходу
Ты вызываешься один раз на пакет. Автоматических повторов нет. Сформулируй ответ за
один проход. Если данных не хватило — запроси их явным списком в конце ответа,
а не догадывайся.
```

---

## 4. User message (в `messages[0].content`)

Ниже — шаблон. Подставьте нужный пакет (A, B или C) и **его список Tier 1**.
Блок вопросов берите из соответствующего `packages/AUDIT-001X.md` (разделы
«Текст запроса»).

```
Ты — независимый архитектурный аудитор. Ниже — список файлов, которые ты должен
прочитать сам, по ссылкам. Содержимое файлов — единственный источник фактов.

РЕВИЗИИ (каждая ссылка закреплена на своей ревизии; не смешивай их):
- pkg  = 6c905c7c3b0cb1252360c52ef6ecb035aa04a81f  — пакет аудита
- pr29 = c082829b11b968965600bdaf87c137b1485a0fa2  — PR #29, P0-контур и спецификация n8n
- pr08 = 3979390                                  — PR #8, реализация A6/A7
- main = 82adb2d28efa05bf8face168485fe07ae340e0bc — main
- pr34 = b3183d2a0e22d5414ab7eef70d62543aa991dfa — PR #34
- pr35 = 051ab3a1182c1ed954b53c9b64f85e8195dbcc91 — PR #35

ФОРМАТ ССЫЛКИ: https://raw.githubusercontent.com/gremoled77-droid/gremovod/<SHA>/<путь>

<<< СЮДА ВСТАВИТЬ СПИСОК TIER 1 ВЫБРАННОГО ПАКЕТА >>>

<<< СЮДА ВСТАВИТЬ ВОПРОСЫ ИЗ packages/AUDIT-001X.md >>>

Требования к ответу — в system prompt. Главное: каждое утверждение о поведении
системы сопровождай ссылкой `путь@SHA:строка`; если код не проверен — пиши
«не проверено»; в конце дай топ-5 рисков по убыванию ожидаемой стоимости и явный
список недостающих данных.
```

---

## 5. Как включить веб-доступ в запросе к KIE

### Вариант A — серверный инструмент Anthropic (рекомендуемый)

```json
{
  "model": "claude-opus-5-5",
  "max_tokens": 16000,
  "stream": false,
  "tools": [
    { "type": "web_fetch_20250910", "name": "web_fetch", "max_uses": 20 }
  ],
  "system": "<текст system prompt из §3>",
  "messages": [
    { "role": "user", "content": "<текст user message из §4>" }
  ]
}
```

> `max_uses` — потолок загрузок за один вызов. Для пакета A: 4 файла Tier 1 плюс
> несколько проверочных из Tier 2 — 20 достаточно. Для пакета C файлов больше,
> поставьте 25.

### Вариант B — свой инструмент `fetch_url`

Если KIE не пропускает серверный `web_fetch`, опишите свой инструмент — тогда
клиент обязан его реализовать:

```json
{
  "name": "fetch_url",
  "description": "Загрузить текстовый файл по URL (raw.githubusercontent.com) и вернуть его содержимое.",
  "input_schema": {
    "type": "object",
    "properties": {
      "url": { "type": "string", "description": "Полный https-адрес raw-файла" }
    },
    "required": ["url"]
  }
}
```

### Вариант C — инструмента нет

Тогда промпт из §3 прямо велит модели сообщить об этом и перечислить нужные
файлы. Это рабочий, хоть и неудобный, путь: файлы можно прислать как `.txt`
(см. `KIE_SETUP.md` §8) или вставить в сообщение текстом.

---

## 6. Оценка расхода при веб-загрузке

| Пакет | Tier 1 (обязательно) | + Tier 2 (по надобности) | Оценка входа |
|---|---|---|---|
| A | ~64 КБ ≈ 19 000 ток. | до ~50 КБ ≈ 15 000 ток. | 19 000–25 000 ток. |
| B | ~58 КБ ≈ 17 000 ток. | до ~90 КБ ≈ 27 000 ток. | 17 000–25 000 ток. |
| C | ~81 КБ ≈ 24 000 ток. | до ~70 КБ ≈ 21 000 ток. | 24 000–30 000 ток. |

При 320 кредитов/MTok вход и 1600 выход: пакет A — до **33.6 кредита (≈ $0.168)**,
весь аудит — до **≈ $0.50**. Оценка символы/3.35; фактическое `usage.input_tokens`
смотрите в ответе.

> ⚠️ Веб-загрузка **тарифицируется как входные токены** — ровно как если бы файлы
> были приложены. Экономии на токенах нет; выигрыш в другом: не нужно переименовывать
> файлы, не нужен zip, и модель может дотянуть исходник для проверки конкретной цитаты.

---

## 7. Чек-лист перед отправкой

- [ ] Включён инструмент веб-доступа (вариант A или B) — иначе модель честно скажет,
      что не может прочитать файлы
- [ ] В `system` — текст из §3 **целиком**, включая правило про текущий вопрос
- [ ] В `messages[0]` — текст из §4 с подставленным списком Tier 1 и вопросами
- [ ] `max_tokens` = 16000
- [ ] `model` = `claude-opus-5-5` (проверить в ответе)
- [ ] Баланс KIE ≥ $1 (пакет C — самый дорогой)
- [ ] Ревизии в списке совпадают с §2 — **не** подставлять имена веток
