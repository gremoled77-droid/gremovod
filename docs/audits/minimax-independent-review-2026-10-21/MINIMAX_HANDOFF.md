# Передача MiniMax: адресные исправления после независимой приёмки

Это подготовленные задания, не автоматическое назначение. Публикация документа не разрешает paid API, merge, изменение main/mavis/work, канона, production SQLite или server deployment. Каждый последующий кодовый PR требует отдельного ограниченного поручения и повторной приёмки.

**Перед исполнением:** во время публикации #58 обновился до `c634c0c915a1afbf3d75df5bc897f75ef5b723ea`, который здесь NOT_REVIEWED. Сначала сравнить его с reviewed `5c47ace...` и повторить адресные regression tests; не реализовывать заново уже исправленные пункты. Исторические результаты/вердикт не переносить автоматически на новый SHA.

## 1. GA-01 — сначала деньги и upgrade

База задачи: принятые зависимости на зафиксированном SHA mavis/work; текущий reviewed head `5c47ace69477d2793deba1155b1d5df91a55e46d`. Не переносить целиком dirty llm_guard из рабочей Studio.

Допустимый минимальный объём: backend/llm_guard.py, backend/main.py только при необходимости общего settlement, backend/test_llm_settlement.py и согласованные existing money tests. Реестр/тарифы/UI/n8n/канон не менять.

| ID | Исправление | Критерий приёмки |
|---|---|---|
| GA01-R1 P1 | Согласованное no-charge evidence | total_tokens=0 не освобождает деньги при положительных/повреждённых остальных счётчиках; chat/task одинаковы |
| GA01-R2 P1 | Атомарная повторяемая миграция confirmed_usd | Fault после ALTER/backfill не оставляет пропущенное подтверждённое; следующий startup восстанавливает корректную схему и факт |
| GA01-R3 P1 | Preflight старых отрицательных/недостоверных расходов | Такие строки не уменьшают общий бюджет; неизвестное не выдаётся за $0; отдельный план применения к реальным данным |
| GA01-R4 P2 | Согласовать reconcile/summary | done после ручного подтверждения показывает полную confirmed сумму и unknown=0; повторный reconcile не списывает повторно |
| GA01-R5 P2 | Причина nonfinite cost | Невалидная цена возвращает unknown/reserve, без TypeError |

Повторить 82 профильных теста, дополнительные контракты из пакета, обе последовательности media/LLM budget, reopen, duplicate, concurrent reserve и запрет повторного submit после UNKNOWN. Старый P1 по `9b6a610` уже исправлен; его не реализовывать заново.

## 2. GA-04 — доверенная проверка и точность CI

Reviewed head `08213fdc271dcef7f203e7cedb866b2588e55257`. Область — существующие workflows/tools/CI-документы из GA-04, без runtime.

1. R1 P1: проверяющий код и его зависимости брать из доверенного base/pinned source. Adversarial fixture изменяет head-checker плюс запрещённый файл и обязана получать nonzero от **реального доверенного entrypoint**. Изменение самого workflow отдельно защищается процедурой/repository enforcement D7; не исполнять head-код под привилегированным pull_request_target.
2. R2 P2: изменение workflow и значимых CI-tools запускает требуемые проверки; docs-only честно не выдаёт full acceptance.
3. R3 P2: привести CI.md/handoff к YAML: media blocking, 455+32 backend, 63 tool tests, trigger-level paths; не называть ручной checker полной схемой Actions.

Проверить read-only permissions, отсутствие secrets/paid submit, fork без credentials, безопасную redaction, deliberate failing test и out-of-scope change на runner. Старые успешные jobs относятся к reviewed SHA; будущий SHA требует своего CI.

## 3. GA-05 — закрыть server-stack trust до remote

Reviewed head `7524c677551c7ba3f34b8ce40a1a655895a88ff5`.

Минимальная область: remote_access.py, test_remote_access.py, deployment-документация. Если для исправления R1 нужен Dockerfile/server command, **сначала согласовать расширение scope**: текущий allowlist GA-05 его не включает. Не менять production env и не открывать backend.

- R1 P1: определить один слой обработки forwarded headers, устранить wildcard-подмену недоверенного peer перед client_ip/is_loopback. Проверка должна брать реальную серверную конфигурацию, а не только bare ASGI.
- R2 P1: число альтернативных trusted addresses не определяет hops. Проверять пропускаемые посредники и закрыто обрабатывать несоответствие topology.
- R3 P2: не удалять malformed элементы, сдвигая цепочку; проверять весь bracketed IPv6/port/suffix.

DoD: changing-XFF → 429 после лимита; spoof loopback не выдаёт сессию; два реальных клиента имеют разные лимиты только через подтверждённый proxy; Host/Origin/cookie/session regressions зелёные. Проба прямого backend не равна доказательству обхода Caddy.

## 4. GA-03 — сначала исправить контракт плана

