# N01–N11: сценарный цех GremoVOD на существующих скиллах

**Дата:** 19.10.2026. **Очередность пилота:** P0/P1 контракты (уже в Draft PR) → сценарный TEXT-only smoke N01–N11 без UI → реальный MP4 / N34–N41 при наличии файла → только после фактических результатов визуальный дизайн Studio.

Это **спецификация и бесплатный mock**, не новый утверждённый канон, не «установленные» внешние скиллы и не реальный работающий production authoring tool. Единый исходный артефакт хранится в существующем FastAPI; n8n не становится второй базой правды.

## 1. Какие навыки действительно есть

В `skills/` указанной ветки GitHub доступны:
- `gremovod-stage-idea` — мотив/препятствие, разворот, финал, причинность.
- `gremovod-series-development` — потенциал продолжения и задачи серии.
- `gremovod-character-comedy` — комедия из характера, желания и реакции, не набор случайных гэгов.
- `gremovod-dialogue-subtext` — речевое действие, подтекст, паузы и реакции.
- `gremovod-screenplay` — стабильные ID сцен, кадров, реплик и соответствие Story Board.
- `gremovod-script-rewrite` — адресный rewrite только проблемных мест с сохранением авторской версии.

Точные навыки `generate-fresh-ideas`, `get-more-perspectives`, `grem`, `match-my-writing-style` отсутствуют в проверенном GitHub каталоге `skills/` и в текущем installed-skills index. Их не объявляем подключёнными. Вместо этого четыре **необязательных авторских режима**:
1. Пять редакторских линз (контрарный ракурс, личный интерес, источники, практическая реализация, упущенный штрих) — подсказки для идеи, **не** пять обязательных завязок; «доказательная база» не делает вымысел фактом.
2. Худсовет (Visionary, Viewer, Operator, Finance, Skeptic) — **один консультативный обзор** либо независимые отзывы по отдельному бюджету, не подменяет A6/A7 и не выдаёт наивное «пять экспертов согласились» за пять реальных проверок.
3. Живые реплики — через существующий character/dialogue/series canon, не через гипотетический `grem`.
4. Style matching — только из реальных примеров речи владельца/персонажа, которые **он явно утвердил**. Не выдумывать профиль по одному логлайну, не вносить в канон автоматически.

Для production S02 должен выдавать read-only versioned `skill_bundle` из whitelist GitHub source files с content SHA, полями `source_commit`, `repo_path`, `allowlist_revision`; все ссылки/файлы untrusted data до отдельной проверки. Если skill/character voice не найден — `BLOCKED_SKILL_OR_VOICE_NOT_APPROVED`. Не сохранять большие тексты целиком в n8n execution logs.

## 2. Исполнимая схема / роли

| Узел | Исполнитель | Выход и проверка |
|---|---|---|
| N01 Intake | Owner + Code | `idea_original`, project/task ID, флаги `DEMO_ONLY`; сохранять исходный текст без переписывания |
| N02 Validation | Code | real project ownership, version, исходный контент, security gate; при демо только schema check, **не** проверенная авторизация Studio |
| N03 Brief | A0 / bounded LLM | заявленные факты отдельно от гипотез; constraints, duration, audience, character lock, `approval_status=CANDIDATE` |
| N04 Research | A4 по необходимости | если не нужно — честный `SKIPPED_NO_RESEARCH_NEEDED`; новости/люди требуют источника и отдельной проверки, не из воспоминаний LLM |
| N05 Freeze | Studio + Owner + S01/S04 | immutable approved brief snapshot, requirements by IDs, source+canon revisions, SHA-256, explicit owner decision; текущий mock **останавливается** здесь без real Studio approval |
| N06 Concepts | A1 / creative LLM | по умолчанию **3 разных** концепта; если задан режим пяти редакторских линз, это методы поиска, а не принудительные пять концептов; никаких медиа |
| N07 Council | A6 + A7; A8 only bounded TEXT_CRAFT if authorized | каждая обязательная req отдельно, канон только из approved snapshot; худсовет — advisory notes; отсутствие evidence `BLOCKED`; ≥2 жизнеспособных разных кандидата для N08 |
| N08 Choice | Owner-only decision | `concept_id`, `snapshot_hash`, user session; рекомендация A0 не равна принятию |
| N09 Script | A1 | сцены/диалоги с стабильными ID, попыткой героя получить ответ, реакциями; rewrites сохраняют оригинал, не ломают заявленный канон |
| N10 QA text | A6/A7; A8 TEXT_CRAFT отдельно по бюджету | проверка каждого текстового требования на одну frozen revision; `PASS` здесь **не** подтверждает видео или характер голоса по звучанию |
| N11 Director plan | A2 | scene→shot/characters/locations/refs, действительные IDs approved canon, unknown refs→`asset_requests`, не выдавать AI-кандидатов за эталоны |

