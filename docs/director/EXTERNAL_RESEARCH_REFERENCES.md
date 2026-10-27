# Карта внешних референсов

Цель документа — показать, что взято из внешних проектов, а что сделано
своими силами, и не допустить переноса кода под чужими лицензиями.

**Правило P0: код внешних проектов не переносится.** Берутся идеи и принципы,
реализация своя, на Python + FastAPI + SQLite + React. Локальные модели не
ставятся, GPL-код в дерево студии не попадает.

## 1. Таблица «референс → концепция → своя реализация → лицензия»

| Референс | Концепция | Своя реализация | Лицензия референса | Код перенесён |
|---|---|---|---|---|
| [Maestro](https://github.com/Blizaine/Maestro) (Wan2GP) | Разделение режиссуры на источник, физические контракты и проверку схемы; пошаговые чекпоинты | `backend/director_contracts/`: `schemas.py` (SourceEvent, PhysicalFact, ShotContract), `validation.py` (Issue, детерминированный порядок), `repair.py` (точечный ремонт) | WanGP Non-Commercial Evaluation License 1.1; вендорённый seed-vc — GPL-3.0 | **Нет** |
| [Maestro](https://github.com/Blizaine/Maestro) | Неизменяемые авторские свойства (геометрия кузова, внешность) нельзя перегенерировать текстом | `LOCKED_PREDICATES` в `schemas.py`, проверки `continuity_locked_change` | та же | **Нет** |
| [Maestro](https://github.com/Blizaine/Maestro) | Флешбек как расхождение порядка показа и хронологии | `presentation_order` / `timeline_order`, `TimeJump`, `FilmOrder`, `continuity_mode` | та же | **Нет** |
| [MoneyPrinterTurbo](https://github.com/IBM-SkillsBuild-AI-Builders-Challenge/MoneyPrinterTurbo) | Машина состояний задачи, идемпотентность, повтор с безопасной ревизией, ревизии артефактов | Ревизии контракта: `revisions.py` (`fingerprint`, `is_stale`, `changed_paths`), `repair.py`; идемпотентность импорта — существующая `storyboard_imports` | MIT | **Нет** |
| [AI Video Production Editor](https://github.com/LudwigKienle/ai-video-production-editor) | UX узлов и инспектора, каталог возможностей провайдера, права агента, 3D-блокинг | `ShotContractInspector.tsx` (инспектор), `CapabilityProfile` + `profile_from_catalog` (каталог возможностей), `locked_paths` (права агента) | GPL-3.0-or-later | **Нет** |
| AI Video Production Editor | Планирование кадра как отдельной сущности между сценарием и генерацией | `ShotContract` + таблица `shot_contracts` в `backend/storyboard.py` | GPL-3.0-or-later | **Нет** |
| StoryBored (из ТЗ) | Выбор дубля и утверждение кадра человеком | `status` контракта `draft → proposed → approved`; утверждение с ошибками запрещено | **не подтверждено** — поиск вёл на коммерческий аудиоплагин storybored.io с EULA, это другой продукт | **Нет** |
| NodeTool, OpenDirector, Showrunner | Вторичные UX-референсы, общее направление | Влияния на код не оказали | **не проверялось** | **Нет** |

## 2. Почему так

- **Maestro и AI Video Production Editor — GPL/некоммерческая лицензия.**
  Включение их кода в студию сделало бы студию производной работой с
  соответствующими обязательствами, а для Maestro ещё и ограничило бы
  коммерческое использование. Поэтому взяты только принципы.
- **MoneyPrinterTurbo (MIT)** разрешает перенос кода, но в этом инкременте
  код тоже не переносился: в студии уже есть своя машина состояний задач
  (`jobs`, `job_delivery`, `job_recovery`), и дублировать её хуже, чем
  согласовать правила.
- **Локальные модели не ставились.** ТЗ запрещает их в P0: студия работает с
  облачными провайдерами через `PiAPI` и существующий `adapters.py`.

## 3. Что осталось непроверенным

| Пункт | Почему | Что сделать |
|---|---|---|
| Commit SHA референсных репозиториев | `git clone` во внешний каталог заблокирован политикой окружения bash; копия репозитория не выполнялась | перед использованием любого кода — зафиксировать SHA и текст лицензии |
| Лицензия StoryBored из ТЗ | Поиск привёл на другой продукт с EULA | уточнить точную ссылку у владельца |
| NodeTool, OpenDirector, Showrunner | Не проверялись: влияния на код не оказали | проверять только если появится конкретная задача на них |
| `THIRD_PARTY_NOTICES` студии | В проекте такого файла нет, а новых внешних зависимостей не добавлялось | создать при первом же добавлении внешней зависимости |

## 4. Проверка на соответствие

- В `backend/director_contracts/` нет импортов сторонних пакетов — только
  `pydantic` и стандартная библиотека.
- В `frontend/src/shotContract.ts` и `ShotContractInspector.tsx` нет новых
  зависимостей — только React и существующие модули студии.
- `git diff --stat` для обоих инкрементов показывает только файлы этого
  репозитория.
- Ни один файл стороннего проекта не скопирован: все имена, структуры и
  сообщения написаны в терминах студии (`production_nodes`, `shot_contracts`,
  «контракт кадра», «событие сценария»).

## 5. Источники

- Maestro: <https://github.com/Blizaine/Maestro> — раздел License
  (WanGP Non-Commercial Evaluation License 1.1), <https://github.com/Blizaine/Maestro/blob/main/LICENSE>
- MoneyPrinterTurbo: <https://github.com/IBM-SkillsBuild-AI-Builders-Challenge/MoneyPrinterTurbo/blob/main/LICENSE>
  (MIT License, Copyright (c) 2024 Harry)
- AI Video Production Editor: <https://github.com/LudwigKienle/ai-video-production-editor>
  (GPL-3.0-or-later), <https://github.com/LudwigKienle/ai-video-production-editor/blob/main/LICENSE>
