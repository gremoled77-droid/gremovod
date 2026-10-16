---
name: "video-flux-3"
description: "Use when writing a prompt for FLUX 3 video (Black Forest Labs): choosing t2v / i2v / Keyframes / video continuation, the CASTLE multi-shot scheme, dialogue and sound; no multi-reference mode yet."
---

# FLUX 3 (Black Forest Labs) — промпты для видео

Статус: правила из инструкции владельца, **вживую не проверены**, модель не включена в запуск. Мультиреференс (Omni Reference) и Video Editing на момент инструкции помечены «Soon»: перед работой проверить, не появились ли они.

## Выбрать режим до написания промпта

| Режим | Вход | Что писать в промпте |
|---|---|---|
| Text-to-Video | только текст | сцена целиком |
| Image-to-Video | одно стартовое фото | только то, что произойдёт дальше |
| Keyframes | несколько стоп-кадров по порядку | переход; модель строит один непрерывный план через кадры |
| Video Continuation | готовый клип | как сцена развивается дальше, без склейки |

Референсов с ролями («Image 1 = герой, Image 2 = машина») нет. Идентичность держится так:
- Keyframes с 2–4 кадрами героя/машины в нужных ракурсах (подходят кадры из коллажа/листа героя, см. `../video-seedance-2-0/references/character-sheet-and-storyboard.md`);
- одно фото как старт-кадр в i2v;
- в мультишоте дословно повторяемое описание субъекта (схема CASTLE).

Разные готовые кадры, которые не должны перетекать друг в друга, — отдельные генерации и хард-кат в CapCut, а не Keyframes.

## Принципы

- Направляй сцену, а не перечисляй предметы. Называй то, что увидела бы камера: конкретные существительные и глаголы.
- Начинай коротко, добавляй детали там, где нужен контроль.
- В i2v не пересказывай картинку, писать только движение и действие.
- Негативных промптов нет: описывай позитивную альтернативу. Исключение: `No on-screen text, no subtitles`.

## Четыре формата записи

1. Короткая фраза: `A red fox leaping through fresh snow, telephoto`
2. Развёрнутая: `[camera] shot of [subject] [action] in [environment]`, затем детали.
3. Именованные поля: `Camera shot: wide, low angle. Subject: ...`
4. Тайм-степ: `0.0–1.5s locked wide of a harbor. 1.5–3.0s slow push-in begins`

На 5 секунд — 2–3 бита, не больше. `HARD CUT` писать явно там, где меняется план.

## Схема CASTLE (мультишот, единый стиль)

Порядок сборки: Core summary → Environment → Subject → Timeline → Audio → Style & Look.

- **C**ore: одна строка на всю последовательность (кто, где, арка).
- **A**udio: на каждый план отдельно; общий трек: `One music bed across all three shots`.
- **S**ubject: фиксированное описание героя, **слово в слово** в каждом плане.
- **T**imeline: `Shot 1 [0.0s-2.5s]: ...` — камера и действие.
- **L**ook: реализм, палитра, зерно.
- **E**nvironment: обстановка, свет, глубина резкости на каждый план.

## Звук и речь

Синхронный звук по умолчанию. Реплика в кавычках с указанием, кто говорит и как: `Грэм on camera, speaking to the lens: "..." Tired, dry delivery`. Без `on camera` или `voiceover` текст может появиться надписью на экране. Язык речи проверять тестом: в инструкции список языков не дан.

## Технический хвост

`Realistic physics, consistent subject identity throughout, stable lighting continuity, no flickering, no morphing.`
