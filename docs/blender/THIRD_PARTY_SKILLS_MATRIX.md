# Матрица сторонних Blender-навыков и дополнений

**Снимок состояния:** 2026-10-26. Установленные версии проверялись локально; «установлено» не означает, что пакет был запущен или совместимость подтверждена.

| Источник / компонент | Версия или ревизия | Установка и известные сведения | Проверка / ограничение |
|---|---|---|---|
| [EL4CTEO/blender-skills](https://github.com/EL4CTEO/blender-skills) | Git SHA `71d031dab8bc6729504d11a78cbe91945401045f` | 22 навыка скопированы в проектные `.agents/skills` и `.claude/skills`; локальная копия репозитория находится в `C:\Users\BLOWKA\AI-tools\blender-skills` | Для всех 25 навыков (22 EL + 3 Expert) хеши 107 сопоставленных файлов в двух каталогах совпали. Лицензию сверять с закреплённым SHA перед распространением; этот набор не вендорится в GremoVOD |
| [edemaistre/blender-expert-skills](https://github.com/edemaistre/blender-expert-skills) | Точная установленная ревизия не зафиксирована в аудиторской записи | Выборочно установлены `blender-expert`, `blender-previs-storyboard`, `blender-hard-surface` | Полная ревизия и лицензия остаются UNKNOWN. Маршрутизатор ожидает другие специалисты полного набора; частичный набор не подтверждает его полную работоспособность. Возможны совпадения с EL-навыками |
| [ifBars/blender-agent-studio](https://github.com/ifBars/blender-agent-studio) | Plugin cache `0.6.4` | Плагин присутствует в Codex cache | CLI диагностика с явным путем Blender доступна; Live MCP не запускался и не включался |
| Mustard Simplify | `2026.3.1`, manifest: min Blender `4.3`, GPL-3.0-or-later | Установлен и включён в профиле Blender 4.5 пользователя | Регистрация дополнения проверена в отдельном фоновом процессе; поведение на `.blend` и выигрыш скорости рендера не измерялись |
| Blender Model Optimizer | `2.1.0`, min Blender `4.2`, manifest MIT; upstream licensing discrepancy | Установлен и включён в профиле Blender 4.5 пользователя | Регистрация проверена; лицензия требует сверки перед распространением. Изменение защищённой геометрии недопустимо без отдельного сравнения хеша/топологии |
| Blender Asset Validator | `1.0.0`, min Blender `4.0`, upstream MIT | Установлен в пользовательских addons Blender 4.5 | Расширение загружено для фоновой проверки; полноценный отчёт на пилотной сцене должен быть приложен отдельно |
| `blender_agent_studio_live.py` | локальный файл, версия отдельно не установлена | Файл присутствует, дополнение не включено | Не активировать в рамках локального headless прогона |

## Правила установки и лицензирования

Пакеты навыков остаются внешними зависимостями пользователя и не копируются в репозиторий приложения. Установка сохраняет уже существующие одноимённые каталоги; скрипт `EL4CTEO/blender-skills/install.ps1` не использовать как есть: он может перезаписывать или удалять каталоги. Проверять SHA и LICENSE именно установленной ревизии, фиксировать URL, дату, версию, лицензию и результат проверки. Для Expert Skills лицензия и точная ревизия пока не подтверждены, поэтому дальнейшее распространение их содержимого блокируется до сверки.

Аддон, доступный локально, не равен smoke-tested сцене. Значения GPL/MIT выше относятся к указанным манифестам/репозиториям по выполненной инвентаризации, не являются юридическим заключением. Не применять автооптимизаторы к утверждённым мешам: перед и после операции сравнивать хеши геометрии, координат, трансформов и размеры.

## Проверенные каталоги и статусы

Все 25 навыков: `INSTALLED` в `C:\AI_Workflow_Studio\.agents\skills` и `.claude\skills`; индивидуальные имена/SHA перечислены в `SKILL_INSTALL_INVENTORY.json`. Render compatibility: `BLOCKED_G1`, для заявленных 5.2 API на 4.5 — UNVERIFIED.

BAS: `INSTALLED`, `C:\Users\BLOWKA\.codex\plugins\cache\blender-agent-studio\blender-agent-studio\0.6.4`. Live MCP: `BLOCKED`, не включён.

MustardSimplify: `INSTALLED`, `C:\Users\BLOWKA\AppData\Roaming\Blender Foundation\Blender\4.5\extensions\user_default\MustardSimplify`. Model Optimizer: `INSTALLED`, соседний каталог `blender_model_optimizer`. Asset Validator: `INSTALLED`, `C:\Users\BLOWKA\AppData\Roaming\Blender Foundation\Blender\4.5\scripts\addons\blender_asset_validator`. Для всех трёх registration check не доказывает render acceptance; scene/addon benchmark `NOT_MEASURED`.
