# Карта документов и навыков

Задача → где искать. Читать точечно, а не подряд: половина файлов в `docs/` —
исторические отчёты, а `docs/HANDOFF_CLAUDE_CODE.md` весит больше, чем весь
контракт агентов.

## Решения и контракты

| Вопрос | Файл |
|---|---|
| Общий контракт всех агентов | `AGENTS.md` |
| Критерии качества разработки | `AGENTS.md`, раздел «Критерии качества разработки» |
| Цель текущей беты и утверждённые решения D1–D4 | `AGENTS.md`, раздел «Цель текущей беты»; источник утверждения — [PR #55](https://github.com/gremoled77-droid/gremovod/pull/55) и [`docs/decisions/2026-10-21-beta-acceptance-D1-D4.md`](https://github.com/gremoled77-droid/gremovod/blob/decisions/beta-d1-d4-20261021/docs/decisions/2026-10-21-beta-acceptance-D1-D4.md) (OWNER_APPROVED) |
| Глобальная приёмка #54 (приёмка реализации, PARTIAL) | [PR #54](https://github.com/gremoled77-droid/gremovod/pull/54) — [реестр решений](https://github.com/gremoled77-droid/gremovod/blob/audit/global-acceptance-20261021/docs/audits/global-acceptance-2026-10-21/07_DECISION_REGISTER.md), [пробелы беты](https://github.com/gremoled77-droid/gremovod/blob/audit/global-acceptance-20261021/docs/audits/global-acceptance-2026-10-21/05_BETA_GAP_ANALYSIS.md), [агенты и знания](https://github.com/gremoled77-droid/gremovod/blob/audit/global-acceptance-20261021/docs/audits/global-acceptance-2026-10-21/04_AGENTS_AND_SKILLS.md) |
| Роли агентов, границы зон, shared-пути | `docs/AGENT_ROLE_MATRIX.md` |
| Трёхагентная сборка и эстафета | `AGENT_BUILD_MANUAL.md` |
| Текущий статус и приёмка задач | `STATUS.md` |
| Решения владельца, менять нельзя без вопроса | `AGENTS.md`, раздел «Решения владельца» |
| Спорные решения и точки «требует Codex» | `docs/CODEX_DECISIONS.md` |
| Что делать дальше по эстафете | `docs/CODEX_NEXT_ACTIONS.md` |
| Пакет к архитектурному ревью | `docs/CODEX_REVIEW_PACKET.md` |
| Handoff прошлых задач | `docs/agent_handoffs/` |
| История сессий и живых тестов | `docs/HANDOFF_CLAUDE_CODE.md` — по разделам |

## Деньги, провайдеры, безопасность

| Вопрос | Файл |
|---|---|
| Подключение нового провайдера | `docs/GENERATION_PROVIDERS.md` |
| Протокол платного LLM-вызова | `docs/PAID_LLM_PROTOCOL.md` |
| Учёт расходов n8n | `docs/N8N_SPEND_ACCOUNTING.md` |
| Каталог моделей и живые тесты | `docs/PIAPI_MODELS_2026-10-16.md` |
| Правила промптов по видеомоделям | `docs/VIDEO_MODELS_PROMPTING_2026-10-17.md` |
| Правила промптов по картинкам | `docs/PROMPT_AND_VIDEO_AUTOMATION.md` |

## Продукт, код и процесс

| Вопрос | Файл |
|---|---|
| Очередь задач | `TODO.md` |
| История версий (0.3.0) | `CHANGES.md` |
| Техническое ТЗ | `docs/TECHNICAL_SPEC.md` |
| Архитектурный план | `docs/ARCHITECTURE_PLAN_2026-10-16.md` |
| Макеты нового дизайна | `docs/design/` |
| Видение и алгоритм ролика | `docs/VISION_AND_ALGORITHM.md` |
| Моушн и монтаж кодом | `docs/MOTION_TOOLS_2026-10-18.md`, `docs/MOTION_STUDIO_PROMPT.md` |
| Git-процесс и каталоги | `docs/GIT_WORKFLOW.md` |
| Внешний доступ и облако | `docs/CLOUD_DEPLOY.md` |

## Киноязык и сценарий — `skills/`

| Задача | Навык |
|---|---|
| Карточка кадра целиком — точка входа | `skills/cinema-shot-design/SKILL.md` |
| Нарратив и жанр | `skills/cinema-narrative-genre/SKILL.md` |
| Миза-сцена | `skills/cinema-mise-en-scene/SKILL.md` |
| Камера | `skills/cinema-camera-work/SKILL.md` |
| Композиция | `skills/cinema-composition/SKILL.md` |
| Оптика и объективы | `skills/cinema-lens-language/SKILL.md` |
| Монтаж | `skills/cinema-editing/SKILL.md` |
| Звук | `skills/cinema-sound-design/SKILL.md` |
| Идея и мир | `skills/cinema-image-system/SKILL.md` |
| Визуальная структура (Block) | `skills/cinema-visual-structure/SKILL.md` |
| Персонажи в кадре | `skills/cinema-character-framing/SKILL.md` |
| Пять столпов — промпты для ChatGPT | `skills/cinema-five-pillars/SKILL.md` |
| Формат сценария для ChatGPT | `skills/gremovod-screenplay/SKILL.md` |
| Переписывание сценария, подтекст диалогов | `skills/gremovod-script-rewrite/SKILL.md`, `skills/gremovod-dialogue-subtext/SKILL.md` |
| Комедия, характер, постановка | `skills/gremovod-character-comedy/SKILL.md`, `skills/gremovod-comedy-staging/SKILL.md` |
| Этапы производства | `skills/gremovod-stage-idea`, `-world`, `-storyboard`, `-frames`, `-video`, `-sound`, `-editing`, `-release` |
| Промпты по видеомоделям | `skills/video-seedance-2-0`, `-seedance-2-5`, `-flux-3`, `-kling-3-omni`, `-kling-3-start-end-frame`, `-minimax-h3` |
