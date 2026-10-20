# QA Text Precheck → Final Media Review — staged QA handoff to Codex

Дата 19.10.2026. **Встроено только в неактивный черновой n8n workflow**, не в FastAPI, не опубликовано; модельные проверки через workflow НЕ вызываются, платных API-вызовов не было. Это новая детализация [QA_EVIDENCE_POLICY.md](QA_EVIDENCE_POLICY.md).

## Зачем два этапа

1. **TEXT_PRECHECK** — ранняя проверка сценария/текста до генерации кадров. Для неё **достаточно ролей A6 REVIEW-REQ и A7 REVIEW-SYSTEM**, A8 REVIEW-CRAFT **не требуется и не должен вызываться**. При этом положительный результат означает только успешную проверку текста, а не готовность ролика к выпуску.
2. **FINAL_MEDIA** — приёмка завершённого мультимодального материала. **Обязательны A6, A7 и A8**, реальное изображение/видео/звук, утверждённые источники, эталон/бар и отдельное финансовое разрешение на Opus. Изолированный контекст каждому критику. Отсутствующий/непросмотренный media scope возвращает BLOCKED.

## Контракт из GremoVOD Web/FastAPI в n8n (предложен, не реализован)

- `review_phase`: `TEXT_PRECHECK` либо `FINAL_MEDIA`. Значение устанавливает авторизованный **FastAPI**, а не модель, не пользовательский промпт и не само n8n.
- `artifact.kind='text'` + `requested_scopes=['TEXT']` — единственный допустимый режим `TEXT_PRECHECK`. Для финального видео нужны соответствующие запрошенные области, исходя из фактического задания, а не устаревшего тестового текста.
- Обязательные `task_id`, `project_id`, `artifact_id`, `artifact_revision`, `canon_revision`, `approved_requirements`, source text revision или media asset IDs, source provenance, утверждённость канона.
- Текстовые критики должны получать реальный **текст** через доверенный контекст, а не только `text_ref`. В нынешнем QA draft есть лишь `text_ref` — это ссылка, а не доказательство прочтения.
- Результат A6/A7 должен иметь чёткий `scope_results.TEXT` и реальные цитаты из предоставленного текста. `TEXT:PASS` не может стать `IMAGE:PASS` или `VIDEO:PASS`.
- В качестве подготовки для дальнейшей работы n8n должен передавать `required_reviewers`; последующие алгоритмы обязаны сверять task/revision/context/approval и быть идемпотентными. Финальный статус выпуска никогда не зависит только от `TEXT_PRECHECK`.
- Сырой результат AI по [JSON Schema](contracts/qa-reviewer-output-v1.schema.json) — **недоверенный**. FastAPI независимо проверяет доказательства, что настоящий media inspector открыл asset; `evidence_verified_by_backend=true` из payload AI или запроса клиента НЕДОСТАТОЧНО. Рекомендуется server-side receipt ID, связанный с project/task/artifact/revision/scope и проверенный в серверном хранилище, а не editable поле.
- При любом input error, несуществующем источнике, неутверждённом каноне или несовместимом `review_phase` → `BLOCKED_INVALID_INPUT`; никаких вызовов моделей/платных генераций.

## Подтверждённое текущее n8n (draft workflow `nh3ARcl4XPW6RHqs`)

7 узлов, manual trigger, никакого HTTP/LLM, активность `false`. На этапе входа определяется `review_phase`, явный текстовый режим разрешён только для text+TEXT. Три детерминированные Code-node ветки остаются; A8 для текста помечен `not_applicable_to_this_phase=true`, сам **не вызывается**. Итог:
- `TEXT_PRECHECK`: `required_reviewers=['REVIEW-REQ','REVIEW-SYSTEM']`; итог `BLOCKED_TEXT_REVIEW_NOT_CONNECTED` до настоящего A6/A7 API. `text_precheck_passed=false`.
- `FINAL_MEDIA`: `required_reviewers=['REVIEW-REQ','REVIEW-SYSTEM','REVIEW-CRAFT']`; без интеграции `BLOCKED_AWAITING_INTEGRATION`.
- Ошибка входа, например VIDEO с `TEXT_PRECHECK`, возвращает `BLOCKED_INVALID_INPUT`.
- `all_passed=false`, `final_release_approved=false` всегда до надёжного внешнего review и отдельного owner approval.
- Вердикты с невалидным scope/evidence или смешанными revision не позволяют заявить PASS; однако текущая Code-node проверка **не может подтверждать доверенность медиа сама по себе**. Блокирующие шлюзы намеренно не принимают реальные вердикты.

**Тесты без расходов:**
- executions **13/17**: text + TEXT ⇒ `TEXT_PRECHECK`, требуются только A6/A7, A8 неактуален, итог `BLOCKED_TEXT_REVIEW_NOT_CONNECTED`.
- execution **14**: video + TEXT/IMAGE/VIDEO ⇒ `FINAL_MEDIA`, все три обязательны, `BLOCKED_AWAITING_INTEGRATION`.
- executions **15/16**: video + `TEXT_PRECHECK` ⇒ ошибки входа, после усиления в 16 итог `BLOCKED_INVALID_INPUT` с причиной.
Все упомянутые executions успешно завершили **технический** Code-node тест; это не означает QA PASS.

## Работы Codex по этапам

1. **Не переделывать** уже реализованный sandbox `backend/automation.py` A2/stub. Добавить отдельную QA-модель (или отдельную строгую версию jobs schema) в feature branch, сверить с таблицами / claim-callback контрактом и ревизиями.
2. Implement `TEXT_PRECHECK`: получить актуальные *approved* requirements+canon+настоящий текст из FastAPI, проверить текстовую revision, создать два независимых reviewer runs/IDs и cost authorization для конкретных моделей. Реальная ошибка Haiku/Kie A6 ранее наблюдалась (internal error after 3 retries), поэтому отсутствие ответа → `BLOCKED` с диагностикой, не PASS.
3. Использовать **поддерживаемый** n8n механизм вызова saved Agents; устаревший node `messageAnAgent` помечен retired — не основывать новый production workflow на нём. A6/A7 сейчас доступны как saved subAgents A0, но это **не** подключение к безопасному QA Orchestrator.
4. Реализовать Server-side `review_phase` + receipt verifier / source provenance; сохранить текстовые доказательства, `checked_scope`, hash/revision, цену и JSON Schema validation; никогда не менять утверждённый канон по LLM output.
5. Для `FINAL_MEDIA` добавить asset inspector, фактические изображения/кадры с временными метками/звук, verified coverage и доверенную server-side expert model approval, затем подключить A8; без этого A8 всегда BLOCKED.
6. Проверить переход `TEXT_PRECHECK:PASS` → **только разрешение перехода к следующему производственному этапу**, а не `FINAL_MEDIA:PASS` или публикация. После реальной media-генерации — новый review по новым artifact revisions.
7. Все критики читают только изолированные пакеты; ни один AI не вправе сам выдать подтверждение, что он посмотрел изображение/видео, и тем самым обойти server-side receipt verifier.

## Границы проверки

- Синтетические цвета машины («жёлтый»/«красный») из предыдущего теста не являются каноном GremoVOD.
- `TEXT_PRECHECK` — два критика, `FINAL_MEDIA` — три. Это **две ступени одной петли**, а не две независимые базы или разные хранилища правил.
- Промежуточный положительный текстовый результат не может перевести продакшен в `released`. Авторское подтверждение нужно отдельно.

Снимок работающего черновика: [qa-orchestrator.safe-draft.snapshot.json](workflows/qa-orchestrator.safe-draft.snapshot.json).
