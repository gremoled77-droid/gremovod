# MiniMax Code + Aider: тяжёлый прогон на реальной задаче GremoVOD

- **Date/time and timezone:** 2026-10-20, 03:30–03:52 MSK (UTC+3)
- **Repository root:** `C:\AI_Workflow_Studio` (remote `https://github.com/gremoled77-droid/gremovod.git`)
- **Test worktree:** `C:\AI_Workflow_Studio\.worktrees\minimax-aider-found-footage-20261020-0330`
- **Branch:** `test/minimax-aider-found-footage-20261020-0330`
- **Git base commit SHA:** `40ca333796a686acab4f0261381924eaf6a82276` (HEAD of `experiment/minimax-aider`, отдельный worktree; основное рабочее дерево с чужими незакоммиченными изменениями не трогалось)
- **MiniMax Code version:** CLI `mcode` отсутствует в `PATH`; прогон выполнен запущенным агентом MiniMax Code (MCode, модель `MiniMax-M3.1-Flash`)
- **Aider version:** `aider 0.86.2` (ранее установлен через `uv tool install aider-chat`; не переустанавливался)
- **Python version used for tests:** `Python 3.13.14` из `C:\AI_Workflow_Studio\.venv` (в worktree `.venv` нет — используется интерпретатор основного дерева, тесты поднимают временную БД)
- **Model requested by Aider:** `openai/MiniMax-M3.1-Flash` (weak model тот же)
- **API endpoint domain:** `api.minimax.io` (base URL `https://api.minimax.io/v1`, OpenAI-совместимый режим)
- **Authentication present:** yes — ключ прочитан из локального DPAPI-хранилища и подставлен в процесс Aider как `OPENAI_API_KEY`; значение не печаталось, не передавалось аргументами командной строки, не попало в репозиторий и в журналы
- **Baseline tests:** 242 теста / 0 упавших; process exit code **0** (до изменений Aider)
- **Aider invoked:** yes; exit code **0**; duration **414,6 с** (6,9 мин); 28k токенов отправлено, 21k получено, **$0.02** по тарифу M3.1-Flash
- **Changed by Aider:**
  - `backend/prompt_rules.py` — SHA-256 `125DA361AB5B` → `84488FE83BA5`
  - `backend/test_prompt_rules.py` — SHA-256 `2D6216E4F8C4` → `5FDD5F317514`
- **Untouched (проверено по хешам):** `backend/prompt_profiles.json` (`FF78FC62094E`), `backend/reel_recipes_data.py` (`71EE77B62087`)
- **New tests on pre-change code:** 3 errors + 1 failure, exit code **1** — тесты действительно ловят отсутствие реализации, а не тавтологичны
- **Final tests:** 246 тестов / 246 прошли; process exit code **0** (прогон выполнен независимо от утверждения Aider)
- **Unintended file changes:** none. Единственный побочный артефакт — каталог кэша тегов `.aider.tags.cache.v4/` в корне worktree (untracked, в коммит не попал). История чата и ввода выведены в `%TEMP%`
- **Git commit SHA:** `d2e2386c2d9660b93eee0cd581c4953674d6a213` (`feat(prompt-rules): профиль промпта found-footage` — один коммит с тремя файлами: две правки Aider + этот отчёт). Второй, служебный коммит этой ветки фиксирует результаты публикации.
- **GitHub push:** **success** — `git push -u origin test/minimax-aider-found-footage-20261020-0330` (новая ветка, без force push).
- **PR URL:** **draft PR #40** — https://github.com/gremoled77-droid/gremovod/pull/40 (base `main`, head `test/minimax-aider-found-footage-20261020-0330`, помечен как экспериментальный; не сливать).
- **Token usage / money:** Aider измерил 28k sent / 21k received и **$0.02** за один вызов по официальному тарифу MiniMax M3.1-Flash ($0.15/M input, $0.60/M output). Сторона MiniMax Code в этом прогоне не измерялась. Источник списания (квота подписки M Plan или баланс pay-as-you-go) не проверялся отдельно
- **Problems and remediation:**
  1. `--no-gitignore` в Aider 0.86.2 означает «не добавлять `.aider*` в `.gitignore`», а не «игнорировать `.gitignore` при выборе файлов». Добавлен `--add-gitignore-files` — иначе часть путей недоступна.
  2. `tools/` закрыт правилом `.gitignore` (строка 30), поэтому файлы в `tools/` требуют `git add -f`. В этой ветке таких файлов нет, правило не менялось.
  3. `git commit` в этом репозитории печатает безобидное `task 'geometric-repack' failed: Permission denied` — фоновое обслуживание Git, на коммиты не влияет.
  4. Побочный эффект неинтерактивного режима: Aider сам предложил и сам выполнил команду проверки (`Run shell command?` → EOF → ответ по умолчанию «да»). Для проверяемости это плюс, но в рабочем сценарии команду запускает человек.
- **Verdict:** **PASS**
- **Recommended next step:** задача из бэклога закрыта на уровне системы правил. Следующий шаг — **проводка стиля в API** (сейчас параметр `prompt_style` не вызывается ни одним маршрутом, то есть профиль пока недостижим из приложения): `backend/main.py` (`compose_preview`, `compose`) и `backend/native_chat.py` должны принимать явный выбор стиля, иначе профиль останется мёртвым кодом. Это решение владельца: где в интерфейсе живёт переключатель «found-footage». После этого — второй прогон Aider и сборка frontend.

---

## Что именно было задано Aider

Задача взята из бэклога владельца, `TODO.md:54`:

> «Профиль промпта "found-footage" в `backend/prompt_rules.py`: WORLD LOCK, биты с таймкодами, блок MANDATORY/NEGATIVE».

