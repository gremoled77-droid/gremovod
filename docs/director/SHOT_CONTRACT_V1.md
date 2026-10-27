# ShotContract v1 — схема, ревизии, совместимость

Контракт кадра — это то, что человек подписывает под постановкой: что в кадре
до действия, что меняется, что в конце, где стоит камера и какие события
сценария кадр закрывает. Всё, что не выражено в контракте, промпт не должен
додумывать.

Реализация: `backend/director_contracts/schemas.py`. Схема — Pydantic v2,
`extra='forbid'` на всех моделях.

## 1. Модели

### SourceEvent — событие сценария

| Поле | Тип | Ограничения | Смысл |
|---|---|---|---|
| `event_id` | str | 1–64 | стабильный ID события |
| `episode_id` | str | 1–64 | серия-владелец |
| `text` | str | 1–2000 | авторская формулировка |
| `kind` | enum | mandatory_action, dialogue, reveal, transition, flashback | тип события |
| `locked` | bool | — | авторское истиранное, не переписывается |
| `causal_after` | list[str] | ≤32 | предшествующие события |
| `presentation_order` | int | 0–10000 | порядок показа |
| `timeline_order` | int | 0–10000 | хронологический порядок |
| `assigned_shot_ids` | list[str] | ≤32 | кадры, закреплённые за событием |
| `repeatable` | bool | — | событие можно показать повторно |

`presentation_order` и `timeline_order` разведены намеренно: флешбек показывается
не в том порядке, в котором происходит.

### PhysicalFact — один проверяемый факт о предмете

| Поле | Тип | Ограничения | Смысл |
|---|---|---|---|
| `subject_id` | str | 1–64 | что именно (автомобиль, персонаж) |
| `predicate` | str | 1–64 | свойство из реестра предикатов |
| `value` | str | ≤200 | текущее значение |
| `from_value` | str? | ≤200 | значение до перехода |
| `to_value` | str? | ≤200 | значение после перехода |
| `action` | str | ≤300 | что именно происходит |
| `event_id` | str? | ≤64 | событие, которым обосновано изменение |

### PhysicalState — состояние предметов внутри кадра

`continuity_mode` (`continuous` | `time_jump` | `flashback`) и три списка:
`opening` (до действия), `transitions` (изменения), `closing` (после).

### CameraPlan — постановка камеры

`framing`, `movement`, `direction` (до 80 символов) и `coordinate_space`
(`actor_world` | `camera_world`) — разные системы координат допустимы, но
записаны явно.

### ShotContract — карточка кадра

| Поле | Тип | Ограничения | Смысл |
|---|---|---|---|
| `shot_id` | str | 1–64 | ID кадра в студии (`production_nodes.id` вида frame) |
| `scene_id` | str | 1–64 | ID сцены (`production_nodes.id` вида episode) |
| `source_event_ids` | list[str] | ≤32 | какие события закрывает кадр |
| `duration_sec` | float | >0, ≤120 | длительность |
| `narrative_role` | enum | setup, reveal, reaction, transition, climax, closing | роль в сюжете |
| `character_ids` | list[str] | ≤32 | персонажи кадра |
| `asset_reference_ids` | list[str] | ≤32 | ID ассетов библиотеки проекта |
| `camera` | CameraPlan | — | постановка |
| `physical_state` | PhysicalState | — | состояние предметов |
| `author_lock_version` | int | 0–100000 | ревизия, на которой автор зафиксировал факты |
| `status` | enum | draft, proposed, approved | состояние контракта |
| `locked_paths` | list[str] | ≤64 | пути полей, которые агент не меняет |

### TimeJump и FilmOrder

`TimeJump(before_event_id, after_event_id, reason)` — объявленный скачок между
соседними событиями хронологии. `FilmOrder(presentation, timeline, time_jumps)` —
два порядка и список скачков.

### CapabilityProfile — возможности endpoint провайдера

Описаны в разделе «Профиль возможностей» в `DIRECTOR_V2_ARCHITECTURE.md`.
Ключевое: состояние `UNVERIFIED` / `BLOCKED` / `READY` считается из
подтверждённых полей, приблизительные значения не выдаются за доказанные.

## 2. Пример

