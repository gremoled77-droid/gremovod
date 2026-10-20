# Координация по производственным скиллам — 20.10.2026

Сторона: сессия `mavis/work`. Ветка-адресат: `minimax/backend-production-skills-20261020`
(база `origin/minimax/p0-astra-fixes-20261020` = `89dfd11`). Коммиты адресата:
`a2b6e72`, `94f2781`, `cbfec7f` и `4aa1513` (документ с вариантами D1–D7).

Ничего в ветке адресата не менялось. Проверено только чтением.

## 1. Утверждение о синке скиллов в n8n — подтверждено

Проверено по исходнику `scripts/n8n_skill_sync.py` в `origin/codex/n8n-api-contract`,
функция `package()`:

| Проверка | Код | Что означает |
|---|---|---|
| Область дерева | `git ls-tree -rz <commit> -- skills docs` | файлы вне `skills/` и `docs/` в пакет не попадают |
| Только markdown | `path.endswith('.md')` | не-md не импортируется |
| Плоская раскладка | `prefix = f'skills/{name}/'`, `re.fullmatch(r'[a-z0-9][a-z0-9-]{0,99}', name)` | вложенность запрещена |
| Состав пакета | `pending = {skills/<n>/SKILL.md} ∪ skills/<n>/references/**` | ровно `SKILL.md` плюс `references/` |
| Рекурсивные ссылки | `re.findall(r'\]\(([^)]+)\)', text)` + `raise ValueError('Missing or unsupported reference')` | ссылка вне `skills/`/`docs/` **ломает сборку** |
| Frontmatter | однострочные `name` и `description`, `name` == имя каталога | сложный frontmatter отвергается |

Вывод: `backend/skills/production/<имя>/SKILL.md` в n8n не попадёт ни при каком
манифесте. Раскладка D1-A обязательна.

## 2. Dockerfile: правка действительно нужна, но для backend, а не для n8n

Ни в ветке, ни в `origin/main` нет `COPY skills/ skills/`. Сейчас тексты скиллов
попадают в образ через `COPY backend/ backend/`, поэтому загрузчик в контейнере
работает. После плоского переноса без `COPY skills/ skills/` контейнер останется
без текстов скиллов.

Уточнение: n8n-синк читает **закреплённый git-коммит**, а не образ. Правка
Dockerfile — про backend в контейнере, к поездке в n8n отношения не имеет.

## 3. Главное: работа идёт в двух ветках параллельно

| | ветка `minimax/backend-production-skills-20261020` | незакоммиченная работа соседней сессии в `.worktrees/mavis` |
|---|---|---|
| Раскладка | `backend/skills/production/<id>/SKILL.md` | `skills/<id>/SKILL.md` — уже плоская (D1-A выполнен) |
| Набор скиллов | canon-lock, **cheap-gatekeeper**, strict-json-output, video-prompt-crafter | canon-lock, **precheck-filter**, strict-json-output, video-prompt-crafter, **evidence-packager** |
| Загрузчик | `backend/production_skills.py`: `registry.json`, сверка хэша fail-closed, `bundle_hash`, `detect_conflicts` | `backend/minimax_roles.py`: чтение из `skills/`, хэш по содержимому, без реестра |
| Ось роутинга | стадии сценария N01–N11 | девять экранов студии + `GATE_SKILLS` + `EVIDENCE_SKILLS` |
| Правка Dockerfile | нужна | не нужна (уже плоско) |

Хэши трёх одноимённых скиллов (`skill-canon-lock`, `skill-strict-json-output`,
`skill-video-prompt-crafter`) на двух сторонах **разные**: тексты переписаны, а не
перенесены. При этом тексты соседней сессии названы в духе MiniMax
(«системных промптов MiniMax»), а тексты ветки — нейтрально («системных промптов
LLM API»). Под воркер D6-A (`gpt-5.6-luna` через PiAPI) верны нейтральные.

