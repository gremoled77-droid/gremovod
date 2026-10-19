# GremoVOD × n8n — рабочая ветка интеграции

**Branch:** `integration/n8n` · **статус:** первый API sandbox-срез и локальный Skill Sync plan с тестами; публикации нет.

Эта ветка объединяет проектирование интеграции GremoVOD Web/FastAPI и n8n Agents. Работа на основной ветке приложения `main` и локальные данные пользователя не затрагиваются до проверки и merge. Ветка наследует зафиксированные задачи из `chatgpt/n8n-web-skill-sync-20261019`.

Первый серверный sandbox-срез: [API-контракт](../../docs/N8N_API_CONTRACT.md)
и [локальный план Skill Sync](SKILL_SYNC.md). Доступны только stub/echo и текстовые
предложения; платные вызовы, UI и живой n8n workflow ещё не подключены.

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
- 6 **самостоятельных n8n Agents** A0–A5, все **draft, unpublished**; на момент снимка каждый настроен на **Anthropic Claude Sonnet 5.5** через Kie credential, в каждом есть сохранённые Skills, вызовы моделей не запускались.
- Из 35 навыков проекта GitHub в агенты добавлена часть; актуальную карту см. в `agent-manifest.json`. Для полного исполнения ссылочных инструкций потребуется импорт `references/**`.
- Полный **Skill Sync**, живая доставка в n8n, Agent orchestration, A6/A7 — планы. Первый API-срез и offline-план описаны выше.
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

## Безопасность ветки

Репозиторий может быть публичным: НЕ коммитить реальные API keys, credential IDs, webhook secrets, персональные user data, локальные projects, файлы медиа, копии базы и платёжную историю. `agent-manifest.json` содержит только публично-безопасные идентификаторы ресурсов n8n и имена моделей/навыков. Все endpoints для приватных callbacks и токены — переменные среды на сервере.

Публикация workflow/агентов и платные LLM/media вызовы — только после отдельного разрешения владельца.
