# GremoVOD — методичка: MiniMax -> KIE Argon, короткое ревью GitHub (2026-10-19)

**Статус:** SPEC / OFFLINE. Это инструкция MiniMax, а не включённая интеграция. Платных вызовов нет. Временный разработчик — MiniMax; независимый ревьюер — Gemini 4 Argon через KIE. Конечное решение — владелец. Передача Codex — 25 октября.

## 0. Что уже имеется

- [PR #22](https://github.com/gremoled77-droid/gremovod/pull/22): безопасный, неактивный ручной KIE Argon review; используйте код `tools/ai_review/argon_review.py` из `experiment/manual-argon-review-20261019`, а не создавайте вторую конкурирующую интеграцию.
- [PR #23](https://github.com/gremoled77-droid/gremovod/pull/23): SPEC пилота Aider/n8n/Git/Argon, не считать внедрением.
- [Issue #27](https://github.com/gremoled77-droid/gremovod/issues/27): контракт визуальной отчётности.
- [PR #29](https://github.com/gremoled77-droid/gremovod/pull/29): фактический MiniMax P0-код для проверки, базовая ветка `codex/p0-fixes-20261019`. Проверить актуальные SHA перед ревью. Из PR #29 нельзя отправлять весь diff одним запросом: он превышает пределы старого скрипта. Разбить на тематические review packets, но **не** посылать их автоматически все подряд.
- `main`, `C:\AI_Workflow_Studio`, рабочие SQLite, канон, медиа и KIE GPT-6 Sol Proxy v2 (порт 8767) не изменять.

## 1. Выбранная архитектура

```text
MiniMax Code (исполнитель; отдельный Git worktree/branch)
  -> локальные unit/lint/secret проверки -> commit + Draft PR
  -> build_review_packet.py (сжатый evidence packet, frozen SHA)
  -> review_gate.py (только серверная политика + ledger + approval)
  -> KIE Argon Chat API (1 текстовый запрос; НИКАКИХ tools)
  -> review-summary.json/md (ссылки и проблемы, привязка к SHA)
  -> Draft PR + n8n dashboard/status (будущий опциональный этап)
  -> MiniMax исправляет замечания БЕЗ автоматического нового вызова Argon
  -> решение владельца; никакого auto-merge
```

Не использовать Aider `--auto-test` для платных запросов. Не подвешивать неограниченный вызов HTTP Request Tool непосредственно к LLM-агенту. Контроль у обычного проверяемого Python-кода, не у системного промпта MiniMax.

## 2. KIE endpoint и схема одного обращения

Документация: https://docs.kie.ai/market/gemini/gemini-4-argon-openai

```http
POST https://api.kie.ai/gemini-4-argon-openai/v1/chat/completions
Authorization: Bearer <KIE_API_KEY_FROM_LOCAL_ENV>
Content-Type: application/json
```

Тело: `{"messages":[{"role":"system","content":"...review policy..."},{"role":"user","content":"...small immutable evidence packet..."}],"stream":false}`. **НЕ** задавать придуманный `model: "argon-model"`; текущий маршрут модели фиксируется endpoint. Не включать `tools`, Google Search, image/PDF, потоковую передачу, высокий reasoning без проверки. Маршрут сейчас отмечен провайдером **chat-only**, а не agent-ready. Читать `choices[0].message.content` и, если присутствует, `credits_consumed` и `usage`. Проверять HTTP status, `code` в теле, корректность и непустоту ответа. Нельзя считать `HTTP 200` достаточным доказательством успеха. Ошибки 429/5xx/timeout/неоднозначный ответ -> `HALTED_UNKNOWN`, без retry.

Баланс KIE можно проверять через `GET https://api.kie.ai/api/v1/chat/credit` (см. https://docs.kie.ai/common-api/get-account-credits). Кредиты — **не USD**; не конвертировать в деньги без подтверждённого тарифа. Сохранить `credits_before`, `credits_after`, `credits_consumed`, `usd_amount:null` при неизвестной цене.

**Секреты:** KIE ключ только локально в environment/менеджере секретов; не передавать MiniMax в промпте; никогда не помещать в коммиты, публичный PR, сырые n8n logs. Никакой записи в `.env` репозитория. У скрипта не должно быть прав на изменение кода/merge.

## 3. Два уровня ревью: экономим токены

**Уровень A (по умолчанию, короткий):**
- Контракт задачи: 300–600 символов.
- PR URL, строго `base_sha` и `head_sha`, `diff_sha256` (считанный локально по Git).
- Краткая сводка MiniMax «что изменил / почему / риск», максимум 1000 символов; считать саммари **недоверенной гипотезой**, а не доказательством.
- Фактические `git diff --check`, команда тестов + реальный exit code и число тестов (без необоснованного PASS).
- **Только критические hunks** реального diff: начальный ориентир до 6 KiB общего **сериализованного** пользовательского payload и до 4 файлов, путь + строки + минимальный контекст. Без полного чата, node_modules, binaries, lockfiles, медиа, больших логов.
- Ссылка предназначена владельцу: модель не обязана уметь открыть GitHub сама. Любое найденное замечание должно иметь доказательство из переданного diff.

**Уровень B (эскалация):** если Argon вернул `NEED_CONTEXT` / `UNSURE` с точным путём/строками, формировать второй пакет строго по указанным кускам, **только при отдельном разрешении**, с новым frozen packet hash; не посылать весь PR и не включать бесконечные дополнительные вопросы. Если разрешения нет — `BLOCKED_NEED_CONTEXT`.

Рекомендуемый ответ Argon — короткий JSON: `verdict: PASS|FINDINGS|NEED_CONTEXT|UNSURE`, `findings:[{severity,path,line,evidence,fix,test}]`, `requested_context:[{path,lines,reason}]`. Некорректный JSON не превращать автоматически в PASS. AI PASS не равен тестовому PASS и не даёт разрешения на merge.

## 4. Жёсткие лимиты (рекомендуемый пилот)

- `MAX_ARGON_CALLS_PER_PR=1`, `MAX_ARGON_CALLS_PER_DAY=2`, `MAX_ARGON_CALLS_PER_WEEK=5`, `MAX_CONCURRENT=1`, `MAX_PACKET_BYTES=6144`, `RETRY_COUNT=0`.
- Лимиты изменить можно только владельцу вне контроля MiniMax. **Программный** sqlite/json ledger под файловой блокировкой или транзакцией: резервировать `(repo, PR, head_sha, payload_sha256)` **до** HTTP, дедуплицировать повтор. При зависании сохранять `HALTED_UNKNOWN`, не отпускать лимит и не переотправлять автоматически. Важно защищаться и от параллельных процессов.
- Отдельный предел по KIE credits `MAX_KIE_CREDITS_PER_DAY` и/или неснижаемый `MIN_KIE_BALANCE` выставить **только после** того, как владелец сам выберет цифры на основании тарифа. Проверять баланс до запроса и после, если API доступен. Одного баланса недостаточно как жёсткого денежного лимита; использовать также количество вызовов и верхнюю ценовую оценку, если тариф известен. При неизвестной цене / отсутствии лимита LIVE заблокирован.
- OFFLINE без ключа — режим по умолчанию. LIVE впервые включить только после явно согласованного владельцем бюджета и разового разрешения на выбранный PR/SHA. Для будущих автоматических проверок владелец отдельно включает ограниченную политику: не выдавать самостоятельно себе разрешения.
- Не считать квоту MiniMax M Plan и баланс KIE одной системой. MiniMax сам проверяет доступность своего подписочного режима, не переключается на PAYG/credits без согласия (https://platform.minimax.io/subscribe/coding-plan).
- Не разрешать модели менять `review_gate.py`, `ledger`, `limit policy` и одновременно запускать их LIVE. Изменения контроллера сначала проходят отдельное офлайн-ревью владельца.

## 5. Минимальный review packet (пример; МОК, не реальный результат)

```json
{
  "schema": "gremovod/argon-evidence/1",
  "task_id": "P0-AUTH",
  "repo": "gremoled77-droid/gremovod",
  "pr_url": "https://github.com/gremoled77-droid/gremovod/pull/29",
  "base_sha": "READ_FROM_GIT_AND_VERIFY",
  "head_sha": "READ_FROM_GIT_AND_VERIFY",
  "diff_sha256": "SHA256_OF_EXACT_REVIEWED_DIFF",
  "scope": "Проверь подделку/просрочку capability; ищи P0-P2 дефекты, не косметику",
  "summary_untrusted": "MiniMax утверждает, что права теперь проверяются серверной подписью",
  "tests": [{"command": "python -m unittest backend.test_p0_budget_authz", "status": "NOT_RUN", "exit_code": null}],
  "hunks": [{"path": "backend/p0_authz.py", "patch": "@@ ... strictly extracted from frozen Git diff ..."}],
  "links_for_human": ["https://github.com/gremoled77-droid/gremovod/pull/29/files"]
}
```

До отправки в KIE проверить, что `head_sha` совпадает с текущим PR head, никаких dirty/untracked включений, diff содержит только разрешённые файлы, нет токенов/credentials/персональных данных. Снимок payload сохраняется **локально**, вне публичного репозитория. В GitHub разрешён только очищенный агрегированный отчёт.

## 6. Что именно MiniMax должен реализовать

1. Только чтение: сверить состояние PR #22/#23/#29, установленный MiniMax, репо, локальные ветки, `git status`, `AGENTS.md`, `CLAUDE.md`. Не пытаться чинить `main`.
2. Выделенный worktree/ветка MiniMax. Повторно использовать `tools/ai_review/argon_review.py` (его Git snapshot(), secret checks, make_prompt, ask_argon), не переписывать KIE Proxy v2. При необходимости вынести общий транспорт без изменения старых контрактов.
3. Добавить `tools/ai_review/build_review_packet.py` (immutable SHA + узкие реальные hunks + лимит 6KiB); `tools/ai_review/review_gate.py` (OFFLINE/LIVE, caps, ledger, locking, approval policy); тесты `tests/test_argon_review_gate.py`; redacted JSON/MD пример.
4. Сделать `docs/ai-review/ARGON_KIE_MINIMAX_SETUP_RU.md`: установка на Windows, переменные окружения только с именами, точные офлайн-команды, инструкции безопасного включения LIVE, аварийный стоп, где лежат отчёты.
5. Офлайн тесты: два параллельных запроса -> не больше одной резервации; один PR/SHA повторён -> NO_NEW_CALL; 429/timeout -> HALTED_UNKNOWN и zero retry; нет ключа/budget/approval -> NO_NETWORK; пустой diff; oversized packet; подозрение на secret; drift PR head; malformed JSON; загрязнённый тестовый отчёт; скачок баланса; отказ в writes.
6. Все изменения — Draft PR, с SHA и локальными тестами. Отчёт содержит точные статусы `OFFLINE/PENDING_APPROVAL/PASS/FINDINGS/BLOCKED/HALTED_UNKNOWN` без имитации вызова Argon.
7. Позже при отдельном разрешении: добавить n8n Cloud **только как диспетчер/витрину**. В n8n не хранить сырые секреты и не делать `Execute Command` (в облаке он отсутствует). n8n получает короткий `run-summary` и ссылки на PR/Actions, не полный код; backend Python остаётся контроллером расходов.

## 7. Режим запуска и критерии приёмки

Этап A: 100% OFFLINE, без KIE сетевого вызова. MiniMax показывает созданные файлы, тесты, пару примеров маленьких пакетов (MOCK), расход 0, Draft PR и запрашивает одобрение для LIVE.

Этап B: только после одобрения владельца и установки KIE ключа в локальном окружении выполняется **один** проверочный Argon API запрос по замороженному SHA и выбранному `P0-AUTH` фрагменту. Ключ никогда не передавать в чат.

Этап C: разобрать findings без циклических запросов; исправления MiniMax в новом коммите; повторное платное ревью по **новому SHA** — только с новым согласованием.

Этап D: при согласии владельца включить one-per-PR автоматический режим в заданных жёстких лимитах; n8n уведомляет, но не может самостоятельно поднять лимиты или разрешить merge.

**STOP условия:** сменился head SHA; секрет в diff; offline tests FAIL; лимит исчерпан; неизвестна цена/кредиты; тайм-аут или HTTP 429/5xx; failed auth; многократный/параллельный запуск; отказ GitHub; модель вернула непроверяемое заключение. Во всех случаях исключить retry и обозначить статус явно.

## 8. Текст для MiniMax

«Прочитай этот документ. Это ТЗ на реализацию экономного и безопасного MiniMax → GitHub → KIE Gemini 4 Argon review. Сначала сделай READ-ONLY аудит PR #22, #23, #29 и текущих веток, покажи список файлов, которые создашь/изменишь, и короткий план. После согласования реализуй только OFFLINE-прототип в отдельной ветке и Draft PR с тестами. Никаких реальных вызовов KIE, правок GPT Proxy, работы с оплачиваемыми API, автоматического включения n8n, правок main или слияний. Повторно используй существующий argon_review.py. Argon через KIE — исключительно chat-only и read-only, маленький frozen Git evidence packet. Контроль лимитов — в коде, не в промпте. Не считай ссылку GitHub достаточным контекстом для Argon. Не выдавай тестовый PASS и AI PASS за готовность к production. Заверши отчетом: пути файлов, ветка, SHA, PR, тесты, расходы, что требует решения владельца».
