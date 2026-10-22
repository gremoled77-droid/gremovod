# GA-03 backend — release gate (Claude, 2026-10-22)

База: `claude/beta-01-20261022` @ `b0ea55d` (PR #78, с исправлением B1). Ветка: `build/claude/ga-03-release-backend`.
Файлы: `backend/release_gate.py` (новый), `backend/release_artifacts.py`, `backend/test_release_gate.py` (новый, 25 тестов). `media_qc.py`/`qa_reviews.py` не менялись — N34/N35 вызываются, не копируются. Frontend не затронут.

## Контракт API (для MiniMax)

`GET  /api/projects/{pid}/release-artifacts/{aid}/gate` — состояние, считается сервером при каждом чтении (SHA-256 файла пересчитывается; для файла ~1 ГБ это секунды, поэтому вызывать по одному артефакту, не в списке).
Поля: `state` (`IMPORTED|TECHNICAL_PASS|OWNER_APPROVED|REJECTED`), `master_sha256`, `qc_verdict`, `qc_stale`, `qc_reason`, `version_id`, `project_revision`, `content_sha256`, `decision`, `decided_at`, `owner_id`, `decision_stale`, `decision_stale_code`, `decision_stale_reason`, `approve_blockers[{code,message}]`, `can_approve`, `can_reject`, `blocked_reason`, `n35_evidence{master,qc,coverage,coverage_status,reason,processing_rights_confirmed}`, `history[]` (до 20 решений).

`POST /api/projects/{pid}/release-artifacts/{aid}/qc/measure` (существует) — запуск N34; тело `{manifest:{...}}`.

`POST .../{aid}/decision` — тело `{decision:'APPROVED'|'REJECTED', owner_id, expected_master_sha256, processing_rights_confirmed, required_modalities:['VIDEO'], note}`. Ответ `{duplicate, gate}`. Ошибки: `detail.code` + `detail.message` (русский текст): `QC_NOT_RUN, QC_NOT_PASSED, QC_STALE, MASTER_FILE_MISSING, MASTER_CHANGED, CONTENT_CHANGED, PROCESSING_RIGHTS_NOT_CONFIRMED, MEDIA_NOT_CONFIRMED, OWNER_ID_NOT_CONFIGURED, OWNER_ID_MISMATCH, MACHINE_TOKEN_FORBIDDEN (403), REJECT_REASON_REQUIRED (400)`.
Импорт `status` теперь `imported` (раньше `ready`). Новая таблица `release_decisions` создаётся при старте (CREATE IF NOT EXISTS, существующие таблицы не меняются).

## Правила
- APPROVED: права подтверждены → мастер есть и N34 PASS → `expected_master_sha256` = живой хеш → QC не устарел → N35 покрытие VIDEO → запись (хеш мастера, хеш `projects.state`, версия, владелец).
- REJECTED: всегда записывается (нужна причина), без PASS и без файла. Привязан к хешу: при изменении файла отказ перестаёт действовать.
- Снимают утверждение: изменение байтов, повторный N34 не-PASS, пропажа файла, изменение `projects.state`. Не снимают: смена заголовка, порядок ключей, рост `revision`.
- Повтор того же решения → `duplicate:true`, без новой записи.

## Честная граница по владельцу: OWNER_AUTH_REQUIRED
`owner_id` из запроса сверяется с `GREMOVOD_OWNER_ID` на сервере — это **атрибуция, не аутентификация**. Локальная сессия общая на процесс; кто её имеет, может передать и `owner_id`. Машинный токен отклоняется явно (403) и middleware'ом. Настоящий вход владельца (PIN/пароль) — решение владельца; не реализовано. Без `GREMOVOD_OWNER_ID` утверждение и отклонение невозможны (fail-closed).

## Проверки (облако)
`pytest backend/test_release_gate.py` — 25 passed; `pytest backend` — 513 passed, 26 subtests. Интеграционная копия (mavis/work + #75 + #58 + #76 + #79 + #78 + этот PR, не пушилась) — 580 passed, 0 конфликтов слияния.
NOT_RUN: GitHub Actions CI, Windows GUI, CapCut, браузерный UI, миграция рабочей SQLite, реальный MP4 владельца.

## Задание MiniMax: экран «Выпуск»
Разрешённые пути (scope `ga-03` в `tools/minimax_task_scopes.json`): `frontend/src/StageSummary.tsx`, `frontend/src/releaseGate.test.mjs`. Стили в `design.css`/новый компонент **не** в scope — если нужны, отдельное согласованное расширение scope; пока использовать существующие классы `ss-*`.
Сделать в `ReleaseSummary` для каждого артефакта (запрос `/gate` по одному):
1. Загрузка MP4: `POST /api/projects/{pid}/release-artifacts` (multipart: `file`, `project_revision`, `title`), показать ошибки 413/415/422/409.
2. Показ версии (`project_revision`, `version_id`) и полного SHA-256 (копируемый).
3. Кнопка «Проверить (N34)» → `qc/measure`; показ PASS_TECHNICAL / FAIL / BLOCKED и `qc_reason`; предупреждение `qc_stale`.
4. Блок N35: покрытие из `n35_evidence`, `reason`.
5. Чекбокс «Подтверждаю право на обработку»; поле «Владелец» (`owner_id`); «Утвердить» отправляет `expected_master_sha256` = показанный хеш. Кнопка неактивна при `approve_blockers`, причина — `message` по-русски; не вычислять допуск на клиенте.
6. «Отклонить» всегда доступна, причина обязательна.
7. Итог: статус, дата `decided_at`; при `decision_stale` показывать `decision_stale_reason`. Счётчик «финальных MP4» = только `state==='OWNER_APPROVED'`; остальные — «ждут приёмки».
8. Тест `releaseGate.test.mjs`: чистые функции (подсчёт финальных, сборка тела решения, выбор текста блокировки). Проверка: `npx tsc --noEmit`, `npm test`, `npm run build`, prettier.
Автозапуск MiniMax не выполнялся.

## Карта интеграции (проверено слиянием во временной копии)
Порядок: #75 (CI/хуки) → #58 → #76 → #79 (R3; #80 — дубликат того же патча от Claude, оставить один) → #78 (BETA-01) → этот PR (GA-03 backend). Последовательные `git merge` от `mavis/work` @ `57cac59`: конфликтов нет, 580 тестов зелёные. После каждого шага повторять `pytest backend`. Пересечение файлов: `backend/release_artifacts.py` — только этот PR; `media_qc.py`/`qa_reviews.py` — #78. Приёмка GA-01 и политика ручной сверки нечитаемой суммы остаются решением владельца; GA-02 не начат.
