# GremoVOD n8n — карта агентов, этапов и навыков

Статус: **этап 1 «Компоновка навыков» выполнен 19.10.2026 в n8n (Draft Agents)**. Автоматической синхронизации GitHub ↔ n8n **ещё нет**. `agent-manifest.json` содержит снимок назначений; он не заменяет n8n Skill API.

## Роли и назначения

| Agent | Основная ответственность | Скиллы (актуально в n8n) | Сейчас | Целевая маршрутизация |
|---|---|---|---|---|
| A0 | Продюсер; вход задания, статусы, состав пакета, бюджет, вопросы автору | `skill-creator`, `doc-coauthoring`, `xlsx` | Claude Haiku 5.5 · reasoning low | Haiku для рутины, Sonnet для сложной координации |
| A1 | Сценарист + сохранение правил мира до выделения отдельного хранителя | `gremovod-screenplay`, `gremovod-dialogue-subtext`, `gremovod-character-dramaturgy`, `gremovod-stage-idea`, `gremovod-stage-world`, `gremovod-world-design`, `gremovod-script-rewrite`, `gremovod-series-development`, `gremovod-character-comedy`, `cinema-narrative-genre`, `cinema-image-system` | Claude Sonnet 5.5 · reasoning medium | Sonnet, Opus только для сложных содержательных задач |
| A2 | Режиссёр; постановка, последовательность шотов, комедийный фокус | `gremovod-stage-storyboard`, `cinema-shot-design`, `cinema-camera-work`, `cinema-character-framing`, `cinema-composition`, `cinema-mise-en-scene`, `cinema-visual-structure`, `gremovod-comedy-staging` | Claude Sonnet 5.5 · reasoning medium | Sonnet, Opus по эскалации |
| A3 | Фото- и видео-промпты под выбранную модель, проверка референсов и ограничений | `gremovod-stage-frames`, `gremovod-stage-video`, `gremovod-cinematic-lighting`, `cinema-lens-language`, `cinema-five-pillars`, `video-flux-3`, `video-kling-3-omni`, `video-kling-3-start-end-frame`, `video-minimax-h3`, `video-seedance-2-0`, `video-seedance-2-5` | Claude Haiku 5.5 · reasoning low | Haiku для шаблонных промптов, Sonnet для сложных |
| A4 | Исследователь; PDF, извлечение материалов, цитирование источников | `pdf`, `doc-coauthoring`, `gremovod-world-design` | Claude Haiku 5.5 · reasoning low | Haiku для извлечения, Sonnet для сопоставления |
| A5 | Звук, ритм монтажа, графика, контроль пакета выпуска | `remotion-best-practices`, `gremovod-stage-editing`, `cinema-editing`, `gremovod-stage-sound`, `cinema-sound-design`, `gremovod-stage-release` | Claude Haiku 5.5 · reasoning low | Haiku для реестров и тех. QA, Sonnet для искусства |

В этой конфигурации **все 35 уникальных навыков из `skills/` репозитория** имеют хотя бы одного получателя в n8n. Наличие нескольких навыков в одном агенте — ожидаемое поведение, **не нужно создавать по одному агенту на навык**. В каждом запросе следует выбирать релевантную инструкцию вместо механического применения всего списка.

## Маршрутизация по восьми этапам

| Этап UI | Ведущий агент | Ключевые навыки | Что отдаёт дальше |
|---|---|---|---|
| 1. Идея | A1 | `gremovod-stage-idea`, `gremovod-screenplay`, навыки диалогов и комедии | черновой сценарий/структура, предложения не объявляются каноном |
| 2. Мир | A1 при поддержке A4 | `gremovod-stage-world`, `gremovod-world-design`, `cinema-image-system` | карточки мира/персонажей/локаций с явными версиями |
| 3. Раскадровка | A2 | `gremovod-stage-storyboard`, `cinema-shot-design`, `gremovod-comedy-staging` | карточки кадров и монтажные зависимости |
| 4. Кадры | A3; A2 — для сложной композиции | `gremovod-stage-frames`, `cinema-five-pillars`, `gremovod-cinematic-lighting` | готовые image-промпты и варианты на утверждение |
| 5. Видео | A3 | `gremovod-stage-video` + **ровно подходящий `video-*`** по активной модели | video-промпт, ограничения, задачи для генерации после согласия |
| 6. Звук | A5 | `gremovod-stage-sound`, `cinema-sound-design` | речевой и звуковой монтажный лист |
| 7. Монтаж | A5 | `gremovod-stage-editing`, `cinema-editing`, Remotion для графики | монтажный лист и пакет для CapCut |
| 8. Выпуск | A5; A0 — итоговый аудит | `gremovod-stage-release` | реестр финальных файлов, вариантов 16:9/9:16 и расходов |

## Правила применения

- **GitHub = источник SKILL.md; n8n = раздельные сохранённые копии**. Изменения на GitHub пока не синхронизируются. Следующий отдельный проект — `GremoVOD Skill Sync`.
- Для пользовательских навыков импортированы также реально существующие Markdown-справки `references/` (если они есть). `gremovod-screenplay/references/example.json` сохранён в n8n как справка `references/example.json.md` с JSON внутри, поскольку n8n принимает Markdown references. Внешние навыки Anthropic/Remotion импортированы как тексты основных инструкций; их дополнительные среды выполнения/системные tools не подключены.
- Скилл `video-*` — **профиль генеративной видеомодели**, не текстовая LLM агента. Агенты сейчас подключены к Kie для текстовых Claude; свойства media API из скиллов нередко относятся к PiAPI. **Не отправлять параметры PiAPI в Kie без проверенного адаптера.**
- `pdf` не даёт агенту автоматического доступа к PDF и Python, а `remotion-best-practices` не создаёт само по себе node/ffmpeg/CapCut среду. Инструменты загрузки/извлечения/рендера потребуют отдельной интеграции.
- Все n8n Agents и 15-узловой workflow v1 сейчас **черновики / выключены**, рабочий конвейер первого поколения не связан автоматически с отдельными saved Agents. Отдельные LLM/медиа-вызовы не запускались.
- Проверка `validate_agent` всех A0–A5 **успешна**, но это не испытание качества и не проверка подключения к веб-backend.
- Прямую запись AI-решений в утверждённый канон запрещать; ответ агента является предложением до подтверждения человека.
- Связь с GremoVOD Web разрабатывать через FastAPI `/api/v1` контракты с общими ID, ревизиями, idempotency и scoped auth. См. `docs/N8N_CODEX_HANDOFF_2026-10-19.md`.

## Что дальше: контрольные точки

- **Пункт 2.** Маршрутизация моделей Kie по сложности (Haiku/Sonnet/Opus), лимиты, учёт токенов; проверить каталог и реальную стоимость отдельно, платные тесты по разрешению владельца.
- **Пункт 3.** Skill Sync по SHA/ревизиям, без дубликатов, обновление draft + проверка, публикация вручную.
- **Пункт 4.** Контракт веб-backend ↔ n8n, sandbox нативных Agents, без платных media calls (параллельно с работой Codex).
- **Пункт 5.** Тест одного эпизода/сцены с правильной передачей канона и ID, затем отдельное решение о публикации.
