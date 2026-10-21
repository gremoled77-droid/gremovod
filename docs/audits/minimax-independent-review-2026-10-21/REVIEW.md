# Итоговый отчёт независимого ревью GA-01 / GA-04 / GA-05 / GA-03

Дата: 2026-10-21, время в Europe/Moscow. Первое итоговое чтение HEAD: 16:15:03 МСК; повторное чтение перед упаковкой подтвердило те же SHA. Актуальный снимок и CI IDs: [evidence/reviewed_refs.json](evidence/reviewed_refs.json).

Режим исходного ревью — READ-ONLY. Временные Git/SQLite/media-фикстуры разрешены. В этом PR добавляются только документы и проверочные файлы. Нет изменений приложения, существующих тестов, зависимостей, workflow, production-данных, канона или веток MiniMax. Нет merge, force-push, платных запросов и автоматических поручений агентам.

## 1. База и доказательства

Репозиторий: `gremoled77-droid/gremovod`.

Реальная база всех четырёх PR: `mavis/work@57cac59ca790d380d8e68f2f6db82674ca142e92`.

| Задача / PR | Проверенный HEAD | Файлов в diff | Вердикт |
|---|---|---:|---|
| GA-01 / #58 | `5c47ace69477d2793deba1155b1d5df91a55e46d` | 3 | CHANGES_REQUESTED |
| GA-04 / #62 | `08213fdc271dcef7f203e7cedb866b2588e55257` | 14 | CHANGES_REQUESTED |
| GA-05 / #63 | `7524c677551c7ba3f34b8ce40a1a655895a88ff5` | 5 | CHANGES_REQUESTED |
| GA-03 / #64 | `0dd0c22d6d87e9ebcc00af550a48b1d605c98bdd` | 1 Markdown | CHANGES_REQUESTED как план; runtime BLOCKED_NOT_IMPLEMENTED |

Ни одному PR не присвоен ACCEPT. Новые находки ниже оценены P1/P2; нового безусловного P0 не установлено. Исходный денежный P0 нельзя считать закрытым: остаются блокирующие денежные P1 и не принята миграция старых записей.

Прочитаны AGENTS.md, CLAUDE.md, AGENT_BUILD_MANUAL.md, STATUS.md, handoff/review packet, отчёты #54 и решения #55. Старый STATUS не использовался как доказательство отсутствия уже реализованного кода. Сравнение — с указанной реальной базой, не с main.

Фактическая рабочая Studio: `C:/AI_Workflow_Studio`, ветка `fix/astra-aider-20261020@40ca333`, dirty; AGENTS называет корень main, но фактическую ветку аудит не исправлял. Исходные worktree/данные/процессы не изменялись. Проверка велась в `C:/Users/BLOWKA/aider-test/outputs/minimax-review-20261021`.

## 2. GA-01 / PR #58

**Вердикт: CHANGES_REQUESTED.** Денежная модель заметно улучшена, но ниже воспроизводимые блокеры.

### Подтверждено

- Разделены подтверждённые затраты и неопределённый остаток агентского прогона.
- Missing/negative/bool/string/слишком большой usage не подтверждает $0; резерв сохраняется.
- Обычный достоверный usage учитывается полностью, включая overrun выше оценки.
- Повторный request_id не повторяет submit; timeout/неразбираемый ответ без no-charge evidence удерживает резерв.
- Старый P1 к `9b6a610` о стирании оплаченных ролей после reconcile **исправлен по существу**: failed снимает только неизвестную часть, повторная сверка → 409. GitHub thread остаётся открытым/outdated; он автоматически не закрывался.
- Новые записи совместимы с текущим spend_ledger; общего второго ledger не создано.

### GA01-R1 · P1 · Противоречивый usage ошибочно доказывает отсутствие оплаты

Источник: `backend/llm_guard.py:733-742`, особенно `:739`; ветка разбора ответа `:831-839`; денежная task-ветка также использует `_not_charged`.

Воспроизведение: один mock-ответ без разбираемого content, с `usage={prompt_tokens:120,completion_tokens:40,total_tokens:0}`. POST `/api/llm/chat` → HTTP 502; mock submit count=1; ledger → `status=failed`, `usd=0`, резерв освобождён. `total_tokens=0` проверяется раньше согласованности остальных счётчиков.

Ожидание: противоречивый usage не является no-charge evidence. Удержать `submission_unknown` и безопасный резерв; использовать одну согласованную проверку счётчиков в chat/task. Тесты: сохранённая `contradictory_usage_parse_failure` и `Ga01Runtime.test_contradictory_zero_total_does_not_release_money`.

