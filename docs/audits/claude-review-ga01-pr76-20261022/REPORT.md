# Независимая ревизия GA-01 (PR #76): CHANGES_REQUESTED

- Объект: PR #76 `minimax/ga-01-money-p0` → `minimax/ga-01-llm-settlement` (PR #58, base `c634c0c915a1afbf3d75df5bc897f75ef5b723ea`)
- Проверенный HEAD: `481f7983373dd020129eca870cc552fe4e058525` (перепроверен: HEAD не менялся на момент публикации)
- Ревьюер: Claude Sonnet 5.5 (`ANTHROPIC_BASE_URL` не задан — не MiniMax). Платных вызовов нет, рабочая SQLite не использовалась, все базы временные.
- Приёмка владельцем: НЕ выполнена. GA-02 не начинать.

## Прошло (воспроизведено)
R1 (`total_tokens=0` не снимает резерв), R2 (повреждённые токены не ломают старт, миграция идемпотентна), R3 (отрицательные суммы во всех статусах не уменьшают бюджет), R4 (сумма ниже подтверждённой не опускает подтверждённое; повтор → 409), R5 (нечисловая/бесконечная цена → `submission_unknown`, без падения).

## Дефекты (воспроизведены тестами `tests/probe76.py`)
| # | Приоритет | Суть | Место |
|---|---|---|---|
| P1-A | P1 | `reconcile(outcome=done)` без `usd`/`unconfirmed_usd`: оценочный резерв становится `confirmed_usd` (0.000014 → 0.000295, `unknown_usd=0`) без факта провайдера | `backend/llm_guard.py` ~875 (`if status == 'done': confirmed = held`) |
| P1-B | P1 | `repair_legacy_money` падает `ValueError` при старте на `estimated_usd='bad'`; при NULL/-5/inf/nan резерв отрицательной строки становится `usd=0.0` | `llm_guard.py` ~673-674 |
| P1-C | P1/P2 | `done` с `usd > confirmed_usd` даёт сводку, где `usd ≠ confirmed + unknown` (0.5 vs 0.1+0). Ремонт R3 сам создаёт такие строки (`done`, usd .1, confirmed -1 → 0) | `summary()`, `repair_legacy_money` |
| P2-A | P2 | `token_count` принимает 1.5 и 1e30 → `confirmed_usd=1.2e23` при `usd=0.5`; `failed`-сверка затем поставит `usd=confirmed` | `token_count`, `confirmed_from_tokens` |
| P2-B | P2, вне GA-01 | `prepare_task` → `NameError: task_identity` (есть в base c634c0c; тесты скрывают monkeypatch). Контракт PR #65 `test_ga02_prepare_works_without_helper_monkeypatches` красный | GA-02 |

Предположения (не воспроизводились): достижимость строк `done` с `usd>confirmed` в рабочем коде вне миграции; поведение на реальной рабочей базе.

## Тесты
- `python -m unittest backend.test_llm_settlement` — 52 PASS
- `python -m pytest backend` — 539 passed, 26 subtests (лог: `pytest_full_at_481f798.txt`)
- PR #65 `Ga01Runtime`+`Ga01Migration` — 7/8 PASS, 1 FAIL (P2-B)
- `tests/probe76.py` — красные на P1-A, P1-B, P1-C, P2-A (запуск: PYTHONPATH на worktree и каталог пробы, временный `STUDIO_DATA_DIR`)
- GitHub Actions на #76: `validate-agent-handoff` SUCCESS, `check-agent-scope` SKIPPED; backend-тестов в CI на #76 нет — NOT_RUN

## ТЗ MiniMax (ветка `minimax/ga-01-money-p0`, разрешённые файлы: `backend/llm_guard.py`, `backend/test_llm_settlement.py`, один handoff в `docs/agent_handoffs/`)
1. P1-A: `done` без `usd` и `unconfirmed_usd` → 422. `confirmed` повышать только при названной сумме.
2. P1-B: безопасный разбор `usd`/`estimated_usd` (конечное неотрицательное, иначе «нечитаемо»). Для нечитаемой оценки резерв не 0: взять консервативный потолок (конечный `usd`>0, иначе цена по токенам, иначе фиксированный потолок резерва). Статус `submission_unknown`, причина в `note`, строку не удалять.
3. P1-C: после ремонта `done` с `usd > confirmed_usd` не показывать как корректную: перевести в `submission_unknown` (разница → `unknown_usd`) либо явно пометить в `note`. `confirmed` без оснований не повышать.
4. P2-A: `token_count` — только целые ≥0 не выше потолка `valid_tokens`; то же в `confirmed_from_tokens`; `confirmed ≤ usd`.
5. На каждый пункт тест red→green (строки: `estimated_usd` 'bad'/NULL/-5/inf; `done` usd>confirmed; токены 1.5/1e30; `done` без суммы). Контракты PR #65 не ослаблять. GA-02/P2-B не трогать.

## Следующее
После нового HEAD — повтор проб и полного pytest; при зелёном — REVIEW_PASS на точный SHA. Merge не выполнялся.
