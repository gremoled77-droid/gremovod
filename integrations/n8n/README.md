# GremoVOD × n8n — рабочая ветка интеграции

**Branch:** `integration/n8n` · **статус:** проектирование и безопасный QA Orchestrator draft; два офлайн-теста без платных API, публикации нет.

QA Orchestrator: [схема и офлайн-тесты](QA_ORCHESTRATOR_IMPLEMENTATION.md) · [снимок узлов](workflows/qa-orchestrator.safe-draft.snapshot.json). **Сам workflow не вызывает A6/A7/A8.** При этом A6/A7 включены в **черновом A0 как subAgents** и проверялись отдельно: A7 успешный Sonnet Preview (FAIL на тестовом нарушении), A6 внутренний сбой Kie. A8 остаётся disabled. [ТЗ подключения FastAPI](QA_FASTAPI_CONNECTION_HANDOFF.md).

Эта ветка объединяет проектирование интеграции GremoVOD Web/FastAPI и n8n Agents. Работа на основной ветке приложения `main` и локальные данные пользователя не затрагиваются до проверки и merge. Ветка наследует зафиксированные задачи из `chatgpt/n8n-web-skill-sync-20261019`.

## Точки входа для Codex

1. [Инструкция передачи / контракт задач](../../docs/N8N_CODEX_HANDOFF_2026-10-19.md)
2. [План и критерии приёмки](../../docs/TODO_N8N_WEB_SKILL_SYNC_2026-10-19.md)
3. [TODO проекта](../../TODO.md), блок «GremoVOD Web ↔ n8n и GitHub Skill Sync»
4. [Текущий снимок n8n Agents](agent-manifest.json) — перечень, не конфигурация для немедленного запуска
5. [Снимок workflow v1](workflows/gremovod-studio-v1.snapshot.json) — очищен от credentials и webhook IDs, **не** файл автоматической миграции
6. [Карта навыков по 8 этапам](../../docs/STAGE_SKILLS_2026-10-16.md)
7. [Правила Git для Codex/Claude](../../AGENTS.md) и [Git workflow](../../docs/GIT_WORKFLOW.md)

## Архитектурное решение

```text
React/Vite GremoVOD Web
            |
            v
      FastAPI /api/v1
         |       \
         |        \ async jobs / callbacks
         v         v
    DB + Assets    n8n (оркестратор и AI Agents)
                       |
                       v
                 Kie / другие LLM
```

- **FastAPI — источник истины:** сценарий, канон, персонажи/локации, production_nodes, медиа, версии и утверждение владельцем. n8n не пишет напрямую в PostgreSQL/SQLite GremoVOD.
- **n8n — исполнитель:** подхватывает задания, вызывает модель и возвращает предложения/артефакты через защищённый API.
- **GitHub — источник навыков:** `skills/*/SKILL.md` + `references/**`; в n8n сейчас есть **копии**, автосинхронизации ещё нет.
- **Списания под контролем:** Kie для текстовых моделей; image/video через разрешённые адаптеры, цены и approvals всегда проверяются backend GremoVOD.
- **Никакого автоматического принятия канона:** AI-результат проходит проверку актуальной ревизии и утверждение пользователя.

## Текущий n8n (проверено 19.10.2026)

- Draft workflow **GremoVOD Studio v1 (без генерации)** — 15 узлов, не активирован. Это **workflow-узлы**, а не автоматические вызовы отдельных сохранённых n8n Agents.
- 6 **самостоятельных n8n Agents** A0–A5, все **draft, unpublished**; на 19.10.2026 A0/A3/A4/A5 = **Claude Haiku 5.5**, A1/A2 = **Claude Sonnet 5.5** через Kie credential, в каждом есть сохранённые Skills, вызовы моделей не запускались.
- Из 35 навыков проекта GitHub в агенты добавлена часть; актуальную карту см. в `agent-manifest.json`. Для полного исполнения ссылочных инструкций потребуется импорт `references/**`.
- **Skill Sync**, веб-API для n8n и A6/A7 — планы, **не реализованы**. A0 как маршрутизатор A1–A5 с low/medium/high = Haiku/Sonnet/Opus подготовлен **только в черновике**; Opus нельзя допускать к живому запуску до серверного approval и бюджетного ограничения. Подробнее: [MODEL_ROUTING.md](MODEL_ROUTING.md).
- Не надо принимать наличие n8n Skills или workflow за наличие готового веб-интеграционного API.

## Предлагаемые назначения

| Агент | Роль | Базовая LLM | Скиллы |
|---|---|---|---|
| A0 | Продюсер / маршрутизатор | Haiku | `skill-creator`, `doc-coauthoring`, `xlsx` |
| A1 | Сценарист | Sonnet | `gremovod-stage-idea`, `gremovod-screenplay`, `gremovod-script-rewrite`, `gremovod-dialogue-subtext`, `gremovod-character-comedy`, `cinema-narrative-genre` |
| A2 | Режиссёр | Sonnet | `gremovod-stage-storyboard`, `cinema-shot-design`, `cinema-camera-work`, `cinema-mise-en-scene`, `cinema-composition`, `gremovod-comedy-staging` |
| A3 | Кадры и промпты видео | Haiku + Sonnet при сложности | `gremovod-stage-frames`, `gremovod-stage-video`, `cinema-five-pillars`, `cinema-lens-language`, `gremovod-cinematic-lighting`; **один** подходящий `video-*` на запрос |
| A4 | Исследователь | Haiku + Sonnet при сложной проверке | `pdf`, исследовательские инструкции; инструменты чтения источников отдельно |
| A5 | Звук, монтаж, выпуск | Haiku + Sonnet при художественных решениях | `gremovod-stage-sound`, `cinema-sound-design`, `gremovod-stage-editing`, `cinema-editing`, `gremovod-stage-release`, `remotion-best-practices` |

**Opus** — только эскалация по содержательной творческой проблеме; сначала отдельное подтверждение бюджета. Не создавать по агенту на каждый навык.

## Планируемая независимая приёмка (3 критика)

Согласно предоставленной владельцем «Дизайн-петле»: A0 — диспетчер проверки и заключения, три независимых критика получают новый контекст и смотрят готовый артефакт. ТЗ → Haiku, канон/система → Haiku/Sonnet, ремесло по bar.md и реальному визуальному результату → Opus **только с разрешением бюджета**. Итог PASS только если все трое PASS; нет рендера = BLOCKED. Повторная работа возвращается конкретному исполнителю, при потолке стоимости — остановка для решения владельца. Подробно: [THREE_CRITICS_LOOP.md](THREE_CRITICS_LOOP.md). **Не внедрено в n8n, опубликованных агентов нет.**

## Безопасность ветки

Репозиторий может быть публичным: НЕ коммитить реальные API keys, credential IDs, webhook secrets, персональные user data, локальные projects, файлы медиа, копии базы и платёжную историю. `agent-manifest.json` содержит только публично-безопасные идентификаторы ресурсов n8n и имена моделей/навыков. Все endpoints для приватных callbacks и токены — переменные среды на сервере.

Публикация workflow/агентов и платные LLM/media вызовы — только после отдельного разрешения владельца.
