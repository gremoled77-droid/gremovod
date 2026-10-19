# Этап P1 — временный AI-ревьюер MiniMax в архитектуре GremoVOD

Дата: 19.10.2026 · Issue: [#27](https://github.com/gremoled77-droid/gremovod/issues/27) ·
ветка: `experiment/minimax-observability-20261020`

Этот документ описывает, что именно добавлено в архитектуру на этапе P1, какие файлы
и узлы n8n созданы, где проходят границы допустимого и что осталось за владельцем.

Изменение кода в репозитории **не означает**, что рабочие процессы n8n обновлены:
обновление n8n — отдельная задача (в этом этапе создан только новый неактивный черновик).

---

## 1. Зачем

С 25.10.2026 MiniMax M Plan используется не только для разработки, но и для проверки кода
через Subscription API Key. Требования владельца:

| Требование | Как выполнено |
| --- | --- |
| Только включённая квота M Plan | `quota.py`: остаток проверяется **до** каждого запроса; не подтверждён → стоп |
| Не трогать credit packs и pay-as-you-go | Окно M Plan исчерпано → `QUOTA_EXHAUSTED`, запрос не отправляется |
| Сначала бесплатные локальные проверки | `localscan.py` + узел 03 n8n: тесты, секреты, лимиты, привязка к SHA |
| Затем по разрешению — ограниченный Git diff | Дифф ≤ 45 КБ, ≤ 12 файлов, только разрешённые пути, привязан к SHA |
| Независимый по контексту запрос | В модель уходят только задача + дифф + тесты; чата и инструментов нет |
| Вывод в Draft PR и в n8n | Узел 10 — отчёт в n8n, узел 11 — комментарий в Draft PR (оба готовы) |
| Смена MiniMax → Argon без правки архитектуры | Один контракт `dev-run-summary/1`, один интерфейс `Reviewer`, три адаптера |
| Реальный запрос — только после согласия | `preflight()` требует `consent=True`; в MOCK сеть не используется вовсе |

## 2. Что создано

### 2.1 Python-пакет `tools/ai_review/` (офлайн, без зависимостей)

| Файл | Назначение |
| --- | --- |
| `contract.py` | Контракт `dev-run-summary/1`: поля, enum-статусы, валидатор без сети и без `jsonschema` |
| `reviewer.py` | Универсальный интерфейс: `ReviewRequest`, `ReviewOutcome`, реестр `get_reviewer("mock\|minimax\|argon")` |
| `payload.py` | Материал ревью: системный промпт + задача + замороженный дифф + тесты; разбор ответа модели |
| `localscan.py` | Общий с Argon локальный скан диффа: лимиты, бинарники, поиск секретов, `allowed_paths` |
| `quota.py` | Охранник: отсечка 25.10.2026, разбор остатка квоты, `preflight()` с fail-closed |
| `report.py` | Русский Markdown-отчёт и короткая сводка для job summary / комментария PR |
| `cli.py` | `review` / `validate` / `report` / `quota` |
| `adapters/mock_adapter.py` | MOCK-ревьюер: детерминированный, без сети и ключей |
| `adapters/minimax_adapter.py` | MiniMax-M3.1-Flash через официальный OpenAI-совместимый API |
| `adapters/argon_adapter.py` | Argon: обёртка над уже проверенной логикой PR #22 |
| `argon_review.py` | Существующий Argon-ревьюер из PR #22 (перенесён без правок) |

### 2.2 Офлайн-тесты `tests/test_review_*.py` — 83 теста, 0 сетевых вызовов

| Файл | Проверяет |
| --- | --- |
| `test_review_contract.py` | Валидация контракта, `PASS`+замечания, `FAIL`+`PASS`, MOCK без usage/cost, stale |
| `test_review_quota.py` | Отсечка 25.10, нераспознанная схема квоты, исчерпание 5-часового/недельного окна, все ворота `preflight` |
| `test_review_payload.py` | Независимый контекст (нет ключей/инструментов), лимит размера, разбор ответа, маскирование секретов |
| `test_review_adapters.py` | MOCK-эвристики, все ворота MiniMax (MOCK/нет согласия/истёк срок/нет квоты), коды `base_resp`, отсутствие автоповторов |
| `test_review_cli.py` | Сквозной MOCK-прогон в временном git-репозитории, репозиторий не меняется |
| `test_review_report.py` | Все разделы отчёта, «НЕ УКАЗАНО» / «НЕ ПОДТВЕРЖДЕНО» вместо выдуманных значений |

Проверки из Issue #27 закрыты: review-payload, schema validation, secret redaction, stale SHA,
quota-exhausted, expiry cutoff, CI FAIL несмотря на AI PASS.

### 2.3 n8n: новый неактивный черновик

`GremoVOD Dev Observability — MOCK (MiniMax Reviewer)` —
<https://gremovod.app.n8n.cloud/workflow/XInjy5I69fd11iLv>
(личный проект GremoVOD, 13 узлов, `active: false`, `activeVersionId: null`, 0 credential).

Исходник: `workflows/WF_07_MiniMax_Reviewer_MOCK.ts` (SDK) и
`workflows/WF_07_MiniMax_Reviewer_MOCK.json` (импорт в n8n Cloud).

Узлы:

| # | Узел | Тип | Роль | Выключен |
| --- | --- | --- | --- | --- |
| 00 | Ручной запуск MOCK | manualTrigger | единственная точка входа, ручной запуск | нет |
| 01 | Нормализация входа | Code | проверка обязательных полей, `provider` ∈ {mock, minimax, argon} | нет |
| 02 | Дедупликация run_id | Code | повторный `run_id` → `NOT_RUN` | нет |
| 03 | Локальные бесплатные проверки | Code | `tests_status == PASS`, поиск секретов, лимит диффа, валидность `diff_sha256`, base≠head | нет |
| 04 | Квота M Plan и отсечка | Code | стоп после 25.10.2026 00:00 +03:00; в LIVE — только при подтверждённой квоте и согласии | нет |
| 05 | Сборка материала ревью | Code | задача + замороженный дифф + тесты → `messages` | нет |
| 06 | Выбор ревьюера | Code | **точка смены провайдера**: `mock` → MOCK; `minimax`/`argon` → URL и тело запроса | нет |
| 07 | HTTP запрос провайдеру | HTTP Request | `POST` на URL из узла 06; MiniMax-M3.1-Flash / Argon | **да** |
| 08 | Валидация ответа | Code | разбор JSON, проверка enum, привязка к SHA; неполный ответ → `UNCERTAIN` | нет |
| 09 | Сборка summary | Code | сборка `dev-run-summary/1` | нет |
| 10 | Отчёт в n8n | Code | Markdown-отчёт в вывод execution | нет |
| 11 | GitHub Draft PR summary | HTTP Request | комментарий в Draft PR | **да** |

Плюс sticky-note с правилами MOCK-режима.

### 2.4 CI и документация

| Файл | Назначение |
| --- | --- |
| `.github/workflows/minimax-review-summary.yml` | Только `workflow_dispatch` + push в свою ветку: офлайн-тесты и MOCK-отчёт в job summary |
| `docs/experiments/MINIMAX_N8N_OBSERVABILITY_RU.md` | этот документ |
| `docs/experiments/MINIMAX_REVIEWER_ADAPTER_RU.md` | контракт и правило переключения MiniMax → Argon |
| `agents/minimax/HANDOFF_FOR_CODEX.md` | что делать Codex после этого этапа |

## 3. Границы, которые мы не переходили

- **Ни одного реального запроса к MiniMax.** Ни одного. Живой вызов требует отдельного
  согласия владельца, ключа и подтверждённого остатка квоты.
- **Ни одного изменения `main`.** Всё в ветке `experiment/minimax-observability-20261020`.
- **Существующие n8n-воркфлоу не тронуты** — создан только новый черновик, и он не активен.
- **Credential не создавались.** Узлы 07 и 11 без credential — назначаются руками при включении.
- **Токен MiniMax в репозитории не попадал.** Ключ берётся из переменной окружения
  `MINIMAX_SUBSCRIPTION_KEY` в момент запуска.

## 4. Что осталось за владельцем

1. **Ключ.** Задать `MINIMAX_SUBSCRIPTION_KEY` в окружении (Subscription Key M Plan,
   не pay-as-you-go ключ — они не взаимозаменяемы).
2. **Согласие на первый живой запрос.** До него всё работает в MOCK.
3. **Проверка остатка.** `python -m tools.ai_review.cli quota` — только чтение, без расхода.
4. **Публикация n8n-черновика** и включение узлов 07/11 с назначением credential.
5. **Draft PR** с этой ветки.

## 5. Как запустить MOCK сейчас

```powershell
cd C:\Users\BLOWKA\Documents\Minimax\gremovod-mplan
python -X utf8 -m unittest discover -s tests -p "test_review_*.py" -v
python -X utf8 -m tools.ai_review.cli review --repo . --base origin/main --head HEAD `
  --scope "Проверка контракта ревьюера" --provider mock --mode MOCK --tests-status PASS `
  --out-dir artifacts/ai-review
```

Результат: `artifacts/ai-review/<run_id>/summary.json` и `report.md`.

## 6. Живой запрос — только после согласия

```powershell
$env:MINIMAX_SUBSCRIPTION_KEY = "<Subscription Key M Plan>"
python -X utf8 -m tools.ai_review.cli quota          # остаток, только чтение
python -X utf8 -m tools.ai_review.cli review --repo . --base origin/main --head HEAD `
  --scope "..." --provider minimax --mode LIVE --consent --tests-status PASS
```

Без `--consent` запрос не уйдёт: `CONSENT_REQUIRED`. Без подтверждённой квоты —
`QUOTA_UNKNOWN`. После 25.10.2026 00:00 (+03:00) — `SUBSCRIPTION_EXPIRED`.

## 7. Ссылки

- Issue: <https://github.com/gremoled77-droid/gremovod/issues/27>
- Issue #28 (разрешение писать код в своей ветке): <https://github.com/gremoled77-droid/gremovod/issues/28>
- Argon-ревьюер (PR #22): <https://github.com/gremoled77-droid/gremovod/pull/22>
- Спека n8n-пилота (PR #23): <https://github.com/gremoled77-droid/gremovod/pull/23>
- Handoff MiniMax (PR #25): <https://github.com/gremoled77-droid/gremovod/pull/25>
- n8n-черновик: <https://gremovod.app.n8n.cloud/workflow/XInjy5I69fd11iLv>
- OpenAI-совместимый API MiniMax: <https://platform.minimax.io/docs/api-reference/text-chat-openai.md>
- M Plan (Subscription Key, квота, credit packs): <https://platform.minimax.io/docs/m-plan/usage-rules.md>
