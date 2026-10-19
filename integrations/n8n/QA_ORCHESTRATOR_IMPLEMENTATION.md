# QA Orchestrator — факт внедрения draft в n8n (19.10.2026)

**Этот конкретный workflow создан и проверен двумя офлайн-тестами: ноль LLM/media вызовов внутри workflow, не опубликован.** Позднее вне workflow выполнены отдельные Preview-тесты saved Agents: A7 Sonnet успешно выдал FAIL на синтетическом нарушении, A6 Haiku завершился API internal error после 3 retries. Доступ к QA через сам workflow по-прежнему отсутствует. См. [QA_FASTAPI_CONNECTION_HANDOFF.md](QA_FASTAPI_CONNECTION_HANDOFF.md).

- **Workflow ID:** `nh3ARcl4XPW6RHqs`, [открыть в n8n](https://gremovod.app.n8n.cloud/workflow/nh3ARcl4XPW6RHqs)
- **n8n project:** `jG7gkyrK2hH0rEBj` (GremoVOD, personal)
- **Режим:** Manual Trigger, нет API/HTTP/LLM, нет credentials, нет публикации, запуска живых критиков нет.
- **Источник для воспроизведения и code review:** [снимок графа](workflows/qa-orchestrator.safe-draft.snapshot.json).
- **Протокол будущей петли:** [THREE_CRITICS_LOOP.md](THREE_CRITICS_LOOP.md).

## Граф

```text
Ручной тест (только sandbox)
       |
Проверка входа: task_id/project_id/artifact_id/revision,
   требования, утвержденный brief, bar.md 5-7 механик,
   benchmark, canon, render_refs
       |
       +------> A6 — шлюз ТЗ (Haiku, НЕ ВЫЗЫВАЕТ LLM) ------+
       |                                                    |
       +------> A7 — шлюз канона (Sonnet, НЕ ВЫЗЫВАЕТ LLM) --+--> Merge 3 inputs --> Проверка вердиктов
       |                                                    |
       +------> A8 — запрет Opus (НЕ ВЫЗЫВАЕТ LLM) ---------+
```

Каждая ветка получает отдельный пакет проверки; другой критик/ход генерации в пакет не включается. Сборщик проверяет три обязательные роли, одну ревизию, единственный вердикт на роль, статусы `PASS|FAIL|BLOCKED`; в текущей реализации все три **обязательно BLOCKED**, даже если входное сообщение содержит фальшивый `approval.expert_model: true`. Никаких скрытых автоматических retries или side effects.

### Результат тестов

1. **Execution 7, success:** синтетический проект с двумя требованиями, каноном, `bar.md` на 5 пунктов, render_ref и *недоверенным* флагом якобы разрешенного Opus. Три пакета изолированы, три `BLOCKED`, агрегатор `BLOCKED_AWAITING_INTEGRATION`, `all_passed=false`, `paid_calls_executed=false`. A8 сообщает `trusted_expert_approval_not_integrated` и `verified_media_inspection_not_available`.
2. **Execution 8, success:** полностью пустой вход. В ответе перечисляются недостающие поля, итог `BLOCKED_AWAITING_INTEGRATION`, ни один критик не объявлен прошедшим.

`success` — статус **технического исполнения Code/Merge в n8n**, а не качества сцены. Пользователь/веб-приложение должны смотреть `status` внутри результата; не трактовать успешное выполнение workflow как одобрение.

## Строгие требования к будущей веб-интеграции (Codex)

1. FastAPI остаётся источником истины, создаёт `task_id`, `project_id`, `artifact_id`, `artifact_revision`, `approved_brief`, `canon_revision`, `bar_revision`, `benchmark_ref`; полномочия approval проверяет **на сервере**, а не из текста.
2. Подключить защищённый workflow trigger/callback и протокол версий, идемпотентную запись результатов. В этом черновике trigger только manual.
3. Изолировать критиков на практике: новый контекст для каждой отдельной проверочной сессии без builder history, chain-of-thought, без результатов других критиков. Данные пакетов уже разделены, но живой вызов ещё не реализован.
4. Вместо блокирующих шлюзов A6/A7 сделать отдельные вызовы соответствующих сохранённых n8n Agents с профильными Skills, но только после авторизации и с контролем реальной модели/стоимости; перед вводом в продакшен проверить точные параметры и инструменты. `A6=nkmWNxBdJcFEXSMF`; `A7=NRWXr5AY2MXAFhcH`.
5. Для A8 `s7IIGiioapxre90t` создать отдельный trusted approval + session cost cap и media inspector: видео→таймкоды/кадры, звук→доступный аудиоматериал/транскрипт, benchmark/bar. До этого **НЕ запускать Opus и не выводить PASS**.
6. Агрегатор: при 3 `PASS` результат `AWAITING_OWNER_APPROVAL`, при любом `FAIL` — `CHANGES_REQUESTED` с одной главной проблемой и возвратом автору этапа; `BLOCKED` не является PASS. При ошибке JSON, дублировании роли, разных artifact revisions — `BLOCKED_INVALID_REVIEW_SET`.
7. Не запускать повторную петлю в n8n автоматически до появления дедупликации `review_id/task_id/round/artifact_revision` и согласованных финансовых лимитов. Не подключать к активному workflow `SrlmcCnwPrOZVnFH` до smoke-тестов.
8. Не пересылать большие файлы и секреты в workflow: библиотека материалов — в FastAPI/Storage, n8n получает проверенные ID/подписанные ссылки с коротким TTL.
9. Использовать `skills/gremovod-review-*` и `skills/gremovod-qa-producer-loop` как источник инструкций. Sync через GitHub пока не автоматический.
10. Добавить **тест статусов** для текста, кадра, видеоматериала: отсутствие benchmark/render, mismatch revision, недоверенный expert approval, выпадение одного критика, строгий запрет ложного `PASS`.

## Что остаётся недоделанным

- Нет автоматических вызовов A6/A7/A8 (только подготовка пакетов и агрегирование BLOCKED).
- Нет технического approval/cost cap/лимита итераций; A8 выключен у A0.
- Нет записи статусов в Web/FastAPI, нет отдельного сохранения history/round в production database.
- Нет экспертизы видео/аудио, только ожидание media inspector.
- Нет webhook-триггера, отсутствует возможность запустить с веб-сайта.

## Evidence scopes — обновление 19.10.2026

Тот же draft workflow `nh3ARcl4XPW6RHqs` обновлён без добавления внешних узлов: `Проверка входа` требует `requested_scopes` и `artifact_scope`, допускает TEXT QA без отсутствующего для текстовой задачи визуального `bar.md`; каждый из 3 независимых шлюзов возвращает `checked_scopes=[]`, `scope_results` c BLOCKED и не делает ложных утверждений о просмотре. Агрегатор требует проверяемого evidence type/source и trusted evidence confirmation перед PASS/FAIL; отсутствие доказательства → BLOCKED. **Это проверка структуры, не настоящая рецензия.**

Офлайн execution IDs 9, 10, 11, 12 — все technical success, `all_passed=false`: (9) только TEXT, (10) поддельный approved_expert_model, псевдоURL рендера и VIDEO, (11) IMAGE только по текстовому описанию, (12) повтор текстового теста после усиления проверки. Без LLM/API/Opus. Источник: [QA_EVIDENCE_POLICY.md](QA_EVIDENCE_POLICY.md), JSON контракт: [qa-reviewer-output-v1.schema.json](contracts/qa-reviewer-output-v1.schema.json).

Не включать реальный reviewer output в агрегатор без независимого серверного evidence verifier и authenticated/approved context, иначе поле `evidence_verified_by_backend` в сырых данных модели может быть подделано.

## Разделение TEXT_PRECHECK и FINAL_MEDIA

Теперь workflow `nh3ARcl4XPW6RHqs` в ручном безопасном draft поддерживает `review_phase` и возвращает `required_reviewers`: `TEXT_PRECHECK → REVIEW-REQ + REVIEW-SYSTEM`, `FINAL_MEDIA → REVIEW-REQ + REVIEW-SYSTEM + REVIEW-CRAFT`. При TEXT_PRECHECK A8 получает `not_applicable_to_this_phase=true` и не вызывается. Самих живых A6/A7 критиков внутри workflow пока тоже нет, поэтому все тех. проверки остаются BLOCKED. Даже будущий положительный текстовый результат не может установить `final_release_approved=true`.

Executions 13–17: правильный текст → TEXT_PRECHECK и BLOCKED_TEXT_REVIEW_NOT_CONNECTED; финальное видео → FINAL_MEDIA и BLOCKED_AWAITING_INTEGRATION; попытка провести видео как текст → BLOCKED_INVALID_INPUT. Никаких платных вызовов. Подробнее: [QA_TEXT_PREFLIGHT.md](QA_TEXT_PREFLIGHT.md). Это обновление сохранено в [snapshot](workflows/qa-orchestrator.safe-draft.snapshot.json).
