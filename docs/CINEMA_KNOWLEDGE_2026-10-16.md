# Киноязык для студии: навыки и подсказки «I» (2026-10-16)

## Откуда
Источник: Jon Lewis, «Essential Cinema. An Introduction to Film Analysis» (2014), главы 2–6. Книга в корень проекта не копируется (это чужой защищённый текст; PDF лежит у владельца). Здесь только пересказ своими словами и выводы для студии.

## Пять тем и соответствующие навыки
Навыки лежат в `skills/`. Каждый: ключевые понятия, применение к ИИ-видео, чек-лист.

| Тема | Навык | Где в студии |
| --- | --- | --- |
| Нарратив и жанр | `skills/cinema-narrative-genre/` | «① Prompt Director + GPT» |
| Мизансцена | `skills/cinema-mise-en-scene/` | панель «Сцена» |
| Работа камеры | `skills/cinema-camera-work/` | «Стартовое меню видео» (CameraPanel) |
| Монтаж | `skills/cinema-editing/` | «③ Video Lab» (только видео) |
| Звук | `skills/cinema-sound-design/` | «④ Audio Lab» |

## Что уже сделано в коде (не закоммичено, сборка не запускалась)
- `frontend/src/CinemaInfo.tsx` (новый): кнопка «I» (lucide `Info`), по клику карточка из трёх пунктов. Тексты в объекте `TOPICS`.
- `frontend/src/App.tsx`: значки у Prompt Director (narrative), Video Lab при kind==='video' (editing), Audio Lab (sound).
- `frontend/src/CameraPanel.tsx`: значок (camera).
- `frontend/src/ScenePanel.tsx`: заголовок «Сцена» обёрнут в `panel-title`, значок (mise).
- `frontend/src/style.css`: стили `.cinema-info*` в конце файла.

## Что проверить дальше
- Полная сборка фронтенда и визуальная проверка пяти мест.
- Решить, нужен ли значок в Image Lab (сейчас нет).
- Открытый вопрос: короткая карточка (сейчас) или полная панель с примерами промптов из навыков.
- Коммит делать только по команде владельца.
