# Codex — пакет перед первым архитектурным ревью

Дата подготовки: 2026-10-19. **Это задача на ревью**, а не требование немедленного объединения PR или включения моделей.

## Где начать (самая короткая дорожка)

1. Читать `AGENTS.md`, `CLAUDE.md`, `AGENT_BUILD_MANUAL.md`, `STATUS.md`, `docs/CODEX_DECISIONS.md`.
2. Сравнить исходный `main` со спецификацией [PR #17](https://github.com/gremoled77-droid/gremovod/pull/17) (base: `codex/n8n-full-production-spec-20261019`), затем зависимый [PR #18](https://github.com/gremoled77-droid/gremovod/pull/18) (base: `feature/n8n-astra-contract-hardening-20261019`). Это **цепочка PR**, не два независимых PR в main.
3. Проверить, что текущая P0 логика корректно встроена в существующие `backend/main.py`, `backend/automation.py`, `backend/security.py`, `backend/adapters.py` — сейчас она **reference-only**, отдельные worker mocks и новая SQLite **не подключены** к реальному FastAPI.
4. Подготовить ограниченное заключение `APPROVE / CHANGES_REQUESTED / BLOCKED` с номерами ошибок, самым безопасным merge/rebase планом и двумя заданиями (Claude / Argon) на НЕпересекающиеся файлы.

## Какие файлы есть

- Канонический текст технического ТЗ: `docs/specs/n8n-production-2026-10-19/{SPECIFICATION.md,NODES.md,nodes.json,VALIDATION.json}`.
- Дополнение P0/Astra: `docs/specs/n8n-production-2026-10-19/ASTRA_FIXES_V1_1.md`, `N34_N41_RUNTIME_MODEL_MATRIX.md`.
- Память/лимиты: `db/schema.sql` (5 новых `p0_*` таблиц, legacy `jobs` нельзя разрушать), `backend/p0_control.py`, `scripts/p0_migrate.py`.
- Тесты: `backend/test_p0_control.py`, `backend/test_p0_migrate.py`, `tests/test_p0_state.js`; мок-медиа: `tools/mock_media_pilot.py`, `tools/mock_evidence.py`.
- Текущий mock слой: `integrations/n8n/WF_00_WF_06_MANIFEST.json`, все семь физически присутствуют в n8n Cloud (parent execution #39 = success, 0 платных API, без фактической media QA).
- **Версионированные JSON-экспорты:** `workflows/WF_00_Core_Infra.json` ... `WF_06_Repair_Router.json`, все `active=false`, без credentials. В родителе шесть `REPLACE_WITH_IMPORTED_WF_0n_ID`. Не запускать копию, пока не переназначены IDs.
- Креативная часть: проверенные `skills/gremovod-*` в git, новые `prompts/**` не утверждены; `canon/**` владелец.

## Критические вопросы Codex (не решать обходом)

**P0-DB:** Будет ли пять `p0_*` таблиц дополнительным shadow-state вместо использования действующей Studio? Нужна одна точка истинного состояния. Подтвердить точный путь SQLite и миграцию с rollback на **копии** настоящей схемы, сохранив все legacy records.

**P0-AUTH:** В reference-функциях есть флаги `trusted_studio_owner`, `trusted_studio_request_authorization`, `provider_evidence_verified`. Любой caller, принимающий эти булевы значения из HTTP/n8n тела, уязвим. Разрешение должно происходить внутри FastAPI из сессии/ACL/CSRF, событий и verified provider evidence.

**P0-MONEY:** UNKNOWN после submit сохраняет резерв и блокирует re-submit; проверить сумму операций, реальные provider client IDs, timeout до/после HTTP, гонки по lease и согласование reserve/spent. Доказать отсутствие второго POST на реальном адаптере, **только после** бесплатных fault-injection тестов.

**P0-MANIFEST:** `manifest_ready` смотрит на присутствующие обязательные строки, но не видит заранее запланированные отсутствующие слоты. Сначала заморозить полный `expected_media_manifest` и проверить комплектность против него; иначе монтаж может пройти при пропущенном slot.

**P0-MEDIA:** GitHub FFmpeg mock создал настоящие синтетические файлы на runner, но `mock://` в n8n не указывает на них. Нужно достоверное outbound file transport Windows→Cloud→Windows, checksum/viewer access и изолированный sample MP4.

**P1-QA:** 1/4/7 sec extracted frames не являются доказательством движения, lip-sync, тембра и склеек. Нужна capability matrix по source+model+time coverage и fail-closed N34/N35/N36–N41. Сейчас A8 и READY блокированы.

**P1-EDITOR:** `CLAUDE.md` содержит принятое решение «монтаж вне Studio в CapCut», а новое ТЗ содержит FFmpeg-сборку N32/N33. Уточнить: FFmpeg — автоматический mock/master-export и технический путь, CapCut — творческий монтаж? Не менять пользовательское продуктовое решение молча.

**P1-WORKFLOW:** n8n MOCK семь workflow реально запускаются (execution #39), но экспорты не могут обращаться к настоящим локальным файлам и workflow parent требует remapping subflow IDs. Не вводить ещё 52 физические workflow.

**P1-SKILLS:** Указанные пользователем `grem`, `get-more-perspectives`, `generate-fresh-ideas` не подтверждены как установленные. Не писать в спецификацию фиктивные исполнимые skills; предложенные идеи отдельно от файловых навыков.

## Результат, который должен вернуть Codex

Короткий структурированный отчёт:
- **Что проверено по факту** (конкретные файлы, тесты, зелёный CI),
- **Критические дефекты** (P0 прежде P1),
- **Какие 2–3 изменения исправить первыми**,
- **Что можно безопасно отдать Claude**, а **что Argon**, с точными непересекающимися путями,
- **Что пока не начинать** (API деньги, real-media QA, изменение канона),
- Решение об отношении PR #17/#18/этого coordination PR к `main` — **не merge автоматически**.

## Текущее ограничение и проверки

- Последний зафиксированный до подготовки координации CI `39220285632` был green (mock/isolated tests).
- User MP4 отсутствует. Настоящий видео- и аудиоанализ не проверен.
- Запуск локального Claude Code / Argon из этого GitHub-чата **не выполнялся**; нет доказанного локального workspace/status.
- `main` и рабочая SQLite **не изменены**.
