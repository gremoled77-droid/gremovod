# Модели PiAPI для шести целевых моделей — сверка с документацией (16.10.2026)

Источник: страницы PiAPI docs (seedream-5, gpt-image-api, gemini-api/nano-banana-2, qwen-image-api, unified-api-schema, unified-webhook, blog gpt-image-2-5-flare-vs-sunburst). Цены — как указано в документации на дату сверки; перед включением модели в запуск перепроверять и ставить `verified_at`.

## Общий API задач (unified)
- Создать: `POST https://api.piapi.ai/api/v1/task`, заголовок `X-API-Key`, тело `{model, task_type, input, config}`.
- Получить: `GET /api/v1/task/{task_id}`. Ответ `{code,message,data:{task_id,model,task_type,status,input,output,meta,error}}`.
- Статусы: pending, processing, completed, failed. Ошибка: `error:{code,raw_message,message,detail}`. Расход в `meta.usage.consume` (в поинтах).
- Формат `output` отличается по моделям: Seedream `output.image_url`, Nano Banana `output.image_urls`, GPT Image async `output.data[0].b64_json` (или url при `response_format=url`).
- Webhook: `config.webhook_config={endpoint,secret}`, заголовок `x-webhook-secret`, повтор через 5 с до 3 раз; только unified-схема; endpoint должен быть доступен из Cloudflare. Для локального/телефонного режима использовать опрос.
- Файлы на стороне PiAPI хранятся ограниченное время (GPT Image — 60 минут): **сохранять результат сразу**.

## 1. Seedream 5.0 Pro и «Fast»
- `model: "seedream"`, `task_type`: `seedream-5-pro` (1K по умолчанию, 2K) и `seedream-5-pro-less-restriction`.
- Цена за картинку: Pro 1K $0.068, 2K $0.136; less-restriction +25% (1K $0.085, 2K $0.17). Референсы: первый бесплатно, дополнительные платные (в документации расхождение $0.003/$0.006 — уточнить).
- **«Seedream 5.0 Fast» на PiAPI не найден.** Есть `seedream-5-lite` (2K/3K, $0.052; less-restriction $0.065). Вероятно, под «Fast» подразумевается Lite — **подтвердить у владельца**.
- Поля: prompt, aspect_ratio (1:1,16:9,9:16,4:3,3:4,3:2,2:3,4:5,5:4,21:9), size, output_format (jpeg/png/webp), image_urls до 10 публичных HTTPS (подписанные временные ссылки могут не работать). Поля `n` нет; пакет только у Lite через `sequential_image_generation=auto` + `max_images` 1–15.
- Модерация: отказ окончательный, кредиты возвращаются.

## 2. GPT Image 2.0 и 2.5 (отдельный API, не unified)
- Модели: `gpt-image-2`, `gpt-image-2.5` (без суффикса), `gpt-image-2.5-flare` (быстрая, ~20 с), `gpt-image-2.5-sunburst` (точнее при правках, ~50–70 с). Это разные модели, не тарифы.
- Эндпоинты: sync `POST /v1/images/generations` и `/v1/images/edits` (Bearer); **async** `POST /api/v1/images/generations/async` и `/edits/async` (X-API-KEY) + опрос `GET /api/v1/task/{id}`. Предпочитать async (sync 30–120 с). До 100 задач одновременно.
- Параметры: model, prompt, n (у `gpt-image-2.5` без суффикса только 1), size (1024x1024 по умолчанию; 1024x1536, 1536x1024), quality (auto/low/medium/high; по умолчанию low; `gpt-image-2` — только medium), response_format (по умолчанию b64_json; есть url), output_format (png).
- Правки: поле `image` (или `image[]`), до 16 файлов по ≤25 МБ, первое — главный объект, маска применяется к первому. Подходит для режима «Допилить».
- Цена (оценка 1024x1024): 2.5 flare/sunburst low ~$0.004, medium ~$0.010, high ~$0.040; `gpt-image-2` low ~$0.008, medium ~$0.032, high ~$0.125; размеры 1024x1536 ≈ ×1.5. Токены (USD/1M): 2.5 flare/sunburst 3.75/6.00/22.50; 2.5 без суффикса 2.50/4.00/15.00; 2.0 5.00/8.00/30.00.
- Нужен собственный адаптер: другой формат запроса/ответа и ключ в заголовке.

