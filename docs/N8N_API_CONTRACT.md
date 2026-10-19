# GremoVOD Web ↔ n8n: контракт v1, первый sandbox-срез

Дата: 19.10.2026. Реализация: `backend/automation.py`. Единственный источник
данных — FastAPI. n8n читает задания и возвращает предложения. Прямого доступа
к SQLite, канону, файлам и оплате нет. Workflow в n8n этим изменением не создаётся.

## Что можно использовать без переделки

| Компонент | Использование |
| --- | --- |
| `main.connect`, SQLite, startup `register(app, studio)` | Транзакции, временные БД тестов, добавочные таблицы |
| `productions`, `production_links`, `production_nodes` | Исходный project, общий production, series, episode/scene, frame/shot; никаких вторых ID сцен |
| `storyboard.snapshot` | `base_revision` существующей доски; смена текста, состава и порядка даёт конфликт |
| `projects.revision`, `production_entities.state` | Версии карточек и идентичности; прежний редактор остаётся местом записи канона |
| Character Vault: `character_assets`, `character_versions`, `production_folders.character_owner` | Реальные/утверждённые/архивные референсы, рабочий образ и общий владелец |
| `library_assets`, `production_files`, `workflow_import` | Хранение и безопасный импорт медиа; n8n передаёт ID, не создаёт копию библиотеки |
| `security.quote/verify_quote/check_budget`, `series_economics`, `GenerationReview` | Существующий путь платных запусков. Пока не подключён к automation: платное полностью запрещено |
| `jobs`, `generation_approvals`, `job_delivery` | Провайдерские задания, резерв бюджета и восстановление скачивания. Для stub не используются |
| `activity` и frontend `ActivityContext`, `ProductionStoryboard`, `WorkflowPanel` | Пригодны для следующего UI-среза; новые задания пока читаются только через automation GET |
| `remote_access` | Прежний вход человека; service credential имеет отдельную проверку |

`agent_runs(id, project_id, created_at, data)` уже используется `/api/agents/run`
для синхронных агентов. Он не изменён. В первом срезе один запуск на задание:
`agent_run_id == task_id`; отдельной таблицы попыток пока нет.

## Идентификаторы и контекст

`project_id` в v1 — **source_project_id общего production**, а не рабочий проект
отдельного кадра. `production_id`, `series_id`, `scene_id`, `shot_id` — существующие
ID; scene имеет kind `episode`, shot — `frame`. Проверяются production → series →
scene → shot и принадлежность выбранных library asset именно source project.
Общие ассеты проектов кадров пока не доступны через этот контракт.

`canon_revision` — SHA256 от версии source project, упорядоченных записей Vault
(ID, character, category, model, note, timestamp) и файловых связей production.
Это версия контекста, не номер художественного утверждения канона.
`base_revision` — без изменений SHA256 из `storyboard.snapshot`.
Обе версии повторно проверяются при создании, первом claim, успешном callback
и approval. Расхождение — 409, без записи предложения или канона.
Уже принятые повторы возвращают прежний результат независимо от последующих правок.

Context возвращает сценарий, существующие узлы, текстовую identity и рабочий
asset персонажей, ID/категории Vault и файловые связи. Файлы, server paths,
provider keys и временные публичные URL не выдаются. Это не media download API.

## Авторизация

- Человек создаёт/отменяет/утверждает задания через существующую сессию Studio.
- n8n использует `Authorization: Bearer <service-token>`: минимум 32 символа,
  серверные переменные `STUDIO_AUTOMATION_TOKEN` и `STUDIO_AUTOMATION_PROJECT_ID`.
  Один token — один source project. Без конфигурации service API отвечает 503.
- Service token читает контекст/очередь/задание, захватывает и завершает задание.
  Он не создаёт и не утверждает задания, даже при одновременной browser cookie.
- Cookie/session не заменяет service token на service-only маршрутах.
- Исключения middleware ограничены `/api/v1/automation/`; каждый маршрут проверяет
  свои credentials. Host/Origin-защита сохраняется, остальные API не открываются.
- Для будущего сервера обязателен HTTPS через доверенный reverse proxy с
  `STUDIO_REMOTE_HOSTS`. Не выставлять локальный Windows backend в интернет.
  TLS, rotation, multi-project credentials и rate limiting — следующий этап эксплуатации.

## Маршруты

Все пути ниже имеют префикс `/api/v1/automation`.

| Метод и путь | Кто | Назначение |
| --- | --- | --- |
| `GET /contexts/{project_id}/{production_id}/{series_id}` | человек/service | Получить актуальные ID и обе ревизии |
| `POST /jobs` | человек | Создать queued; повтор ключа с тем же телом возвращает тот же task |
| `GET /jobs` | service | До 100 queued task_ids своего проекта, в порядке создания |
| `GET /jobs/{task_id}` | человек/service | Восстановить состояние, request, result, result_ref и журнал |
| `POST /jobs/{task_id}/claim` | service | Атомарно queued → running, зафиксировать execution_id n8n |
| `POST /callbacks` | service | running → review_required либо failed |
| `POST /jobs/{task_id}/cancel` | человек | queued/running/review_required → cancelled |
| `POST /jobs/{task_id}/review` | человек | review_required → approved/rejected; канон не меняется |

