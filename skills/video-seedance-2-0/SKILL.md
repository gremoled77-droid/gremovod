---
name: "video-seedance-2-0"
description: "Use when writing a prompt for Seedance 2.0 video (up to 15 s, @Image/@Video/@Audio references, beat-sync, scene extension) for the GremoVOD cartoon or a short promo; covers limits, reference tags, timing, character collage/model sheet workflow and the technical tail."
---

# Seedance 2.0 — промпты для видео

Статус: правила из инструкции владельца (ТВ-реклама) и практикума GORA ACADEMY (экшн и мультфильм), **вживую через студию не проверены**. Модель 2.0 не включена в запуск (`launch_enabled` в `backend/model_catalog.py`). Лимиты у провайдера (PiAPI) уточнять перед запуском.

## Когда выбирать

- Ролик до 15 секунд одним проходом. Для 30 с: две генерации и склейка, либо Seedance 2.5.
- Черновая раскадровка и пробы перед дорогим финалом на 2.5.
- Нужен ритм под музыку (beat-sync) или лип-синк под готовую озвучку.

## Референсы

- Теги `@Image1`, `@Image2`, `@Video1`, `@Audio1` (нумерация по типу, с `@`).
- Лимит: до 9 изображений + 3 видео + 3 аудио.
- Каждому тегу сразу назначать роль одной фразой: `@Image1 — лист персонажа Грэма, сохранить лицо и одежду`, `@Image2 — ВАЗ-2106, точная форма и цвет`, `@Audio1 — озвучка, лип-синк точно по ней`.
- Минимум: один референс на героя, один на машину/локацию, один на стиль или композицию.
- Один ракурс героя даёт «дрейф» лица. Надёжнее коллаж из нескольких ракурсов или лист персонажа (см. `references/character-sheet-and-storyboard.md`).

## Как строить промпт

1. Список референсов с ролями.
2. Формат (`16:9` или `9:16`).
3. Стиль и палитра (цвета фиксировать явно).
4. Разбивка по секундам: камера и действие в каждом отрезке (3–4 отрезка на 15 с).
5. Явный момент «читаемого» кадра героя или машины без эффектов поверх.
6. Технический хвост.

Секунды писать как диапазоны: `[0-3s]`, `[3-8s]`, `[8-13s]`, `[13-15s]`. Один приём камеры на отрезок из списка: slow push in, crash zoom, orbital shot, low angle, handheld shake, tracking shot, crane shot. Замедление: `slow motion 120fps`, возврат: `snap to real-time`.

## Шаблон под мультсериал

```
@Image1 — Грэм, lock face, outfit and proportions. @Image2 — ВАЗ-2106, preserve exact shape, color and plates.
Format 9:16. Style: stylized 3D cartoon, warm dusk palette of amber, teal and asphalt grey.

[0-3s] Low-angle tracking shot, Грэм parks the car at a wet Minsk curb, headlights flare
[3-8s] Slow push in through the windshield, Грэм checks the meter and sighs, steam from a cup
[8-12s] Whip pan to the street, passenger silhouette runs toward the car in the rain
[12-15s] Camera settles, car and Грэм fully clear, no effects over the characters

Stable face and car geometry throughout. No morphing. No deformation. No flickering. No ghosting. Realistic physics.
```

Для звука: `music and cuts synced to @Audio1's beat`, `lip sync reference @Audio1 exactly`, `impact sound cue at 8s`.

## Продление сцены

Готовое видео подключается как `@Video1`; в Seedance грузить **концовку исходника около 5 секунд**, чтобы модель поняла, что продолжает. Промпт продолжения:

1. Открыть строкой: `@Video1 — direct visual continuation reference. Replicate camera style, color palette, motion blur, atmosphere and all character appearances from @Video1 exactly. Scene continues from the final frame of @Video1.`
2. Формат и стиль те же, что в исходнике (для сериала: стилизованный 3D-мульт, не «hyper-realistic live-action»).
3. 3–4 отрезка `[0s–Xs]`, не больше 15 с суммарно, в каждом приём камеры.
4. Технический хвост.

Для Seedance 2.5 продление в несколько раундов описано в `video-seedance-2-5`.

## Промпт через LLM

Чтобы не тратить генерации на ручные промпты: загрузить в текстовую модель этот скилл (или инструкцию .txt) + картинку героя + важные элементы, которые нужно показать, а не придумывать, и описание сюжета. Просить «только готовый промпт, без пояснений».

## Рекламный режим (если нужен ролик-реклама)

Уровни эффектов: 1 премиальный минимализм, 2 максимальный VFX, 3 смешанный (рекомендуется: чистое начало, эффекты в кульминации, чистый финал). Указывать уровень в начале промпта. Финальный «геройский» кадр продукта 1.5–2 с без эффектов, логотип не закрывать. Не больше 2–3 типов переходов на 15 с.

Библиотека приёмов (называть конкретно, не «cool effects»): crash zoom, whip pan, orbital shot, snap zoom, dolly zoom, crane rise, speed ramp; match cut, smash cut on beat, light-wipe; sparks, volumetric light rays, lens flare sweep, rim light.

## Реальные лица и модерация

Seedance может останавливать генерацию с реальными лицами. Законный путь: нейтральные референсы, коллаж ракурсов, фото в полный рост. Для мультяшного Грэма проблема не возникает. Приёмы обхода фильтра (накладывать сетку на лицо, стилизация под рисунок ради обхода проверки) в скилл **не включены**.

## Чего избегать

- Не слать много референсов без ролей.
- Не перегружать эффектами весь ролик без пауз.
- Не закрывать героя/логотип частицами в ключевые секунды.
- Не писать абстракции («красиво», «круто», «cool», «nice»).
- Не упоминать знаменитостей и защищённых персонажей: описывать внешность словами.

## Технический хвост (всегда в конце)

`Stable face/product throughout. No morphing. No deformation. No flickering. No ghosting. Realistic physics. 4K cinematic.`
