---
name: "generate"
description: "Use when the owner asks to generate an image through PiAPI from the terminal (/generate): runs scripts/generate.py against the studio API with a price estimate and explicit confirmation; default model seedream-5-pro, 16:9."
---

# /generate — картинка через PiAPI

Правила: платный запуск идёт только через оценку цены и подтверждение владельца. Ключ PiAPI не читать и не печатать: его берёт бэкенд студии. Скрипт: `scripts/generate.py`.

1. Бэкенд студии должен работать на :8000 (`/api/health`). Если нет, скажи об этом, не запускай сам.
2. Покажи оценку (без оплаты), из корня репозитория:
   `.\.venv\Scripts\python.exe scripts\generate.py "<промпт>"`
   Модель по умолчанию `seedream-5-pro`, формат `16:9`. Остальные флаги из аргументов (`--model`, `--aspect`, `--size`) передай как есть. Промпт, если он по-русски, переведи в английский кинематографичный, но покажи итоговый текст.
3. Назови владельцу модель, формат, проект и цену. Спроси «Запускаем?» и жди явного «да» в чате.
4. После «да» повтори ту же команду с `--yes`. Выведи ссылки на результат.
5. Если модель не включена в запуск (`launch_enabled`), бэкенд откажет: сообщи причину и предложи проверенную модель (seedream-5-lite, nano-banana-2.1, gpt-image-2), не обходи отказ.