**A0 не запускается** по сетевым ошибкам, несовпадению хэша/JSON или exhausted budget; их обрабатывают deterministic Code/S05. Финансовый потолок относится и к A1/A2/критикам, а не только к видео.

## 3. Тестовый кейс без новой информации о каноне

**Завязка из обсуждавшегося проекта:** Грэм приближается к ВАЗ‑2106; ракурсы не раскрывают удлинение/тюнинг. В пути к аэропорту только водитель и классические автомобильные детали. В финале — первое полноценное раскрытие лимузина. Это исходное авторское ограничение, а не просьба дописывать характер/диалоги. Если актуальный canonical source не получен из backend — `DEMO_SOURCE_NOT_VERIFIED`.

Mock workflow должен:
- вернуть исходную идею и её статус `SYNTHETIC_DEMO`;
- сформировать **несколько редакторских вопросов**, а не утверждённый текст сценария;
- зафиксировать отсутствие реальной owner auth/approved source;
- показать N06–N11 как `BLOCKED_NEEDS_OWNER_OR_APPROVED_SOURCE`, не имитировать автоматическое продвижение;
- продемонстрировать, что N08 owner selection и N09 script не происходят без owner decision;
- вернуть итоговое `final_release_approved=false`, `owner_choice=null`, `paid_calls=0`.

Отдельно тестировать подставными данными: корректный формат N06 concepts (минимум 2 distinct viable), дубликаты концепций, stale snapshot, отсутствие голоса, подмена character ID, попытка N08 auto-select; все reject через Code.

## 4. Политика голоса персонажа

Диалог пишется не «общим пацанским стилем» на всю серию. A1 получает `character_id + canonical_personality_revision + speaker_goal + relationship + approved_voice_guidance`. Фразы должны обслуживать действие/намерение, не быть набором сленга. Подмена говорящего, придуманное `voice_id`, неутверждённая фамилия/биография ⇒ BLOCKED. `grem` без установленного источника не исполняется.

Гипотезы о стиле отделяются от `approved_dialogue_examples`. Вход с `style_preset_id`, не подтверждённым владельцем, не допускается на N09. Если данных недостаточно, возвращается нейтральный кандидат для редакторского выбора, не самопринятый канон.

## 5. Физическое n8n и backend

Не требуется 11 отдельных платных AI-агентов и не нужно запускать 5 «советников» как 5 обязательных запросов:
- `preproduction_orchestrator`: ручной/авторизованный вход, переходы/бюджет/owner gate через trusted backend.
- `ideas_concepts_script`: A0 (по необходимости), A1, schema checks; одна модель/запрос на логический шаг, без автоматического повторного заказа.
- `review_concept_and_text`: независимые A6/A7, необязательный A8(TEXT), отдельные и не пересекающиеся контексты.
- `director_plan`: A2 после approved script и reference checks.
- `S02 skill bundle resolver`: только versioned read-only instruction packages.

Из кода S01/S04/S08 и approvals уже существует **reference-only** SQLite в `integrations/n8n/pilot_state_sqlite.py` — это НЕ готовые API и НЕ live одобрения. Не добавлять отдельную production DB и не раскрывать Windows loopback в облако.

**Следующие проверяемые границы:** owner approves frozen brief; user picks concept; A1 produces script; A6/A7 verify; A2 emits stable director plan. Лишь после этого и появления MP4 возвращаемся к мультимодальному N34–N41.

## 6. О сроках из присланного плана

Цифры «7–8 workflow, 15–20 скриптов, 3.5–4.5 недели» — оценки, **не выверенное ТЗ и не обещанный срок**. Потребуются дополнительные работы над source-of-truth, миграциями, закрытой доставкой видео, коннекторами Kie, валидацией источников и human QA. Высокие риски срока — provider изменяет APIs, мультик с voice continuity и цена повторных дублей. План на 1–2-минутный пилот не должен автоматически менять установленный автором формат сериала (серии 3.5–4 мин).
