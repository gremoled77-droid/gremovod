# Сценарий, агенты и доступные знания

## Реальный runtime

| Контур | Что действительно поступает | Что не подтверждено |
|---|---|---|
| Producer Stage | selected character identity, approved/reference IDs с проверкой ownership, bounded world/constraints; [backend/producer_stage.py:175](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/producer_stage.py#L175) | файл/изображение не отправляется для визуального анализа — только metadata и notes |
| Сценарный фон Producer | [backend/producer_stage.py:246](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/producer_stage.py#L246) вызывает [backend/idea_background.py:10](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/idea_background.py#L10) и читает ровно `skills/gremovod-screenplay/idea-background.md`, сообщает content hash | наличие десятков других SKILL.md не делает их автоматически частью запроса |
| Story Plan | отдельные карточки, scene/cast/location IDs, revision/preview/apply; [backend/story_plan.py:62](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/story_plan.py#L62) | отдельный сценарный engine не нужен; перенос Producer scenes в этот план в одном UI-сценарии не принят |
| Agents prototype | 3 prompt-роли и предыдущий output внутри одного последовательного run; [backend/main.py:714](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L714), [backend/main.py:823](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L823) | это не независимые fresh critics. У них общий контекст предыдущих ролей; paid runtime имеет P0-01 |
| Continuity | prompt-role и структура кадра/авто/референсов | долговременный before/after ledger костюмов, реквизита и состояния сцен не подтверждён |
| Prompt Adapter | model registry, system rules, prompt_profiles, schema adapters, source revisions | live поведение/параметры всех моделей не проверены |
| Selected skills в text tasks | клиент передаёт id + инструкции; [backend/llm_guard.py:65](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/llm_guard.py#L65), [backend/llm_guard.py:274](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/llm_guard.py#L274) | это не server-side загрузка доверенного файла по content hash; сам task lifecycle сломан |
| n8n Agents A0–A8 | versioned mapping в integrations/n8n/STAGE_SKILL_MAP.md и agent-manifest | документы о прежнем preview не доказывают, что текущий Cloud исполняет именно эти версии |
| N34/N35/critics | local measurements, signed report, immutable snapshot/packets [backend/qa_reviews.py:46](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/qa_reviews.py#L46) | live visual/audio capability критиков и художественное принятие пилота NOT_RUN |

## Где знания остаются документацией

Для Producer доказана загрузка screenplay background. Для Prompt Adapter доказаны кодовые правила/профили. Для навыков киноязыка есть справки и ручной экспорт; автоматическое подключение **всей** библиотеки книг ко всем агентам не доказано. Это **P2-02**, не требование загрузить все книги в каждый prompt.

Локальная уникальная ветка `minimax/skill-catalog-20261020@5e64c69` добавляет read-only каталог/проверку ссылок и tests. Она на 2 коммита впереди mavis; в remote snapshot отсутствует. Не поручать заново писать каталог. CLI-каталог ещё не означает интегрированный runtime loader.

Существуют полезные знания по композиции, сценарию, комедии, свету, звуку и монтажу. В первую бету нужен небольшой выбранный stage packet с известной revision, а не ещё один Writers' Room/Character Vault/универсальный агент.

## Исследования #50–53

| Материал / зафиксированный SHA | Что прочитано | Применимость без превращения в канон |
|---|---|---|
| [PR #50](https://github.com/gremoled77-droid/gremovod/pull/50), 3a9cf18 | GREMOVOD_APPLICABILITY_REVIEW и наличие исходного master-prompt | Сопоставить предложения с media_qc/edit_list/motion/clip_chain. Автовырезка пауз постановочного диалога — не обязательная функция |
| [PR #51](https://github.com/gremoled77-droid/gremovod/pull/51), 23a83f2 | GREMOVOD_CHAIN_APPLICATION | Самостоятельный payoff, существующий target link и защита reveal — полезные ручные checks. Цепочки Shorts — AFTER_BETA |
| [PR #52](https://github.com/gremoled77-droid/gremovod/pull/52), ffe1317 | 03_GREMOVOD_EXPERIMENT и PR summary | Гипотезы выпуска/метрик и отделение фактов от предположений. Не превращать чужую схему канала в beta requirement |
| [PR #53](https://github.com/gremoled77-droid/gremovod/pull/53), e2f9f95 | 02_AGENT_GATES_AND_TZ, 03_MINIMAX_SMALL_TASKS и PR overview | Completeness/duplicate IDs/unknown cast/model-contract lint полезны; сначала проверить существующий Producer/Story Plan |

Первичный чужой PDF целиком и 1641-строчный master prompt в этом аудите не изучались заново: **NOT_RUN**, задача здесь — оценить применимость сохранённых собственных выводов. Точные ссылки:
[docs/research/video-editing/GREMOVOD_APPLICABILITY_REVIEW_2026-10-20.md:1](https://github.com/gremoled77-droid/gremovod/blob/3a9cf18a4b6d29b8ad518a2491e5697b8fca984b/docs/research/video-editing/GREMOVOD_APPLICABILITY_REVIEW_2026-10-20.md#L1);
[docs/research/story-chaining/GREMOVOD_CHAIN_APPLICATION_2026-10-20.md:1](https://github.com/gremoled77-droid/gremovod/blob/23a83f251a63143cfa37f5530ee4f170931e5e2a/docs/research/story-chaining/GREMOVOD_CHAIN_APPLICATION_2026-10-20.md#L1);
[docs/research/channel-business-model-2026-10-20/03_GREMOVOD_EXPERIMENT.md:1](https://github.com/gremoled77-droid/gremovod/blob/ffe1317610d589051b2852c0e9744e33671d44b5/docs/research/channel-business-model-2026-10-20/03_GREMOVOD_EXPERIMENT.md#L1);
[docs/research/gemini-ladybug-workflow-2026-10-20/02_AGENT_GATES_AND_TZ.md:1](https://github.com/gremoled77-droid/gremovod/blob/e2f9f95ed3df67c0db2b2a64b0a7cfbf5f623c0a/docs/research/gemini-ladybug-workflow-2026-10-20/02_AGENT_GATES_AND_TZ.md#L1).

## Что уже умеет обычный код

- Producer schema/reference ownership и unknown beat/character checks: [backend/producer_stage.py:267](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/producer_stage.py#L267), [backend/producer_stage.py:304](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/producer_stage.py#L304), текущие test_producer_stage.
- Story Plan unique card IDs, foreign scene/cast/location и stale revision: [backend/story_plan.py:62](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/story_plan.py#L62).
- Model fields, reference URL/ownership, duration/size, quote payload и request_id — существующие adapters/validators/tests.
- N34: full decode/streams/duration/hash и наблюдения, без LLM; N35: evidence/rights/modality gates.
- Потенциальное дополнение после денег: неполные перечисления beat IDs и диапазоны вместо отдельных битов. Нельзя автоматически объявить это багом текущего утверждённого контракта: PR #53 — предложение.

## Где сейчас возникает повторная работа

MM-002 REVIEW_EXISTING смотрел старую базу и предлагает общий счётчик, который уже есть в mavis. MM-001 исправлял older guarded_chat, а текущая ветка уже имеет часть этих правок и новые callers. Codex StoryPlan/UI и Mavis StoryPlan следует сравнивать по поведению, а не переписывать по названию. n8n draft не должен становиться второй системой project IDs/approvals/расходов.

## Только владелец

Утверждение канона, реплик, сходства лиц/голосов, геометрии автомобиля и момента reveal; оценка комического payoff, пауз, музыки и финального монтажа. Технический PASS не разрешает выпуск. Для художественного решения нужны доступный реальный master, hash версии и явное решение человека.
