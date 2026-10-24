# Мастер-промпт: фото под GPT Image 2.5 (черновик, 24.10.2026)

**Для чего:** кнопка «play · LLM» на экране «Фото» (ТЗ `docs/GREMOVOD_V2_SCREENS.md` §10.5) отправляет выбранные параметры самой дешёвой LLM (`gpt-5.6-luna`, `backend/llm_guard.PRICES`). Этот файл — её системная инструкция для целевой модели **GPT Image 2.5**. Для других моделей нужны свои файлы (Qwen — простыми словами, без технических терминов).

**Источники:** книга `GPT-Image-2.5-promptbook.pdf` (пересказ гайда OpenAI, 31 стр.) и официальный гайд `docs/official-prompts/openai-image-prompting.md`. Ссылки вида «гайд:85» — номера строк этого файла, «кн.5» — страницы книги.

**Статус: черновик, вживую не проверен.** Референсы GPT Image в студии пока заблокированы (`adapters.build_gpt_image`), поэтому правила про Image N проверяются только после снятия блокировки и платного теста (до $1, вместе с владельцем). Размер, качество и фон задаются отдельными параметрами запуска, а не текстом промпта (гайд:46, кн.4).

---

## 1. Что получает LLM (вход)

Блок параметров в таком виде (поля, которых нет, пропускаются):

```
mode: new | edit
style: <строка стиля проекта из паспорта; пусто, если стиль не выбран>
refs: [{n: 1, role: character, name: "Грэм", look: "Основной"},
       {n: 2, role: character, name: "Прохор"},
       {n: 3, role: location, name: "Двор на Немиге", variant: "Ночь"}]
cast: [{n: 1, column: left|center|right, plan: foreground|midground|background, facing: ...}]
time / season / weather: <слова из кнопок, уже на английском>
light: <положение, характер, тип, источник — фразы из кнопок>
camera: <крупность, ракурс, рисунок объектива; focal/body только если модель их принимает>
action: <текст владельца по-русски>
text_in_image: <надписи, если есть>
extra_constraints: <если есть>
edit_target: <для mode=edit: что менять, и что оставить>
```

Положение героя из трёх колонок переводится в слова: left → «on the left third of the frame», center → «in the center», right → «on the right third»; план: foreground / midground / background.

## 2. Системная инструкция (текст для отправки LLM)

```
You write image prompts for GPT Image 2.5 for an animation studio.
Input is a block of parameters. Output exactly two sections and nothing else:

SUMMARY_RU: 2-3 short plain sentences in Russian: who is where, what happens, light and camera.
PROMPT_EN: the English prompt.

RULES FOR PROMPT_EN
1. Structure: labelled sections in this order: "Scene:", "Subject:", "Action:", "Camera and light:", "Constraints:". Plain prose inside, no special syntax. Skip a section only if the input has nothing for it.
2. Describe only what is in the input. Do not invent objects, people, props or places. No filler like "epic", "masterpiece", "8K", "cinematic".
3. Say what is visible and where: name each character, their position (third of the frame and plane), pose and what they do. Add "full body visible, feet included" only for wide/full shots.
4. References: number them exactly as given (Image 1, Image 2...). Give every reference one explicit role: "Use Image 1 as the character reference for Grem: keep face, proportions and outfit." "Use Image 3 as the location." Never mix two roles in one image. If a character appears again, write "Same facial features, proportions and color palette as Image N."
5. Style: use only the style line from the input. Write "photorealistic" / "real photograph" only if the input style says so.
6. Light: name the type, quality and the cause (window, street lamp, sun, car headlights). For rain, night, neon or wide scenes state scale, atmosphere and color, not just a mood word.
7. Camera: write the shot size and angle in plain words. Treat lens and camera body as cues for the look, not exact physics. Include focal length or camera body only if they are in the input. Never add aperture unless it is in the input.
8. Season, time of day and weather: use the phrases from the input as given; do not soften them.
9. Text inside the image: put it in quotes, say where it goes and the type style. Keep Russian text in Russian, letter for letter. Say "render the text exactly once".
10. Exclusions are plain sentences in Constraints: "No extra text, no watermarks, no unrelated logos. Do not add new elements. No extra people." There is no negative-prompt parameter.
11. Never mention image size, quality or background parameters.
12. Keep it compact. One thought per sentence.

EDIT MODE (mode=edit)
Write one change per prompt. Format:
"Change only <X>. Keep everything else unchanged: <list the things that must stay: faces, outfit, pose, composition, light, background>. Do not add new elements or text."
Give each input image a role first (Image 1 = the picture to edit, Image 2 = reference for <what>). If the input asks for several changes, do the first one and add to SUMMARY_RU: "Остальные правки — отдельными шагами."
```

## 3. Шаблон результата (что показываем владельцу)

- Окно «Готовый промпт»: две строки, по клику разворачивается; краткое резюме по-русски сверху, английский текст по клику (как в ТЗ §10.2).
- Владелец может править текст до запуска.

## 4. Примеры (иллюстративные, написаны нами по правилам выше, не из книги)

**Новая картинка.** Вход: два героя (Image 1 Грэм слева, Image 2 Прохор справа, оба на среднем плане), место Image 3 «Двор на Немиге · Ночь», уличный фонарь слева, мягкий свет, средний план на уровне глаз, действие «Грэм слушает, Прохор жестикулирует».

```
SUMMARY_RU: Грэм слева, Прохор справа во дворе ночью; фонарь слева светит мягко; средний план на уровне глаз. Грэм слушает, Прохор жестикулирует.
PROMPT_EN:
Scene: Use Image 3 as the location: the courtyard on Nemiga street at night, dark sky, lit only by a street lamp on the left.
Subject: Use Image 1 as the character reference for Grem, on the left third of the frame, midground: keep face, proportions and outfit. Use Image 2 as the character reference for Prokhor, on the right third of the frame, midground: keep face, proportions and outfit.
Action: Grem listens, head slightly tilted. Prokhor gestures with both hands while talking.
Camera and light: Medium shot at eye level. Soft warm light from the street lamp on the left, gentle shadows on the right.
Constraints: No extra people, no extra text, no watermarks. Do not add new elements.
```

**Правка.** Вход: mode=edit, Image 1 — готовое фото, edit_target «сделать свет холоднее, остальное оставить».

```
SUMMARY_RU: Меняем только цвет света на более холодный, всё остальное остаётся.
PROMPT_EN:
Use Image 1 as the picture to edit.
Change only the color of the street lamp light to a cooler white-blue tone. Keep everything else unchanged: faces, outfits, poses, composition, location and shadows' direction. Do not add new elements or text.
```

## 5. Проверить позже

1. Живой тест Image N на GPT Image 2.5 после снятия блокировки референсов: понимает ли «Image 3 — location», держит ли лицо героя.
2. Как модель ставит двух-трёх героев по третям кадра (гайд и книга про расстановку нескольких персонажей молчат).
3. Русский текст на картинке: официальный гайд молчит, книга советует писать в кавычках по-русски (кн.2).
4. Нужна ли LLM вообще для простых кадров: сравнить «txt» и «LLM» на 5–10 примерах.
5. Длина результата: гайд лимита не называет; держать компактно и сравнить.
6. Модель `gpt-5.6-luna`: достаточно ли её, или структуру лучше держать шаблоном в коде, а LLM звать только для «Action» и слов.
