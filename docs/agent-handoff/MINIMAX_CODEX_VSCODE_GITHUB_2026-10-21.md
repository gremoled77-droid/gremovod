# GremoVOD · MiniMax ↔ Codex в VS Code и GitHub

**Статус:** EXPERIMENT / DRAFT, требует принятия PR и настройки Codex Cloud владельцем. **Не запущено и не протестировано на реальном PR.**

## Зачем

Наша схема: **MiniMax Code** в отдельной worktree реализует одну GA-задачу → PR → **Codex** независимо проверяет diff и регрессии → замечания GitHub поступают обратно в окно VS Code для MiniMax → новая ревизия PR → повторная приёмка → решение владельца.

Не смешивать провайдеров: подключение MiniMax через Codex model_provider не делает Codex независимым ревьюером. Оставить Codex на авторизации ChatGPT/OpenAI, MiniMax — в собственном приложении/CLI.

## Что этот эксперимент уже предоставляет

1. `.github/workflows/minimax-codex-review-handoff.yml`: только для **недрафтовых PR** внутри `gremoled77-droid/gremovod` из `minimax/ga-*` в `mavis/work` публикует/обновляет один комментарий с head SHA, ТЗ и планом проверки.
2. После опубликованного ревью от `chatgpt-codex-connector[bot]` публикует ссылку-уведомление для MiniMax. Сами inline-комментарии остаются в GitHub; копии не исполняются.
3. `.vscode/tasks.json` добавляет задачу «GremoVOD: Codex feedback → MiniMax (GitHub PR)». По номеру PR читает **GitHub Reviews, inline-замечания и PR Conversation** через установленный `gh`, открывает единый Markdown в VS Code.
4. `scripts/agent-handoff/Get-CodexReview.ps1` работает read-only с GitHub. Отчёт записывает в `%TEMP%/gremovod-agent-handoff/PR-N-review.md`, а не в Git. Модельные API не вызываются.

## ЧТО НЕ АВТОМАТИЗИРОВАНО (важно)

