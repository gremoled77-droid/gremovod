# MiniMax — предварительный последовательный протокол (до ответа Argon)
**Статус: DRAFT, authored by ChatGPT, ARGON REVIEW NOT_RUN.** Не называть этот документ «планом Аргона». Целевая задача: Issue #27. Основной период: 20–24 октября 2026. Передача Codex: 25 октября.

## Обязательные правила
- **Ровно один активный шаг.** Сначала прочитать `docs/ai-review/MINIMAX_STEP_TRACKER_TEMPLATE.md` (или его текущую рабочую копию в собственном PR) и ссылки на evidence. Не начинать M(n+1) до PASS M(n). Каждый BLOCKED/FAIL → запись причины и остановка; без самостоятельных бесконечных попыток.
- **Один шаг = один небольший отдельный коммит** (по возможности), тесты, ссылка, отчёт владельцу, обновление трекера. Все коммиты в отдельной MiniMax-ветке/worktree, PR всегда Draft. Не писать напрямую в `main` и ветки Codex/Claude/Argon.
- `ARGON_TO_MINIMAX_PLAN_RU.md` появится **только после настоящего ответа Argon**. Он не может сам писать в GitHub — текст переносит MiniMax/владелец с явной отметкой источника, затем владелец утверждает, что план согласован. При расхождениях с существующей безопасностью `AGENTS.md`/PR #23 приоритет безопасности, остановка и уточнение владельца.
- **Разрешение на оплату отдельное от разрешения на код.** Никаких KIE/PiAPI/MiniMax PAYG, credit packs, произвольных API, автоматических retry, `--auto-test` с моделями, автослияния. M Plan ключ/квота только после проверки и отдельного согласия на конкретный LIVE вызов.
- При передаче прав не слать приватные персонажи, медиа, базы, локальные референсы или секреты в публичный GitHub/модель/n8n. Статус модели PASS не заменяет CI и решение человека.

## Предложенный маршрут (Argon обязан оценить порядок и риски)
| ID | Чёткое действие | Файл/доказательство | PASS / условие перехода | STOP |
|---|---|---|---|---|
| M00 | **READ ONLY:** проверить remote, `git status`, `git worktree list`, существующие Issues #21/#24/#26/#27 и Draft PR #22/#23/#25, файлы `AGENTS.md`/`CLAUDE.md`, доступные Actions и n8n. | `docs/ai-review/MINIMAX_BASELINE_RU.md` (позже, в своей ветке) | Протокол фактов vs SPEC и SHA готов, secrets не выданы. | Нет доступа / непонятна ветка / незакоммиченные файлы в зоне работ. |
| M01 | Однократно запросить стратегию Argon из `ARGON_MINIMAX_ONE_SHOT_REQUEST_20261019.md`; MiniMax сохраняет **реальный** ответ в два файла, без редакторского приписывания авторства. Получить подтверждение владельца. | `ARGON_TO_MINIMAX_PLAN_RU.md`, `ARGON_TO_MINIMAX_DECISIONS_RU.md`, Draft PR | План получен, принадлежность ответа проверена, владелец принял последовательность. | Нет Argon, API платный и не разрешён, неподтверждённый ответ. |
| M02 | Создать отдельный worktree MiniMax из подтверждённого base SHA; не трогать рабочий `C:\AI_Workflow_Studio` и чужие ветки. | `git worktree list` + branch + сохранённый SHA в tracker | Независимый рабочий каталог, чистая ветка. | Ветки/файлы владельца могут измениться. |
| M03 | Снять и выполнить baseline **бесплатных** тестов без сети, указать реальные команды/версии, результаты и текущие дефекты. | `docs/ai-review/MINIMAX_TEST_BASELINE.md` + чистые logs без секретов | PASS у минимальных проверок или задокументированные исходные failures, не замаскированные как новые PASS. | Тесты трогают пользовательские данные/делают API. |
| M04 | Реализовать versioned JSON контракт статусов и standalone offline Markdown renderer для `run-summary.md`; отчёт «что/зачем» только из подтверждённых данных. | Код + 10+ офлайн unit tests + образец MOCK отчёта | Все новые тесты PASS; неизвестные данные NOT_RUN/UNKNOWN; secret redaction. | Секреты, ложный PASS, несовпадение SHA. |
| M05 | Добавить безопасный GitHub Actions шаг с `GITHUB_STEP_SUMMARY` для offline-report и optional artifact. Не активировать автоматически платные job. | Драфт PR + Checks / пример Markdown Summary | Offline job запускается подтверждённо, доказательства Actions URL / SHA. | workflow не доступен default branch для dispatch, нет прав. |
| M06 | Специфицировать n8n MOCK flow: GitHub event → ID+SHA validation → dedup → read-only Actions/PR status → нормализация → отчёт. В Cloud нет Execute Command. | Проверенная схема/mock fixture и node map в docs или отдельный JSON без cred | Offline/dry-run схема связана с `run_id`, никакой публикации и LIVE. | Нестабильный event mapping / credentials или приватные payload. |
| M07 | **Только после отдельного разрешения:** создать отдельный inactive MOCK n8n workflow, протестировать его вручную на фиктивном событии, не менять существующие 18. | n8n workflow ID + execution URL + screenshot/summary | Есть настоящий execution ID и результат MOCK, никого не списало. | Нет доступа, активный workflow, неожиданные внешние запросы. |
| M08 | **Опционально, только отдельное разрешение:** один LIVE MiniMax Subscription API запрос на маленький очищенный diff после проверки активной M Plan квоты/expiry, model ID, Key type, SHA и лимита. Автоматически завершать к 25 октября; не уходить на PAYG. | Provider usage + run ID + PR comment sanitized, review status | Факт ответа и использования квоты подтверждён; `CI` отдельно от model opinion. | Quota unknown/exhausted, timeout, 429, credit pack, PAYG, expiration, cost unknown. Если нет согласия — `SKIPPED_BY_OWNER`, не мешать M09. |
| M09 | Завершение: owner report, ссылки на PR/Issue/Actions/n8n, найденные риски, доказательства тестов, `HANDOFF_FOR_CODEX.md` к 24.10. | Draft PR + `agents/minimax/HANDOFF_FOR_CODEX.md` | Codex сможет продолжить с SHA и шагов, не повторяя исследования. | Доклад заявляет неподтверждённые LIVE успехи. |

**Приоритет шага M09 при дедлайне:** если настаёт 24 октября и не закончены M05–M08, MiniMax не должен форсировать запуск API/автоматику. Он записывает, что именно осталось, и передаёт незавершённое Codex.

## Формат обязательного краткого отчёта MiniMax после каждого шага
```text
Task/Step: Mxx
Status: PASS | BLOCKED | FAIL | SKIPPED_BY_OWNER | NOT_RUN
Git branch / base SHA / HEAD SHA:
Изменено (точные пути):
Почему (ссылка на Issue/согласованное ТЗ):
Бесплатные тесты (команды и результат):
AI calls: NONE | one approved call + usage
Argon status: NOT_RUN | actual finding link
n8n status: NOT_RUN | MOCK execution URL
PR / commit / Actions links:
Проблемы:
Требуется решение пользователя: ДА/НЕТ
Единственный следующий шаг: Mxx или STOP
```
