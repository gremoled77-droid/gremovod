# ТЗ Codex — Photo Editor / Image Editing Pipeline
Дата: 2026-10-19. Статус: approved for implementation planning; код ещё не интегрирован.
Проект: AI Workflow Studio / GremoVOD. Приоритет: P1, после проверки текущих веток и согласования конфликтов.

## Контекст и правила
Прочитать `AGENTS.md`, `CLAUDE.md`, `docs/HANDOFF_CLAUDE_CODE.md`, `docs/GIT_WORKFLOW.md`, `TODO.md` перед изменениями. Текущий стек React 18 + TypeScript + Vite 6, FastAPI + SQLite, Windows-first, local-first. Работать только в собственном worktree Codex `C:/AI_Workflow_Studio/.worktrees/codex` / ветке `codex/work` (или согласованной feature-ветке в отдельном worktree); не переключать рабочую main и не вмешиваться в claude/work. Перед началом `git fetch origin`, проверить статус и открыть PR после тестов. Порты Codex 8001/5174 и отдельный STUDIO_DATA_DIR; никогда не запускать/останавливать основной сервис 8000/5173. Никаких платных API-запросов, никакой загрузки рабочих медиаданных/баз/ключей в git.

## Три исходных GitHub-проекта
1. `https://github.com/mukeshsoni/react-image-editor` — MIT, компонент `@mukeshsoni/react-image-editor` (React canvas, неразрушающая коррекция, crop, цвет, кривые, ретушь, undo/redo, экспорт). Использовать package из npm только после проверки версии, лицензии, peerDependencies React 18, доступности npm и безопасности; фиксировать версии lockfile. Прототип интеграции лучше писать как обёртку, не копировать весь репозиторий.
2. `https://github.com/danielgatis/rembg` — MIT, Python-пакет для фоновой сегментации. Поставить как OPTIONAL dependency (например, `backend/requirements-image.txt`), не в основной requirements, чтобы отсутствие тяжёлых моделей не ломало запуск GremoVOD. Проверить совместимость Python 3.13 / Windows / onnxruntime и фактический размер моделей на тестовом стенде. По умолчанию CPU, GPU только при совместимости.
3. `https://github.com/pricklygorse/Interactive-Image-Background-Remover` — образец интерактивного выделения (positive/negative clicks, bounding box, кисть, trimap, волосы, alpha matting), SAM/mobile-SAM, BiRefNet, LaMa. Это PyQt desktop-приложение, его GUI НЕ включать в React. Перед заимствованием кода проверить явную лицензию исходников и лицензии каждой модели/весов: отсутствие лицензии трактовать как запрет на копирование. До проверки — использовать только как функциональный референс и самостоятельно написать API/UX поверх разрешённых библиотек. Никаких бесконтрольных скачиваний весов.
В документе `docs/PHOTO_EDITOR_DEPENDENCY_AUDIT.md` вести таблицу: URL, commit/tag/версия, лицензия кода, лицензия модели, Python/Node compatibility, CPU/GPU требования, риски CVE, решение use/wrap/reference-only.

## Цель
Встроить редактор изображений в GremoVOD: открыть референс из Character Vault, кадр из галереи / «Кадры» / раскадровки; выполнить точные и локальные коррекции; сохранить как новую версию того же ассета или отдельный производный ассет, сохранив оригинал, происхождение и привязки. Предоставить экспорт в дальнейшие image/video-модели без автоматического расхода кредитов. Русский UI в стиле существующей студии, адаптация на мобильном.

## Функциональные этапы и приоритет
### Phase 0 — аудит, скелет
- Изучить текущую схему library/assets, upload, маршруты Character Vault / CreateScreen / Lightbox и сохранения проектов. Не создавать параллельный самостоятельный asset store при наличии штатного.
- Проверить лицензии и npm package React editor, выбрать совместимый релиз или реализовать лёгкую собственную обёртку; оформить архитектурное решение.
- Feature flag `photo_editor_enabled`; отсутствие optional deps не должно портить текущую сборку.

### Phase 1 — MVP без моделей и без оплаты
- Открыть изображение из gallery/Character Vault/Lightbox; drag-and-drop + выбор файла в рамках существующих правил хранения.
- Crop: свободная рамка, 1:1, 4:5, 9:16, 16:9, поворот/выравнивание, зеркальное отражение.
- Resize: pixel width/height, lock aspect ratio, fit/fill, выбор ресемплинга; показывать оригинальные и конечные размеры.
- Light: экспозиция, контраст, highlights, shadows, whites, blacks, brightness, gamma.
- Color: temperature/tint, saturation/vibrance, HSL, RGB curves, white balance, presets. Sharpness, denoise по возможности библиотеки.
- Full preview / before-after / 100% zoom / панорамирование; Ctrl+Z/Y; Reset отдельных инструментов и всех настроек.
- Неразрушающие параметры хранить сериализованно с `schema_version`; вычисление превью может выполняться в браузере, финальный экспорт обязан совпадать с превью в пределах документированных погрешностей. Никогда не перезаписывать originals.
- Экспорт JPEG/PNG/WebP, качество, alpha и цветовой профиль (если сохранение ICC пока не гарантировано — явно предупреждать и тестировать). EXIF orientation учитывать, metadata/privacy policy зафиксировать.
- Выходные ассеты хранятся в выделенном месте в существующей asset library; атомарная запись временного файла с заменой; generate thumbnails. Нельзя обращаться по произвольным путям клиента.

