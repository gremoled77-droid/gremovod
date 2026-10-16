# Видеомодели: сводка исследований по промптам (17.10.2026)

Свод инструкций владельца, практикумов, видео Practice Ai и проверок Codex. Правила по каждой модели лежат в навыках `skills/video-*`; здесь карта источников, различия «инструкция против PiAPI» и очередь проверок. Ничего из этого не включает модель в запуск: за запуск отвечает `launch_enabled` и живая проверка (`verified_at`) в `backend/model_catalog.py`.

## Источники

| Источник | Что дал | Где использовано |
|---|---|---|
| Файлы владельца (Seedance 2.0, 2.5, FLUX 3, MiniMax H3, Kling 3.0 Omni, Kling 3.0 Start+Last Frame) | правила промптов, лимиты референсов, тех. хвосты | все `skills/video-*` |
| Практикум GORA ACADEMY («Промпты для видео») | коллаж ракурсов героя, лист персонажа, продление сцены, замена героя в кадре и видео | `video-seedance-2-0/references/character-sheet-and-storyboard.md`, `video-kling-3-omni` |
| FlashMovieAI Seedance Director v1.2.0 | каркас промпта с `CUT`, русская речь кириллицей, аудио-авторитет, журнал непрерывности | `video-seedance-2-5/references/directing-and-dialogue.md` |
| Видео Practice Ai «5 правил режиссуры» | пять столпов, 5 вопросов, формула кадра | `skills/cinema-five-pillars`, `backend/prompt_rules.py`, заготовки «Кадров» |
| Проверки Codex по PiAPI (`docs/PIAPI_MODELS_2026-10-16.md`, `docs/official-prompts/*`, `docs/SEEDANCE_25_480P_5S_PROMPT.md`) | реальные поля, цены, теги, проверенные вызовы | поправки к Seedance 2.5 и MiniMax H3, `model_catalog.py` |
| Страницы PiAPI, сохранённые 17.10.2026: `seedance2-piapi`, `seedance-private-asset-piapi`, `kling3-piapi`, `kling3-omni-piapi` (`docs/official-prompts/*`, добавлены в `scripts/fetch_prompt_docs.py`) | реальные имена полей, цены, теги, ограничения | `video-seedance-2-0`, `video-kling-3-omni`, `video-kling-3-start-end-frame`, `model_catalog.py` |
| Ветка `codex/work` (книги, комедия, Мак-ки, навыки этапов) | `skills/gremovod-*`, `docs/*` | см. ниже |

## Модели

| Модель | Через PiAPI и студию | Теги референсов | Лимиты референсов | Статус |
|---|---|---|---|---|
| Seedance 2.5 | `seedance-2.5`, 480p/720p/1080p, 4–30 с, `edit`/`extend`, черновой режим | `@image1`, `@video1`, `@audio1` | 30 / 10 / 10; видео и аудио до 30 с каждое | в запуске (480p, 5 с по цене проверен); видео и аудио-референсы адаптером не отправляются |
| Seedance 2.0 | `seedance-2`, `-fast`, `-mini` (+ `-less-restriction`), режимы `text_to_video`, `first_last_frames`, `omni_reference`, 4–15 с | `@image1`, `@video1`, `@audio1`; ассеты `asset://<id>` (только `-less-restriction`) | 9 / 3 / 3, всего до 15; видео до 15.4 с, аудио до 15 с | не включена, страницы сохранены 17.10 |
| MiniMax H3 | `txt2video`, `img2video` (первый кадр) | теги не отправляются | один первый кадр | в запуске, проверен 16.10 |
| Kling 3.0 Omni | `kling` / `omni_video_generation`, поля `images`, `video`, `multi_shots`, `resolution` | `@image_1`, `@image_2`, `@video` (через PiAPI) | картинки списком; с видео не больше 4; мультишот без видео | не включена, страница сохранена 17.10 |
| Kling 3.0 Start+Last Frame | `kling` / `video_generation`, `image_url` + `image_tail_url`, `version` 3.0 или 3.0-turbo | позиции кадров, не теги | 2 кадра; turbo без звука и мультишота | не включена, страница сохранена 17.10 |
| FLUX 3 | в локальной документации PiAPI нет | мультиреференса нет (Omni: Soon) | 4 режима: t2v, i2v, Keyframes, v2v | не включена |

## Расхождения, найденные при сведении

