---
name: "video-seedance-2-0"
description: "Use when writing a prompt for Seedance 2.0 video (up to 15 s, @Image/@Video/@Audio references, beat-sync, scene extension) for the GremoVOD cartoon or a short promo; covers limits, reference tags, timing, character collage/model sheet workflow and the technical tail."
---

# Seedance 2.0 — промпты для видео

Статус: правила из инструкции владельца (ТВ-реклама) и практикума GORA ACADEMY (экшн и мультфильм), **вживую через студию не проверены**. Модель 2.0 не включена в запуск (`launch_enabled` в `backend/model_catalog.py`). Лимиты у провайдера (PiAPI) уточнять перед запуском.

## Через PiAPI (`model: "seedance"`, task_type `seedance-2*`)

Источники: `docs/official-prompts/seedance2-piapi.txt` и `seedance-private-asset-piapi.txt` (сохранены 17.10.2026; страницы PiAPI). Не проверено вживую. Сводка по моделям: `docs/VIDEO_MODELS_PROMPTING_2026-10-17.md`.

| task_type | Уровень | Цена за секунду (480p / 720p / 1080p) |
|---|---|---|
| `seedance-2` | Pro | $0.10 / $0.20 / $0.50 |
| `seedance-2-fast` | Fast | $0.048 / $0.096 / нет 1080p |
| `seedance-2-mini` | Mini | $0.042 / $0.084 / нет 1080p |
| `…-less-restriction` | те же уровни, мягче модерация | примерно +10% к строгому |

- **Режимы** (`mode`, при пропуске определяется сам): `text_to_video` (без референсов); `first_last_frames` (1–2 картинки как первый и последний кадр, jpg/jpeg/png/webp/bmp; `aspect_ratio` можно `auto` по первой картинке); `omni_reference` (до 9 картинок, до 3 видео mp4/mov до 100 МБ, до 3 аудио mp3/wav суммарно до 15 с; всего 1–15 референсов; одно аудио без картинки или видео не принимается).
- **Длительность** целое 4–15 с (по умолчанию 5); сумма входных видео до 15.4 с. **Разрешение** `480p` по умолчанию (у Mini `720p`); 1080p только у `seedance-2`. Старые `*-preview` и `*-vip` переадресуются на формальные модели.
- **Формат:** `21:9`, `16:9` (по умолчанию), `4:3`, `1:1`, `3:4`, `9:16`.
- **Цена с видео-референсами:** цена × выход + цена/2 × длительность входных видео.
- **Теги:** `@image1`, `@video1`, `@audio1` строчными по порядку своих массивов; допустим китайский формат `@图片1`. Ссылка на отсутствующий файл даёт ошибку.
- **Модерация:** при отказе кредиты возвращаются; строгие Pro и Fast могут повторить проверку один раз, у Mini повтор только для текста на 720p, у `-less-restriction` повтора нет.
- **Пиковые часы:** 09:00–15:00 по GMT очередь может доходить до нескольких часов (в Минске это 12:00–18:00).

## Private Asset Library

Хранит лица, персонажей, видео и аудио один раз и ссылается на них как `asset://<asset_id>`; даёт устойчивую идентичность героя между кадрами и не обрабатывает файл при каждом запуске.

- **Только модели `-less-restriction`.** Строгие варианты отклоняют `asset://` с кодом 422; `auto_upload_assets: true` тоже требует `-less-restriction`. Решение, использовать ли этот уровень модерации, принимает владелец.
- Загрузка: `POST /api/v1/asset/upload` (`url` публичный не меньше 24 ч, `asset_type` Image/Video/Audio, `name`), ответ 202 с `asset_id`; статусы `Processing` → `Active` (можно использовать) или `Failed` (не скачался, отклонён, несколько лиц). Заголовок `X-API-Key`; нужен план не ниже hobbyist.
- Квоты и срок хранения при простое: hobbyist 500 и 3 дня, developer 2000 и 7, premium 5000 и 15, enterprise 10000 и 15; обращение продлевает срок. `Failed` в квоту не входят.
- Требования: картинка до 30 МБ, пропорции 0.4–2.5, стороны 300–6000 px, форматы jpeg/png/webp/bmp/tiff/gif/heic; видео mp4/mov до 50 МБ, 2–15 с, 24–60 к/с; аудио mp3/wav до 15 МБ, 2–15 с.
- **Паттерн для сериала:** главный герой (Грэм) и ВАЗ-2106 как управляемые ассеты, `image_urls: ["asset://…", "https://…сцена.png"]` и `auto_upload_assets: false`; разовые гости и фон идут обычными ссылками или временным автозагрузчиком (`auto_upload_assets: true`). В промпте ассеты называются теми же `@image1`, `@image2` по позиции.

## Когда выбирать

- Ролик до 15 секунд одним проходом. Для 30 с: две генерации и склейка, либо Seedance 2.5.
- Черновая раскадровка и пробы перед дорогим финалом на 2.5.
- Нужен ритм под музыку (beat-sync) или лип-синк под готовую озвучку.

## Референсы

- Теги `@image1`, `@image2`, `@video1`, `@audio1` (нумерация по типу, с `@`).
- Лимит: до 9 изображений + 3 видео + 3 аудио.
- Каждому тегу сразу назначать роль одной фразой: `@image1 — лист персонажа Грэма, сохранить лицо и одежду`, `@image2 — ВАЗ-2106, точная форма и цвет`, `@audio1 — озвучка, лип-синк точно по ней`.
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
@image1 — Грэм, lock face, outfit and proportions. @image2 — ВАЗ-2106, preserve exact shape, color and plates.
Format 9:16. Style: stylized 3D cartoon, warm dusk palette of amber, teal and asphalt grey.

[0-3s] Low-angle tracking shot, Грэм parks the car at a wet Minsk curb, headlights flare
[3-8s] Slow push in through the windshield, Грэм checks the meter and sighs, steam from a cup
[8-12s] Whip pan to the street, passenger silhouette runs toward the car in the rain
[12-15s] Camera settles, car and Грэм fully clear, no effects over the characters

Stable face and car geometry throughout. No morphing. No deformation. No flickering. No ghosting. Realistic physics.
```

Для звука: `music and cuts synced to @audio1's beat`, `lip sync reference @audio1 exactly`, `impact sound cue at 8s`.

## Продление сцены

Готовое видео подключается как `@video1`; в Seedance грузить **концовку исходника около 5 секунд**, чтобы модель поняла, что продолжает. Промпт продолжения:

1. Открыть строкой: `@video1 — direct visual continuation reference. Replicate camera style, color palette, motion blur, atmosphere and all character appearances from @video1 exactly. Scene continues from the final frame of @video1.`
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

## Связанные материалы

- Сводка по всем видеомоделям, источники и расхождения: [docs/VIDEO_MODELS_PROMPTING_2026-10-17.md](../../docs/VIDEO_MODELS_PROMPTING_2026-10-17.md).
- Что и зачем ставить в кадре и клипе: [gremovod-stage-video](../gremovod-stage-video/SKILL.md) (страница «Видео»), [gremovod-stage-frames](../gremovod-stage-frames/SKILL.md) (страница «Кадры»), [cinema-five-pillars](../cinema-five-pillars/SKILL.md) (формула кадра и чек-лист).
