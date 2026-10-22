---
name: "trycgi-photo"
description: "Use when writing prompts for photo/image generation in GPT Image 2.5 (flare/sunburst) or Nano Banana 2.1 under the TRY CGI (AI HERO) system: strict photorealism, one ready prompt per answer, 360° reference sheets, reference roles, edits with a keep-list, and the artifact-cleanup mode (fractal detail, moire, oversharpening). Includes model choice rules and per-model prompt templates."
---

# TRY CGI: промпты для фото (GPT Image 2.5 и Nano Banana 2.1)

Источники: протокол и мастер-промпт TRY CGI (AI HERO); официальный гайд OpenAI (Cookbook, gpt-image-2/2.5); материалы Google (Gemini API), fal.ai, KDnuggets, сравнения Pixverse/fal. Пересказ своими словами. Пункты из пользовательских пересказов «с Reddit» не проверены и сюда не включены. Старый протокол (DALL-E 3, «8k, Unreal Engine, ray-traced») для этих моделей устарел.

## Когда подключать

Пишем или разбираем промпт для кадра, референс-листа или правки фото в GPT Image 2.5 или Nano Banana 2.1; в студии это каталог `backend/model_catalog.py` и системные правила `backend/prompt_rules.py`. Киноязык кадра: [cinema-five-pillars](../cinema-five-pillars/SKILL.md) и [cinema-shot-design](../cinema-shot-design/SKILL.md).

## Базовые правила TRY CGI (для обеих моделей)

- Модель выбрана заранее, вопросов не задаём. Тип кадра определяем сами: обычное изображение или 360° reference sheet (признаки: 360, turnaround, reference sheet, character/location/prop sheet, «со всех сторон»). Неясно: обычное изображение.
- Изображения сами не генерируем. Выдаём один готовый промпт в блоке кода (плюс при необходимости пропорции и использование референсов).
- Постоянные предпочтения: строгий фотореализм, физически точный свет, правдоподобные материалы, естественные несовершенства, сохранение личности, лица, композиции и ракурса, без «мультяшности» и «общего AI-вида».
- Референсы: Image 1 — личность, Image 2 — одежда, Image 3 — локация, Image 4 — предмет, Image 5 — стиль.
- 360° sheet: квадрат, сетка 2×2, один и тот же объект, личность и дизайн без изменений, меняется только ракурс (персонаж: front, 3/4, side, back).
- Слова-паразиты («beautiful», «amazing», «stunning», «masterpiece») заменять физическими свойствами: «overcast daylight», «matte black ceramic», «50mm feel».
- Не смешивать противоречия («минимализм» и «гипердетализация»): модель усредняет.
- Вид по умолчанию: без плёночного зерна и «киношных» эффектов (halation, grain). Зерно добавляется отдельно при монтаже. Решение владельца (вариант А): зерно добавляем при монтаже.

## Какую модель выбрать

| Задача | Модель |
|---|---|
| Естественная кожа, «снято на камеру», живой портрет, материалы | Nano Banana 2.1 |
| Текст на вывесках и упаковке, раскладка, точное следование длинному ТЗ, прозрачный фон | GPT Image 2.5 (sunburst — финал и мелкий текст, flare — быстрые черновики) |
| Стабильность лица между кадрами | Проверять на своих референсах: сравнения расходятся |

## GPT Image 2.5

Порядок промпта: тип результата → сцена → объект → детали (материал, свет, цвет) → ограничения → назначение.

- Начинать с типа результата: Product photo, Cinematic still, Commercial poster.
- Реализм: слова «photorealistic» или «real photograph» и «no glamorization, no heavy retouching». Материалы называть точно (не «чашка», а «матовая чёрная керамика с необожжённым ободком»).
- Камера (объектив, глубина резкости) задаёт общий вид, а не точную симуляцию. Для ночи, дождя, неона добавлять масштаб, атмосферу и цвет.
- Люди: кадрирование, масштаб, направление взгляда, взаимодействие с предметом. Пример: «full body visible, feet included; looking down at the book, not at the camera; hands naturally gripping the handlebars».
- Текст: в кавычках, позиция, шрифт, редкие слова по буквам, «render exactly once», «no extra text». До 3–4 слов. Проверять орфографию.
- Правка: строка 1 «Change only X», строка 2 «Keep exactly: …» (личность, геометрия, композиция, свет, ракурс, надписи). Повторять список в каждой итерации, модель его не удерживает.
- Референсы: номер и роль каждого, как соединять и что куда переносится. Для персонажа: «Do not redesign the character».
- Итерации: одно изменение за ход.
- Параметры задаются в API, а не текстом: `quality`, `size` (края до 3840, кратно 16, отношение до 3:1), `background`. «Transparent background» в тексте рисует фальшивую шашечку.
- Качество: старт с low или medium; high для мелкого текста, крупных портретов и правок с сохранением лица.
- Эталон-шаблон:

