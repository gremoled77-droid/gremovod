# claude — BETA-02: офлайн-приёмка кандидата GA-01 + GA-03 (Issue #85)

Статус: **CODE_COMPLETE** (гейт и тесты готовы и проходят на временной интеграционной копии). **CI_PASS: NOT_RUN** (в Actions тесты backend/frontend не гоняются). **OWNER_ACCEPTED: нет. RELEASE_GO: нет — отчёт гейта всегда NO_GO** (причины ниже). Платных вызовов 0.

## Одна команда
# BETA-02 — офлайн-приёмка (quick)

- Время: 2026-10-22T17:50:52Z
- HEAD: `acf86b9a72b258765ac2d14c7d6e4e34a9304c6e` (build/claude/beta-02-offline-acceptance, dirty=False)
- Технический вердикт: **FAIL** · релизный: **NO_GO** · код выхода 1
- Платных вызовов: **unknown** · данные: temp · fault: нет
- Среда: 3.13.16, Linux

| Шаг | Обязательный | Статус | Тесты (всего/упало/ошибки/пропущено) | Код | Сеть | Причина |
|---|---|---|---|---|---|---|
| GA-03: release gate (backend/test_release_gate.py) | да | **FAIL** | 0/0/0/0 | 1 | — | pytest завершился кодом 1: failed=0, errors=0 |
| N34/N35 и приёмка QA (B1: старый QC не наследуется) | да | **FAIL** | 0/0/0/0 | 1 | — | pytest завершился кодом 1: failed=0, errors=0 |
| BETA-02: контракт HTTP, перезапуск, резервная копия | да | **FAIL** | 0/0/0/0 | 1 | — | pytest завершился кодом 1: failed=0, errors=0 |
| BETA-02: fail-closed матрица, токен, гонка | да | **FAIL** | 0/0/0/0 | 1 | — | pytest завершился кодом 1: failed=0, errors=0 |
| GA-01 рядом с выпуском: неизвестная сумма держит траты (нужен #79) | да | **FAIL** | 0/0/0/0 | 1 | — | pytest завершился кодом 1: failed=0, errors=0 |
| GA-01: тесты денег (R3, расчёт LLM, граница денег, резервы) | да | **BLOCKED** | 0/0/0/0 | — | — | нет обязательных файлов: backend/test_ga01_unreadable_barrier.py, backend/test_llm_settlement.py |

## Не выполнялось (NOT_RUN)
- Браузерный smoke экрана «Выпуск» (frontend — отдельная задача MiniMax #84/#86)
- CapCut GUI и реальный MP4 владельца
- Рабочая SQLite и реальные файлы владельца (запрещено)
- GitHub Actions: тесты backend/frontend в CI не запускаются, идут только scope и handoff
- Живые платные провайдеры (запрещено)

## Источники в дереве
- #75 `bfb57631f2` CI и хуки: ОТСУТСТВУЕТ
- #58 `c634c0c915` GA-01 база: ОТСУТСТВУЕТ
- #76 `8fb6b76e3b` GA-01 исправления MiniMax: ОТСУТСТВУЕТ
- #79 `784ea0c780` GA-01 R3, нечитаемая сумма: ОТСУТСТВУЕТ
- #78 `b0ea55dab5` BETA-01, фикс B1: в дереве
- #81 `d249dded05` GA-03 backend gate: в дереве
- #83 `59e8196f72` GA-03 гонка решений и кэш хеша: в дереве

## Почему NO_GO
- OWNER_AUTH_REQUIRED: идентификатор владельца сверяется с GREMOVOD_OWNER_ID — это не аутентификация (пароль отложен владельцем)
- GA-01: решения владельца по сверке нечитаемой суммы и приёмка #58/#76/#79 не получены
- Живые проверки (браузер, CapCut, реальный MP4, CI с тестами) не выполнялись
- обязательный шаг упал: release-gate
- обязательный шаг упал: qc-n34-n35
- обязательный шаг упал: integration-release
- обязательный шаг упал: integration-failclosed
- обязательный шаг упал: ga01-money-coexistence
- обязательный шаг заблокирован: ga01-money-suites

## Разделение статусов
- CODE_COMPLETE: False
- CI_PASS: NOT_RUN (в Actions не гоняются тесты)
- OWNER_ACCEPTED: false
- RELEASE_GO: false

Отчёт: /tmp/beta02-report-akweowl1/report.json
# BETA-02 — офлайн-приёмка (full)

- Время: 2026-10-22T17:50:52Z
- HEAD: `acf86b9a72b258765ac2d14c7d6e4e34a9304c6e` (build/claude/beta-02-offline-acceptance, dirty=False)
- Технический вердикт: **FAIL** · релизный: **NO_GO** · код выхода 1
- Платных вызовов: **unknown** · данные: temp · fault: нет
- Среда: 3.13.16, Linux

| Шаг | Обязательный | Статус | Тесты (всего/упало/ошибки/пропущено) | Код | Сеть | Причина |
|---|---|---|---|---|---|---|
| GA-03: release gate (backend/test_release_gate.py) | да | **FAIL** | 0/0/0/0 | 1 | — | pytest завершился кодом 1: failed=0, errors=0 |
| N34/N35 и приёмка QA (B1: старый QC не наследуется) | да | **FAIL** | 0/0/0/0 | 1 | — | pytest завершился кодом 1: failed=0, errors=0 |
| BETA-02: контракт HTTP, перезапуск, резервная копия | да | **FAIL** | 0/0/0/0 | 1 | — | pytest завершился кодом 1: failed=0, errors=0 |
| BETA-02: fail-closed матрица, токен, гонка | да | **FAIL** | 0/0/0/0 | 1 | — | pytest завершился кодом 1: failed=0, errors=0 |
| GA-01 рядом с выпуском: неизвестная сумма держит траты (нужен #79) | да | **FAIL** | 0/0/0/0 | 1 | — | pytest завершился кодом 1: failed=0, errors=0 |
| GA-01: тесты денег (R3, расчёт LLM, граница денег, резервы) | да | **BLOCKED** | 0/0/0/0 | — | — | нет обязательных файлов: backend/test_ga01_unreadable_barrier.py, backend/test_llm_settlement.py |
| Весь backend pytest | да | **FAIL** | 0/0/0/0 | 1 | — | pytest завершился кодом 1: failed=0, errors=0 |

## Не выполнялось (NOT_RUN)
- Браузерный smoke экрана «Выпуск» (frontend — отдельная задача MiniMax #84/#86)
- CapCut GUI и реальный MP4 владельца
- Рабочая SQLite и реальные файлы владельца (запрещено)
- GitHub Actions: тесты backend/frontend в CI не запускаются, идут только scope и handoff
- Живые платные провайдеры (запрещено)

## Источники в дереве
- #75 `bfb57631f2` CI и хуки: ОТСУТСТВУЕТ
- #58 `c634c0c915` GA-01 база: ОТСУТСТВУЕТ
- #76 `8fb6b76e3b` GA-01 исправления MiniMax: ОТСУТСТВУЕТ
- #79 `784ea0c780` GA-01 R3, нечитаемая сумма: ОТСУТСТВУЕТ
- #78 `b0ea55dab5` BETA-01, фикс B1: в дереве
- #81 `d249dded05` GA-03 backend gate: в дереве
- #83 `59e8196f72` GA-03 гонка решений и кэш хеша: в дереве

## Почему NO_GO
- OWNER_AUTH_REQUIRED: идентификатор владельца сверяется с GREMOVOD_OWNER_ID — это не аутентификация (пароль отложен владельцем)
- GA-01: решения владельца по сверке нечитаемой суммы и приёмка #58/#76/#79 не получены
- Живые проверки (браузер, CapCut, реальный MP4, CI с тестами) не выполнялись
- обязательный шаг упал: release-gate
- обязательный шаг упал: qc-n34-n35
- обязательный шаг упал: integration-release
- обязательный шаг упал: integration-failclosed
- обязательный шаг упал: ga01-money-coexistence
- обязательный шаг упал: backend-full
- обязательный шаг заблокирован: ga01-money-suites

## Разделение статусов
- CODE_COMPLETE: False
- CI_PASS: NOT_RUN (в Actions не гоняются тесты)
- OWNER_ACCEPTED: false
- RELEASE_GO: false

Отчёт: /tmp/beta02-report-hhr5tewq/report.json
Нужны python с зависимостями  и pytest, ffmpeg/ffprobe (без них шаги BLOCKED, автоустановки нет). Код выхода: 0 — все обязательные шаги PASS, 1 — есть FAIL, 2 — есть BLOCKED/NOT_RUN. Отчёты  и  (временная папка или ).  пишется только при PASS всех обязательных шагов и нуле сетевых попыток по ловушке  (loopback разрешён, любой другой DNS/connect — ошибка). Данные: временный , реальные файлы ключей изолированы патчами, ролики — локальный ffmpeg.

## Карта SHA (проверена  2026-10-22)
Закреплена в ; база  57cac59.
| PR | Ветка | SHA |
|---|---|---|
| #75 | mavis/ci-final-2026-10-22 | bfb57631f24a |
| #58 | minimax/ga-01-llm-settlement | c634c0c915a1 |
| #76 | minimax/ga-01-money-p0 | 8fb6b76e3bc8 |
| #79 | build/claude/ga-01-r3-unreadable-barrier | 784ea0c78062 |
| #78 | claude/beta-01-20261022 | b0ea55dab5ea |
| #81 | build/claude/ga-03-release-backend | d249dded050c |
| #83 | build/claude/ga-03-ui-e2e | 59e8196f72b4 (база этой ветки) |
Не включены: #86 (frontend MiniMax) и #87 (scope) — по условию Issue frontend не затрагивается. Дрейф HEAD источника = повторная оценка.

## Результаты
Временная интеграционная копия (НЕ публиковалась):  + 7 источников (все слияния CLEAN, конфликтов нет) + эта ветка; HEAD копии 992240c.
| Шаг | Обязательный | Статус | Тесты (всего/упало/ошибки/пропущено) | Код | Сеть | Причина |
|---|---|---|---|---|---|---|
| GA-03: release gate (backend/test_release_gate.py) | да | **PASS** | 34/0/0/0 | 0 | 0 |  |
| N34/N35 и приёмка QA (B1: старый QC не наследуется) | да | **PASS** | 56/0/0/0 | 0 | 0 |  |
| BETA-02: контракт HTTP, перезапуск, резервная копия | да | **PASS** | 6/0/0/0 | 0 | 0 |  |
| BETA-02: fail-closed матрица, токен, гонка | да | **PASS** | 15/0/0/0 | 0 | 0 |  |
| GA-01 рядом с выпуском: неизвестная сумма держит траты (нужен #79) | да | **PASS** | 4/0/0/0 | 0 | 0 |  |
| GA-01: тесты денег (R3, расчёт LLM, граница денег, резервы) | да | **PASS** | 117/0/0/0 | 0 | 0 |  |
| Весь backend pytest | да | **PASS** | 628/0/0/0 | 0 | 0 |  |

Повторный  на той же копии: те же статусы и счётчики по всем шагам (стабильно). Самопроверка гейта:  (вернули B1 — старый QC наследуется изменённым файлом),  (владелец не проверяется),  (нечитаемая сумма принимается за число) — **FAIL, код 1** во всех трёх;  ловит шаг GA-01 рядом с выпуском. На самой ветке без GA-01 (#58/#76/#79 отсутствуют) гейт честно даёт **BLOCKED, код 2** (деньги не проверены, «меньше проверок» не равно «зелёный»).

Первый прогон на копии падал (3 теста денежных случаев): это был дефект самого теста (не изолированы файлы ключей, недопустимый ) — исправлено в , продуктовый код не менялся.

## Что покрыто независимо от  ()
Контракт HTTP и схема ; полный путь с отказом без QC → N34 → N35 → утверждение точного SHA → перезапуск; перезапуск после изменения байтов и новая проверка (решение по старым байтам не воскресает, 2 записи истории); резервная копия SQLite (online backup) + копия библиотеки → решение сохранено,  ok; восстановление без файла ≠ утверждение; повтор QC не меняет хеш и решение; действия выпуска не меняют регистр денег и не вызывают провайдера; матрица fail-closed (неверный/пустой SHA, чужой владелец, нет прав, владелец не настроен, 409 при старой ревизии импорта); машинный токен 403/401; изменение байтов после QC; пропавший файл; 5 параллельных одинаковых утверждений → одна запись; отказ без QC и без файла; GA-01: нечитаемая сумма блокирует траты проекта до и после перезапуска,  200, , провайдер не вызван, выпуск (бесплатный) продолжает работать; старая запись другого проекта его не блокирует.

## Блокеры и NO_GO
- P1 OWNER_AUTH_REQUIRED:  ≠ аутентификация (пароль отложен владельцем).
- P1 GA-01: решения владельца по ручной сверке нечитаемой суммы и приёмка #58/#76/#79 не получены; политика не придумывалась. Ссылки на GA-01-тесты — только существующие; код GA-01 не менялся.
- NOT_RUN: браузерный smoke и frontend Version 6.0.2
tsc: The TypeScript Compiler - Version 6.0.2

COMMON COMMANDS

  tsc
  Compiles the current project (tsconfig.json in the working directory.)

  tsc app.ts util.ts
  Ignoring tsconfig.json, compiles the specified files with default compiler options.

  tsc -b
  Build a composite project in the working directory.

  tsc --init
  Creates a tsconfig.json with the recommended settings in the working directory.

  tsc -p ./path/to/tsconfig.json
  Compiles the TypeScript project located at the specified path.

  tsc --help --all
  An expanded version of this information, showing all possible compiler options

  tsc --noEmit
  tsc --target esnext
  Compiles the current project, with additional settings.

COMMAND LINE FLAGS

--help, -h
Print this message.

--watch, -w
Watch input files.

--all
Show all compiler options.

--version, -v
Print the compiler's version.

--init
Initializes a TypeScript project and creates a tsconfig.json file.

--project, -p
Compile the project given the path to its configuration file, or to a folder with a 'tsconfig.json'.

--showConfig
Print the final configuration instead of building.

--ignoreConfig
Ignore the tsconfig found and build with commandline options and files.

--build, -b
Build one or more projects and their dependencies, if out of date

COMMON COMPILER OPTIONS

--pretty
Enable color and formatting in TypeScript's output to make compiler errors easier to read.
type: boolean
default: true

--declaration, -d
Generate .d.ts files from TypeScript and JavaScript files in your project.
type: boolean
default: `false`, unless `composite` is set

--declarationMap
Create sourcemaps for d.ts files.
type: boolean
default: false

--emitDeclarationOnly
Only output d.ts files and not JavaScript files.
type: boolean
default: false

--sourceMap
Create source map files for emitted JavaScript files.
type: boolean
default: false

--noEmit
Disable emitting files from a compilation.
type: boolean
default: false

--target, -t
Set the JavaScript language version for emitted JavaScript and include compatible library declarations.
one of: es6/es2015, es2016, es2017, es2018, es2019, es2020, es2021, es2022, es2023, es2024, es2025, esnext
default: es2025

--module, -m
Specify what module code is generated.
one of: commonjs, es6/es2015, es2020, es2022, esnext, node16, node18, node20, nodenext, preserve
default: undefined

--lib
Specify a set of bundled library declaration files that describe the target runtime environment.
one or more: es5, es6/es2015, es7/es2016, es2017, es2018, es2019, es2020, es2021, es2022, es2023, es2024, es2025, esnext, dom, dom.iterable, dom.asynciterable, webworker, webworker.importscripts, webworker.iterable, webworker.asynciterable, scripthost, es2015.core, es2015.collection, es2015.generator, es2015.iterable, es2015.promise, es2015.proxy, es2015.reflect, es2015.symbol, es2015.symbol.wellknown, es2016.array.include, es2016.intl, es2017.arraybuffer, es2017.date, es2017.object, es2017.sharedmemory, es2017.string, es2017.intl, es2017.typedarrays, es2018.asyncgenerator, es2018.asynciterable/esnext.asynciterable, es2018.intl, es2018.promise, es2018.regexp, es2019.array, es2019.object, es2019.string, es2019.symbol/esnext.symbol, es2019.intl, es2020.bigint/esnext.bigint, es2020.date, es2020.promise, es2020.sharedmemory, es2020.string, es2020.symbol.wellknown, es2020.intl, es2020.number, es2021.promise, es2021.string, es2021.weakref/esnext.weakref, es2021.intl, es2022.array, es2022.error, es2022.intl, es2022.object, es2022.string, es2022.regexp, es2023.array, es2023.collection, es2023.intl, es2024.arraybuffer, es2024.collection, es2024.object/esnext.object, es2024.promise, es2024.regexp/esnext.regexp, es2024.sharedmemory, es2024.string/esnext.string, es2025.collection, es2025.float16/esnext.float16, es2025.intl, es2025.iterator/esnext.iterator, es2025.promise/esnext.promise, es2025.regexp, esnext.array, esnext.collection, esnext.date, esnext.decorators, esnext.disposable, esnext.error, esnext.intl, esnext.sharedmemory, esnext.temporal, esnext.typedarrays, decorators, decorators.legacy
default: undefined

--allowJs
Allow JavaScript files to be a part of your program. Use the 'checkJs' option to get errors from these files.
type: boolean
default: `false`, unless `checkJs` is set

--checkJs
Enable error reporting in type-checked JavaScript files.
type: boolean
default: false

--jsx
Specify what JSX code is generated.
one of: preserve, react, react-native, react-jsx, react-jsxdev
default: undefined

--outFile
Specify a file that bundles all outputs into one JavaScript file. If 'declaration' is true, also designates a file that bundles all .d.ts output.

--outDir
Specify an output folder for all emitted files.

--removeComments
Disable emitting comments.
type: boolean
default: false

--strict
Enable all strict type-checking options.
type: boolean
default: true

--types
Specify type package names to be included without being referenced in a source file.

--esModuleInterop
Emit additional JavaScript to ease support for importing CommonJS modules. This enables 'allowSyntheticDefaultImports' for type compatibility.
type: boolean
default: true

You can learn about all of the compiler options at https://aka.ms/tsc/ на копии (UI #86 не входит), CapCut и реальный MP4, рабочая SQLite, живые провайдеры, CI с тестами.
- Замечание по среде: каталог  целиком в ; новые файлы добавлены , как прежние .
- Самопроверка: секретов и абсолютных домашних путей в отчётах нет (тест на редактирование + регулярка), сеть закрыта ловушкой, временные папки/worktree удаляются; хеширование ролика ~1 с на синтетических файлах.