```json
{
  "shot_id": "frame-7",
  "scene_id": "episode-3",
  "source_event_ids": ["card-1"],
  "duration_sec": 4.0,
  "narrative_role": "reveal",
  "character_ids": ["char-grem"],
  "asset_reference_ids": ["asset-vaz-front"],
  "camera": {"framing": "medium", "movement": "push_in", "direction": "", "coordinate_space": "actor_world"},
  "physical_state": {
    "continuity_mode": "continuous",
    "opening": [
      {"subject_id": "vaz", "predicate": "door_state", "value": "closed", "from_value": null, "to_value": null, "action": "", "event_id": null}
    ],
    "transitions": [
      {"subject_id": "vaz", "predicate": "door_state", "value": "", "from_value": "closed", "to_value": "open", "action": "гость открывает дверь", "event_id": "card-1"}
    ],
    "closing": [
      {"subject_id": "vaz", "predicate": "door_state", "value": "open", "from_value": null, "to_value": null, "action": "", "event_id": null}
    ]
  },
  "author_lock_version": 1,
  "status": "draft",
  "locked_paths": []
}
```

## 3. Правила ревизий

1. **Ревизия целая и локальная.** У каждого контракта своя ревизия
   (`shot_contracts.revision`), а не одна на серию. Правка одного кадра не
   инвалидирует остальные.
2. **Запись требует основания.** `PUT .../director/contracts/{shot_id}` принимает
   `base_revision`. Если текущая ревизия отличается — `409` и текст
   «Контракт изменился в другом окне». Чужая правка не перетирается.
3. **Отпечаток состояния.** `fingerprint(payload)` — sha256 от каноничного JSON:
   ключи отсортированы, порядок полей не влияет. `is_stale(expected, payload)`
   отвечает на вопрос «то ли это состояние, которое человек видел, когда
   подписывал предложение».
4. **Канонизация обязательна.** Модель Pydantic и словарь с теми же данными
   должны давать один отпечаток, иначе `is_stale` всегда отвечает «устарело».
   Для этого есть `payload_of`.
5. **Правка — точечная.** `repair(shot, changes)` применяет только перечисленные
   пути, не трогает заблокированные автором поля, проверяет результат целиком и
   отклоняет правку целиком, если она ломает непрерывность.
6. **Диф — для показа.** `diff(before, after)` возвращает список изменённых
   путей, а не новое состояние.

### Правила статусов

| Ситуация | Что происходит |
|---|---|
| Контракт сохранён без ошибок | статус сохраняется как прислан (`draft`, `proposed`, `approved`) |
| Контракт сохранён с ошибками | статус принудительно становится `draft`, в ответе `downgraded: true` |
| Чужой `shot_id` или сцена | `400` |
| Кадр не найден в серии | `404` |
| Конфликт ревизии | `409` |
| Ошибка схемы (FastAPI-валидация тела) | `422` |

Утвердить контракт с ошибками непрерывности нельзя: это и есть точка, где
человеческое решение и проверка совпадают.

## 4. Обратная совместимость

Схема v1 зафиксирована так:

- `extra='forbid'` на всех моделях — лишнее поле отклоняется, а не
  игнорируется. Это защищает от молчаливой потери данных, но означает, что
  **старый клиент, шющий поле, не сможет читать новый контракт**.
- Обязательные поля контракта не имеют значений по умолчанию, кроме явных
  `default_factory`. Контракт, созданный по v1, читается v1 без потерь.
- Порядок и набор полей не являются частью контракта: отпечаток строится по
  канонизованному словарю, поэтому перестановка полей не ломает ревизии.

### Правило добавления полей

1. Новое поле добавляется с `default`, а не как обязательное.
2. Версия схемы поднимается, поле входит в `SHOT_CONTRACT_V1` как необязательное.
3. Старые записи остаются валидными: `model_validate` их читает.
4. Изменение типа или семантики поля — это новая версия схемы, а не правка v1.

### Что хранится и как

Таблица `shot_contracts(series_id, shot_id, data, revision, updated_at)`,
первичный ключ — пара `(series_id, shot_id)`. В `data` лежит JSON контракта.
Повреждённая запись не роняет раздел режиссура: она пропускается при чтении и
перезаписывается при следующем сохранении.

## 5. Где что лежит

| Правило | Файл |
|---|---|
| Схемы | `backend/director_contracts/schemas.py` |
| Замечания и их порядок | `backend/director_contracts/validation.py` |
| Правила реестра событий | `backend/director_contracts/event_ledger.py` |
| Непрерывность | `backend/director_contracts/continuity.py` |
| Ревизии и отпечатки | `backend/director_contracts/revisions.py` |
| Точечный ремонт | `backend/director_contracts/repair.py` |
| Компиляция промпта | `backend/director_contracts/prompt_compiler.py` |
| Хранение и маршруты | `backend/storyboard.py` |
| Форма и замечания в UI | `frontend/src/shotContract.ts`, `frontend/src/ShotContractInspector.tsx` |
