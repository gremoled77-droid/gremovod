# Skill Sync: подготовка без записи в n8n

`scripts/n8n_skill_sync.py` создаёт только JSON-план из **полного commit SHA** GitHub,
уже полученного через обычный `git fetch`. Читает git blobs; незакоммиченные файлы
не попадают в пакет. Источник назначений — agent-manifest того же commit.

```powershell
python -X utf8 scripts/n8n_skill_sync.py --commit <40-hex-sha> --bindings <local-bindings.json>
```

Bindings — локальный JSON-массив. Первое исследование допускает `[]`.
Каждая подтверждённая связь имеет поля:

```json
{
  "agent_id": "existing-agent-id",
  "name": "gremovod-stage-storyboard",
  "skill_id": "existing-skill-id",
  "content_sha256": "last-accepted-package-hash",
  "baseSkillHash": "fresh-remote-skill-hash",
  "baseConfigHash": "fresh-remote-config-hash"
}
```

Не записывать вымышленные IDs/hashes в реестр. Текущий inventory содержит agent IDs,
но не skill IDs/hashes. Сначала потребуется read-only inventory живого n8n и
подтверждённое сопоставление; существующий skill нельзя считать отсутствующим.

План:

- `bind_existing` — ID не сопоставлен; никакого create/upsert без существующего ID.
- `noop` — тот же SHA256 пакета; повторное создание запрещено.
- `update_draft` — найден тот же skill_id и concurrency hashes; **предложение** обновить черновик.
- `blocked` — отсутствующая ссылка/неподдерживаемый header/нет concurrency hashes.

Пакет включает SKILL.md, все Markdown references/** и рекурсивные локальные
Markdown-ссылки в skills/docs. Хеш учитывает имена файлов и содержимое: изменение
одного reference тоже обновление. Symlinks, файлы вне skills/docs и немаркированные
типы не импортируются. Отсутствующая ссылка блокирует пакет. Внешние URL остаются
ссылками и не скачиваются. Навыки из сторонних репозиториев исключаются из плана:
они требуют своего отдельного проверенного источника.

Поддерживается консервативный профиль frontmatter репозитория: однострочные name
и description. Это не универсальный YAML parser; сложный YAML блокируется.
Пакет не выполняет инструкции и не проверяет художественную пригодность навыка.

Будущий исполнитель должен повторно прочитать draft n8n, сверить актуальные
baseSkillHash/baseConfigHash, показать diff, обновить **тот же skill_id**, проверить
draft и только после успешной проверки сохранить новый content_sha256 в bindings.
При conflict — перечитать и пересмотреть diff; не создавать замену/дубликат.
Адаптацию repo-relative references к фактическому формату пакета n8n нужно проверить
отдельно: этот план содержит file hashes, не deployment payload.
Публикация — отдельное действие владельца. Живой API n8n этим скриптом не вызывается.

## Аудит исходного inventory a06ab54

Проверен локальный план для 12 назначений из этого репозитория: 1 `bind_existing`,
11 `blocked`. Причины: ссылки на `frontend/src/StageNav.tsx` (код вне формата пакета),
отсутствующий `docs/CAMERA_MOVEMENT_COURSE_2026-10-16.md` и приватный
`projects/GremoVOD/КИНО_И_ПРОИЗВОДСТВО.md`. Это список препятствий переносу, а не
успешная синхронизация. Нужна отдельная адаптация ссылок/справочников перед обновлением
n8n. Планировщик намеренно не читает и не переносит приватный projects.
