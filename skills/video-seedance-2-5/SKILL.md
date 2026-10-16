---
name: "video-seedance-2-5"
description: "Use when writing a prompt for Seedance 2.5 video (up to 30 s in one pass, 30+10+10 references, local edit, 3D blockout, scene extension, beat-sync) for the GremoVOD cartoon or a promo; covers limits, tags, 3-act timing and the technical tail."
---

# Seedance 2.5 — промпты для видео

Статус: правила из инструкции владельца (ТВ-реклама, Seedance 2.5) и практикума GORA ACADEMY (для 2.0, перенесено по аналогии). В каталоге `backend/model_catalog.py` модель уже есть и проверена по цене/параметрам PiAPI; **правила промптов и расширенные референсы (видео, аудио) вживую не проверены**. Лимиты уточнять у провайдера: они зависят от платформы (BytePlus, PiAPI, Higgsfield, Dreamina).

## Чем отличается от 2.0

- До 30 с одним непрерывным проходом, консистентность героя и света на всей длине.
- До 50 референсов: 30 изображений + 10 видео + 10 аудио.
- Точность следования промпту выше (~20%), лучше физика ткани, жидкости, дыма.
- Локальная правка готового клипа без пересъёмки.
- 3D white-model (clay): грубая болванка фиксирует камеру и композицию, Seedance дорабатывает свет и материалы.
- Дороже 2.0: черновики и раскадровку гонять на 2.0, финал собирать на 2.5.

## Референсы

- Теги как в 2.0: `@Image1`, `@Video1`, `@Audio1`.
- Каждому тегу роль; при большом числе группировать по смыслу (герои, локации, стиль, звук, блокаут).
- Сложная вещь (машина, мелкие надписи): 3–5 ракурсов вместо одного.
- Герой: лист персонажа и коллаж ракурсов (см. `../video-seedance-2-0/references/character-sheet-and-storyboard.md`); при 30 изображениях можно держать лист, коллаж и кадры раскадровки одновременно.

## Структура: три акта

Hook (0–5 s) — задаёт мир и настроение. Development (5–22 s) — раскрытие, нарастание, возможна смена локации внутри одного прохода. Resolution (22–30 s) — кульминация и чистый финальный кадр.

Смену локации без склейки писать явно: `seamlessly transition to [scene] while camera continues its move`.

## Шаблон

```
@Image1 — Грэм, lock identity. @Image2 — ВАЗ-2106, strict shape and color reference.
@Video1 — 3D white-model blockout of camera path, follow exact movement and framing, apply final lighting on top.
@Audio1 — soundtrack and voice reference, cuts sync to its beat.
Format 16:9. Style: stylized 3D cartoon, warm dusk palette.

[0-5s] Opening — ...
[5-14s] Development — camera continues one unbroken move, seamlessly transition to ...
[14-24s] Climax — ...
[24-30s] Resolution — clean frame, Грэм and car fully readable, lip sync reference @Audio1 exactly

Stable character identity and car geometry across the full 30 seconds. No morphing. No deformation. No flickering. No ghosting. Realistic physics. Consistent lighting.
```

## Продление и правка

- **Продление дальше 30 с** (multi-round extension): прикладывать концовку предыдущего клипа (~5 с) как `@Video1` и открывать промпт строкой `@Video1 — direct visual continuation reference. Replicate camera style, color palette, motion blur, atmosphere and all character appearances from @Video1 exactly. Scene continues from the final frame of @Video1.` Референсы героя дублировать, как в предыдущем раунде. Схема взята из практикума для 2.0; на 2.5 проверить.
- **Локальная правка:** `@Video1 — original clip, regenerate only [деталь], keep camera, motion, lighting and timing unchanged.` Экономит генерации при мелких правках.

## Звук

Один аудиофайл может вести темп всего ролика: `video cuts and camera moves synced precisely to @Audio1's beat drops`. Развитие по актам: `music builds from minimal ambient tension to full arrangement by the climax at 24s`. Русская озвучка: проверять лип-синк на малом отрезке до полной генерации (в инструкции язык не уточняется).

## Чего избегать

- Не загружать много референсов без ролей (первая причина путаницы).
- Не больше 3–4 типов переходов на 30 с.
- Не закрывать героя эффектами в финале (держать 2–3 с чистого кадра).
- Не писать абстракции вместо конкретных приёмов камеры и света.
- Реальные лица: нейтральные референсы, коллаж ракурсов; обход фильтра модерации не использовать.

## Технический хвост

`Stable face/product throughout. No morphing. No deformation. No flickering. No ghosting. Realistic physics. 4K cinematic. Consistent identity and lighting across the full 30 seconds.`
