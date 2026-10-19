# Aider + MiniMax M3.1 Flash для GremoVOD

Краткая инструкция по запуску Aider в репозитории GremoVOD с моделью
`openai/MiniMax-M3.1-Flash` через OpenAI-совместимый API MiniMax M Plan.

Связанные документы: `docs/GIT_WORKFLOW.md` (ветки и push), `agents/minimax/` (интеграция MiniMax в бэкенд).

---

## 1. Однократная установка ключа

Ключ **никогда** не пишется в репозиторий, в `.aider.conf.yml`, в отчёты и в логи.
Он вводится с маскированием в терминале и сохраняется в зашифрованном виде
(Windows DPAPI, область `CurrentUser`) **вне репозитория**:

```
C:\Users\BLOWKA\.minimax\credentials\minimax-mplan.key
```

Команда (запускать из корня GremoVOD, ключ вводится вручную — ввод не отображается):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\aider\Set-MiniMaxApiKey.ps1
```

Скрипт:

1. спросит `MiniMax Subscription Key` с маскированием (`Read-Host -AsSecureString`);
2. проверит ключ запросом к `https://api.minimax.io/v1/chat/completions`
   и напечатает `API authentication successful` при успехе;
3. зашифрует ключ через DPAPI и запишет файл вне репозитория.

Ключ берётся в личном кабинете: <https://platform.minimax.io/console/plan>

Альтернатива, если ключ уже есть в переменной окружения
(удобно для CI, ключ не попадает в историю команд):

```powershell
$env:MINIMAX_API_KEY = '...'
powershell -ExecutionPolicy Bypass -File .\scripts\aider\Set-MiniMaxApiKey.ps1 -FromEnvironment
```

---

## 2. Запуск

Из корня GremoVOD (`C:\AI_Workflow_Studio`):

```powershell
.\scripts\aider\Start-AiderGremoVOD.ps1
```

Лаунчер подставляет ключ в `OPENAI_API_KEY` **только на время процесса** и запускает:

```
aider --model openai/MiniMax-M3.1-Flash
       --weak-model openai/MiniMax-M3.1-Flash
       --openai-api-base https://api.minimax.io/v1
       --map-tokens 2048
       --no-auto-commits --no-dirty-commits
       --no-cache-prompts --cache-keepalive-pings 0
       --edit-format diff
       --model-metadata-file scripts/aider/aider-minimax.model.metadata.json
```

Посмотреть собранную команду без запуска:

```powershell
.\scripts\aider\Start-AiderGremoVOD.ps1 -PrintCommand
```

Однократный вопрос без интерактивного чата:

```powershell
.\scripts\aider\Start-AiderGremoVOD.ps1 -AiderArgs @('--message','Что делает backend/camera_catalog.py?')
```

В каталоге `C:\AI_Workflow_Studio` уже лежат локальные (игнорируемые Git) файлы
`.aider.conf.yml` и `.aider.model.metadata.json` — благодаря им обычный запуск
`aider` в корне репозитория тоже работает с теми же настройками, если переменная
`OPENAI_API_KEY` уже экспортирована в сессии терминала.

---

## 3. Работа с контекстом

| Действие | Команда в чате Aider |
| --- | --- |
| Добавить файл в контекст | `/add backend/camera_catalog.py` |
| Добавить несколько | `/add backend/*.py frontend/src/**/*.tsx` |
| Показать, что сейчас в контексте | `/tokens` |
| Убрать файл из контекста | `/drop backend/camera_catalog.py` |
| Пересобрать карту репозитория | `/map` (или `/map refresh`) |
| Показать карту | `/map --show` |
| Незакоммиченные изменения | `/diff` |
| Откатить все правки текущей сессии | `/undo` |
| Выйти | `/exit` или `Ctrl+D` |

Карта репозитория строится по тегам (tree-sitter) и занимает 2048 токенов:
в репозитории GremoVOD обнаруживается 530 файлов.

---

## 4. Проверка изменений

Aider настроен на `--no-auto-commits` и `--no-dirty-commits`: он **никогда** сам
не коммитит и не коммитит грязное дерево. Поэтому каждое изменение проверяется вручную:

```powershell
git status --porcelain
git diff
```