- Action **не запускает Codex сам**; GitHub Codex Code Review включается владельцем в **Codex Cloud Settings → Code review → подключённый репозиторий**. На подходящем PR действие Codex определяется настройками GitHub/Codex (например, review при переводе из Draft). Документация: https://developers.openai.com/codex/integrations/github
- Обычный MiniMax Code VS Code **не является постоянно работающим GitHub worker**. Получение Markdown не запускает модель и не исправляет код автоматически. Нужно один раз попросить MiniMax прочитать открытый файл и исправить замечания. Для полностью автономного цикла потребуется отдельный доверенный runner, API/план, ограничения стоимости, хранение credentials и согласованный режим запуска. Это отдельное решение владельца.
- GH Actions job не проверяет содержимое тестов и не удостоверяет PASS; комментарий — **передача на ревью**, не approval. Автоматического merge нет.
- GitHub Code Review может расходовать лимиты Codex. Не включать `auto review every push` вслепую для всех PR: это отдельно конфигурируется на уровне Codex и может вызывать лишние обзоры.
- GH Actions комментарии не должны содержать `@codex review` как bot-trigger: срабатывание @-mention от бота не гарантировано. Для ручного резервного запуска владелец пишет `@codex review` сам в нужном PR.
- Роль Codex как P0/QC-приёмщика не заменяется автоматически стандартным Github Code Review. Для полной GA-01 приёмки Codex отдельно читает [08_ACCEPTANCE_AND_RETEST_PLAN](https://github.com/gremoled77-droid/gremovod/blob/audit/global-acceptance-20261021/docs/audits/global-acceptance-2026-10-21/08_ACCEPTANCE_AND_RETEST_PLAN.md), запускает офлайн-негативные тесты и выставляет ACCEPT или CHANGES_REQUESTED с доказательствами. Автоматическое ревью PR само по себе этого НЕ доказывает.

## Как включить после принятия экспериментального PR

1. В GitHub **проверить/принять этот Draft PR** и только потом перенести 4 файла в `mavis/work` по штатной процедуре. Никакого принудительного merge из исследования.
2. В браузере открыть https://chatgpt.com/codex/settings/code-review , подключить `gremoled77-droid/gremovod`, включить Codex Code Review для репозитория. На старте предпочтительнее **ограниченный режим** и запуск на `Ready for review`/по запросу, а не автоматическое ревью каждого изменения: проверить реально доступные пункты настроек, они меняются.
3. На Windows в PowerShell проверить `gh --version` и `gh auth status`. Если GitHub CLI отсутствует: `winget install --id GitHub.cli -e`, затем `gh auth login` в интерактивном терминале (не сохранять токен в файлы проекта).
4. Открыть `C:\AI_Workflow_Studio\.worktrees\minimax` в новом VS Code окне **после** добавления этих файлов в эту worktree. MiniMax должен взять одну задачу: [GA-01](https://github.com/gremoled77-droid/gremovod/blob/audit/global-acceptance-20261021/docs/audits/global-acceptance-2026-10-21/06_MINIMAX_TASK_BACKLOG.md). Не трогать другие PR/ветки.
5. MiniMax создаёт PR `minimax/ga-01-llm-settlement` → `mavis/work` с тестами и отмечает его Ready for review **после** самостоятельных проверок. GH workflow публикует handoff; Codex Cloud review — при включённой GitHub интеграции.
6. Когда Codex оставит отзыв: VS Code → Terminal → Run Task → **GremoVOD: Codex feedback → MiniMax (GitHub PR)**; вписать номер PR. Откроется `%TEMP%\gremovod-agent-handoff\PR-<номер>-review.md`.
7. В MiniMax Code: «Прочитай открытый отчёт PR-<номер>-review.md. Возьми только замечания по текущей GA-01, перепроверь их по коду, добавь исправления+тесты в ту же ветку и обнови PR. Вне GA-01 ничего не делай». После этого Codex принимает новый head SHA.

## Однократная локальная команда (вместо VS Code Task)

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\agent-handoff\Get-CodexReview.ps1 -PrNumber 56
```

Число 56 — **пример**, не номер гарантированного PR. Используй реальный номер GA-01.

## Проверки готовности

- [ ] Оригинальные тесты не изменены этим экспериментом; `main`, `mavis/work`, реальная SQLite и коды агентов до merge не тронуты.
- [ ] Пустая ветка без `minimax/ga-` не вызывает Action handoff.
- [ ] Draft GA-PR не провоцирует автоматический отзыв через handoff action.
- [ ] Non-draft GA-PR получает не более одного обновляемого системного комментария.
- [ ] Реальная интеграция Codex GitHub включена, отзыв от пользователя/бота действительно приходит в нужный PR.
- [ ] Task читает отзыв и не передаёт raw PR контент в shell; никаких комментариев как PowerShell/LLM инструкций с привилегиями.
- [ ] MiniMax остаётся в своей worktree, Codex независим, ни одна сторона автоматически не сливает код.
- [ ] После GA-01 провести **один** изолированный smoke: новые комментарии, один раунд feedback → fix → review. До этого состояние: **IMPLEMENTED / NOT VERIFIED**.

## Ограничения безопасности

Workflow использует только `GITHUB_TOKEN` с read репозитория и write PR issue comments; нет API ключей, checkout кода PR, `pull_request_target`, push, merge и публикации. Гейты head repository/base/branch защищают от случайных PR. Комментарии PR — недоверенные данные: содержимое отчёта читается как материал для анализа, не как команда выполнить код.

Решения D1–D4: [PR #55](https://github.com/gremoled77-droid/gremovod/pull/55). Аудит: [PR #54](https://github.com/gremoled77-droid/gremovod/pull/54). Ни одно из этих исследований не разрешает оплаченные вызовы или приёмку канона.