Запрос `POST /jobs` (значения ID/revision берутся из sandbox, не копируются буквально):

```json
{
  "project_id": "existing-source-project",
  "production_id": "existing-production",
  "series_id": "existing-series",
  "scene_id": "existing-episode-node",
  "shot_id": null,
  "canon_revision": "64-hex-from-context",
  "base_revision": "64-hex-from-context",
  "idempotency_key": "unique-request-key",
  "correlation_id": "trace-from-web",
  "stage": "storyboard",
  "agent_role": "A2",
  "instruction": "Верни текстовое предложение раскадровки",
  "skills": [{"name": "gremovod-stage-storyboard", "skill_commit_sha": "40-hex-pinned-source-commit"}],
  "reference_asset_ids": [],
  "model_provider": "stub",
  "model": "echo",
  "model_reason": "Sandbox contract verification",
  "estimated_cost": 0,
  "allowed_paid_media": false
}
```

Skills — записанные версии входа, а не доказательство их загрузки в n8n.
Проверка доступности commit/package исполнителем требуется до реального LLM.
В этом срезе доступны только storyboard/A2, stub/echo, нулевая оценка, без tools.
Неизвестные поля, цена > 0, другой provider/model или paid media дают 422.
Нет скрытого fallback на провайдера и нет исходящего сетевого вызова.

Claim: `{"execution_id":"n8n-execution-id"}`. Повтор того же claim для running
возвращает состояние. Другой execution или терминальное задание — 409.
Исполнитель обязан дождаться успешного claim до исполнения и не запускать
исполнение повторно, если его execution_id уже был захвачен ранее.

Callback:

```json
{
  "task_id": "returned-task-id",
  "execution_id": "n8n-execution-id",
  "event_id": "unique-callback-key",
  "status": "review_required",
  "proposal": "Текст предложения, без автоматической записи в сцену",
  "error_code": ""
}
```

Для failed требуется непустой `error_code` и пустой proposal. Callback не принимает
URL, media payload, стоимость, approval или patch канона. Ошибки — ограниченные
коды без токенов/ответов провайдера. `result_ref=automation:<task_id>` ссылается
на результат GET задания, не на библиотечный файл.

Review: `{"decision":"approved"}` или rejected. Approval относится только к
предложению; не разрешает оплату и не вызывает применение. Маршрута `/apply` нет.
Дальнейшая правка канона идёт отдельным запросом существующего редактора с его
актуальной ревизией и явным решением человека.

## Доставка, повторы и журнал

`automation_jobs` хранит очередь и текущее состояние, UNIQUE(project_id,
idempotency_key). Сравнивается всё нормализованное тело: другой payload — 409.
`automation_events` одновременно журнал переходов и inbox дедупликации callbacks:
PRIMARY KEY(task_id,event_id), одинаковое событие не вставляется повторно,
изменённое тело того же event_id — 409. Событие и состояние фиксируются одной
SQLite-транзакцией с `BEGIN IMMEDIATE`, включая одновременные create/claim.
Журнал не копирует входные prompts и credentials; предложение хранится в результате
и принятом callback для точного сравнения повторов. Содержимое proposal считается
приватными данными проекта и не пишется в обычные application logs.

Pull-очередь — минимальный durable outbox: commit задания сохраняет его для polling,
claim исключает его из очереди. Отдельный HTTP dispatcher, lease, auto retry,
dead-letter и повторная выдача running **не реализованы**. При потере ответа claim
используется прежний execution_id; при неопределённом исходе не делать новый платный
вызов. Зависшее running отменяется человеком, затем создаётся новое reviewed задание
с новым ключом. Cancel сохраняет терминальное состояние; поздний callback не
воскрешает задачу и не останавливает процесс n8n принудительно.

HTTP: 401 — credential, 404 — отсутствующий/чужой ресурс, 409 — конфликт версии,
повтора или состояния, 422 — схема, 503 — service не настроен.

## Проверка и следующий срез

`backend.test_automation` проходит путь одна сцена → queued → claim → callback →
review → GET, не меняя канон и не создавая provider jobs/approvals. Покрыты повторы,
конкуренция, отмена, ревизии, Vault, изоляция и remote cookie gate на временных данных.
`backend.test_n8n_skill_sync` проверяет pinned commit, reference hash, stable ID,
noop, duplicate binding и заблокированную ссылку на приватные данные.

Дальше: отдельный sandbox n8n flow с echo вместо модели (после разрешения на запись
workflow); затем UI/лента и выборочное применение предложения; затем интеграция
серверных денежных approvals, лимитов и учёта LLM; media download через короткие
подписанные URL; только потом реальные модели. PostgreSQL/S3 и SSE здесь не вводятся.
