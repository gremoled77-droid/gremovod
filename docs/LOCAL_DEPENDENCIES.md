# Локальные зависимости студии

Проверка от 15 октября 2026 года.

Python 3.13.14, Node.js 24.16.0, npm 11.13.0 и зависимости из backend/requirements.txt уже установлены. `pip check` не обнаружил конфликтов. `npm ls --depth=0` и `npm run build` проходят.

FFmpeg и FFprobe 9.0.2 Essentials установлены локально:

```text
C:\AI_Workflow_Studio\tools\ffmpeg\bin\ffmpeg.exe
C:\AI_Workflow_Studio\tools\ffmpeg\bin\ffprobe.exe
```

Источник: https://www.gyan.dev/ffmpeg/builds/ — Windows-сборки, на которые ссылается https://ffmpeg.org/download.html. Архив ffmpeg-release-essentials.zip проверен по опубликованному SHA256. Источник и фактический хеш сохранены в tools/ffmpeg/installation.json. Лицензия и README сохранены рядом с bin. Архив и бинарные файлы исключены из Git.

Backend самостоятельно добавляет локальный bin в PATH своего процесса. START_WINDOWS.bat и DIAGNOSE_WINDOWS.bat также учитывают эту папку. Глобальный PATH и системные каталоги Windows не менялись. После установки backend перезапущен.

Проверка: `.\.venv\Scripts\python.exe -m unittest backend.test_smoke -v` — 7 успешных тестов. Добавлен тест Audio Lab: создаётся синтетический тон, выполняются импорт, анализ длительности, проверка требования согласия и обрезка с denoise/normalize, затем проверяется реальный WAV: 44 100 Гц, моно, одна секунда. Все файлы проверки находятся во временном каталоге; внешние API заблокированы заглушками.

Это обеспечивает локальную обработку аудио. Интеграции ElevenLabs/Fish Audio, распознавание речи и облачная очередь требуют отдельной реализации; устанавливать SDK для существующих HTTP-заготовок сейчас не требуется. Платные запросы при установке и проверках не выполнялись.