Reviewed document head `0dd0c22d6d87e9ebcc00af550a48b1d605c98bdd`; runtime в нём отсутствует.

Минимум реализации после утверждения:

- Одна таблица решений в текущей Studio SQLite, существующие N34 и N35, один серверный read model.
- Рекомендованные обязательные условия: master exists; N34 PASS_TECHNICAL по текущему SHA; N35 CONFIRMED по тому же master/snapshot, правам и обязательным модальностям; APPROVED владельца по тому же SHA/snapshot.
- APPROVED требует всех QC/integrity guards; REJECTED записывается и при FAIL/BLOCKED, с owner auth и project/artifact ownership. Последнее решение определяет результат; история сохраняется.
- Импорт — IMPORTED, техническая готовность — TECHNICAL_PASS, только явное действующее решение — OWNER_APPROVED. Старые ready rows не становятся одобренными автоматически.
- Snapshot выпуска и revision импорта сохраняются; cosmetic project save не отменяет решение, существенные изменения требуют новой приёмки. Конкретный content/snapshot anchor должен быть выбран, а не подразумеваться.
- gate включить в backend response-model и реальный HTTP JSON. UI: «Утвердить / Отклонить», причины блокировки, ожидаемый SHA, обработка 409 и повторное чтение.

Не строить второй QA engine, новый ledger или новую систему пользователей. Для текущего single-owner пилота достаточно серверной атрибуции локальной owner-сессии. Machine-token не может утверждать выпуск.

N1–N15 + positive/reopen дополнить N35 PARTIAL/BLOCKED/stale, REJECTED при FAIL/missing file, cosmetic save, существенный snapshot change, HTTP response-model и UI-командами. Платные критики не являются предусловием.

## 5. GA-02 — только после принятого GA-01

SQL reserve INSERT уже исправлен в актуальном GA-01. Не возвращать старый positional INSERT. Восстановить отсутствующие task_identity/task_request_id в существующем контракте.

Настоящие endpoints prepare → permit → execute без monkeypatch helpers/reserve: same request/spec replay, changed spec 409, permit expiry/revision conflict, double/concurrent execute, missing key, startup/reopened SQLite, stored result replay. Provider submit ≤1; timeout/parse failure не разрешает оплачиваемый retry. Отдельный lifecycle-test путь заранее внести в согласованный scope, если он отсутствует.

## 6. Решения владельца

Не переоткрывать D1–D4: база mavis/work; GA-01 перед GA-02; локальные QC/owner без обязательных paid critics; CapCut-пилот без блокера n8n Cloud.

Нужны конкретные решения:

1. Обработка старых недостоверных денежных записей и план безопасного upgrade/rollback на копии до production.
2. Закрепить N35 CONFIRMED и immutable release snapshot/cosmetic правило для GA-03; current local session как owner attribution.
3. D7: доверие к workflow/обязательные checks/защита веток. Не утверждать enforcement без чтения effective settings.
4. Для remote: фактическая proxy topology, trusted IP/hops и изоляция backend. Для реального пилота D5: master и утверждённый snapshot. D6 — отдельно перед live n8n.

## 7. Безопасный порядок интеграции — пока только предложение

После исправлений и независимой приёмки: GA-04 → GA-01 → GA-02; уточнение/реализация GA-03 → общий retest. GA-05 принять до remote; локальный pilot от него не зависит. Merge выполняется только после отдельного разрешения, по одной проверенной ветке, с новым фиксированным candidate SHA.

GA-04+GA-01 и GA-04+GA-05 не имеют текущих file overlaps; combined fresh-SQLite suite 530 PASS. Это не доказательство безопасного upgrade старой БД и не доказательство отсутствия конфликтов будущего GA-03 runtime.

## 8. Полный MOCK E2E после исправлений

Один candidate SHA, отдельные порты при необходимости (не 8000/5173), собственный временный STUDIO_DATA_DIR, только synthetic media, zero provider calls.

1. Project → согласованные mock refs/snapshot → Producer mock → StoryPlan preview/apply → board.
2. Mock image/video + audio import → общий бюджет media/LLM в обоих порядках; duplicate, timeout/UNKNOWN, reconcile, reopen.
3. Edit-list/CapCut export → synthetic MP4 → import → N34 → N35 → owner APPROVED по одному SHA/snapshot; reopen сохраняет решение.
4. Отказы: missing/changed master, stale QC/snapshot, N35 PARTIAL/BLOCKED, machine-token, REJECTED при FAIL, duplicate decision, cosmetic и существенная правка.
5. Browser desktop/mobile: переходы, следующий шаг, console/API, счётчики; backup/restore **копии** данных и совпадение hashes.

Затем настоящий выбранный владельцем D5 master: CapCut import/render, full decode/audio/sync, human canon/rights review, N34/N35/owner по одному SHA. Paid smoke — только после денежной приёмки и отдельного разрешения конкретного request/provider/model/цены/потолка; UNKNOWN не повторять.
