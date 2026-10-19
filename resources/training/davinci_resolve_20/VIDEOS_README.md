# Отдельная загрузка обучающих видео DaVinci Resolve в ZIP

Официальный источник: https://www.blackmagicdesign.com/products/davinciresolve/training

**Внимание:** по состоянию на 19 октября 2026 года страница Blackmagic Design предлагает ZIP-загрузки **20 видеоуроков, названия файлов которых содержат DaVinci Resolve 17**. При этом PDF-учебники на странице относятся к версии 20, а шапка сайта уже указывает Resolve 21. Мы не переименовываем видео и не выдаём их за курс версии 20.

Видео ZIP и материалы Fairlight Audio Guide (Lesson Files Parts 1–4) — **разные архивы**. Скрипт не затрагивает Fairlight Audio Guide Part 2, даже если пользователь удалил его вручную.

## Windows: запуск из корня GremoVOD

Обновить скрипты:

```powershell
git pull
```

Сначала посмотреть список без загрузки:

```powershell
py -3 resources\training\davinci_resolve_20\download_videos.py --list
```

Скачать **все 20 ZIP с видео**, оставив их архивами:

```powershell
py -3 resources\training\davinci_resolve_20\download_videos.py
```

Скачать только звук (7 видеоуроков Fairlight):

```powershell
py -3 resources\training\davinci_resolve_20\download_videos.py --section Fairlight
```

Скачать только Fusion (4 видеоурока):

```powershell
py -3 resources\training\davinci_resolve_20\download_videos.py --section Fusion
```

Можно выбрать несколько категорий: `--section Edit --section Color`.

Если захочешь **дополнительно распаковать видео** из ZIP, добавь `--extract`. По умолчанию ZIP-файлы **не распаковываются** и не удаляются.

## Папки на ПК

```text
GremoVOD/
  resources/training/davinci_resolve_20/
    download_videos.py
    video_catalog.json
    downloaded/                     # игнорируется GitHub
      Training_Videos_ZIP/
        Edit/
        Color/
        Fairlight/
        Fusion/
        download-report.json
        Extracted_Videos/            # только при --extract
```

## Поведение

- `curl.exe` — штатный компонент Windows 10/11; Python 3.12+ уже используется в GremoVOD.
- Скрипт проверяет ZIP, пропускает уже загруженные файлы, пытается возобновить прерванные загрузки; ошибки записывает в `download-report.json`. Для принудительной перезагрузки служит `--force`.
- Скачивание может занять много места на диске; объём ZIP заранее не гарантирован.
- Для публикации в GitHub предназначены **только Python-скрипт и текстовый каталог ссылок**; исходные ZIP/видео остаются на диске и защищены `.gitignore`.
- Скрипт ничего не удаляет из прежних `Fairlight_Archives`, `Fairlight_Audio` или `PDF` (они загружались другим скриптом).
- Эти ссылки были сверены с официальной страницей. Проверка содержимого ZIP и фактическая загрузка потребуют запуска на твоём Windows-ПК.


## Проверить вес ZIP до скачивания

Скрипт запрашивает **только HTTP-заголовки** (HEAD); тело ZIP не скачивается:

```powershell
py -3 resources\training\davinci_resolve_20\download_videos.py --sizes
```

Проверка только Fairlight:

```powershell
py -3 resources\training\davinci_resolve_20\download_videos.py --section Fairlight --sizes
```

Если сервер не возвращает `Content-Length`, для архива отобразится `размер не предоставлен сервером`, а итоговый объём останется неизвестным — скрипт не придумывает вес.

## Выбор нескольких конкретных видео вместо всех 20

Можно фильтровать по словам в названии. Например, скачать сначала три урока по звуку:

```powershell
py -3 resources\training\davinci_resolve_20\download_videos.py --section Fairlight --match "Sound Design" --match "Mixing" --match "Recording VO"
```

Или проверить только их вес, добавив `--sizes`. `--match` допускает несколько повторений, в этом случае берётся объединение совпадений. Чтобы предварительно проверить набор, добавь `--list`.

### Практическая ценность для GremoVOD

- В первую очередь: Introduction to Sound Design, Introduction to Mixing, Recording VO and ADR, Introduction to Editing (Part 1/2), Visual Effects in the Edit Page.
- Во вторую очередь: Basic Compositing, Introduction to Fusion, Color Management и Delivering Content.
- Отложить: DaVinci Resolve Mini Panel (специализированное физическое устройство), Multicam Editing (многокамерная съёмка), Dolby Atmos Integration (требовательный объемный звук), Channel Mapping and Linked Groups (редкие задачи).

Одни лишь скачанные видео **не обучают** AI-агентов. Чтобы пополнить скиллы проекта, нужно распознать речь, извлечь скриншоты важных UI-сцен, сформулировать конкретные методы и проверить их на наших материалах.


## Исправление массовой ошибки "not a valid ZIP" (19.10.2026)

Первая версия `DOWNLOAD_8_VIDEOS.cmd` могла скрывать причину неудачной проверки файлов. Актуальная версия вызывает единый Python-проверщик, сначала обследует уже скачанные файлы `.part` и восстанавливает те, которые являются корректными ZIP. Никаких больших файлов повторно не качает при режиме диагностики.

Из корня проекта:

```powershell
git pull
py -3 resources\training\davinci_resolve_20\download_videos.py --priority-eight --verify-only
```

Для попытки скачать только недостающие файлы с остановкой при первой ошибке:

```powershell
py -3 resources\training\davinci_resolve_20\download_videos.py --priority-eight --stop-on-error
```

Файл `DOWNLOAD_8_VIDEOS.cmd` выполняет обе операции с промежуточным запросом подтверждения. Если вместо ZIP приходит HTML или неполный ответ, скрипт показывает первые байты и размер; пришлите эту диагностику, чтобы установить первопричину. HTTP 100% означает завершение передачи, а не гарантию корректности архива.
