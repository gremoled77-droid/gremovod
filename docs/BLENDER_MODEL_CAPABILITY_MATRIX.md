# Blender → модели: фактическая матрица

Дата проверки: 2026-10-24. Код закреплён на `9a84a0b89af4c2b3fc0b5929602fd12d73b99239`. DOCUMENTED не означает реализовано, `verified_at` — историческая отметка каталога. В этой сессии live-вызовов нет.

## Реальные маршруты GremoVOD

По [adapters.py](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/adapters.py#L99), [model_catalog.py](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/model_catalog.py#L60), [main.py](https://github.com/gremoled77-droid/gremovod/blob/9a84a0b89af4c2b3fc0b5929602fd12d73b99239/backend/main.py#L460):

| Модель / provider | Endpoint / adapter | Image ref | Motion video | First/last | Edit / extend | Ограничения и цена из кода | Статус |
|---|---|---|---|---|---|---|---|
| Seedance 2.5 / PiAPI | `/api/v1/task`; `seedance_25`; model `seedance`, task `seedance-2.5` | `input.image_urls`, до 30 | `input.video_urls`, до 10; `@video1` | Специального first/last контракта нет; изображения с текстовой ролью не равны endpoints | Есть mode/omni_reference ветки edit, extend | 4–30 s; 480/720/1080p; audio до 10; video/audio суммарно ≤30 s каждый тип. $0.15/$0.35/$0.80 за выходную секунду + половина ставки за входную video-second | VERIFIED_CODE + 13 offline tests; **BLOCKED** `launch_enabled=False`, live отсутствует |
| MiniMax H3 / PiAPI | `/api/v1/task`; `minimax_h3`; model `Qubico/minimax-h3`; txt2video / img2video | Только один `input.image` | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | 5–15 s, 480/768/1080p; $0.03/$0.05/$0.07 за s | Launch enabled, каталог verified_at 2026-10-16; graybox PNG возможен, motion-video нет |
| Hunyuan I2V / PiAPI | `/api/v1/task`; special fallback main.py; `Qubico/hunyuan`, img2video-replace | Ровно один image | UNSUPPORTED | UNSUPPORTED | UNSUPPORTED | Provider-default duration; $0.09 flat в каталоге | Launch enabled, verified_at 2026-10-15; тестировать длительность отдельно, не переносить 8 s автоматически |
| Kling 3.0 / PiAPI профиль | Нет executable adapter; prompt_only | UNSUPPORTED в router | UNSUPPORTED в router | UNSUPPORTED в router | UNSUPPORTED в router | API-options и executable quote отсутствуют; стоимость запуска UNKNOWN | BLOCKED, launch disabled |
| Runway | Нет adapter/catalog route | UNSUPPORTED в проекте | UNSUPPORTED в проекте | UNSUPPORTED в проекте | UNSUPPORTED в проекте | Цена интеграции UNKNOWN | Не подключён к backend; доступный connector не является интеграцией |
| Seedance 2.0, Wan, Veo, Sora, LTX и другие названия prompt-профилей | Нет доказанного executable пути для данного previz | Не считать поддержкой | Не считать поддержкой | Не считать поддержкой | Не считать поддержкой | UNKNOWN | Вне первого эксперимента |

Включённые image-модели Seedream 5 Pro/Lite, Nano Banana 2.1, GPT Image и Qwen могут помогать подготовке изображений, но не переносят траекторию видео. GPT edits refs и Qwen image refs имеют собственные ограничения адаптеров. Создавать новые платные reference sheets автоматически нельзя; использовать утверждённые владельцем исходники.

## Первичные API-источники и разрывы

### Seedance 2.5

[PiAPI API](https://app.piapi.ai/docs/seedance-api/seedance-25) описывает image/video/audio references, edit/extend и отдельную оплату входного видео. Это совпадает с ветками `adapters.py:118–236`; `wire_body:336–345` отправляет только model/task_type/input. Роли reference_manifest сами в API не уходят: нужен детерминированный compiler slots → URLs + prompt tags, без изменения порядка. Draft 480p → final 1080p — отдельный платный вызов, не бесплатный upscale; API описывает срок финализации draft 7 дней. Для пилота эту ветку не использовать.

Текст `docs/VIDEO_MODELS_PROMPTING_2026-10-17.md:21,54` об активном Seedance/неотправляемых refs противоречит текущему каталогу и адаптеру. Приоритет здесь у исполняемого gate и payload; обновление старого документа — отдельная задача. `video-seedance-2-5` skill — режиссёрская инструкция, а не подтверждённый live-тест.

Путь local MP4 → внешний допустимый URL ещё отсутствует как проверенный transport. `reference_upload.py` сейчас обслуживает изображения. `check_refs` требует HTTPS, отвергает literal localhost и credentials; это не полная защита DNS rebinding/SSRF. Для нового server-side upload/download нужны allowlist, ограничения размера/redirects и проверки адресов; signed URLs не писать в Git/публичный audit log.

### Kling: документация шире текущего проекта

[PiAPI Kling 3 API](https://app.piapi.ai/docs/kling-api/kling-3-api) документирует начальный `image_url`, конечный `image_tail_url`, 3–15 s и multishots. [Kling 3 Omni API](https://app.piapi.ai/docs/kling-api/kling-3-omni-api) документирует video references, но использует **`images` и `video`**, теги **`@image_1` и `@video`**; при video — до четырёх images и без multi_shots. Не копировать Seedance `video_urls` / `@video1` в Kling. Документация страницы также содержит более новую версию 4.0: её условия не переносить на 3.0.

Нужно отдельно реализовать adapter, enums/limits, quote, upload и tests; затем получить разрешение на проверочный live-вызов. Документированные тарифы обычного Kling не доказывают тариф конкретного Omni video-reference payload; до точной сверки **UNKNOWN**. Включение prompt-only профиля одним флагом недопустимо.

### Runway: возможный P2, без обещаний о переносе движения

[Runway API](https://docs.dev.runwayml.com/api/) содержит `/v1/video_to_video` и `/v1/image_to_video`; [input assets](https://docs.dev.runwayml.com/assets/inputs/) описывает video input, HTTPS/upload URI и ограничения. Aleph 2.0 принимает 2–30 s, до 30 fps; наличие endpoint не гарантирует сохранение дверей, сторон и траектории. Модели/тарифы зависят от конкретного route. Нужны новый adapter внутри существующего router, credential boundary, asset transport, quote, reconciliation. Цена целевого запуска UNKNOWN. Внешний Runway connector в Codex не даёт приложению этих возможностей автоматически.

## Что передавать из Blender

| Артефакт | Назначение | Первый маршрут |
|---|---|---|
| Preview MP4 | Только композиция, темп, положение и движение; не фактура graybox | Seedance video reference после P1 и разрешения |
| First / middle / last PNG | Локальная приёмка, контактный лист; иногда composition reference | Существующие image refs, с явной ролью; не называть last PNG гарантированным endpoint |
| Утверждённый vehicle sheet | Внешний вид жёлтого LIMO_2106, передок, оба борта | Seedance image refs; MiniMax только один совместно подготовленный approved image |
| Character sheet | Идентичность Грэма | Только следующий отдельный эксперимент; в первом тесте отсутствует |
| Stage bible / `.blend` / JSON | Истина координат, конструкция, hashes | Локальные данные, **не API-вложения модели** |
| Depth/normal/masks | Потенциальные контрольные карты | Ни у одного исследованного adapter специальный ControlNet-like transport не реализован |

Текст `motion_only` — наше ограничение смысла, не жёсткая гарантия модели. Цветовые proxy/materials могут протечь в результат. Проверять руками, не объявлять геометрическую правду обеспеченной провайдером.

## Гейты до первого вызова

1. Утверждены local preview, реальные refs и права на их передачу; asset hashes зафиксированы.
2. Реализован проверяемый video upload с TTL/ownership; внешний upload разрешён отдельно от бесплатного local render.
3. Показан точный wire payload без секретов, проверены limits, durations и текущая цена.
4. Пройден существующий GenerationReview → signed quote → reserve → submit; для первичной live-верификации модели предусмотрен ограниченный и явно разрешённый путь, без общего включения непроверенной модели.
5. Сверено реальное списание/статус. UNKNOWN сохраняет hold, повтор запрещён до reconciliation.

Рекомендуемый первый кандидат — Seedance 2.5 как единственный уже написанный motion-video adapter, **при условии снятия перечисленных блокеров**. MiniMax — image-only baseline другого типа, не замена motion A/B.
