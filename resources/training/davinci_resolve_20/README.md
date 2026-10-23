# DaVinci Resolve 20 — официальные обучающие материалы для GremoVOD

Изолированный модуль загрузки официальных обучающих материалов Blackmagic Design. Сами большие PDF и медиафайлы хранятся только локально, **в GitHub не коммитятся**.

**Источник:** https://www.blackmagicdesign.com/products/davinciresolve/training

## Что загружается

- **6 PDF**: Beginner’s Guide, Editor’s Guide, Fairlight Audio Guide, Colorist Guide, Visual Effects Guide и Advanced Visual Effects Guide.
- **4 ZIP** с учебными материалами Fairlight Audio (Part 1–4). Скрипт извлекает из архивов отдельные файлы WAV, MP3, AIFF, FLAC, OGG, M4A, WMA, CAF и BWF. ZIP сохраняются для полноценной работы с учебными проектами. Это **не** аудиодорожки из обучающих видео.
- Прямые официальные ссылки: [catalog.json](catalog.json).

## Запуск на локальном Windows 10/11

Открой терминал **в корне репозитория GremoVOD**, обнови проект командой `git pull`, затем:

```powershell
py -3 resources\training\davinci_resolve_20\download.py
```

Нужны Python 3.12+ и штатный curl.exe в Windows. Дополнительных Python-пакетов нет. Уже загруженные файлы пропускаются, при прерывании загрузки скрипт пытается продолжить её.

Только PDF:

```powershell
py -3 resources\training\davinci_resolve_20\download.py --pdf-only
```

Только Fairlight:

```powershell
py -3 resources\training\davinci_resolve_20\download.py --audio-only
```

Для экономии места после извлечения можно указать `--remove-zips` (но остальные исходные материалы из ZIP тогда будут потеряны). Чтобы скачать только исходные ZIP без извлечения аудио — `--no-extract`.

## Структура после выполнения

```text
resources/training/davinci_resolve_20/
  README.md
  catalog.json
  download.py
  downloaded/                 # локально, игнорируется Git
    PDF/                      # 6 официальных книг
    Fairlight_Archives/       # 4 исходных ZIP
    Fairlight_Audio/          # аудиофайлы, разбитые по архивам
    download-report.json      # источники, размеры, SHA-256, ошибки
```

**Важно:** файлы Fairlight могут занимать много места. Проверь свободный объём диска. Не публикуй авторские PDF и ZIP в открытом GitHub-репозитории. Если ZIP не содержит аудиофайлов как отдельных файлов, он сохраняется для ручного извлечения других видов медиаданных.

Ссылки взяты с официальной страницы 19.10.2026. На сайте для скачивания предлагаются руководства DaVinci Resolve 20.
