# Codex — закрытие трёх дефектов P0, 19.10.2026

**Локальный коммит исправлений:** `7225a64`. Отправка ветки в GitHub не выполнена: автоматический контроль отклонил escalation для `git push`, поскольку потребовал отдельного явного разрешения владельца на отправку изменённых файлов во внешний remote. Обход другими инструментами не выполнялся. Удалённая ветка отсутствовала при заключительной read-only проверке; PR и новый GitHub CI не создавались. Для публикации требуется подтверждение на отправку только `codex/p0-fixes-20261019` в `gremoled77-droid/gremovod`, без main/merge.

- **Сделано:** R-01 (новая попытка при UNKNOWN), R-02 (неполный expected manifest), R-03 (частично применённая миграция) исправлены в отдельной ветке `codex/p0-fixes-20261019`, от review-коммита `c4aaf3f` / пакетного head `9287455`. Владелец прямо поручил исправления Codex; Claude/Argon не запускались и не получали сообщений.
- **Файлы:** `backend/p0_control.py`, `backend/test_p0_control.py`, `backend/test_p0_regressions.py`, `backend/test_p0_migrate.py`, `db/schema.sql`, `scripts/p0_migrate.py`, `.github/workflows/n8n-astra-pilot.yml`, `db/README.md`, `STATUS.md`, журнал/очередь Codex и ссылки в историческом review. Старый review-command сохранён через импорт штатных регрессий.
- **Следующий шаг:** архитектурное ревью исправлений, затем отдельная задача R-04/R-05: единый бюджет Studio и доверенная авторизация. Не повторять R-01–R-03 в Claude BUILD-01. Production migration, owner API, transport и реальные провайдеры остаются отключёнными.

## Проверенный результат

1. Проверка другого незавершённого действия `run_id/slot_id/kind` выполняется под BEGIN IMMEDIATE до резервирования и повторно до submit. Новый envelope/job ID не обходит UNKNOWN; резерв первой операции сохраняется. Проверена реальная гонка двух соединений/потоков в WAL: один резерв и один отказ. Подтверждённый terminal failure допускает следующую явно авторизованную попытку.
2. `freeze_manifest` сохраняет весь план текущего snapshot в `p0_runs.expected_media_manifest` до производства и создаёт MISSING placeholders. Удаление обязательной строки, подмена required/kind/revision или отсутствие hash больше не дают PASS. План нельзя переопределить внутри исходной версии; отсутствие freeze блокирует montage. Смена версии требует нового freeze, прежние asset-записи автоматически не удаляются.
3. Preflight известных P0-колонок и весь DDL/ALTER/quick_check выполняются одной транзакцией. Fault injection через SQLite authorizer подтверждает rollback после создания части таблиц и после ALTER старой схемы. Старый layout обновляется одной nullable-колонкой, записи остаются. Имя backup резервируется эксклюзивно; подтверждена защита от конкурирующего создания файла backup. Чужая активная транзакция никогда не коммитится установщиком.

## Выполненные проверки на Windows

```powershell
# STUDIO_DATA_DIR был отдельным временным каталогом, без рабочей SQLite
python -X utf8 -m unittest discover -s backend -p 'test_*.py' -q
# 327 tests, OK; включает настоящий FFmpeg/ffprobe на synthetic fixtures

python -X utf8 -m unittest -q tools.test_agent_coordination tools.test_agent_scope
# 14 tests, OK

node --test tests/test_p0_state.js
# 7 PASS; повторные Python emergency cases, не независимый provider E2E
```

Python использован из `C:/AI_Workflow_Studio/.venv/Scripts/python.exe`. Фокусный набор P0 — 36 PASS, из них 11 acceptance-регрессий. Они добавлены в существующий `n8n-astra-pilot.yml`, а прежние три FAIL сохранены как историческое доказательство в `CODEX_REGRESSION_RESULTS.txt`. Текущий результат сохранён отдельно в `CODEX_P0_FIX_RESULTS.txt`. `git diff --check` PASS.

Рабочие `main`, SQLite, канон, исходные пользовательские файлы и n8n Cloud не менялись. Миграция проверена на временных БД и восстановленном из исходника старом P0 layout, не на копии пользовательской базы. UI не менялся. Защищённые owner sessions/ACL, общий старый+новый бюджет, reconciler UNKNOWN и реальные provider POST остаются незавершёнными; устранение трёх ошибок не означает PRODUCTION_READY.
