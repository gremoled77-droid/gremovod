# Nano Banana 2.1 — гайд по промптам (кадры мультфильма, несколько героев + локация)

Пути: docs/official-prompts/ в .worktrees/gremovod-v2 (banana21-model.txt, banana-prompting.txt, banana-framework.txt).

## 1. Модель и лимиты
- Официально модель `gemini-nano-banana-2.1`: вход текст/картинка/видео/PDF, выход картинка+текст, вход до 131 072 токенов. [banana21-model.txt]
- Разрешения 1K (по умолчанию), 2K, 4K. [banana21-model.txt]
- До 14 референсов: до 4 персонажей (сходство) и до 10 объектов (точность). [banana21-model.txt, banana-prompting.txt]
- До 3 картинок можно дать как стилевые референсы. [banana-prompting.txt]
- Режим размышления: minimal / medium (по умолчанию) / high. [banana-prompting.txt]
- Официальных форматов больше (3:2, 4:5, 21:9, 1:4 и др.), но PiAPI даёт только 16:9, 9:16, 1:1, 4:3, 3:4; разрешение 1K/2K/4K; формат png/jpg/webp. [backend/model_catalog.py]
- В студии max_refs=10 (поле image_urls), цена 1K $0.03, 2K $0.04, 4K $0.09; `launch_enabled` пока False. [backend/model_catalog.py]
- Thinking level и поиск-grounding в параметры PiAPI в студии не выведены. [backend/model_catalog.py]
- Русский в списке языков есть (ru-RU), но английский надёжнее. [banana-prompting.txt]

## 2. Структура промпта (официально)
- Начинать с сильного глагола-операции («Create…», «Using the provided image, change…»). [banana-framework.txt]
- Без референсов: [Subject] + [Action] + [Location/context] + [Composition] + [Style]. [banana-framework.txt]
- С референсами: [Reference images] + [Relationship instruction] + [New scenario]. [banana-framework.txt]
- Связное описание сцены, не список ключевиков. [banana-framework.txt]
- Позитивная формулировка: «empty, deserted street», а не «no cars». [banana-framework.txt, banana-prompting.txt]
- Конкретика материалов и цель картинки улучшают результат. [banana-prompting.txt]
- Сложную сцену разбивать на шаги: фон, передний план, деталь. [banana-prompting.txt]
- Модель не всегда выдаёт заказанное число картинок. [banana-prompting.txt]