### GA01-R2 · P1 · Сбой backfill оставляет необратимо неполную миграцию

Источник: `backend/llm_guard.py:556-564`, `confirmed_from_tokens` в `:252-266`; последствия reconcile `:705-709`.

Воспроизведение: временная старая SQLite; добавить confirmed_usd; внедрить `sqlite3.OperationalError` при восстановлении подтверждённой части; перезапустить setup. ALTER остаётся, UPDATE откатываются, `confirmed_usd=NULL` во всех старых строках. Следующий startup видит колонку и пропускает backfill. Тот же дефект получен со строковым старым счётчиком `bad` → TypeError.

Подтверждённое при последующей сверке может трактоваться как 0. Нужны атомарная миграция, повторяемое восстановление незавершённого backfill и валидация старых счётчиков без падения startup. Нормальный upgrade/reopen без внедрённой ошибки проходит.

Тесты: `legacy_migration_normal/invalid/fault`; класс `Ga01Migration`.

### GA01-R3 · P1 · Отрицательные расходы старой базы продолжают уменьшать бюджет

Источник: `backend/llm_guard.py:560`; суммирование `backend/spend_ledger.py:88-90`.

Воспроизведение: старая запись `done / usd=-0.14 / tokens=(-1000000,-1000000)`, допустимая при исходной ошибке, плюс положительные обязательства $0.23. После upgrade остаётся `usd=-0.14`, добавляется `confirmed_usd=-0.14`; `spent()` → $0.09.

Это наследуемый дефект данных, не новая негативная стоимость обычного вызова на HEAD #58. Тем не менее upgrade не обезвреживает данные исходного P0. Нужны preflight и явная политика недостоверных старых строк: они не могут уменьшать доступный бюджет; не выдавать неизвестный исторический расход за подтверждённый ноль. Реальную SQLite не исправлять без отдельного утверждения плана.

Тест: `Ga01Migration.test_legacy_negative_spend_cannot_lower_combined_budget`.

### GA01-R4 · P2 · Ручная сверка и summary расходятся в confirmed/unknown

Источник: `backend/llm_guard.py:711-728`, `summary :214-222`.

Воспроизведение: две роли подтверждают $0.000014, одна без usage; сверить её как `done/unconfirmed_usd=0.001`. Ответ: `status=done,usd=0.001014,confirmed_usd=0.000014,unknown_usd=0.001`. Summary: `unknown_calls=0,unknown_usd=0`, confirmed остаётся $0.000014. Общая сумма сохраняется, но разбивка недостоверна.

Ожидание: после явной ручной фиксации факта confirmed отражает всю подтверждённую сумму; неизвестного остатка нет. Сохранённый тест автора ожидает старое confirmed, поэтому изменить также regression-ожидание, не только ответ API.

Тест: `Ga01Runtime.test_manual_settlement_reports_the_whole_confirmed_fact`.

### GA01-R5 · P2 · Ветка nonfinite price падает при построении причины

Источник: `backend/llm_guard.py:399-416`.

Воспроизведение: корректные токены, price_in=NaN. actual_cost отвергает сумму, но usage_problem возвращает None; конкатенация причины в :416 вызывает TypeError. Это защитная ветка с синтетически повреждённой ценой, не доказательство NaN в текущем реестре. Ожидание: `submission_unknown`, резерв и конкретная причина без аварии.

### Что выполнено и что остаётся заявлением автора

Независимо: 82 профильных pytest PASS, в том числе все 30 тестов backend/test_llm_settlement.py; дополнительные пробы выше; совместно 530 backend PASS / 26 subtests PASS. Старый PR body содержит 20 тестов и старый HEAD — числа не принимались как текущая проверка.

Task-reserve INSERT **уже исправлен** явными columns в `llm_guard.py:450`, несмотря на старый текст PR. Однако настоящий POST `/api/llm/tasks` без monkeypatch падает на `task_identity` (`:606`); submit count=0. `task_request_id` также отсутствует. GA-02 не выполнена; тесты с подменой helpers/резерва не доказывают endpoint lifecycle.

MiniMax: R1–R5, migration/reopen regression, актуализировать handoff. Владелец: утвердить порядок разбора старых недостоверных расходов до рабочей миграции. Округление до 6 знаков — известное наследуемое ограничение, отдельно оценить точность; глобальная смена тарифов/точности этим PR не поручается.

## 3. GA-04 / PR #62

**Вердикт: CHANGES_REQUESTED.** Восемь успешных jobs проверены по GitHub API и полным логам, но защита scope не является доверенной границей.

### GA04-R1 · P1 · PR может изменить проверяющий код и пройти scope guard

Источник: `.github/workflows/agent-scope-guard.yml:21-31`; `tools/check_agent_scope.py:144-168,193-215`.

Временный Git fixture: базовый commit уже содержит манифест; ветка `minimax/ga-05-probe` меняет запрещённый backend/main.py и сам tools/check_agent_scope.py, добавляя return [] в forbidden_files. Без изменения базового манифеста checker из head возвращает `AGENT_SCOPE: role=task:ga-05, changed=2, forbidden=0`, exit 0.

Чтение manifest из base полезно, но недостаточно: проверяющий код/импортируемые зависимости тоже должны быть доверенными. Bootstrap на base без манифеста дополнительно проверяется по собственной декларации PR и не является независимой защитой. Изменения самого workflow требуют защищённого ревью; нельзя просто перенести head-код под привилегированный pull_request_target.

Фикстура не меняет настоящие ветки. Она воспроизводит текущую команду workflow. После изменения архитектуры trusted gate MiniMax должен обновить эту end-to-end фикстуру, чтобы она запускала новый доверенный entrypoint, а не обходила его прямым вызовом старого head-script.

### GA04-R2 · P2 · Изменение CI/проверяющего инструмента может не запустить тяжёлую проверку

Источник: `.github/workflows/studio-offline-ci.yml:18-32`.

Проверена статическая матрица простых glob-patterns: backend/main.py, llm_guard.py, character_voice.py, spend_ledger.py, frontend/src/StageSummary.tsx → matched; docs-only → skipped. Но изменение только самого studio-offline-ci.yml или tools/check_agent_scope.py также skipped. Включить соответствующие инфраструктурные пути в retest. Новые remote PR для path-filter проб не создавались.

### GA04-R3 · P2 · Handoff и заявления о проверке схемы неточны

Источник: `backend/CI.md:13-18`, `docs/audits/ga-04-studio-offline-ci.md`, `tools/check_ci_contracts.py:68-91`.

CI.md называет media-job информационным, текущий YAML делает его блокирующим. В конце handoff осталась рекомендация job-level path filters, хотя актуальный workflow использует trigger-level paths. 487 backend в реальных логах — 455 unit + 32 media, не 487 unit плюс media. Локальная ручная таблица допустимых YAML-ключей/условий не является полной реализацией схемы Actions.

### Что подтверждено

- GitHub: offline run 39600260621, contracts 39600260691, scope 39600260706, coordination 39600260836 — success; все 8 job IDs в JSON.
- Логи: 455 backend unit + 32 media; 120 frontend PASS; TypeScript/Vite build success; 63 tool tests; 32 coordination/scope tests.
- Локально: 63 tool tests PASS / 7 subtests PASS. Первый архивный запуск без origin/mavis/work дал инфраструктурную ошибку одного repository-diff теста; после отдельного git checkout/ref весь набор прошёл. Эта первая ошибка не приписана продукту.
- contents:read, таймауты, нет repository secrets или paid commands в проверенном YAML; синтетический secret обнаруживается, значение в диагностике не печатается.
- В прочитанных 8 job-логах не обнаружены проверенные Google/GitHub/Anthropic credential formats. Это не универсальный секрет-аудит.
- Нормальные scope allow/deny, общие запреты canon/skills/docs-specs/AGENTS и соответствующие legacy-ветки покрыты штатными тестами.

**CI успешен, branch protection/required checks владельцем не утверждены (D7).** Effective settings сейчас не подтверждались. Другой always-run workflow не делает path-skipped heavy checks автоматически успешными или обязательными.

Наблюдение о Google: в трёх docs/official-prompts HTML найдено 20 совпадений формата, 10 разных строк. Они не печатались. Утверждение автора «действующие ключи» не проверено, принадлежность/доступность не установлены; не поручать владельцу ротацию чужих ключей как доказанно необходимых. История не переписывалась.

MiniMax: trusted checker, retest paths, точный handoff. Владелец: отдельное D7 о branch/ruleset protection и списке required checks. Исправления settings не входят в этот пакет.

## 4. GA-05 / PR #63

**Вердикт: CHANGES_REQUESTED.** Bare ASGI обход changing-XFF исправлен; deployment-stack требует исправления/проверки до remote.

### GA05-R1 · P1 · Uvicorn уже подменяет peer до client_ip/is_loopback

Источник: `Dockerfile:21` (существовавший wildcard forwarded-allow-ips), `backend/remote_access.py:155-161,173-178`.

Временная ASGI-проба реальным ProxyHeadersMiddleware из установленного Uvicorn 0.54.0:

| Сценарий | Без middleware | С wildcard из Dockerfile |
|---|---|---|
| 7 неверных паролей, XFF меняется | 401×5,429×2 | 401×7 |
| Внешний peer, loopback Host/XFF, GET /api/session | 401 | 200 |
| Затем /api/projects с полученной тестовой сессией | 401 | 200 |

Условие: атакующий может напрямую обратиться к backend с такими заголовками. Compose не публикует порт Studio на host; обход публичного Caddy этой пробой **не доказан**. Это pre-existing deployment condition, не новая регрессия пароля. Но заявления «по умолчанию request.client — непосредственный peer» недостаточно для описанного server stack.

Нужен один согласованный владелец обработки forwarded headers: отключить предварительную подмену либо ограничить и проверить её доверие вместе с приложением. Не открывать backend наружу. Добавить тест фактической Docker-команды; packaged regression извлекает настройки CMD, а исторический reproduce сохраняет wildcard-пробу.

### GA05-R2 · P1 при нескольких hops · Пропускаемые посредники не проверяются

Источник: `backend/remote_access.py:132-170`.

Непосредственный peer 10.0.0.2 доверен, hops=2, XFF=`203.0.113.7,198.51.100.20` → выбран первый адрес, хотя второй не доверенный proxy. Это даёт подставной identity при append-прокси и несоответствии заявленной цепочки. Список двух альтернативных proxy/CIDR не означает два последовательных hops; default len(trusted_proxies) такую неоднозначность создаёт.

Нужна проверка пропускаемых посредников/явная fail-closed topology. Поддельный префикс не должен выбирать identity при неверной цепочке. Реальная deployment-конфигурация не читалась.

### GA05-R3 · P2 · Невалидные части цепочки игнорируются, IPv6 suffix не проверяется

Источник: `backend/remote_access.py:100-101,163-170`.

XFF `203.0.113.7,invalid,198.51.100.20`, hops=2 → invalid удаляется, выбирается 203.0.113.7. `[2001:db8::7]:bad`, `:999999` и `]trailing` принимаются как IP 2001:db8::7. Ожидание: отвергнуть malformed элемент/цепочку и безопасно использовать peer, а не менять позиции или принимать некорректный порт.

### Результаты и границы

20 локальных remote_access tests PASS: direct IPv4/IPv6/trusted proxy, Host, Origin, cookie и сессии. Полный backend совместно 530 PASS. На HEAD #63 GitHub показывает только skipped scope-check, полного CI нет. Заявленный автором full run не подменяет проверку текущего совместного candidate.

MiniMax: R1–R3, stack-level regression, точный trust contract. Владелец: до remote подтвердить фактическую topology, адреса/hops и недоступность backend извне. Локальный offline-пилот GA-05 не блокирует.

## 5. GA-03 / PR #64 — архитектурный план

**Вердикт: CHANGES_REQUESTED как документ. Runtime BLOCKED_NOT_IMPLEMENTED.** В PR изменён только docs/audits/ga-03-release-gate.md, 348 строк. N1–N15 описаны, но не выполнены как release-gate tests.

Правильно: одна Studio SQLite, переиспользование N34/master_facts/sha256, server-owned state, SHA в решении, история APPROVED/REJECTED, без обязательных трёх платных критиков и второго QA engine.

### GA03-R1 · P1 · N35 не включён в обязательные условия

Источник плана: `docs/audits/ga-03-release-gate.md:81,123-129,207-215`; текущий контракт `backend/qa_reviews.py:46-98`.

Пять инвариантов требуют N34+approval, но не processing_rights и покрытия обязательных модальностей из N35. По D3 рекомендовано обязательное N35 `CONFIRMED` для того же master SHA и выбранного snapshot. Это не равно ожиданию платных critic verdicts. D3 не содержит буквального статуса CONFIRMED; это рекомендация реализации его существующего N34/N35-контракта, требующая явного закрепления владельцем.

### GA03-R2 · P1 · REJECTED недостижим при проваленном QC

