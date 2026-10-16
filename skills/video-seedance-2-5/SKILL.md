---
name: "video-seedance-2-5"
description: "Use when writing a prompt for Seedance 2.5 video (up to 30 s in one pass, 30+10+10 references, local edit, 3D blockout, scene extension, beat-sync) for the GremoVOD cartoon or a promo; covers limits, tags, 3-act timing and the technical tail."
---

# Seedance 2.5 — промпты для видео

Статус: правила из инструкции владельца (ТВ-реклама, Seedance 2.5) и практикума GORA ACADEMY (для 2.0, перенесено по аналогии), сверены с документацией PiAPI (`docs/official-prompts/seedance-piapi.txt`, `docs/SEEDANCE_25_480P_5S_PROMPT.md`, разбор Codex). В каталоге `backend/model_catalog.py` модель уже включена в запуск и проверена по цене/параметрам; **правила промптов и расширенные референсы (видео, аудио) вживую не проверены**. Обзор по всем моделям: `docs/VIDEO_MODELS_PROMPTING_2026-10-17.md`.

## Через студию и PiAPI (task_type `seedance-2.5`)

| Параметр | Значение |
|---|---|
| Разрешение | 480p, 720p (по умолчанию), 1080p; 4K нет |
| Цена за секунду | 480p $0.15, 720p $0.35, 1080p $0.80 (`seedance-2.5-less-restriction` ×1.1) |
| Длительность | целое 4–30 с (по умолчанию 5) |
| Формат | 16:9 (по умолчанию), 9:16, 4:3, 3:4, 21:9, 1:1, `adaptive`; при картинке-референсе её пропорции важнее заданных |
| Референсы | до 30 картинок, до 10 видео, до 10 аудио; суммарная длина видео и суммарная длина аудио каждая не больше 30 с; аудио одно допускается |
| Теги в промпте | `@image1`, `@video1`, `@audio1` (строчными, по порядку массива; сервис сам конвертирует). Ссылка на несуществующий файл даёт 400 |

- **Теги.** Вариант `@Image1` из инструкций относится к интерфейсам Dreamina и других платформ. Через PiAPI и в студии писать строчными (`reference_label` в `prompt_rules.py` делает так же).
- **Реальные задачи** задаются `omni_reference_task_type`: `auto` (по умолчанию, модель сама определяет по тексту), `reference` (генерация по референсам), `edit` (правка исходного видео 4–30 с: `aspect_ratio: adaptive`, `duration: -1`) и `extend` (продолжение вперёд или назад: `aspect_ratio: adaptive`, `duration` 4–30). Если заявленный тип не совпадает с тем, что модель поняла из промпта, задача падает: для `extend` писать `Extend @video1 forward: …`, для `edit` писать `In @video1, change …`.
- **Видео-референсы дороже:** длительность входного видео × (цена/2) + выход × цена.
- **Черновой режим (draft).** Сначала черновик `draft: true` на 480p (дешёвый), затем финал по `draft_task_id` на 1080p (промпт, референсы, длительность не передаются, берутся из черновика; черновик живёт 7 дней). Это заменяет схему «черновик на 2.0, финал на 2.5» там, где нужно то же содержимое.
- **Что умеет адаптер студии сейчас:** обычная генерация с картинками-референсами (`image_urls`), 480p/5 с проверены по цене. Правку и продление видео и аудио-референсы адаптер пока не отправляет: `SEEDANCE_RULES` в `prompt_rules.py` запрещает писать `@videoN`/`@audioN` без реально переданных файлов. Отправка этих полей это отдельная задача адаптера.
- Режим `reference` не гарантирует точный первый кадр: картинка-референс задаёт пространство, композицию и свет, а не обязательно кадр 0.

## Чем отличается от 2.0

- До 30 с одним непрерывным проходом, консистентность героя и света на всей длине.
- До 50 референсов: 30 изображений + 10 видео + 10 аудио.
- Точность следования промпту выше (~20%), лучше физика ткани, жидкости, дыма.
- Локальная правка готового клипа без пересъёмки.
- 3D white-model (clay): грубая болванка фиксирует камеру и композицию, Seedance дорабатывает свет и материалы.
- Дороже 2.0 при равных условиях. Дешёвый путь на самой 2.5: черновой режим (480p), финал 1080p по тому же `draft_task_id`. Раскадровку и пробы можно гонять на 2.0.