### Phase 2 — автоматическая маска фона
- FastAPI endpoints условно `POST /api/image-editor/jobs/remove-background`, `GET /api/image-editor/jobs/{id}`, `POST /api/image-editor/versions` (перед реализацией согласовать с существующими api-маршрутами); поддержка локальной очереди/worker и ошибок.
- rembg по запросу пользователя; прозрачный PNG + маска grayscale, мягкие края, режимы white/black checkerboard, сохраняемая маска. Отмена, индикатор прогресса и ограничение параллельных задач.
- Не запускать новые модели или скачивать веса автоматически без явного согласия; в Settings показать размер скачивания, источник, лицензию, CPU/GPU и локальный путь.
- Отсутствие модели: корректный UI «Модель не установлена», обычный редактор продолжает работать.

### Phase 3 — интерактивная сегментация
- Плюс/минус точки, прямоугольник, add/subtract кисть, feather, edge clean, trimap, refine hair, preview alpha, маска как отдельный layer; адаптер для доступной лицензированной SAM/mobile-SAM либо альтернативы.
- Работать с координатами оригинала, масштабирование UI не изменяет маску; batch jobs позже, если тесты проходят.
- LaMa/inpainting — только отдельным необязательным адаптером после проверки лицензий и требований, не смешивать с «без изменения личности».
- Приоритет чистого выделения героев и авто (включая зеркала, волосы, уши, ремни, окна и тонкие детали).

### Phase 4 — pipeline
- `Open in Photo Editor` на карточках gallery/Character Vault/shot frames.
- `Save as new version` / `Save derivative` / `Use as reference`; учитывать approved/rejected/model-specific метки: производная версия не становится approved автоматически.
- Передача asset ID в текущий image/video pipeline; автоизменение референса и перезапись канона запрещены.
- Позднее: batch corrections, style-matching в сцене, цветовые пресеты для миров/локаций, автоматизация через workflow nodes.

## Preserve Identity
- Режим по умолчанию для approved characters, props/vehicles. Классические детерминированные операции доступны; генеративные inpaint/outpaint/change-object скрыты или требуют явного выхода из режима с предупреждением.
- Сохранять ROI/protected masks для лица, шерсти, маркировок авто и других утверждённых элементов; не обещать абсолютную сохранность: цвет, кадрирование и ретушь могут визуально менять восприятие. Подтверждать любую destructive/AI transform.
- Все операции и parent asset ID журналируются.

## Формат данных (предложение, адаптировать к текущей схеме)
```json
{
  "schema_version": 1,
  "parent_asset_id": "uuid",
  "source_sha256": "sha256",
  "operations": [{"type": "crop", "params": {"ratio": "16:9"}}],
  "masks": [],
  "preserve_identity": true,
  "renderer_version": "1",
  "result_asset_id": "uuid"
}
```
Backend должен проверять schema/version/ranges, MIME по содержимому, размеры и лимиты, владение asset ID и доступ к проекту; CORS/CSRF/auth согласно существующим security-модулям. Защита от decompression bombs, path traversal, вредоносного EXIF, очень больших входов. Оригинал и версии используют content hashes и timestamps; очищать временные файлы через действующую политику.

## Тесты / приемка
1. Существует кнопка «Редактировать» на текущем ассете, картинка открывается без обращения к платным моделям.
2. Crop 16:9/9:16, resize, exposure/color, undo/redo; после сохранения исходник побайтово неизменён; новая версия доступна в галерее и возвращается в pipeline.
3. Набор golden images с альфа-каналом, EXIF orientation, RGB JPEG, RGBA PNG, очень большой картинкой, кириллическими названиями файлов, прямоугольниками нечетного размера; близость preview/export проверяется.
4. Без rembg/onnxruntime и без сети основная студия запускается, типы/сборка проходят.
5. С установленным rembg локальная сегментация создаёт прозрачный PNG и маску, сохраняет в asset store, обрабатывает невозможность модели/отмену.
6. UI и API не допускают overwrite original и path traversal; чужие asset IDs недоступны.
7. E2E (Playwright при наличии в проекте) по маршруту Character Vault → Editor → Save derivative → Gallery → Use as reference.
8. Запустить `python -X utf8 -m unittest discover -s backend -p "test_*.py"`, `npm test`, `npm run build`; обновить README, docs handoff, TODO и записать фактические PASS/FAIL, версии и причины пропусков.
9. Никаких платных моделей / API ключей / рабочих данных в тестах. Порты 8001/5174 и temp STUDIO_DATA_DIR. Не объединять main автоматически.

## Definition of done / PR
Codex делает реализацию поэтапными коммитами: Phase 0 audit → Phase 1 Editor MVP → Phase 2 local background removal → Phase 3 masking (после проверки лицензии/весов) → Phase 4 linkage. Для каждого этапа: короткий отчёт о файлах, командах, тестах, screenshots UX, рисках, fallback и стоимости ($0). Создать PR на main, не мержить до проверки владельцем. Не включать третьи репозитории как vendor/submodule без обоснования, совместимости и лицензий.
