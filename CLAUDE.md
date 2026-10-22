@AGENTS.md

# GremoVOD Studio — работа в Claude Code

Студия производства ИИ-контента: мультсериал про таксиста Грэма (ВАЗ-2106, Минск).
Владелец — grem. Общаться по-русски, коротко и по делу; интерфейс студии тоже на русском.

## Как устроена конфигурация

- `AGENTS.md` — общий контракт с Codex, импортирован выше и читается целиком.
- `.claude/rules/` — тематические правила. Правило с `paths` подгружается только
  тогда, когда работа идёт с подходящими файлами; без `paths` — каждый раз.
- `.claude/skills/` — повторяемые процедуры; грузятся по запросу, а не сразу.
- `.claude/hooks/` — три хука `PreToolUse`: Git, секреты и данные, платные вызовы.
  Что именно они отклоняют — `.claude/rules/guards.md`.
- `skills/` — 36 навыков по киноязыку и сценарию. Claude Code не подхватывает их
  автоматически: путь к нужному навыку даёт `.claude/rules/knowledge-map.md`.

## С чего начать сессию

1. `git status --short`, `git branch --show-current`, `git worktree list`.
2. Прочитать `STATUS.md`, если задача входит в текущую эстафету.
3. Найти документ по теме через `.claude/rules/knowledge-map.md`.
   `docs/HANDOFF_CLAUDE_CODE.md` большой и исторический — читать разделы по теме,
   а не файл целиком.

## Стек и запуск

- Backend: FastAPI + SQLite, `backend/main.py` плюс модули с `register(app, studio)`.
  Порт 8000.
- Frontend: React 18 + TypeScript + Vite 6, `@xyflow/react` для узлов. Порт 5173,
  папка `frontend/`.
- Запуск: `.\.venv\Scripts\python.exe scripts\start_studio.py` или `START_WINDOWS.bat`.
  «already running» — порты заняты старым процессом.
- Здоровье: http://127.0.0.1:8000/api/health
- Порты 8000/5173 принадлежат рабочей студии в корне `main`; свой стенд — 8001/5174
  со своим `STUDIO_DATA_DIR`. Подробности — в `AGENTS.md`, раздел «Запуск и данные».

## Проверки перед коммитом

- Backend: `python -m pytest backend` в venv проекта.
- Frontend, из `frontend/`: `npm test` и `npm run build` (`tsc --noEmit && vite build`).
- Форматирование frontend: `npx prettier --write <файлы>`, конфиг
  `frontend/.prettierrc.json`.
- UI проверять в браузере на http://127.0.0.1:5173, а не только сборкой.
- Не устанавливать системные пакеты и не запускать платные API ради проверки.

## Процедуры

- Проверка изменений и честный отчёт о результатах — скилл `gremovod-verify`.
- Передача работы, handoff и Draft PR — скилл `gremovod-handoff`.
- Поиск документа или навыка по теме — скилл `gremovod-context`.

## Куда смотреть дальше

- `TODO.md` — очередь задач, `CHANGES.md` — история версий (сейчас 0.3.0).
- `docs/` — решения, спецификации и отчёты о проверках; карта — в
  `.claude/rules/knowledge-map.md`.
- Цель текущей беты и решения D1–D4 — в `AGENTS.md`, раздел «Цель текущей беты»
  (ссылки на глобальную приёмку #54).