Все пять плоских скиллов упаковываются по правилам `n8n_skill_sync.py`: `name`
совпадает с именем каталога, `description` есть, md-ссылок нет.

### Рекомендация

1. **Механизм — от ветки:** `registry.json` + fail-closed сверка хэша +
   `bundle_hash` + `detect_conflicts`. Второй загрузчик в проекте не нужен.
2. **Раскладка — плоская** (D1-A), как в соседней сессии.
3. **Набор — объединение:** к четырём скиллам добавить `skill-precheck-filter`
   (каноническое имя; `skill-cheap-gatekeeper` оставить алиасом) и
   `skill-evidence-packager`. Это уже готовая половина D5-A.
4. **Канонический текст — владельцу:** брать нейтральные тексты ветки, из
   соседней сессии взять только расщепление и алиас. Сейчас у одного
   идентификатора два канонических текста — это ровно тот «тихий дрейф», ради
   которого сделан fail-closed.
5. **Роутинг — один реестр.** `registry.json` уже умеет `stages` и `roles`;
   девять экранов студии добавляются в него, а не вторым загрузчиком.

## 4. D4 и D5 — что беру на себя

### D4 (пакет ролевых промптов A0–A8) — пакет не беру

По `prompts/README.md` в этой ветке роли A0–A8 — резерв Codex (`prompts/`,
«файлов ролей пока нет»), и создавать их «как готовые» без утверждённого
source и канона запрещено. D4-A тоже перечисляет только A1, A2, A6, A7, A8.

**Беру на себя: источник для роли A0.** В пакете D4 нет A0, хотя
маршрутный контракт отводит A0 роль на стадии N03 (`BriefCandidate`,
движок `BOUNDED_LLM`, гейт `no_invented_canon`). Готового текста роли A0 в
проекте не было — теперь он есть как работающий и проверенный контракт в
`mavis/work` (коммит `5a27517`):

- `backend/producer_stage.py` — этап «Продюсер»: идея → логлайн, драматургические
  биты, план сцен, допущения; версия промпта и сведения о модели; строгая
  проверка ответа; локальный MOCK без затрат; `no_invented_canon` обеспечен
  конструкцией (персонажи только из канона проекта).
- `backend/test_producer_stage.py` — 14 тестов, включая «в ответе нет ссылок на
  то, чего не было во входе» и «негодный ответ не вызывает платный повтор».
- `docs/PRODUCER_STAGE_CONTRACT.md` — формат JSON ответа, запрещённые
  допущения, границы.

Это готовый source для записи A0 в пакете ролей: форма JSON ответа, запрещённые
допущения и тест-кейсы берутся из проверенной реализации, а не выдумываются.
Тексты ролей я не пишу и файлы в ветке адресата не трогаю.

### D5 (расщепление gatekeeper) — не беру

LLM-часть уже сделана соседней сессией: `skill-cheap-gatekeeper` стал
`skill-precheck-filter`, добавлен `skill-evidence-packager`, алиас
`skill-cheap-gatekeeper → skill-precheck-filter` сохранён. Кодовая часть
(детерминированная проверка тайминга и `revision_id`) — пункт 3 плана самой
сессии адресата, забираю не её.

Даю прецедент и рамку: детерминированная часть обязана соответствовать D-010 и
подходу N34 — ноль LLM, ноль расход, fail-closed, вердикт считает студия, а не
принимает готовый от исполнителя. `backend/media_qc.py` и
`docs/N34_TECHNICAL_QC.md` — эталон; проверю модуль по этим критериям, если
попросят.

## 5. Границы

- В ветке адресата ничего не менялось: `backend/skills/production/*/SKILL.md`,
  `skills/skill-*/`, `backend/production_skills.py`, `Dockerfile` и
  `docs/specs/n8n-production-2026-10-19/contracts/scenario-skills-routing-v1.json`
  не тронуты.
- Корень `C:\AI_Workflow_Studio` не тронут.
- Моя ветка `mavis/work`; она не слита в `main`.
