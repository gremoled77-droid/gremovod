# GremoVOD — шаблон отчёта тестового прогона Aider + n8n + Argon

**Этот файл — шаблон, НЕ результат прогона.** Заполнять только из реальных GitHub/n8n/KIE логов после удаления секретов. Не публиковать сырые сообщения, API keys, приватный diff и персональные данные. Полный протокол: [AIDER_N8N_ARGON_PILOT_PLAN_RU.md](AIDER_N8N_ARGON_PILOT_PLAN_RU.md).

## 1. Паспорт прогона

| Поле | Значение |
|---|---|
| Дата UTC | NOT_RUN |
| Task ID / Run ID | NOT_RUN |
| Режим | OFFLINE / MOCK / MANUAL_LIVE / E2E_LIVE |
| Инициатор / owner approval | NOT_RUN |
| GitHub Actions URL | NOT_RUN |
| n8n execution URL | NOT_RUN |
| Draft PR URL | NOT_RUN |
| Base SHA (полные 40 символов) | NOT_RUN |
| Head SHA (полные 40 символов) | NOT_RUN |
| Frozen diff SHA-256 | NOT_RUN |
| Allowed paths | NOT_RUN |
| Рабочий provider/model/route | NOT_VERIFIED |
| Reviewer provider/route | KIE Gemini 4 Argon (LIVE NOT VERIFIED) |

## 2. Релизные ворота

- [ ] G0: утверждён безопасный task + модель/маршрут/оценка.
- [ ] G1: офлайн негативные тесты; нулевые платные вызовы.
- [ ] G2: одиночный ручной вызов Argon с отдельным согласием и совпадением SHA.
- [ ] G3: одиночный платный coder (либо BLOCKED_ROUTE с причиной).
- [ ] G4: ручной Actions bootstrap и offline job.
- [ ] G5: n8n mock GitHub dispatch + idempotency.
- [ ] G6: один полный live end-to-end + owner decision.

**При отсутствии явного доказательства статус остаётся NOT_RUN.** Не превращать failure/blocked в PASS.

## 3. Результаты тестов

| Группа | Количество выполненных | PASS | FAIL | SKIP | Подтверждение (Actions log / CI) |
|---|---:|---:|---:|---:|---|
| Offline reviewer из PR #22 | 0 | 0 | 0 | 0 | NOT_RUN |
| T01–T12 безопасность и git | 0 | 0 | 0 | 0 | NOT_RUN |
| T13–T20 сеть / budget / approvals | 0 | 0 | 0 | 0 | NOT_RUN |
| T21–T25 права / гонки / сравнение | 0 | 0 | 0 | 0 | NOT_RUN |
| Python/Frontend регрессия | 0 | 0 | 0 | 0 | NOT_RUN |

## 4. Состояние Git

- Git branch: NOT_RUN
- Файлы и changed lines: NOT_RUN
- Diff check (<= 45 KB, <= 12 files): NOT_RUN
- Dirty/untracked check: NOT_RUN
- Secret scan: NOT_RUN
- Schema validation: NOT_RUN
- CI tests: NOT_RUN
- Reviewer evaluated the exact HEAD and frozen diff: NOT_RUN
- Write to main: **NO** (проверить при тесте)
- Auto merge: **DISABLED** (проверить при тесте)

## 5. Реальные деньги, токены и время

| Вызов | Статус | Provider / model | Input | Cached / write | Output / reasoning | Credits | Расход USD (подтверждённый) |
|---|---|---|---:|---:|---:|---:|---:|
| Aider coder | NOT_RUN | NOT_VERIFIED | — | — | — | — | — |
| Argon reviewer | NOT_RUN | KIE (route to verify) | — | — | — | — | — |
| Optional repair (не разрешён в первом E2E) | DISABLED | — | — | — | — | — | — |

- API estimated preflight: NOT_RUN
- API billed actual from provider dashboard: NOT_RUN
- UNKNOWN_CHARGE incidents: NOT_RUN
- GitHub runner minutes/cost if applicable: NOT_RUN
- n8n executions/cost if applicable: NOT_RUN
- Budget owner grant / expiry / hash: NOT_RUN
- Итоговая стоимость, включая неопределённость: NOT_RUN

## 6. Argon findings

| Severity | File:line | Evidence | Minimal fix | Regression test | Status |
|---|---|---|---|---|---|
| — | — | NOT_RUN | — | — | NOT_RUN |

Вердикт reviewer: NOT_RUN. Отсутствие находок не доказывает безошибочность. Запрещено выводить PASS при ошибке API, при несовпадении SHA, при CI FAIL и без human approval.

## 7. Остановки и решения

- Был ли повтор HTTP/LLM вызова без отдельного согласия? NOT_VERIFIED
- Зафиксированы ли 429 / timeout / UNKNOWN_CHARGE? NOT_VERIFIED
- Утечки в GitHub/n8n logs? NOT_VERIFIED
- Совпадают ли SHA одобренной ревизии и review? NOT_VERIFIED
- Существующие workflows GremoVOD оставлены без изменений? NOT_VERIFIED
- Рабочий Windows прокси 8767 не менялся и не опубликован? NOT_VERIFIED

**Owner decision:** PENDING — GO / CONDITIONAL / NO-GO.  
**Разрешённый следующий шаг:** NONE UNTIL REVIEW.  
**Требуются новые платные подтверждения:** YES, каждый по отдельности.

## 8. Финальная сравнительная таблица

| Критерий | Aider + API | Codex по подписке | Примечание |
|---|---|---|---|
| Качество исправления по заранее заданным tests | NOT_RUN | NOT_RUN | Один base SHA и одинаковый task |
| Время выполнения | NOT_RUN | NOT_RUN | Без ручного ожидания |
| Реальная денежная стоимость | NOT_RUN | Нельзя вывести стоимость одного запуска из цены подписки | Метрики разного типа |
| Git-diff, количество файлов | NOT_RUN | NOT_RUN | Без сторонних изменений |
| Заметные ошибки на независимом review | NOT_RUN | NOT_RUN | Одинаковая методика |
| Риск повторных оплат/сбоев | NOT_RUN | NOT_RUN | Отдельная оценка |
| Решение по эксплуатации | PENDING | PENDING | Не обещать 5–10x без данных |
