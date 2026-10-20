# Карта слияния `mavis/work` ↔ P0-база — 20.10.2026

Сторона: сессия `mavis/work`. Слияние **не выполнялось** — это разбор, чтобы
владелец решал по фактам, а не по ощущениям.

| | Значение |
|---|---|
| Моя ветка | `origin/mavis/work` = `0a28b32` (база `origin/main` 4b1c1b2 + money-ledger + N34/N35 + этап «Продюсер») |
| P0-база | `origin/minimax/p0-astra-fixes-20261020` = `89dfd11` |
| Общий предок | `82adb2d` |
| Разрыв | моя ветка на 31 коммит впереди |

## 1. Факт: слияние текстово почти чистое

`git merge-tree --write-tree origin/mavis/work origin/minimax/p0-astra-fixes-20261020`
даёт **ровно один конфликтный файл — `backend/security.py`**. Всё остальное
сливается автоматически, включая `AGENTS.md` и `docs/HANDOFF_CLAUDE_CODE.md`.

Из P0-базы в мою ветку **приходят** модули, которых у меня нет:
`backend/p0_control.py`, `backend/spend_ledger.py`, `backend/p0_authz.py`,
`backend/p0_provider_dispatch.py` и их тесты.

Регистрации модулей **не теряются**: в автослитом `backend/main.py` присутствуют
все модули P0-базы плюс мои `media_qc`, `producer_stage`, `qa_reviews`,
`release_artifacts`. Точка оплаты выживает целиком:

```
main.py:147  def require_spend_reservation(spend,payload=None)
main.py:165  LLM_TRANSPORTS={}
main.py:167  async def provider_chat(provider, key, payload, spend=None)
main.py:177  async def request_piapi(method,path,key,payload=None,spend=None)
main.py:200  LLM_TRANSPORTS['piapi']=... spend=spend
```

Все платные точки вызова передают `spend=`. Резерв в журнале расходов после
слияния остаётся обязательным.

## 2. Единственный конфликт — и он и есть суть всей задачи

`backend/security.py::budget_state` — обе стороны называют себя «единым
счётчиком», но считают разное:

| Что попадает в бюджет | Моя сторона | Сторона P0 |
|---|---|---|
| медиа-одобрения (`generation_approvals` + `jobs`) | `reservations()` | `spend_ledger.legacy_reservations()` — **тот же самый SQL** |
| платные LLM-вызовы (`llm_calls`) | `llm_reservations()` | **не считает** |
| P0-конверты (`p0_budget_envelopes`, центы) | **не считает** | `p0_reservations()` |
| перерасход (`overrun_cents`) | не считает | `overrun_reserved_usd` |
| ключи ответа | `media_reserved_usd`, `llm_reserved_usd` | `legacy_reserved_usd`, `p0_reserved_usd`, `overrun_reserved_usd` |

Единицы совместимы: центы делятся на 100 (`(reserved_cents + spent_cents) / 100`),
лимиты везде в USD. Но **состав разный, и ни одна сторона не считает всё**.

### Почему «выбрать сторону» — это не разрешение

- Взять сторону P0 → журнал `llm_calls` выпадает из `budget_state`, и
  `check_budget` перестаёт ограничивать платные LLM-вызовы.
- Взять мою сторону → P0-конверты и перерасход выпадают, и медиа-генерации
  через конверты перестают ограничиваться.

Обе резолюции проходят merge без ошибок и **молча ломают границу денег**.

### Правильная резолюция — объединение, а не выбор

Нужна третья функция: медиа + LLM + P0-конверты + перерасход, где деление
центов на 100 живёт в одном месте (`spend_ledger`). Плюс убрать дублирование
SQL: `security.reservations()` и `spend_ledger.legacy_reservations()` — это
один и тот же запрос в двух местах.

## 3. Три механизма подтверждения, а не два

| Механизм | Где | Что подтверждает |
|---|---|---|
| `security.quote` / `verify_quote` | моя ветка | оценка → подпись → вызов |
| `security.execution_permit` | моя ветка (из перенесённой работы 42852da) | задание → permit → исполнение |
| `p0_authz` + `p0_control.authorize` | P0-база | capability и атомарный резерв конверта в одной транзакции |