## Референсы

- Теги как в 2.0: `@image1`, `@video1`, `@audio1`.
- Каждому тегу роль; при большом числе группировать по смыслу (герои, локации, стиль, звук, блокаут).
- Сложная вещь (машина, мелкие надписи): 3–5 ракурсов вместо одного.
- Герой: лист персонажа и коллаж ракурсов (см. `../video-seedance-2-0/references/character-sheet-and-storyboard.md`); при 30 изображениях можно держать лист, коллаж и кадры раскадровки одновременно.

## Структура: три акта

Hook (0–5 s) — задаёт мир и настроение. Development (5–22 s) — раскрытие, нарастание, возможна смена локации внутри одного прохода. Resolution (22–30 s) — кульминация и чистый финальный кадр.

Смену локации без склейки писать явно: `seamlessly transition to [scene] while camera continues its move`.

## Шаблон

```
@image1 — Грэм, lock identity. @image2 — ВАЗ-2106, strict shape and color reference.
@video1 — 3D white-model blockout of camera path, follow exact movement and framing, apply final lighting on top.
@audio1 — soundtrack and voice reference, cuts sync to its beat.
Format 16:9. Style: stylized 3D cartoon, warm dusk palette.

[0-5s] Opening — ...
[5-14s] Development — camera continues one unbroken move, seamlessly transition to ...
[14-24s] Climax — ...
[24-30s] Resolution — clean frame, Грэм and car fully readable, lip sync reference @audio1 exactly

Stable character identity and car geometry across the full 30 seconds. No morphing. No deformation. No flickering. No ghosting. Realistic physics. Consistent lighting.
```

## Продление и правка

- **Продление дальше 30 с** (multi-round extension): прикладывать концовку предыдущего клипа (~5 с) как `@video1` и открывать промпт строкой `@video1 — direct visual continuation reference. Replicate camera style, color palette, motion blur, atmosphere and all character appearances from @video1 exactly. Scene continues from the final frame of @video1.` Референсы героя дублировать, как в предыдущем раунде. Схема взята из практикума для 2.0; на 2.5 проверить.
- **Локальная правка:** `@video1 — original clip, regenerate only [деталь], keep camera, motion, lighting and timing unchanged.` Экономит генерации при мелких правках.

## Звук

Один аудиофайл может вести темп всего ролика: `video cuts and camera moves synced precisely to @audio1's beat drops`. Развитие по актам: `music builds from minimal ambient tension to full arrangement by the climax at 24s`.

**Русская речь.** Реплики писать кириллицей дословно, с именем говорящего, повторяя их внутри нужного `CUT`. Если слова, паузы или лип-синк должны быть точными, подключать готовую дорожку и назначать её единственным авторитетом по речи. Готовые формулировки и правила: `references/directing-and-dialogue.md`. Работоспособность на PiAPI проверить на коротком отрезке до полной генерации.

## Режиссура, референсы, непрерывность

Каркас промпта (`Format … 24 fps, exactly N seconds` → Style → References → Characters → Scene → Audio → `CUT n - 00.00-04.20` → Negative), стратегия длительности, референс-иерархия, журнал непрерывности и чек-лист проверки: `references/directing-and-dialogue.md`.

## Чего избегать

- Не загружать много референсов без ролей (первая причина путаницы).
- Не больше 3–4 типов переходов на 30 с.
- Не закрывать героя эффектами в финале (держать 2–3 с чистого кадра).
- Не писать абстракции вместо конкретных приёмов камеры и света.
- Реальные лица: нейтральные референсы, коллаж ракурсов; обход фильтра модерации не использовать.

## Технический хвост

`Stable face/product throughout. No morphing. No deformation. No flickering. No ghosting. Realistic physics. 4K cinematic. Consistent identity and lighting across the full 30 seconds.`

## Связанные материалы

- Сводка по всем видеомоделям, источники и расхождения: [docs/VIDEO_MODELS_PROMPTING_2026-10-17.md](../../docs/VIDEO_MODELS_PROMPTING_2026-10-17.md).
- Что и зачем ставить в кадре и клипе: [gremovod-stage-video](../gremovod-stage-video/SKILL.md) (страница «Видео»), [gremovod-stage-frames](../gremovod-stage-frames/SKILL.md) (страница «Кадры»), [cinema-five-pillars](../cinema-five-pillars/SKILL.md) (формула кадра и чек-лист).
