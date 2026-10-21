# Проверка v1 — 21 октября 2026

Все изменения ограничены `extensions/agent-monitor/`. Ветка `feature/gremovod-agent-monitor-v1`, база `ba078cb` из незавершённого Draft PR #59. Dispatcher не запускался и не изменялся.

| Проверка | Результат / граница |
| --- | --- |
| `npm test` | 16/16 PASS; TypeScript build PASS; chronology проверена между Git timezone offsets и UTC |
| Journal | 12 000 событий, 200 KiB malformed line, bounded UI, полный ID dedupe; restart, truncated write, filters |
| GitHub adapters | Mock exact/stale/moving SHA, official bot verification, pagination, Actions, network/rate-limit failure; paid APIs отсутствуют |
| Security | Credential-shaped fixtures скрываются; file/link boundary; Webview script/image injection inert |
| Real Git | Прочитана feature worktree: branch/HEAD/status через настоящий Git; baseline SHA `ba078cb2a48a56b3d6af8d5963373c62d05cad8b` |
| Extension host | VS Code 1.142.0, изолированные profile/extensions/workspace; extension activated, панель открыта |
| Live GitHub | Read-only PR #58: SHA `9b6a610a6b1afcb4e24b869649a387b7b6d5e8bf`, Changes requested, P0/P1/P2 = 0/1/0 |
| Webview | Поиск/сброс фильтра, выбор Handoff, Refresh, HTML injection, закрытие/повторное открытие без потери ID |
| Watcher | Синтетический `LAUNCHED` в тестовом dispatcher directory обновляет панель; live activity остаётся Unknown |
| Offline/cache | Ошибки сети проверены mock-адаптером. В финальном host run после успешного live чтения повторное открытие получило реальный сетевой отказ; панель сохранила историю и cached PR, показала Not connected |
| VSIX | `npm run package` PASS; VS Code CLI: `Extension 'gremovod-agent-monitor-0.1.0.vsix' was successfully installed.` Только отдельный install-profile/install-extensions |

**Скриншоты настоящего VS Code**, не HTML-превью: [обзор](vscode-live-pr58.png), [шкала](vscode-live-timeline.png). На них только live GitHub-события; локальная fixture добавлялась после снимков. В общем счётчике последующего host-results одна watcher fixture отмечена отдельно.

`host-results.json` — машинная запись host run, timestamps UTC. Ошибка первого тестового подхода (Playwright внутри extension host / navigator) устранена переносом Playwright в отдельный Node process. Уникальный runner path исключает повторное использование старого тестового модуля desktop host. Fixed-delay ожидание Refresh заменено ожиданием фактического обновления.

Упаковщик предупреждает об отсутствии LICENSE: package помечен `UNLICENSED`, никакая открытая лицензия владельцу не назначалась. VSIX не включает test logs, profiles, screenshots, fixtures, dev dependencies и package lock. Установка в основной профиль, Marketplace, merge, запуск моделей, production/SQLite и полный Studio regression не выполнялись. Для изменения только extension полная backend/frontend suite не требуется.

Окончательная приёмка владельца: установить локальный VSIX, открыть нужную worktree и проверить чтение своих PR/отчётов, переход к источнику и копирование. Реальную активность CLI нельзя подтверждать без heartbeat в исходном диспетчере; этот Draft не выдаёт её за известную.
