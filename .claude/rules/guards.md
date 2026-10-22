# Автоматические ограничения сессии

В репозитории три хука `PreToolUse` (`.claude/settings.json`). Они отклоняют команду
**до** её выполнения, поэтому обойти их «по-тихому» нельзя.

| Хук | Что отклоняет |
|---|---|
| `.claude/hooks/guard_git.py` | `push`/`merge`/`rebase`/`reset`/`checkout` в защищённую ветку (`main`, `master`, `mavis/work`), `push --force`, `git clean -f`, удаление чужой ветки или worktree |
| `.claude/hooks/guard_paid.py` | `scripts/live_piapi_test.py` без `--dry-run`, `scripts/watch_hunyuan_test.py`, прямые обращения к платным хостам (`api.piapi.ai`, `api.openai.com`, …) |
| `.claude/hooks/guard_files.py` | запись в ключи (`*_API_KEY.txt`, `.env`), SQLite, `backend/media/`, `backend/library/`, `backend/character_library/`, `runtime/`, `projects/`, `.claude/settings.local.json` |

Правила:

- Отклонённая хуком команда — это сигнал, а не сбой. Не искать обход: перечитать
  причину, исправить задачу или выполнить вручную с разрешения владельца.
- Платный запуск не выполняется в сессии вообще. Разрешение владельца на конкретный
  запрос оформляется через `GREMOVOD_ALLOW_PAID=1` в окружении сессии и через
  бюджетный пакет студии — не через эту переменную.
- Хуки **не заменяют** `scripts/check_git_files.py` (pre-commit) и CI-сканер секретов:
  pre-commit ловит путь в staged-изменениях, CI — в diff, хуки — в момент действия.

Проверить хуки без запуска студии:

```powershell
python -m unittest tests.test_claude_hooks -v
```
