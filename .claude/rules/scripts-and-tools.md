---
paths:
  - "scripts/**"
  - "tools/**"
  - "runtime/**"
---

# Скрипты, утилиты и рабочие данные

## Скрипты

- `scripts/start_studio.py` — запуск студии. `scripts/live_piapi_test.py` — **платный**
  живой вызов модели, запускается только с разрешения владельца и только с `--dry-run`
  при проверке.
- `scripts/check_git_files.py` — единственное определение «запрещённого пути».
  Его используют pre-commit, CI-сканер секретов и хук `guard_files.py`. Правило
  меняется в одном месте.
- `scripts/p0_paid_dispatch_audit.py` — единственное определение платных хостов
  (`PAID_HOSTS`). Хук `guard_paid.py` им пользуется.

## Проверки без установки пакетов

```powershell
python -m unittest tools.test_agent_coordination tools.test_agent_scope -v
python -m unittest tests.test_claude_hooks -v
python scripts/check_git_files.py --staged
```

## Рабочие данные

- `runtime/`, `projects/`, `backend/media/`, `backend/library/`,
  `backend/character_library/` — локальные данные владельца. Хук `guard_files.py`
  не даёт их записать, `scripts/check_git_files.py` не даёт их закоммитить.
- `.venv/`, `node_modules/`, `frontend/dist/`, `tmp/`, `exports/`, `output/` —
  воспроизводимое, в Git не нужно.
- `tools/` — исходники CI-проверок, они в Git. `tools/downloads/` и `tools/ffmpeg/`
  — локальные загрузки, они не в Git.
