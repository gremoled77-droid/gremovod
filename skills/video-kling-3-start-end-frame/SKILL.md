---
name: "video-kling-3-start-end-frame"
description: "Use when animating between two storyboard frames with Kling 3.0 (Start Frame + Last Frame): how to prepare the pair, write only the transition, 5-second phase timing, negative prompt; incompatible with multi-shot."
---

# Kling 3.0 — Start Frame + Last Frame

Статус: правила собраны из документации провайдеров и практических гайдов (официального шаблона у Kling нет), **вживую через студию не проверены**. Модель не включена в запуск. Имена полей зависят от провайдера: сверять с документацией PiAPI.

## Когда выбирать

Есть два кадра раскадровки (начало и конец действия), нужен один плавный план между ними. Для смены планов и диалога по кадрам — мультишот из `video-kling-3-omni`.

**Ласт-кадр работает только в одношотовом режиме.** Мультишот допускает только первый кадр. Выбор: два ключевых кадра и один план, либо мультишот и один старт-кадр.

## Как передать кадры

- Интерфейс kling.ai: Image to Video → «Add End Frame».
- API: одна картинка = первый кадр, две = первый и последний; либо `frame: first/last`, индексы 0 и -1, либо поля `image` и `image_tail`.
- Соотношение сторон подхватывается из картинок, но оно должно быть одинаковым (и желательно разрешение).

## Как готовить пару

- **Ласт-кадр делать из старт-кадра**, а не с нуля: тот же герой, одежда, свет, палитра, фон. Меняется только то, что должно измениться.
- Можно менять: поза, жест, мимика, ракурс в пределах плана, крупность, положение в кадре, состояние предмета (дверь закрыта/открыта), свет (мягко).
- Ломает переход: другой персонаж/лицо, другая одежда, другая локация, зеркальный разворот, резкая смена стиля.
- Слишком разные кадры = монтажная склейка, а не плавное движение.
- Машина и герой должны совпадать по форме, цвету, деталям в обоих кадрах.

## Промпт: описывать только переход

Порядок: что происходит между кадрами (одно действие, без внешности) → камера (один приём, направление и скорость) → темп (`smooth continuous motion, no cuts`) → окружение → стиль → аудио → формат.

Формула: [что двигается] + [камера] + [темп] + [изменения окружения].

Длительность: 5 с рабочий стандарт (3–15 возможны). Раскладка на 5 с: 0–1.5 с начало движения, 1.5–3.5 с основная фаза, 3.5–5 с выход в ласт-кадр. На 10 с — 5 фаз по 2 с. Писать: `motion settles exactly into the final composition by the last frame`. Не растягивать на 10–15 с малое движение: модель начнёт придумывать лишнее.

## Шаблон

```
START FRAME: [кадр 1]
LAST FRAME: [кадр 2 — тот же кадр, изменено только: ...]
PROMPT (EN):
Action — Грэм leans toward the passenger window and opens the door from inside.
Camera — static, no movement.
Pacing — smooth deliberate motion, single continuous take, no cuts.
Environment — rain keeps falling, headlights unchanged.
Audio — rain on the roof, door latch click, no music.
Duration: 5s. Aspect ratio: 9:16. Mode: pro.
Smooth continuous motion, no cuts, no camera shake. Stable facial identity and clothing throughout. No morphing, no deformation, no flickering. Realistic physics and weight. Motion resolves exactly into the final frame composition.
NEGATIVE: cuts, scene change, morphing, extra people, text overlay, watermark
```

У Kling негативный промпт есть (до 2500 символов), туда выносить `no cuts, no morphing, no camera shake`.

## Мультишот без ласт-кадра (напоминание)

Master Prompt + `Shot 1: … Shot 2: …`, до 6 планов по 1–12 с, до 500 символов на план, сумма равна общей длительности. Описание героя один раз и дословно в каждом плане.

## Элементы и звук

Включить «Bind elements to enhance Consistency» (в интерфейсе kling.ai; через API проверить). Элемент до 3 картинок, имя, голос. Речь EN/CN/JP/KR/ES; **русской речи нет**, реплики накладывать в монтаже.

## Чего избегать

Переописывать внешность и фон, уже видные на кадрах; два сильно разных кадра; мультишот вместе с ласт-кадром; несколько приёмов камеры в плане; абстракции («красиво», «кинематографично»); ласт-кадр, нарисованный с нуля.

## Технический хвост

`Smooth continuous motion, no cuts, no camera shake. Stable facial identity and clothing throughout. No morphing, no deformation, no flickering. Realistic physics and weight. Motion resolves exactly into the final frame composition.`
