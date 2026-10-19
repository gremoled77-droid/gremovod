# STATUS — GremoVOD · эстафета трёх разработчиков

**Проверено:** 2026-10-19. **Текущий владелец эстафеты:** координатор (ChatGPT, подготовка передачи Codex). **Состояние:** `READY_FOR_CODEX_REVIEW`, не `PRODUCTION_READY`.

## Три строки для следующего исполнителя

- **Сделано:** разработаны P0-модуль памяти/бюджета и 7 связанных MOCK workflow; код проверен изолированными SQLite/FFmpeg тестами. Подготовлены правила для Codex, Claude Code, Argon, 7 обезличенных JSON-экспортов и CI-защита чужих областей в новых task-ветках.
- **Файлы:** `AGENT_BUILD_MANUAL.md`, `STATUS.md`, `docs/CODEX_REVIEW_PACKET.md`, `docs/CODEX_DECISIONS.md`, `docs/CODEX_NEXT_ACTIONS.md`, `db/schema.sql`, `backend/p0_control.py`, `integrations/n8n/WF_00_WF_06_MANIFEST.json`, `workflows/`, `prompts/`.
- **Следующий шаг:** **Codex** ревью зависимости PR #17 → #18, поиск конфликтов с существующими `backend/main.py` / Studio SQL, фиксация contracts в отдельной ветке и выдача двух независимых build-заданий Claude/Argon. Никаких изменений main до ревью.

## Статус реальных задач

| ID | Кому | Область | Статус | Условие приёмки |
|---|---|---|---|---|
| REVIEW-00 | Codex | Архитектура PR #17 и PR #18, D-001–D-012, P0 data reconciliation | **READY_TO_PICK_UP** | No shadow SQLite, documented safe migration/rollback |
| BUILD-01 | Claude Code | Реальный FastAPI State Manager S01 + Studio auth S09 + восстановление S04/S05 | **NOT_ASSIGNED_IN_LOCAL_WORKTREE** | Тесты на копии SQLite, два Resume, права, zero real spend |
| BUILD-02 | Claude Code | Windows media worker, FFmpeg/ffprobe и safe asset access | **NOT_ASSIGNED_IN_LOCAL_WORKTREE** | Хэши реальных бесплатных test файлов совпали на обеих сторонах |
| INTEGRATE-01 | Argon | Seven n8n draft modules, source-controlled workflow JSON, mock dispatcher | **NOT_ASSIGNED_IN_LOCAL_WORKTREE** | Реальные asset IDs вместо `mock://`; модельных вызовов 0 |
| REVIEW-01 | Codex | Отдельное ревью каждого build PR | **PENDING_IMPLEMENTATION** | CI + ревизии/деньги/evidence подтверждены |
| MEDIA-01 | Владелец / все | Настоящий MP4 и художественная A6/A7/A8 проверка | **BLOCKED_NO_USER_MP4** | Подлинные video/audio evidence, просмотр конкретной версии |
| PAID-01 | Владелец / Codex | Подключение TTS, image, video, lip-sync | **BLOCKED_NO_TRUSTED_REQUEST_APPROVAL** | Проверены API, цена, rights, разрешение конкретного submit |
| RELEASE-01 | Владелец | Утвердить канон и выпуск | **BLOCKED_NO_APPROVED_CANON_OR_FINAL_MASTER** | Подлинная сессия и 3 fresh независимых media verdict |

## Где сейчас изменения

- <https://github.com/gremoled77-droid/gremovod/pull/17> — **Draft**: Astra P0/P1/P2 спецификация.
- <https://github.com/gremoled77-droid/gremovod/pull/18> — **Draft**: P0 SQLite + семь MOCK WF. **Основан на ветке PR #17**, нельзя делать два неразобранных merge в main.
- <https://github.com/gremoled77-droid/gremovod/actions/runs/39220285632> — в прошлой проверке CI успешен. Тесты — **временная база и mock медиа**, не реальная production.
- n8n `WF_00` <https://gremovod.app.n8n.cloud/workflow/j8Xqv8GQHjfJ5fVI>, execution #39: 7 модулей, 3 mock кадра/дорожки, targeted repair, 0 AI spend, `final_release_approved=false`.
- Эта координационная ветка: `coordination/agent-roles-handoff-20261019`, основана на `feature/p0-studio-foundation-20261019`; её PR также должен оставаться **Draft**.

## Принцип следующего шага

**Не создавать заново то, что уже существует.** Не подключать платные API, не писать в production SQLite, не объединять PR до проверки. Код, выполненный в GitHub runner, **не означает** работоспособность на локальном Windows. Если решение спорно — `docs/CODEX_DECISIONS.md` и `CODEX_DECISION_REQUIRED`.

## Формат обновления после передачи

Обновляй эти три строки **координатором одним коммитом**: `Сделано / Файлы / Следующий шаг`. Агент записывает своё состояние в `docs/agent_handoffs/<role>-<task>.md` либо в PR; так конфликтов с STATUS.md не будет.