## 3. Свет, камера, объектив, композиция
- Свет: «three-point softbox setup», «Chiaroscuro lighting with harsh, high contrast», «Golden hour backlighting creating long shadows». [banana-framework.txt]
- Камера/объектив (официально): «low-angle shot with a shallow depth of field (f/1.8)», «wide-angle lens», «macro lens», «aerial view». [banana-framework.txt, banana-prompting.txt]
- Тип камеры меняет «визуальную ДНК»: GoPro, Fujifilm, одноразовая плёночная. [banana-framework.txt]
- Цвет/плёнка: «1980s color film, slightly grainy», «Cinematic color grading with muted teal tones». [banana-framework.txt]
- Таблицы «мм → эффект» официально нет; мм и f/ работают как стилевые подсказки, а не точные настройки (строгих тестов нет). Неофициально. [https://fal.ai/learn/tools/how-to-use-nano-banana-2]
- Неофициально: одна камера и один объектив на промпт, две камеры усредняются. [https://fliki.ai/blog/nano-banana-2-prompting-guide]
- Неофициально: свет описывать направлением и ролью («key light from upper left, rim light from behind»). [https://fliki.ai/blog/nano-banana-2-prompting-guide]
- Для мультфильма камера-тело вряд ли нужна: ракурс и объектив словами, стиль отдельно (проверить, п. 10). [вывод по banana-framework.txt]

## 4. Референсы и постоянство персонажа
- Официальный образец ссылается по порядку: «the blue floral dress from the first image… the woman from the second image». [banana-prompting.txt]
- Официальный шаблон: что у элемента из image 1 остаётся неизменным, описать подробно (лицо, логотип). [banana-prompting.txt]
- Роли референсов называть явно: структура, текстура, палитра, лицо. [banana-framework.txt]
- 360° вид героя: по ракурсам, прикладывая прежние результаты и референс позы. [banana-prompting.txt]
- Практика студии: порядок image_urls = «image 1, 2…»; «Character A = image 1, Character B = image 2, location = image 3». Нумерация подтверждена неофициально. [https://nanobananatool.com/blog/nano-banana-2-character-consistency]
- Неофициально: лист героя 3–6 кадров (анфас, 3/4, в рост), одинаковый свет, один персонаж на лист. [https://nanobananatool.com/blog/nano-banana-2-character-consistency, https://flowith.io/blog/nano-banana-consistent-characters-storyboard/]
- Неофициально: фразу про сходство ставить в начало и не переписывать описание черт от кадра к кадру. [https://nanobananatool.com/blog/nano-banana-2-character-consistency]
- Неофициально: несколько героев склонны смешиваться; помогает «Character A from the first image, Character B from the second, keep both faces exactly». [https://nanobananatool.com/blog/nano-banana-2-character-consistency]
- Больше 4 героев в кадре сходство не гарантировано. [banana21-model.txt]

## 5. Правки
- Шаблон: «Using the provided image, change only the [element] to [new]. Keep everything else exactly the same, preserving the original style, lighting, and composition.» [banana-prompting.txt]
- Диалоговые уточнения: «make the lighting a bit warmer», «keep everything the same, but change the expression». [banana-prompting.txt]
- Править в режиме редактирования, а не генерировать заново, и перечислять, что сохранить (неофициально). [https://fliki.ai/blog/nano-banana-2-prompting-guide]
- В студии исходный кадр подавать первым референсом (не проверено). [п. 10]

## 6. Текст на картинке
- Точные слова, стиль шрифта («bold, white, sans-serif»), цвет, положение. [banana-prompting.txt, banana-framework.txt]
- Приём: сначала составить текст в беседе, потом просить картинку с ним. [banana-framework.txt, banana-prompting.txt]
- Можно писать промпт на одном языке, а текст просить на другом. [banana-framework.txt]
- Неофициально: слова в кавычках + шрифт + положение + иерархия размеров в одном предложении. [https://fliki.ai/blog/nano-banana-2-prompting-guide]
- Кириллица (вывески Минска): примеров в источниках нет. [п. 10]

## 7. Ошибки и ограничения
- Аудио-вход не поддерживается. [banana-prompting.txt]
- Grounding не использует реальные фото людей из веба. [banana-prompting.txt]
- Все картинки несут SynthID и C2PA. [banana-framework.txt]
- Типичные ошибки (неофициально): списки тегов, «masterpiece, best quality», противоречащие стили, негатив, чрезмерно точные числа. [https://fal.ai/learn/tools/how-to-use-nano-banana-2, https://fliki.ai/blog/nano-banana-2-prompting-guide, https://www.imagine.art/blogs/nano-banana-2-lite-prompt-guide]
- Неофициально: если камеру игнорирует, поставить ракурс и объектив в начало и убрать конфликтующие стили. [https://sider.ai/blog/ai-image/advanced-camera-angle-prompts-for-nano-banana-pro]

## 8. Советы сообщества (неофициально)
- Reddit: WebFetch заблокирован, поиск тредов не вернул; реддит-советов нет. [reddit.com, пропущено]
- Дрейф героя: перегенерировать, взяв лучшие прошлые кадры референсом, периодически делать «чистый» референс. [https://flowith.io/blog/nano-banana-consistent-characters-storyboard/]
- В серии указывать номер кадра («panel 3 of 6, keep identity with panels 1 and 2»). [https://nanobananatool.com/blog/nano-banana-2-character-consistency]
- Сильный стиль (имена художников) перебивает лицо; короткая сцена держит идентичность. [https://nanobananatool.com/blog/nano-banana-2-character-consistency]
- Слабый промпт лучше переписать, чем гонять повторно. [https://fliki.ai/blog/nano-banana-2-prompting-guide]

## 9. Библиотеки скиллов и промптов (неофициально)
- https://github.com/geschaeftlichschlueter-boop/nano-banana-prompts — Claude-skill + knowledge/nano_banana_prompting.md (содержимое не удалось получить). 
- https://github.com/YouMind-OpenLab/nano-banana-pro-prompts-recommend-skill — SKILL.md подбора из 10 000+ промптов (Pro, не 2.1).
- https://github.com/ZizheRuan/awesome-nanobanana2 — промпты и примеры для NB2.
- https://github.com/imagineVid/Awesome-nano-banana-prompts-and-skills — промпты с результатами и workflow.
- https://www.skillsdirectory.com/skills/saren-ai-nano-banana — SKILL.md с базовыми принципами.
- Осторожно: списки «секретных токенов» похожи на хайп. [https://metricsmule.com/ai/best-nano-banana-prompts/]

## 10. Что неизвестно, проверить живым тестом
- Как PiAPI передаёт порядок image_urls: работает ли «first/second/third image». [model_catalog.py]
- Сколько героев + локация держатся реально (официально 4 героя, у нас до 10 refs). [banana21-model.txt]
- Держится ли мультяшный стиль референсов; нужен ли стилевой референс (до 3). [вывод]
- Работают ли мм и f/ в мультстиле или лучше слова («wide shot», «low angle»). [п. 3]
- Кириллица на вывесках; 16:9 при 1K. [п. 6]
- Влияет ли PiAPI на thinking level. [model_catalog.py]
- Правка «change only X» с первым референсом-кадром: сохраняются ли лица. [п. 5]
