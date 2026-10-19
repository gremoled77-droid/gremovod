# MiniMax Step Tracker — ШАБЛОН для отдельной рабочей ветки
**Статус: TEMPLATE, НЕ фактический отчёт.** Создан 2026-10-19. Source of truth после старта — живой tracker в собственной ветке MiniMax / Draft PR; этот файл служит только образцом. Ни один шаг ниже не считается выполненным.

## Карточка запуска
- Task: GitHub Issue #27 (observability); стратегический запрос Argon — см. файл `ARGON_MINIMAX_ONE_SHOT_REQUEST_20261019.md`.
- Owner approval of Argon plan: **NOT_RUN**
- active_step: **M00**
- latest_completed_step: **NONE**
- mode: **OFFLINE**
- run_id: **NOT_ASSIGNED**
- current MiniMax branch: **NOT_ASSIGNED**
- base_sha: **UNKNOWN**
- head_sha: **UNKNOWN**
- diff_sha256: **UNKNOWN**
- reviewed_sha: **NOT_RUN**
- M Plan subscription route/quota: **NOT_VERIFIED**
- monetary cost: **UNKNOWN** (это НЕ нулевая подтверждённая стоимость)
- Argon invocation: **NOT_RUN**
- MiniMax reviewer invocation: **NOT_RUN**
- n8n execution: **NOT_RUN**
- GitHub Actions run: **NOT_RUN**
- Draft PR: **NOT_CREATED**
- owner_decision: **PENDING**

## Линейная очередь
| Шаг | Статус | Evidence (точная ссылка/commit/log) | Блокер/следующее действие |
|---|---|---|---|
| M00 — Инвентаризация | NOT_RUN | — | READ ONLY аудит |
| M01 — Единичный план Argon и утверждение | NOT_RUN | — | Запрос только после согласия на конкретный API расход |
| M02 — Worktree | NOT_RUN | — | Не трогать main |
| M03 — Базовые тесты | NOT_RUN | — | Без сети |
| M04 — JSON контракт + Markdown renderer | NOT_RUN | — | Offline |
| M05 — GitHub Actions summary | NOT_RUN | — | Без платного dispatch |
| M06 — n8n MOCK design | NOT_RUN | — | Без изменения существующих workflow |
| M07 — n8n MOCK draft/execution | NOT_RUN | — | Нужен отдельный owner approval |
| M08 — Один MiniMax Subscription API review | NOT_RUN | — | Опционально, отдельный owner approval и verified quota |
| M09 — Итог / Codex handoff | NOT_RUN | — | В срок до 24 октября |

## Правило продвижения
При запуске читать `active_step`. Выполнить **только его**, зафиксировать тесты и фактические ссылки, обновить статус и записать причину; затем менять `active_step` на следующий. Запрещено отмечать этап PASS по одному намерению или документации. Если найден FAIL/BLOCKED — остановиться и спросить пользователя. `SKIPPED_BY_OWNER` допустим только у явно опционального шага при письменном решении владельца; затем продолжить по утверждённому маршруту. Если появляется новый HEAD, не использовать старый Argon/AI verdict — перевести его в STALE_REVIEW.

## Последнее сообщение MiniMax владельцу (обновлять после каждого этапа)
- Дата UTC:
- Текущий шаг:
- Что именно сделано:
- Commit/PR:
- Тесты:
- API calls/квота/cash:
- Риски и blockers:
- Единственное следующее действие:
- Нужна ли авторизация владельца:
