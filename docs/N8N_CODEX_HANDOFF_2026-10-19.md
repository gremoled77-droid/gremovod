# Handoff для Codex: GremoVOD Web ↔ n8n

Дата: **2026-10-19** · статус: **ТЗ и источники собраны, код интеграции ещё не написан**.

## Зачем

Владелец развивает React/Vite + FastAPI GremoVOD (локально, затем веб/PWA) и n8n Cloud с шестью самостоятельными Agents A0–A5 и навыками из GitHub. Нужно связать их **контрактом API**, сохраняя единый канон, файлы, бюджеты и историю задач. Реальная генерация медиа, публикация, внесение новых решений в канон требуют утверждения пользователя.

## Прежде чем изменять код

1. Прочитать `AGENTS.md`, `CLAUDE.md`, `docs/GIT_WORKFLOW.md`, `docs/HANDOFF_CLAUDE_CODE.md`, `docs/TECHNICAL_SPEC.md`, `docs/STORYBOARD_PERSISTENCE_2026-10-16.md`.
2. `git fetch origin` и **прочитать** ветку `origin/integration/n8n` и `integrations/n8n/README.md`, `docs/TODO_N8N_WEB_SKILL_SYNC_2026-10-19.md`.
3. Работать в согласованном Codex worktree `codex/work`; не переключать занятые worktree. Для параллельной разработки n8n по разрешению владельца допустим **новый отдельный worktree**, основанный на `origin/integration/n8n`. Не изменять рабочую копию `main` и не перенаправлять тесты в боевую SQLite.
4. Перед конфликтующими изменениями сравнить `git status` и ветку; не переносить неучтённые изменения чужой работы, не делать force-push.

## Текущие существующие компоненты в коде

- `backend/storyboard.py` и `production_nodes` — существующая иерархия сцен/кадров, стабильные ID, ревизии и защищённый импорт.
- `backend/production_entities.py` — версии карточек, связи героев/локаций и выбранные файлы, `base_revision`.
- `backend/workflow_import.py` — безопасный импорт референсов в библиотеку.
- `backend/model_catalog.py` / `backend/adapters.py` — параметры провайдеров и проверенные режимы.
- `backend/security.py`, `backend/economics.py`, `backend/series_economics.py`, `frontend/src/GenerationReview.tsx` — согласование платных операций.
- `backend/job_delivery.py` — восстановление скачивания после уже завершённого задания.
- `backend/remote_access.py`, `docs/CLOUD_DEPLOY.md` — удалённый вход через cookie; это **не service credential** для n8n.
- `frontend/src/WorkflowPanel.tsx`, `ProductionStoryboard.tsx` — будущие клиентские точки интеграции; API-контракт должен предшествовать UI.

## Порядок работ для Codex

**Фаза 1. Проектирование контракта (без облачных/платных вызовов).**
- Подготовить `docs/N8N_API_CONTRACT.md`: `POST /api/v1/automation/jobs`, `GET /api/v1/automation/jobs/{task_id}`, `POST /api/v1/automation/callbacks`, `GET /api/v1/automation/contexts/{...}` и механизмы отмены/согласования; это **предлагаемые маршруты**, не существующие.
- Сначала сверить с действующими таблицами/jobs/production_nodes, избежать дублирования.
- Описать `idempotency_key`, `correlation_id`, `base_revision`, `skill_commit_sha`, `model_provider`, `estimated_cost`, `approval_state`, `result_ref` и статусные события. Разделить входное задание, событие, результат, правку канона.

**Фаза 2. Минимальная серверная реализация и тесты.**
- Миграция схемы для `agent_runs` и `automation_events`/outbox при необходимости; API router с сервисной авторизацией; принимать повторную доставку идемпотентно; на устаревшие ревизии отвечать 409; callbacks без прямого редактирования канона.
- Написать интеграционные тесты в отдельной временной БД: дубликат запроса/ответа, неверный токен, чужой project_id, устаревшая версия, отсутствие медиа approval, отмена и повторная доставка.
- Медиа остаётся у backend, n8n получает URL/ID; локальный Windows backend нельзя экспонировать напрямую в интернет.

**Фаза 3. Интерфейс обмена с n8n.**
- Один sandbox flow для пути web → FastAPI → n8n → callback → FastAPI → web. В n8n на первом этапе заглушка вместо платной LLM и media generation.
- UI видит задания и результаты через GET/SSE и подтверждает предложения; не пишет напрямую в n8n.
- Отдельным проектом — GitHub Skill Sync по TODO: SHA файла/references, сопоставление agent+skill id, update существующего skill, draft validation, approval публикации.

**Фаза 4. Наблюдаемость и передача.**
- Сохранять причину выбора модели Haiku/Sonnet/Opus, версии навыков, расход/оценку и версию канона. Логи исключают ключи и содержимое приватных media.
- Продемонстрировать одну сцену от задания до результата без платных генераций, сохранить тесты, коммиты и отчёт.

## Схема сообщения (черновой пример — уточнить после сверки существующего API)

```json
{
  "task_id": "uuid",
  "idempotency_key": "uuid",
  "project_id": "existing-project-id",
  "scene_id": "existing-node-id",
  "shot_id": "existing-frame-id-or-null",
  "stage": "storyboard",
  "agent_role": "A2",
  "base_revision": "actual-revision",
  "inputs": {
    "script_version_id": "existing-version-id",
    "reference_asset_ids": []
  },
  "execution": {
    "model_tier": "creative",
    "allowed_paid_media": false
  },
  "skills": [{"name": "gremovod-stage-storyboard", "git_commit_sha": "sha"}]
}
```

Это **предложение контракта**, не утверждение, что все поля уже есть в базе. Не генерировать фиктивные ID в рабочем проекте.

## Модель ветвления и сдачи

Ветка `integration/n8n` — долгоживущая согласованная ветка интеграции. Рекомендуемый безопасный процесс: новый отдельный worktree/feature branch от `origin/integration/n8n` **после проверки условий AGENTS.md**, PR обратно в `integration/n8n`, проверка тестов, затем отдельное объединение проверенного набора в `main`. Альтернатива — реализовать изменения в закреплённой `codex/work`, сохранив чужую работу, и отдельно cherry-pick только относящиеся к n8n коммиты в интеграционную ветку. Не переносить по умолчанию весь `codex/work` в `main` или `integration/n8n`.

Не выполнять живые n8n вызовы, публикации workflow, платные Kie/PiAPI запросы и изменения существующей базы без разрешения владельца.