Внутри чата Aider: `/diff` — показать правки, `/undo` — откатить их.

Дополнительно перед коммитом полезно прогнать проектные проверки
(`backend/pytest`, `ruff`) — см. `AGENTS.md` и `docs/GIT_WORKFLOW.md`.

---

## 5. Сохранение в Git

Автоматический push запрещён: Aider ничего не отправляет в сеть сам.

```powershell
git switch -c feature/<короткое-описание>   # работа в отдельной ветке
git add -p
git commit -m "feat(<область>): <что изменено>"
git push origin feature/<короткое-описание>  # вручную, только по решению владельца
```

Рабочее дерево GremoVOD содержит незакоммиченные изменения, поэтому правки Aider
ведутся в отдельной ветке или отдельном worktree:

```powershell
git worktree add -b feature/aider-minimax-20261020 C:\AI_Workflow_Studio\.worktrees\aider-minimax origin/main
```

---

## 6. Передача результатов Argon / Opus на аудит

Подготовка (без публикации наружу):

1. Все изменения — в отдельной ветке; коммиты подписаны и читаемы.
2. Проверки прогнаны, `git status` чистый по незакоммиченным файлам.
3. Автоматический push не выполняется — ветка остаётся локальной до решения владельца.

Передача аудитору (Argon / Opus) — один из вариантов:

```powershell
# a) Патч без истории коммитов
git diff origin/main...feature/aider-minimax-20261020 > C:\Users\BLOWKA\aider-minimax\review-aider.patch

# b) Ветка целиком (пуш выполняет владелец)
git push origin feature/aider-minimax-20261020

# c) Набор файлов для чтения
git diff --name-only origin/main...feature/aider-minimax-20261020
```

Результат работы Aider можно приложить как обычный diff — секретов в нём нет:
ключ живёт только в DPAPI-хранилище и в переменной окружения процесса.

---

## 7. Метаданные модели и предупреждение "Unknown context window size and costs"

Aider берёт лимиты и цены из базы LiteLLM. Модели `openai/MiniMax-M3.1-Flash`
в ней нет, поэтому Aider предупреждает об неизвестном контексте и ценах.
Значения заданы явно в `scripts/aider/aider-minimax.model.metadata.json`
(и в локальном `.aider.model.metadata.json`, который Aider подхватывает сам).

| Параметр | Значение | Источник |
| --- | --- | --- |
| Контекстное окно | 1 000 000 токенов | MiniMax, документация по text generation API: <https://platform.minimax.io/docs/guides/text-generation> |
| Выход | 128 000 токенов | значение для семейства MiniMax-M3 в базе LiteLLM (`minimax/MiniMax-M3`) и локальная конфигурация MiniMax Code |
| Ввод | $0.15 за 1M токенов | <https://platform.minimax.io/docs/pricing/overview> |
| Вывод | $0.60 за 1M токенов | <https://platform.minimax.io/docs/pricing/overview> |
| Чтение кэша | $0.015 за 1M токенов | <https://platform.minimax.io/docs/pricing/overview> |

Значения не выдуманы: контекст и цены взяты из официальной документации MiniMax,
лимит вывода — из локальной базы LiteLLM. Обновлять файл нужно только при смене
модели или тарифов.

---

## 8. Диагностика

| Симптом | Причина и решение |
| --- | --- |
| `No MiniMax key found` | не создан DPAPI-хранилище, см. раздел 1 |
| `Unknown context window size and costs` | не подхватился `model-metadata-file`, см. раздел 7 |
| `UnicodeEncodeError` в `cp1251.py` | в лаунчер добавлен `PYTHONIOENCODING=utf-8`; при ручном запуске `aider` выполните `$env:PYTHONIOENCODING='utf-8'` |
| `401 / AuthenticationError` | ключ истёк или введён с ошибкой — повторите раздел 1 |
| `400 ... reasoning_effort` | MiniMax не принимает значение `none`; оставляйте `reasoning_effort` по умолчанию |
| `unrecognized arguments: --repo-map-tokens` | правильное имя — `--map-tokens` |

Проверка окружения без расхода квоты:

```powershell
aider --version
.\scripts\aider\Start-AiderGremoVOD.ps1 -PrintCommand
aider --show-repo-map --map-tokens 2048
```
