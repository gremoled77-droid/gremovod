# Контракт для Claude Code — BUILD-01

- Сделано: Codex проверил PR #17–19 и воспроизвёл R-01/R-02/R-03. Контракт подготовлен; Claude не запущен, сообщение не отправлено.
- Файлы: разрешённая область `backend/p0_control.py`, `backend/test_p0_control.py`, `backend/test_p0_migrate.py`, `db/schema.sql`, `scripts/p0_migrate.py`, собственный `docs/agent_handoffs/claude-build01.md`. Не править workflows/, integrations/n8n/, docs/specs/, canon/, shared STATUS/CI.
- Следующий шаг: в отдельной ветке `build/claude/p0-state-recovery` от проверенного head `9287455` перенести три [регрессии](../specs/n8n-production-2026-10-19/review_p0_regressions.py) в backend tests и сделать их зелёными; затем сдать PR Codex. Не переключать существующую claude/work.

Порядок: (1) запрет новой попытки при незавершённой/UNKNOWN операции того же логического действия; (2) immutable expected manifest до производства; (3) preflight+versioned atomic migration и rollback на копии. Нужны реальные конкурирующие соединения, истечение lease, restart и fault injection; тесты без платных адаптеров.

Решение S01: production только существующий studio.DB; reference pilot не подключать. Существующие jobs/generation_approvals/spending_limits сохранять. Отдельный независимый P0 project/day budget недопустим; до общего сервиса R-04/R-05 не открывать paid/owner/READY routes. Изменения main.py/security.py/automation.py требуют следующего ограниченного назначения после сравнения соответствующих веток.

Приёмка: три дефекта больше не воспроизводятся; rollback сохраняет и schema, и legacy records; один submit intent на незавершённое логическое действие при любых новых ID/envelope; обязательный отсутствующий slot блокирует montage. Полный штатный P0 тестовый набор PASS. Никаких изменений единственной рабочей SQLite, канона, рабочих портов или provider calls.
