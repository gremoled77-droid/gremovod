# Деньги и безопасность

Снимок: `57cac59ca790d380d8e68f2f6db82674ca142e92`. Только временные данные, сетевые вызовы провайдеров подменены. Никаких реальных credentials не использовано.

## Что действительно улучшилось

Общий счётчик уже включает media approvals, LLM, P0 и n8n: [backend/spend_ledger.py:147](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/spend_ledger.py#L147). `security.budget_state` делегирует ему ([backend/security.py:123](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/security.py#L123)); check/reserve в media использует `BEGIN IMMEDIATE` ([backend/main.py:557](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L557)), LLM — [backend/llm_guard.py:609](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/llm_guard.py#L609). `test_money_boundary`, `test_unified_budget`, `test_n8n_spend` прошли в текущем прогоне. Старую проблему MM-002 «LLM не видит общий media-бюджет» нельзя заново ставить на реализацию в этой базе.

### Инвентарь исполняемых путей

| Путь | Проверенный участок | Фактическая граница / ограничение |
|---|---|---|
| Image/video PiAPI | [backend/main.py:538](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L538) → [backend/main.py:177](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L177) | quote + approval + jobs/approvals reserve; duplicate request_id возвращает прежний job |
| Image/video KIE | [backend/main.py:565](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L565) → [backend/kie.py:17](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/kie.py#L17) | caller проверяет ledger, транспорт проверяет лишь наличие spend; сам transport не доказан универсальной денежной границей |
| Общий LLM/chat | [backend/llm_guard.py:625](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/llm_guard.py#L625) | signed quote, reserve, idempotency; неверный usage не валидируется полностью |
| Compose, Story Plan, Producer | [backend/main.py:395](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L395), [backend/story_plan.py:226](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/story_plan.py#L226), [backend/producer_stage.py:416](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/producer_stage.py#L416) | делегируют существующему LLM-контуру; реальные paid ответы NOT_RUN |
| Agents | [backend/main.py:792](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L792) | один резерв на 3 последовательных вызова; settlement уязвим при неполном usage |
| MiniMax text tasks | [backend/llm_guard.py:438](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/llm_guard.py#L438) | отдельный prepare/permit/execute lifecycle сломан; см. P1-01 |
| Fish / ElevenLabs TTS | [backend/character_voice.py:129](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/character_voice.py#L129) | собственные quote/check/reserve и прямой stream POST; полного единообразия dispatch нет |
| n8n | [backend/n8n_spend.py:195](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/n8n_spend.py#L195) | scoped machine token, role ceiling, общий резерв; факт сообщает вызывающий, workflow-fragment не доказывает его применение в Cloud |
| Старый /api/chat | [backend/main.py:232](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L232) | закрыт; это не действующий обход OpenAI |

`scripts/p0_paid_dispatch_audit.py` — эвристический текстовый инвентарь, не доказательство полноты: ищет названия/hosts, включая неисполняемые упоминания и тесты. Старое «55 мест, за шлюзом 0» в P0_ASTRA_STATUS относится к прежней базе. Прямой OpenAI-вызов старой версии agent_completion в кандидатной ветке уже заменён provider registry.

## P0-01 — недостоверный учёт LLM — P0 BLOCKER

**Подтверждено без API:**

1. `/api/agents/estimate`: цена 0.000843 USD для синтетического brief. Три mock-ответа `('Synthetic result', {})`. `/api/agents/run` вернул 200, mock вызван 3 раза, записанный факт **0.0**. Причина: `usage.get(...) or 0` и безусловный `done`: [backend/main.py:829](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/main.py#L829).
2. `/api/llm/chat` с правильной quote и mock-ответом `prompt_tokens=-1000000, completion_tokens=-1000000` вернул 200, `cost_usd=-0.14`. Причина: проверяется только isinstance(int), а не неотрицательность и исключение bool: [backend/llm_guard.py:678](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/llm_guard.py#L678). Доверяется ответу внешней системы; отрицательное значение снижает общий бюджетный итог.
3. **Условный дефект task-пути:** после синтетического корректного резерва 0.10 USD, с in-memory заглушкой недостающего helper и reserve-helper, `execute_minimax_task` при TimeoutError записал `failed, usd=0, estimated_usd=0.1`. [backend/llm_guard.py:377](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/llm_guard.py#L377). Непосредственно через публичный lifecycle сейчас не достижим из-за P1-01; нельзя заявлять, что именно этот task-сценарий уже списал реальные деньги.

**Исправление:** один проверенный расчёт settlement в существующем модуле, валидные неотрицательные int (не bool), конечная сумма; отсутствие/повреждение usage не доказывает $0; сохранять резерв/UNKNOWN с причиной; достоверный перерасход учитывать полностью. Все LLM callers должны соблюдать это правило. Платёжные повторы после неопределённости — только после доказательной сверки.

**Не дублировать MM-001:** `f9f810f` уже содержит valid_tokens/actual_cost для старого guarded_chat. Его можно использовать как источник небольшого исправления после адаптации к нынешнему реестру, статусам и task-протоколу. Прямое копирование старого файла уничтожит новую функциональность.

## P1-01 — task lifecycle BROKEN

[backend/llm_guard.py:463](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/llm_guard.py#L463), [backend/llm_guard.py:471](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/llm_guard.py#L471), [backend/llm_guard.py:327](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/llm_guard.py#L327) вызывают `task_identity` / `task_request_id`, определений в этом snapshot нет. Настоящий POST prepare на временной базе: **NameError: task_identity is not defined** после записи task. Это не ошибка мок-провайдера.

Чтобы проверить следующий слой, только внутри тестового процесса подставлен helper и подготовлен signed permit. Execute упал: **table llm_calls has 11 columns but 10 values were supplied**, provider calls = 0. Сравнить INSERT без списка столбцов ([backend/llm_guard.py:337](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/llm_guard.py#L337)) с startup ALTER note ([backend/llm_guard.py:426](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/llm_guard.py#L426)). После исправления этих ошибок обязателен retest P0-01: нельзя открыть скрытый unsafe-handler.

В незакоммиченном локальном `C:/AI_Workflow_Studio/backend/llm_guard.py` найдены определения helpers на строках 237/250. Они не входят в кандидатный SHA и не приняты/не тестировались здесь. Не потерять и не копировать весь файл.

## P1-02 — X-Forwarded-For обходит throttling

[backend/remote_access.py:89](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/remote_access.py#L89) берёт первый XFF без проверки trusted peer. Login использует этот ключ в `_fails`: [backend/remote_access.py:145](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/remote_access.py#L145). На временном TestClient с синтетической remote-конфигурацией семь неверных паролей, каждый с новым XFF, дали **[401,401,401,401,401,401,401]**, вместо ограничения после MAX_FAILS=5.

Это **не доказанный обход аутентификации**. Условие эксплуатации: внешний клиент может донести произвольный XFF до backend (прямое подключение или неверно настроенный proxy). Реальная топология NOT_RUN. В `Caddyfile` reverse_proxy есть, но его фактическое развёртывание не подтверждено. Не применять к loopback проверке старый дефект автоматически: `is_loopback` здесь уже проверяет request.client.host ([backend/remote_access.py:94](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/remote_access.py#L94)).

## Дополнительные границы

- Auth: Host/Origin/session gate + scoped machine-token prefix allowlist есть; отрицательные auth-тесты прошли. [backend/security.py:162](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/security.py#L162), [backend/service_auth.py:23](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/service_auth.py#L23). Общая owner/helper RBAC на всех файловых маршрутах не принята.
- n8n settlement принимает `failed` и caller USD без provider evidence ([backend/n8n_spend.py:126](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/backend/n8n_spend.py#L126)). Это доверенная машинная зона, не доказательство фактической цены. Активация workflow требует отдельного evidence/owner-контракта; в этом аудите не объявлено новым эксплуатируемым P0.
- UNKNOWN: общий резерв удерживается в существующих LLM/media/P0 тестах; это не доказывает семантическую блокировку любого нового ID одной и той же операции во всех legacy-путях.
- SQLite factory: `main.connect` и P0 open_db ещё различаются. Тестовый запрет второй рабочей БД не равен доказанному глобальному filesystem/CI запрету.
- Backup/restore на рабочей SQLite, ACL/шифрование диска, fault recovery реального Windows-worker: **NOT_RUN**. Проверялись только временные SQLite и откаты в тестах.
- Цены: совпадение frontend/backend реестров проверено тестами; действительность тарифов у провайдеров **NOT_RUN**. Цифры в этом отчёте — результаты локального реестра, не актуальное коммерческое предложение.