## 3. Nano Banana 2.1
- Есть. `model: "gemini"`, `task_type: "nano-banana-2.1"` (и старый `nano-banana-2`).
- Цена: 2.1 — 1K $0.03, 2K $0.04, 4K $0.09; 2 — $0.06/$0.08/$0.12.
- Поля: prompt, image_urls (публичные), aspect_ratio (список в документации не указан; по умолчанию 16:9), resolution 1K/2K/4K, output_format jpg/png/webp (тип возвращаемого файла проверять по Content-Type). Выход: `output.image_urls`.

## 4. Qwen Image 2.1
- **«Qwen Image 2.1» на PiAPI не найден.** Есть `Qubico/qwen-image`: `txt2img` ($0.015; поля prompt, negative_prompt, width, height, seed, steps, flow_shift) и `image-edit` (на базе 2509, $0.025; image1–image3).
- Подтвердить у владельца: достаточно ли существующего Qwen Image, либо Qwen 2.1 запускается через KIE (в model-studio уже есть схема qwen).

## Следствия для каталога backend/model_catalog.py
- Включены к запуску сейчас: seedream-5-lite, seedance-2.5, hunyuan-i2v. Добавить адаптеры: seedream-5-pro, nano-banana-2.1 (unified), gpt-image-2 / 2.5 (отдельный async-адаптер), qwen (после решения).
- Ключ `PIAPI_API_KEY` один для unified и GPT Image; формат заголовка разный.
- Цены хранить с датой проверки; бюджет и оценка считаются до отправки.

---
# Дополнение 16.10.2026 (после ответов владельца)

## Решения владельца
- «Seedream 5.0 Fast» = **seedream-5-lite** (вариант `seedream-5-lite-less-restriction` — при необходимости).
- GPT Image 2.5: в интерфейсе на выбор **`gpt-image-2.5` (без суффикса)** и **`gpt-image-2.5-flare`**; для правок по умолчанию **`gpt-image-2.5-sunburst`**.
- В видео добавить **MiniMax H3**.
- Qwen 2.1 — страница https://piapi.ai/ru/qwen-image-2-1.
- Все параметры моделей уточняются на следующем этапе (отмечено в TODO).

## Qwen Image 2.1 (Turbo)
- `model: Qubico/qwen-image-2.1`, `task_type: txt2img`. Только текст → изображение, **без референсов и правок**, один результат на запрос (нет `n`).
- Поля: prompt, width/height (64–4096 px, произведение ≤ 1 763 584; 1328×1328 проходит, 4096×4096 нет), steps 1–16 (рекомендовано 8), seed (-1 = случайный). `negative_prompt` и `flow_shift` принимаются, но Turbo их игнорирует. Цена $0.015 за картинку.
- Документация PiAPI по этому пункту устарела (описывает прежний `Qubico/qwen-image`); значения взяты со страницы модели. Формат ответа (`image_url` / `image_urls`) проверить на реальном вызове.
- Правки и референсы: старый `Qubico/qwen-image`, `task_type: image-edit` (image1–image3, $0.025).

## MiniMax H3
- `model: Qubico/minimax-h3` (и `Qubico/minimax-h3-nsfw` — «less restriction», модерация сохраняется), `task_type`: `txt2video` / `img2video` (изображение = первый кадр). Последнего кадра и референса субъекта нет.
- Поля: prompt до 2000 символов, image (для img2video; публичный JPG/PNG), resolution 480P/768P/1080P (в примерах встречаются «512p» и нижний регистр — **проверить на реальном вызове**), duration 5–15 с (целое), aspect_ratio 16:9 / 9:16 / 1:1, seed. Отдельного параметра звука нет — MP4 приходит со встроенным стерео-звуком, включённым в цену.
- Выход: `data.output.video` (URL MP4, путь «ephemeral» — ссылка временная; сохранять сразу).
- Цена за секунду (за запрошенную длительность, только успешные): 480P $0.03, 768P $0.05, 1080P $0.07 (nsfw: $0.04/0.06/0.08). Пример 5 с / 480P = $0.15.
- Прежние Hailuo: `hailuo`, `video_generation`, v2.3 / v2.3-fast (6 или 10 с; 768/1080), от $0.16.