1. **Регистр тегов Seedance.** В инструкциях `@Image1`, через PiAPI `@image1` (сервис сам конвертирует). Скиллы исправлены на строчные.
2. **MiniMax H3 Omni Reference.** Инструкция описывает 9+3+3 референса, но через PiAPI доступны только `txt2video` и `img2video`; разрешение только строчными (`480p`). Раздел Omni остаётся для приложения Hailuo.
3. **Seedance 2.5: продление и правка.** Инструкция описывает их общими словами, у PiAPI это `omni_reference_task_type` (`edit`, `extend`) с жёсткими `aspect_ratio: adaptive` и `duration`. Тип должен совпадать с формулировкой промпта, иначе задача падает.
4. **Черновики.** Схему «черновик на 2.0, финал на 2.5» дополняет черновой режим самой 2.5 (480p, затем 1080p по `draft_task_id`, 7 дней).
5. **Русская речь.** У Kling нативной русской речи нет (EN/CN/JP/KR/ES). Для Seedance 2.5 и FLUX 3 язык нужно проверять тестом; практичный путь: готовая дорожка (ElevenLabs/Fish) как аудиореференс или озвучка в CapCut.
6. **Теги Kling.** В инструкциях `@Имя` и `<<<element_1>>>`, через PiAPI `@image_1` и `@video` (с подчёркиванием, у Seedance без него: `@image1`). Привязки элемента и голоса в схеме Omni PiAPI нет.
7. **Поля Start+Last Frame.** В инструкциях `image`/`image_tail` или `frame`, у PiAPI `image_url` и `image_tail_url`. Запрет «ласт-кадр только в одношотовом режиме» взят из документации kie.ai; PiAPI его не оговаривает.
8. **Private Asset Library** доступна только на `-less-restriction` вариантах Seedance 2 (мягкая модерация), на строгих `asset://` даёт 422. Использовать ли этот уровень, решает владелец.
9. **Пиковые часы Seedance 2** 09:00–15:00 GMT (12:00–18:00 в Минске): очередь может быть очень длинной.
10. **Правила ChatGPT в студии.** `SEEDANCE_RULES` запрещает `@videoN` и `@audioN` без реально переданных файлов; это согласуется с текущим адаптером.

## Что взято из `codex/work`

Перенесено в `claude/work` только исследования и навыки:
- `docs/BOOKS_STUDY_REGISTER_2026-10-16.md`, `docs/COMEDY_CHARACTER_TOOLS_2026-10-16.md`, `docs/MCKEE_STORY_FOUNDATION_2026-10-16.md`, `docs/SKILLS_PRODUCTION_REFERENCE.md`, `docs/STAGE_SKILLS_2026-10-16.md`;
- `skills/gremovod-stage-*` (idea, world, storyboard, frames, video, sound, editing, release), `skills/gremovod-character-comedy`, `skills/gremovod-character-dramaturgy`, `skills/gremovod-comedy-staging`, `skills/gremovod-world-design`;
- правки `skills/cinema-narrative-genre` и `skills/gremovod-screenplay`.

Не переносилось и остаётся на ветке Codex (дойдёт через `main`): просмотрщик медиа (`Lightbox.tsx`, `MediaAssetActions.tsx`, `mediaAsset.ts`, `lightbox.css`, правки `HomeScreen`, `CreateScreen`, `ProductionStoryboard`, `backend/temp_cleanup.py` и тесты), `scripts/export_codex_skills.py`, строки в `AGENTS.md`, `CLAUDE.md`, `docs/HANDOFF_CLAUDE_CODE.md`.

Связка навыков: `gremovod-stage-frames` (страница «Кадры») + `cinema-five-pillars` для промпта кадра; `gremovod-stage-video` (страница «Видео») + `video-<модель>` для выбранной модели. Навык этапа говорит, что и зачем ставить, навык модели говорит, как это записать в промпт под её поля.

## Очередь проверок и задач

1. Адаптер Seedance 2.5 написан (`video_urls`, `audio_urls`, `edit`/`extend`, `draft`, цена с входным видео, раскладка в `GenerationReview`), тесты офлайн. Осталось: форма в «Видео» для выбора видео/аудио референсов, `task` и черновика; живой тест `edit`/`extend`/`draft` на 480p с малой суммой только по разрешению владельца.
2. Kling Elements: сохранить страницу PiAPI «Kling Elements Video Generation API» (элементы и голос в схеме Omni отсутствуют) и сверить с `video-kling-3-omni`. Сделано: страницы Kling 3.0 и Kling 3.0 omni (17.10).
3. FLUX 3: выяснить, есть ли он у PiAPI; пока навык описывает модель по инструкции владельца.
4. Seedance 2: решение владельца про `-less-restriction` ради Private Asset Library; живой тест загрузки и ссылки `asset://` на 480p, 4 с с малой суммой. Сделано: страницы Seedance 2 и Private Asset Library сохранены (17.10).
5. Живая проверка русской речи: Seedance 2.5 с аудиореференсом на коротком отрезке.
6. Нативная русская речь у Kling и FLUX 3: не ожидать, озвучку класть дорожкой.