Текст задания (полностью) лежит в `%TEMP%\gremo-found-footage-task.txt` и сводится к семи пунктам: добавить профиль с тремя обязательными блоками; выбирать его явно, а не эвристикой; **явно разрешить конфликт** с действующими правилами «one coherent shot / one camera move / exactly one camera motive»; писать по-английски в регистре остальных правил; поднять `RULES_VERSION` и обновить его тест; добавить тесты, падающие на старом коде; не трогать другие файлы и не коммитить.

Конфликт был заложен намеренно: найденный-футаж с битами по таймкодам допускает несколько дубов внутри одного ролика, тогда как `PILLARS_VIDEO` и `VIDEO_RULES` требуют одного связного дубля и одного движения камеры. Умение разрешить это без противоречия — главная содержательная часть задачи.

В контекст Aider намеренно отданы четыре файла: `backend/prompt_rules.py`, `backend/prompt_profiles.json`, `backend/test_prompt_rules.py` и `backend/reel_recipes_data.py` (последний — только как источник домашнего формата; менять его запрещено, и Aider его не тронул).

## Что Aider сделал

Диф — 51 строка в двух файлах, ничего лишнего:

**1. Новый блок правил** (`backend/prompt_rules.py`):

```
FOUND-FOOTAGE PROFILE. Apply only when explicitly selected.
WORLD LOCK: State the fixed location, lighting, geometry and cast, including the exact number of
heroes and other principal characters. State what remains unchanged throughout the video. By
default, state that there are no cuts or time jumps. Derive the lock only from the brief and actual
supplied references; never invent characters, props or references.
TIMECODED BEATS: Use sequential contiguous intervals in the exact form "0-3s: ...". Cover the full
requested duration from 0s to the end with no gaps or overlaps, and describe the visible action in
each interval in chronological order. Treat each interval as a timed part of the recording, not
automatically as a cut. Keep every take continuous. If several takes are explicitly requested, make
only those requested take boundaries explicit and invent no other cuts or time jumps. Treat this as
the explicit exception to the video-wide one-coherent-shot, one-principal-action, one-camera-move and
one-camera-motive defaults: apply those limits within each continuous take, not across the whole
video.
MANDATORY/NEGATIVE: End with two labelled blocks: "MANDATORY: ..." and "NEGATIVE: ...". List what
must be visible in MANDATORY and what must not appear in NEGATIVE. Derive both blocks only from the
brief and actual supplied references. Use only actual supplied reference indexes; never invent
entities, props or references.
```

**2. Механизм выбора** — обратно совместимый и fail-fast:

```python
def system_rules(spec, prompt_style=None):
    if prompt_style is not None and prompt_style!='found-footage':
        raise ValueError(f'Unknown prompt style: {prompt_style}')
    if prompt_style=='found-footage' and spec['kind']!='video':
        raise ValueError('The found-footage prompt style requires a video model')
```

Профиль дописывается в конец, после модельного, — так модельные правила остаются приоритетными. Старый вызов `system_rules(spec)` даёт **побайтово тот же** результат, что и до правки.

**3. Версия** `RULES_VERSION` `2026-10-17.1` → `2026-10-20.1`, тест версии обновлён синхронно.

**4. Тесты** (`backend/test_prompt_rules.py`, +4): профиль применяется только по явному запросу; не просачивается в другие модели; требует видеомодели; контракт вывода и правила пяти столпов сохраняются.

### Доказательство, что тесты не тавтологичны

Старая реализация `prompt_rules.py` (из HEAD) была собрана в изолированный каталог вместе с новым файлом тестов:

```
test_found_footage_profile_applies_only_when_explicit   ... ERROR  (TypeError: system_rules() got an unexpected keyword argument 'prompt_style')
test_found_footage_profile_keeps_output_contract_and_pillars ... ERROR  (то же)
test_found_footage_profile_requires_video_model            ... ERROR  (то же)
test_version_bumped                                        ... FAIL  ('2026-10-17.1' != '2026-10-20.1')
Ran 8 tests — FAILED (failures=1, errors=3), exit code 1
```

С новой реализацией — `Ran 246 tests ... OK`, exit code 0.

## Замечания для ревью (не блокеры)

1. **Профиль лежит в `prompt_rules.py`, а не в `prompt_profiles.json`.** Формально TODO требует именно `prompt_rules.py`, и доменно это верно: `PROFILES` — это профили *моделей* по `task_type`, а found-footage — профиль *стиля*. Но если владелец захочет и дальше расширять стили, место для стилевых профилей стоит завести отдельно.
2. **Параметр пока никуда не передаётся.** `prompt_style` не вызывается ни одним маршрутом — до проводки в API это фактически недостижимый из приложения код. Это осознанно оставлено следующим шагом, а не сделано молча.
3. **«По умолчанию — без склеек» против «допускаются несколько дубов».** Правило сформулировано как «по умолчанию без склеек и скачков времени; если в брифе явно просят несколько дубов — только эти границы». Это разумное прочтение, но его стоит подтвердить у владельца: возможно, для found-footage «несколько дубов» должно быть правилом по умолчанию, а не исключением.
4. **Формат таймкодов** задан как `0-3s:` — в UI рецептов тот же формат записан как `0–3 с` (с неразрывным дефисом и кириллической «с»). Для LLM-вывода это не важно, но если строки будут показываться пользователю, стоит свести к одному виду.

## Чего этот прогон не доказывает

Это один прогон на одной задаче в одном модуле. Он показывает, что Aider способен взять реальный пункт бэклога, понять устройство системы правил, разрешить заложенное противоречие, написать правила в доменном регистре, обновить версию и написать нетавтологичные тесты — и что весь набор из 246 серверных тестов остаётся зелёным. Он не показывает качество работы на больших многофайловых фичах и не заменяет ревью владельца.
