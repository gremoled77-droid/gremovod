# Независимая приёмка исправлений MiniMax — 2026-10-21

**Общий результат: CHANGES_REQUESTED.** Полный совместный backend-набор зелёный, но дополнительные пробы выявили ошибки, которых в нём нет. Полноценная offline-бета не принята; для изолированной MOCK-демонстрации — CONDITIONAL GO. Реальная платная бета — NO GO.

Этот пакет — документы и безопасные тестовые фикстуры для передачи MiniMax. Он не исправляет runtime, не принимает исходные PR и не разрешает merge, paid submit, изменение production SQLite, канона или deployment.

| Документ | Содержание |
|---|---|
| [REVIEW.md](REVIEW.md) | Полный итоговый отчёт: точные SHA, вердикты, P1/P2, пути/строки, воспроизведения, границы доказательств |
| [MINIMAX_HANDOFF.md](MINIMAX_HANDOFF.md) | Ограниченные задания, критерии повторной приёмки, решения владельца, порядок интеграции и MOCK E2E |
| [TEST_RESULTS.md](TEST_RESULTS.md) | Реально выполненные тесты, GitHub jobs, красные regression contracts и команды запуска |
| [reviewed_refs.json](evidence/reviewed_refs.json) | Машиночитаемые SHA, вердикты и исходные GitHub CI run/job IDs |
| [offline_results.json](evidence/offline_results.json) | Структурированные результаты дополнительных проб и упаковочной проверки |
| [SHA256SUMS.json](evidence/SHA256SUMS.json) | Хеши опубликованных файлов и исходных локальных журналов; сами полные журналы не публикуются |

## Проверенные PR

Общая реальная база: `mavis/work@57cac59ca790d380d8e68f2f6db82674ca142e92`.

| PR | HEAD | Вердикт |
|---|---|---|
| [#58 GA-01](https://github.com/gremoled77-droid/gremovod/pull/58) | `5c47ace69477d2793deba1155b1d5df91a55e46d` | CHANGES_REQUESTED |
| [#62 GA-04](https://github.com/gremoled77-droid/gremovod/pull/62) | `08213fdc271dcef7f203e7cedb866b2588e55257` | CHANGES_REQUESTED |
| [#63 GA-05](https://github.com/gremoled77-droid/gremovod/pull/63) | `7524c677551c7ba3f34b8ce40a1a655895a88ff5` | CHANGES_REQUESTED |
| [#64 GA-03, только план](https://github.com/gremoled77-droid/gremovod/pull/64) | `0dd0c22d6d87e9ebcc00af550a48b1d605c98bdd` | CHANGES_REQUESTED; runtime BLOCKED_NOT_IMPLEMENTED |

Основания: аудит [#54](https://github.com/gremoled77-droid/gremovod/pull/54) и решения D1–D4 [#55](https://github.com/gremoled77-droid/gremovod/pull/55). D5–D7 не подменяются этим отчётом. Все выводы относятся к указанным SHA, а не автоматически к будущим исправлениям.

## Как читать тесты

- `tests/reproduce_ga01.py`, `reproduce_ga04.py`, `reproduce_ga05.py` — сохранённые дополнительные пробы исходного ревью. Они утверждают наблюдаемую ошибку. Их exit 0 означает **ошибка воспроизведена**, а не ACCEPT.
- `tests/regression_contracts.py` — противоположные утверждения о безопасном поведении. На проверенных неисправленных HEAD они должны быть красными. Файлы специально не добавлены в существующий `backend/test_*.py` или workflow: документационный PR не должен выглядеть как исправление продукта.
- `tests/run_offline.py` — единственная рекомендуемая точка запуска. Она извлекает Git-объекты во временный каталог, назначает временный `STUDIO_DATA_DIR` и не запускает сервер. Оригинальные checkout и данные не используются как runtime.

Платформенная граница: используется Python audit hook на внешние socket.connect текущего процесса, не OS-level network sandbox. Изученные дочерние процессы фикстур выполняют только локальные Git-команды. Нет проверки, способной доказать универсальную безопасность произвольного будущего кода из `--ref`.

Подробные команды, зависимости и ограничения находятся в [TEST_RESULTS.md](TEST_RESULTS.md). Дополнительные агенты не запускались; публикация этого отдельного Draft PR прямо разрешена владельцем в текущем чате.