## Каталог PiAPI: что предлагается добавить (по полезности для GremoVOD)
Данные взяты с каталога https://piapi.ai/models и docs; строки `model`/`task_type` и число референсов для большинства **не проверены**.

Видео и консистентность:
1. **Seedance 2 / 2.5** — omni-референс (изображения + видео + аудио) и **Private Asset Library** (сохранённые лица/персонажи по asset ID) — лучшее для постоянства Грэма в видео. Seedance 2 от $0.042–0.08/с.
2. **Kling 3.0 / 3.0 Omni / Elements / Motion Control** — мультиреференсы, сцены из нескольких планов, перенос движения; от $0.10/с. Есть `image_tail_url` (последний кадр) у более ранних версий.
3. **Veo 3.1** (текст и изображение → видео) от $0.06/с; **Wan 2.6** от $0.08/с — запасные варианты и дешёвые вставки.
4. **OmniHuman 1.5** ($0.13/с) и **Kling Avatar** (от $0.052/с) — говорящий персонаж по картинке + аудио: естественное продолжение цепочки «реплика ElevenLabs/Fish → видео».
Изображения и правки:
5. **Nano Banana Pro** ($0.105+) — тяжёлая модель для сложных правок; **Flux Kontext** ($0.02) — дешёвые точечные правки; **Z-Image Turbo** ($0.002) и **Flux schnell** ($0.0015) — очень дешёвые черновики/раскадровка.
Инструменты:
6. **Upscale изображений** (от $0.001/MP) и **видео** (от $0.0003/кадр) — для связки «дешёвая модель + апскейл» из TODO.
7. **Remove Background / Segment With Prompt** — маски и вырезка; **JoyCaption** (изображение → промпт) — описание референсов; **MMAudio** (видео → звук); **File Upload** — свои публичные ссылки на референсы у PiAPI (бесплатно на тарифе Creator и выше) вместо временного TempFile.
8. Face swap (от $0.02) — только с согласием и правами на лица; не включать по умолчанию.
Аудио:
9. ElevenLabs и Fish Audio **на PiAPI отсутствуют** — остаются прямыми подключениями. На PiAPI есть F5-TTS (клонирование голоса), Seed Audio 1.0, музыка (Udio, DiffRhythm, ACE-Step).
Не рекомендуется: Midjourney (сервис на PiAPI закрыт/внешний), Suno (противоречивый статус).
LLM: единый OpenAI-совместимый эндпоинт (`/docs/llm-api/completions`) — GPT, Claude, DeepSeek; для платного LLM-резерва пригодится после проверки тарифов.

## Противоречия в источниках (проверить)
Длительность Seedance 2.5 (4–15 с или 1–30 с); цена Seedance 2 ($0.042 или $0.08/с); поверхностные страницы без `model`/`task_type` для большинства видеомоделей; тариф Creator ($15 или $8/мес).

## Раскладка по разделам интерфейса (решение владельца 16.10.2026)
- **Видео:** seedance-2.5, minimax-h3, **Seedance 2 (+ Private Asset Library, omni-референс)**, **Kling 3.0 / Omni / Elements**.
- **Другое:** OmniHuman 1.5, Kling Avatar, Flux Kontext, Z-Image Turbo, апскейл изображений и видео.
- **Изображения:** seedream-5-lite, seedream-5-pro, nano-banana-2.1, GPT Image (2.0; 2.5 / 2.5-flare; правки — 2.5-sunburst), qwen-image-2.1.
