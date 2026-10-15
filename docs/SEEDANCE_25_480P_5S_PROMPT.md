# Seedance 2.5 — ночная улица, 480p, 5 секунд

Промпт сохранён в проекте «Seedream Lite — первый реальный тест». Видео не запускалось; платный LLM для текста не вызывался.

Референс @image1: сохранённый кадр улицы, роль — пространство, композиция, архитектура и свет. Метка требует фактической передачи изображения первым элементом image_urls. Это reference-guided generation; точное совпадение первого кадра не гарантируется.

Настройки: resolution=480p, duration=5, aspect_ratio=16:9. Для будущего адаптера PiAPI предполагаются mode=omni_reference и omni_reference_task_type=reference; эти поля не отправлялись. generate_audio, enhance_prompt и отдельный negative_prompt не добавлены без проверки соответствующих полей провайдера. Один плавный dolly, вторичное движение тумана и воды; без смены сцены и новых объектов.

Применены ai-video (BRIEF) и cinematic-studio (motion.md, providers.md). Визуальный контекст взят из выбранного кадра; навыки брендинга/голоса не создают новых требований для этого немого тестового шота.

Официальная схема: https://piapi.ai/docs/seedance-api/seedance-25 (проверено 15 октября 2026). 480p и длительность 5 секунд поддерживаются. По опубликованной ставке $0.15/с предварительная оценка будущего видео без video/audio references — $0.75. Разрешение на предыдущий тест изображения не распространяется на запуск видео.

## Prompt

Use @image1 as the reference for the street layout, architecture, camera framing, materials and lighting. Begin with a composition closely matching the reference: an empty Minsk street at blue hour after rain, warm amber streetlamps, cool blue shadows and wet pavement. Preserve the existing stylized animated-film appearance.

One continuous five-second shot. From 0 to 1 second, hold the wide composition almost still. From 1 to 4.5 seconds, the camera makes a very slow, smooth forward dolly along the street centreline, advancing only about one metre at a constant eye-level height. Keep the lens focal length fixed: this is physical camera travel, not a zoom. Near lamp posts and building edges show slight natural parallax against the distant street. From 4.5 to 5 seconds, gently ease the camera to a stop.

A thin layer of existing mist drifts slowly across the distant street. Sparse, small circular ripples expand naturally in the foreground puddles; amber lamp reflections shift subtly with the water surface and the camera perspective. Keep this secondary movement restrained. The lamps remain steady, with unchanged light positions, exposure and colour temperature.

Preserve the building silhouettes, straight vertical lines, window spacing, balconies, overhead wires and road geometry throughout. Keep the street empty. No new people, vehicles, signs or text. No cuts, transitions, orbit, handheld shake, sudden acceleration, focus pulls, day-to-night changes, bending architecture, texture crawling or invented objects. No dialogue or music.