```
Cinematic still. [сцена, место, время]. [Объект: материал, одежда, поза, кадрирование, взгляд, руки].
[Свет: источник, направление, цвет]. Photorealistic, real photograph, natural skin texture and fabric wear,
no glamorization, no heavy retouching. Keep exactly: [личность, пропорции, композиция].
No extra text, no watermarks, no unrelated logos.
```

## Nano Banana 2.1

Писать 1–3 связных предложения, не набор тегов. Порядок: объект → композиция → действие → место → стиль.

- Не использовать бустеры («8k, masterpiece, ultra detailed») и взвешенный синтаксис: не помогают и могут навредить.
- Язык фотографа: «85mm portrait lens», «shallow depth of field», «late afternoon light raking from the left». Свет — источник, направление, цветовая температура. Эпоха или носитель задают весь вид («1960s aesthetic»).
- Правки без масок, простым языком: «Change only the subject's neck and shoulders…». Критичное защищать по именам: «the face (eyes, nose, expression) must remain completely untouched».
- При смене фона или одежды: «cast realistic shadows consistent with the original light source».
- Одна правка за промпт в сложной сцене; сложное делить на этапы, лучше многоходовым диалогом.
- Референсы подписывать ролями: «the person in image 1», «the car in image 2». Практический предел: около 3 входов для надёжности; по документации Google до 14 суммарно (до 5 персонажей и 10 объектов). Сверять с лимитом в `model_catalog.py` (`max_refs`).
- Текст: двойные кавычки, у каждого элемента свой стиль, 3–5 надписей. Мелкий текст на 1K плывёт, брать 2K; точный текст добавлять в редакторе.
- Формат задавать параметром, не словами. Исходники для правок — чёткие и крупные.
- Эталон-шаблон:

```
[Объект с одеждой и позой] in [место], [композиция и кадрирование]. [Действие].
Lit by [источник, направление, температура]. Shot on [камера], [фокусное] lens at [диафрагма],
shallow depth of field. Photorealistic, natural skin texture, no heavy retouching.
Keep exactly: [личность, лицо, пропорции].
```

## Режим: очистка артефактов (de-artifact pass)

Не использовать, если нужен киношный вид с зерном: режим удаляет и зерно. Применять только к кадрам с артефактами.

### 1. Когда применять
Фрактальная микродетализация (камни, листва, земля, фон), муар, повторяющиеся узоры и текстуры, цифровой перешарп, пятнистость, «шум» в тенях. Лучше до перевода кадра в видео, иначе артефакты мерцают.

### 2. Шаблон с зонами
Верхний слой — «что убрать и где», нижний — неизменный список. Уровень размышления ставить «Высокий» (если модель его поддерживает; не проверено).

```
Clean this image of generation artifacts while keeping its original look.
Remove grain, digital noise, fractal structures, moire, repeating patterns and artificial micro-detail
in these zones: [земля / деревья / фон / камни / ...].
Simplify overly complex areas; replace chaotic repeated textures with clean organic surfaces with
irregular detail. Remove artificial sharpness and oversharpening. Smooth tonal transitions, clean colors.
Keep necessary detail, volume and material texture; avoid over-smoothing, blur and plastic look.
Keep exactly: composition, object placement, character appearance, face, proportions, poses, lighting,
colors, perspective, art style.
Do not add new objects, do not reinterpret the scene, do not increase detail.
```

Краткая версия: «Remove grain and noise and fractal detail in [zones]. Do not touch composition or face.»

### 3. Предупреждение
Мастер-промпт требует «natural imperfections» и «film-quality realism». Этот режим их стирает, поэтому он отдельный и не включён по умолчанию. Если кожа стала пластиковой, повторить с акцентом на «visible skin pores, natural texture».

## Не проверено вживую

Режим очистки, влияние `quality` на артефакты, поддержка уровня размышления и поиска-заземления в PiAPI, лимит референсов GPT Image 2.5. Не включать как «проверено» до подтверждения владельца (`verified_at`).