Источник плана: `:167-180`.

Единый маршрут для APPROVED/REJECTED требует PASS_TECHNICAL. Сценарий QC FAIL/BLOCKED → владелец отклоняет → предусловие не даёт записать отказ. QC/свежесть должны ограничивать APPROVED; REJECTED должен сохраняться после проверки owner-сессии и принадлежности артефакта, в том числе при проблемном QC/файле, с определённым якорем решения.

### GA03-R3 · P1 · API/UI путь не доведён до действий владельца

Источник плана: `:250-256`; текущие `backend/release_artifacts.py:13-27,173`, `frontend/src/StageSummary.tsx:121-170`.

Счётчик и подпись не заменяют «Утвердить / Отклонить», обработку 409 и обновление read model. Поле gate нужно включить в backend response-model ReleaseArtifact: изменение одного artifact_record фильтруется response_model. Backend route под /api/projects остаётся только для owner-сессии; machine-token отрицательный тест обязателен.

### GA03-R4 · P2 · Cosmetic save отменяет approval

Источник плана: `:129,238-240,325-331`; projects.revision растёт при обновлении state/title.

Рекомендация пилоту: решение относится к неизменяемому release snapshot, SHA мастера и revision импорта. Косметическое сохранение проекта не отменяет приёмку; существенное изменение материалов/канона требует нового snapshot/решения. Просто убрать текущую revision без другого существенного якоря недостаточно.

Минимум: одна таблица решений, один read model, один endpoint с раздельными guards APPROVED/REJECTED, существующие N34/N35, две UI-команды. Для одного владельца достаточно серверной owner-session attribution, без новой системы пользователей. Старые ready imports сохраняются; отсутствие approval не делает их одобренными, даже если QC уже был.

Тесты к N1–N15 дополнить: N35 PARTIAL/BLOCKED/stale SHA, REJECTED при FAIL/отсутствующем файле, cosmetic save, существенный snapshot change, наличие gate в реальном HTTP JSON, API запрет machine-token. Новые runtime/gate tests в этом PR намеренно не симулируются.

MiniMax: уточнить план до runtime. Владелец: подтвердить обязательность N35 CONFIRMED, snapshot/cosmetic правило и принятие решений локальной owner-сессией. Не открывать заново D1–D4 и не требовать paid critics.

## 6. Совместимость и готовность

GA-04+GA-01 и GA-04+GA-05 не пересекаются по изменённым файлам. Из точных snapshot создана временная combined-копия без merge: архив GA-04 плюс непересекающиеся изменения GA-01/GA-05. **530 backend PASS, 26 subtests PASS, 219.78s.** Профильные тесты входят в это число и не суммируются повторно.

Свежие SQLite/модули совместимы. Upgrade/recovery старой базы не принят по R2/R3. GA-02 должна опираться на принятую версию GA-01, явные INSERT columns и confirmed_usd; не возвращать устаревший резерв. До неё paid Task API не готов, хотя один SQL-баг уже закрыт.

GA-04 покрывает предполагаемые файлы GA-03, включая backend/release_gate.py и frontend/src/releaseGate.test.mjs. Другой путь теста или отдельный GA-02 lifecycle test нужно заранее согласовать в allowlist; не ослаблять guard в том же PR задачи. Git/code conflict будущего ещё не написанного runtime подтвердить невозможно.

**Offline-бета: NO GO до денежных исправлений, GA-02, реализации GA-03 и browser/MOCK E2E.** Изолированная демонстрация с mock data — CONDITIONAL GO без заявления о финальном выпуске.

**Paid-бета: NO GO.** Дополнительно нужны конкретный master/snapshot D5, human/CapCut/N34/N35 приёмка, проверенные provider/billing contracts, безопасный upgrade/restore и отдельное разрешение на конкретный paid smoke. Для remote — GA-05/topology; для n8n — отдельный D6, но Cloud по D4 локальный пилот не блокирует. D7 отдельно определяет enforcement GitHub checks.

Не выполнены: browser/mobile E2E, живой Caddy, реальный CapCut render/master, production backup/restore, live n8n, provider billing. Локально frontend build заново не запускался: проверены GitHub logs на SHA GA-04. Никакое это ограничение не скрыто зелёным MOCK.

Порядок работ, точные задачи и E2E — [MINIMAX_HANDOFF.md](MINIMAX_HANDOFF.md). Проверки и воспроизведения — [TEST_RESULTS.md](TEST_RESULTS.md).