Плюс в P0-базе есть `p0_provider_dispatch` (fail-closed, mock-only). Правило
проекта — не заводить четвёртый механизм, а сводить к общему ядру.

## 4. Разные способы вызвать провайдера

| | Моя ветка | P0-база |
|---|---|---|
| выбор провайдера | реестр `llm_spec` + `provider_chat` + `LLM_TRANSPORTS` | жёстко `provider != 'piapi'` → 400 «Платный LLM доступен только через PiAPI» |
| реестр цен | `model_catalog.LLM_MODELS` — один источник | таблица в коде |
| ключ | `connections.PROVIDERS[...]['header_key']` | `request_piapi` напрямую |
| резерв перед вызовом | `require_spend_reservation` в точке выхода | у `request_piapi` параметра `spend` не было вовсе |

Текстового конфликта тут нет: версия P0 — общий предок, побеждает моя. Значит
`p0_provider_dispatch` после слияния останется в дереве, но **не станет
единственным путём к провайдеру**. Это ослабление надо закрыть явно: либо
`provider_chat` начинает спрашивать `p0_provider_dispatch`, либо решение
«PiAPI — единственный провайдер» переносится в реестр, а не в условие в коде
(иначе вернётся запрещённый хардкод вендора).

## 5. Рекомендуемый порядок

1. **Сначала деньги, потом остальное.** Слить P0-базу в `mavis/work` как
   добавление (конфликт один), но **не разрешать его выбором стороны** —
   написать объединённый `budget_state` и один источник SQL для медиа.
2. Добавить `llm_reservations` в `spend_ledger.state()`, чтобы P0-контур видел
   LLM-расходы, и `p0_reservations` + `overrun` в `security.budget_state()`.
3. Проверить `p0_provider_dispatch` после слияния: либо он в пути к провайдеру,
   либо решение о единственном провайдере живёт в реестре.
4. Свести три механизма подтверждения к двум: `quote` (оценка → подпись) и
   `p0_control.authorize` (конверт + capability). `execution_permit` — либо
   встаёт внутрь `authorize`, либо снимается.
5. Только после этого — переносить `producer_stage` и ветку скиллов: оба
   зависят от решения по провайдеру (реестр) и от единственного счётчика.

## 6. Что уже готово к переносу

| Что | Где | Статус |
|---|---|---|
| Единый реестр моделей и провайдеров | `mavis/work` | готов, `model_catalog.LLM_MODELS` |
| Транспорты и точка выхода к провайдеру | `mavis/work` | готов, `LLM_TRANSPORTS` + `require_spend_reservation` |
| Журнал LLM-расходов | `mavis/work` | готов, `llm_calls` + `llm_reservations` |
| Этап «Продюсер» (роль A0) | `mavis/work` `5a27517` | готов, 14 тестов, MOCK без затрат |
| N34 / N35 | `mavis/work` | готов, 32 теста |
| Конверты, capability, fail-closed | P0-база | готов, приходит слиянием |
| Канон с утверждёнными карточками | **нигде** | `canon/` содержит только `TEST_*` с `approved: false` |

## 7. Чего карта не закрывает

- **Канон.** Без утверждённых карточек и версии канона пакет ролей A0–A8
  (D4) закрыть нельзя: хэшировать нечего. `canon/characters/TEST_CHARACTER_A.json`:
  `{"kind": "MOCK_CHARACTER_ONLY", "approved": false, "canonical": false}`.
- **Учёт расходов n8n-агентов.** Единственная граница — нативный cap n8n;
  в бюджете Studio записей нет.
- **Video-capable модель и ключ** для N36–N38.
- **Цена MiniMax**: 0,15/0,6 в профиле Aider против 0,3/1,2 в backend-реестре.

Проверки на дату разбора: `python -X utf8 -m unittest discover -s backend -p
"test_*.py"` — 350 тестов, OK (в состоянии с незакоммиченной работой соседней
сессии); frontend — 104 pass, сборка успешна.
