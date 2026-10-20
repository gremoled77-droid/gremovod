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

> **Скрипты устанавливаются в корень репозитория.** Ветка `feature/aider-minimax-20261020`
> содержит `scripts/aider/*`; копия также живёт в `C:\Users\BLOWKA\aider-minimax\` (вне
> репозитория) и может использоваться из любого каталога. Если запустить лаунчер из
> каталога, который не является git-репозиторием, он не найдёт корень и завершится с
> понятной ошибкой — тогда передайте путь явно: `-RepoPath C:\AI_Workflow_Studio`.

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

### Быстрая самопроверка (одна команда)

```powershell
.\scripts\aider\Test-AiderSetup.ps1
```

Проверяет по пунктам: версии инструментов, наличие и расшифровку DPAPI-хранилища,
авторизацию в API MiniMax (HTTP 200), определение корня репозитория лаунчером,
построение карты репозитория и полный набор серверных тестов. Печатает `[ OK ]` /
`[FAIL]` по каждому пункту и возвращает ненулевой код, если что-то красное.
Быстрый вариант без тестов и без обращения к API: `-SkipApi -SkipTests`.

### Таблица симптомов

| Симптом | Причина и решение |
| --- | --- |
| `No MiniMax key found` | не создан DPAPI-хранилище, см. раздел 1 |
| `Unknown context window size and costs` | не подхватился `model-metadata-file`, см. раздел 7 |
| `UnicodeEncodeError` в `cp1251.py` | в лаунчер добавлен `PYTHONIOENCODING=utf-8`; при ручном запуске `aider` выполните `$env:PYTHONIOENCODING='utf-8'` |
| `401 / AuthenticationError` | ключ истёк или введён с ошибкой — повторите раздел 1 |
| `400 ... reasoning_effort` | MiniMax не принимает значение `none`; оставляйте `reasoning_effort` по умолчанию |
| `unrecognized arguments: --repo-map-tokens` | правильное имя — `--map-tokens` |
| `Skipping ... that matches gitignore spec` | Aider не берёт файлы, совпадающие с `.gitignore`; проверочный файл держите вне игнорируемых каталогов (`tmp/`, `tools/`) |
| `Creating empty file <слово>` | сработал авто-ответ на вопрос «Add file to the chat?» — см. раздел 9 |

Проверка окружения без расхода квоты:

```powershell
aider --version
.\scripts\aider\Start-AiderGremoVOD.ps1 -PrintCommand
aider --show-repo-map --map-tokens 2048
```

---

## 9. Особенности поведения Aider (проверено на этой связке)

Эти грабли проверены на Aider 0.86.2 + MiniMax M3.1 Flash, зафиксированы, чтобы не
повторять их в рабочей смене.

1. **Не используйте `--yes` и `--yes-always`.** Эти флаги автоматически отвечают «да»
   на вопрос «Add file to the chat?». Aider считает именем файла любое слово из запроса
   и, если файла нет, **создаёт пустой файл** в корне репозитория. Проверено: запрос
   «…replace the word PLACEHOLDER with VALUE42…» создал 12 пустых файлов
   (`Keep`, `PLACEHOLDER`, `the`, `word` и т. п.). Обычный интерактивный режим без
   этих флагов такого не делает.
2. **В неинтерактивном запуске (нет TTY) EOF считается ответом «да»** — так устроен
   `confirm_ask` в `aider/io.py`. Поэтому однострочный запуск `--message` сам применяет
   предложенную правку. Правки применяются, но `--no-auto-commits` гарантирует, что
   в Git ничего не уедет.
2a. **Опасное следствие: без терминала Aider применяет правку даже когда просили только
   прочитать.** Модель по привычке возвращает блок `SEARCH/REPLACE` (в системном промпте
   Aider сказано «ONLY EVER RETURN CODE IN A SEARCH/REPLACE BLOCK»), а EOF трактуется как
   «да» — и блок применяется. Проверено 20.10.2026: задание «процитируй значения из файла»
   закончилось строкой `Applied edit to backend/prompt_rules.py`. Файл при этом остался
   побайтово идентичен HEAD, потому что блок вышел no-op. **Любой не-no-op блок изменил бы
   код проекта молча.** Вывод: задания на чтение в неинтерактивном режиме допустимо
   запускать только в отдельном worktree и только с проверкой `git diff` по хешам. В
   основном рабочем дереве — всегда интерактивно, с подтверждением.
2b. **Текст задания не должен попадать в командную строку.** `--message "..."` в PowerShell
   при передаче массивом в нативный процесс разбирается на отдельные аргументы, и слова
   запроса Aider принимает за имена файлов и создаёт их (проверено: 12 пустых файлов).
   Безопасная форма — `--message-file <путь>`: текст читается из файла и в argv не попадает.
3. **Файлы под `.gitignore` не попадают в контекст** (`tmp/`, `tools/`, `backend/media/`
   и т. п.). Для проверки правок нужен файл вне игнорируемых каталогов.
4. **Строка системного промпта заставляет модель отвечать блоком `SEARCH/REPLACE`**
   даже когда изменения не нужны. На вопрос «процитируй код» MiniMax M3.1 Flash
   возвращает блок с одинаковыми `SEARCH` и `REPLACE`. Для запросов на чтение удобнее
   `--file <путь>` + «процитируй первые строки», а не «назови файлы».
5. **Кодировка консоли.** На кодовой странице cp1251 Aider падает с `UnicodeEncodeError`
   при печати карты репозитория. Лаунчер выставляет `PYTHONIOENCODING=utf-8` и
   `PYTHONUTF8=1` для дочернего процесса; при ручном запуске `aider` сделайте то же самое.
6. **Стоимость видно сразу.** С загруженными метаданными Aider печатает реальную
   стоимость запроса (например, `$0.0012 message`), что подтверждает, что лимиты
   и цены модели подхвачены и предупреждение об их отсутствии больше не появляется.

---

## 10. Что уже проверено

| Проверка | Результат |
| --- | --- |
| `aider --version` | 0.86.2 (установлен через `uv tool install aider-chat`) |
| Авторизация MiniMax | HTTP 200, модель `MiniMax-M3.1-Flash` |
| Обнаружение файлов | `Git repo: .git with 530 files` |
| Карта репозитория | `Repo-map: using 2048 tokens`, карта строится без обращения к API |
| Тестовый запрос | ответ на русском, правок нет, `exit=0` |
| Чтение файла | `--file backend/main.py` — файл в чате, строки процитированы дословно |
| Механизм правки | `Applied edit to aider-edit-probe.md`, строка заменена, коммитов нет |
| Автокоммит | не выполняется (`--no-auto-commits --no-dirty-commits`) |
| Push | не выполнялся |
