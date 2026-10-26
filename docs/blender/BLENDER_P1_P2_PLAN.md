# План P1 и P2 после локального P0

P1 и P2 — будущие карточки. Они не означают готовность провайдера, не разрешают внешний upload и не требуют платный вызов. P0 execution сейчас `BLOCKED_G1`: нет проверенной одноразовой среды без секретов. Для локального synthetic smoke нужны owner-provided isolation receipt, реализация isolated launcher и проверка его ограничений; затем владелец отдельно должен принять proxy или передать approved canon. Пока эти условия не выполнены, live integration остаётся закрытой.

| Карточка | Зависимости | Definition of Done | Проверка | Исполнитель |
|---|---|---|---|---|
| P1-1: разрешение канонических ассетов | P0 отчёт; владелец передаёт утверждённый `.blend`/asset id, версию, SHA и физические размеры | Stage bible с осями, бортами и дверями сверяется с источником; snapshot геометрии защищённого меша неизменяем | Негативные тесты на чужой asset id, устаревшую версию и смену SHA; owner review двух сторон машины | Codex, владелец канона |
| P1-2: совместимость Blender и addon smoke | P0 CLI результаты; выбранный поддерживаемый Blender runtime | Зафиксированы версия Blender, addon revisions/licenses, открытие, сохранение, повторное открытие и проверка `.blend` | Условный тест на закреплённом runtime; failure при неизвестной совместимости | Codex |
| P1-3: reference contract к текущим адаптерам | Актуальная матрица возможностей `backend/adapters.py` и `model_catalog.py`; P1-1 approval канона | Role/slot/tag и payload строятся только для функций, реально поддержанных адаптером; unsupported режимы fail closed | Mock проверяет ref order, changed hash, запрещённую роль и неизвестный endpoint; без отправки | Codex |
| P1-4: согласование и существующий бюджетный lifecycle | P1-3; существующие GenerationReview/quote/confirm-token/budget и reconcile правила | Перед dispatch используется существующая оценка и подтверждение; состояния cost `NOT_SUBMITTED/RESERVED/SETTLED/UNKNOWN` согласованы; нового approval/budget сервиса нет | Mock: без approval нет dispatch; changed reference аннулирует согласование; `UNKNOWN` удерживает сумму и запрещает retry | Codex |
| P1-5: reference transport | P1-1…P1-4 и отдельное явное разрешение на конкретный файл/endpoint/стоимость | Только одобренный asset проходит действующий transport; `.blend` не принимается как reference без подтверждённой поддержки | Локальные mock-тесты ownership/размера/hash/endpoint. Live upload или paid call — только после отдельного согласования владельца | Codex, владелец |
| P1-6: общий QC отчёт и визуальное принятие | Локальная media_qc, доступный ffprobe, завершённый P1 smoke | Существующий `backend/media_qc.py` получает измерения; отдельный сервис QC не создаётся; технический статус отделён от owner verdict | Декодирование и метаданные через существующий runner; ручной review всех обязательных кадров | Codex, владелец |
| P2-1: UI просмотра раскадровки | Принятый P1 контракт; существующие storyboard, production workspace, folder/storage path | UI показывает версии, кадры, continuity и QC; комментарий/решение аудитируются в существующей модели | UI-тест согласования и доступа к чужому production | Codex |
| P2-2: привязка утверждённого результата к production | P2-1; `production_folders`/`checked_path` и существующие asset/node сущности | `.blend`, кадры и отчёты хранятся внутри проверенного production/node пути; в Git не попадают медиа или DB | Тест traversal и ownership; повторная синхронизация не создаёт параллельный asset registry | Codex |
| P2-3: оркестрация батчей | P2-1, P2-2; заранее подтверждённые лимиты и rate-limit policy | Очередь запускает только валидированные локальные shot; внешние шаги остаются за существующей approval границей; n8n не запускает произвольный shell | Dry-run с повторяемым manifest и ограниченной очередью; никаких deployment или paid runs | Codex, MiniMax по отдельным изолированным карточкам |

## Незавершённые зависимости P0

До карточек P1 Codex должен реализовать и проверить isolated launcher (pin SHA, timeout, memory/disk/process tree), выполнить diagnostic → save/reopen → immutable master и отдельную копию попытки → 192 кадра в двух аспектах → MP4/измеренный QC/owner review. Затем нужен измеренный benchmark на одинаковом engine и качестве. DoD: реальные отчёты доступа, времени, памяти, SHA, кадров и решения владельца. Сейчас эти проверки BLOCKED_G1/NOT_MEASURED.

## Разблокировка G1

Владелец предоставляет и утверждает одноразовую Windows VM или отдельную Windows учётную запись без секретов, credential mounts и доступа к пользовательским проектам; указывает разрешённые каталоги, сетевую политику и лимиты времени/диска/памяти. Исполнитель сохраняет краткий isolation receipt и проверяет его до любого Blender-процесса. Если host isolation невозможно подтвердить, весь Blender/MCP execution остаётся `BLOCKED_G1`; офлайн schema/runner/security tests продолжаются независимо.

## Архитектурные инварианты

- Использовать действующий production/node folder boundary (`production_folders.checked_path`), существующие entity/file записи и ownership проверки; не добавлять второй registry или параллельную SQLite.
- Использовать `backend/media_qc.py` и его measurements/verdict там, где контракт подходит; не заводить второй backend QC.
- Внешний dispatch обязан проходить уже существующие model catalog, GenerationReview, quote/confirm token, budget reservation и reconciliation. Не считать UI-возможности модели доказательством адаптерной поддержки.
- Смена approved reference/hash или неизвестная стоимость блокирует retry. Любая внешняя загрузка требует точного scope, файла, endpoint и стоимости.
- Каждый task owner несёт только свою таблицу/файлы; не запускать параллельную работу двух исполнителей по одним файлам.
- До отдельных проверок MiniMax и Claude не вызывать сторонние LLM/агенты и не передавать им приватный канон. MiniMax можно поручить независимую проверку docs/тест-плана после указания точных файлов; это не разрешает API-запуск.
