# Матрица ответственности — GremoVOD

Подтверждённая организационная схема на 19.10.2026. Проверяй `AGENT_BUILD_MANUAL.md` и `STATUS.md`; само наличие этого документа не создаёт GitHub branch protection или CODEOWNERS с реальными аккаунтами.

| Действие / каталог | Codex | Claude Code | Argon | Владелец |
|---|---|---|---|---|
| `docs/specs/**`, `nodes.json`, `VALIDATION.json` | **Owner/Reviewer** | Read/Propose | Read | Consulted |
| `db/**`, `backend/**`, денежные и session API | **Required Reviewer** | **Builder** | No write | Approves actual spend |
| `scripts/**`, `tools/**`, FFmpeg/Whisper | Reviewer | **Builder** | Integrates by stable API | Consulted |
| `workflows/**`, `integrations/n8n/**` | Required Reviewer | Builds contract stubs only when assigned | **Builder/Tester** | Owner decision |
| `prompts/**`, `skills/**` | Schema/QA Reviewer | **Builder** | Read/use | Canon/voice approval |
| `canon/**` | Read/review | Read | Read | **ONLY owner approves** |
| `.github/**`, `STATUS.md`, `AGENTS.md`, `CLAUDE.md` | Required Reviewer | Assigned single editor | Assigned single editor | Approval if rights change |
| `frontend/**` | Reviews contracts | Builder if assigned | Only if assigned | UI decisions after pilot |
| `tests/**` | Determines coverage | Backend/FFmpeg tests | n8n mock tests | Acceptance |

**Shared paths are explicitly leased per task** in `STATUS.md` prior to writes. Domain owner != exclusive filesystem permission; code review before merge matters more than a directory label.

## Проверка перед push

- Видишь чужие незакоммиченные изменения? **STOP**. Не делать reset, checkout, auto-merge.
- Правишь файл чужой зоны? Создать Codex-approved handoff с конкретными путями.
- Создаёшь workflow JSON? Проверить `active:false`, нет credentials и платных API, родительские ссылки переназначены только в изолированном тесте.
- Изменяешь бизнес-правило или канон? Зафиксировать `CODEX_DECISION_REQUIRED`, никаких silently merged assumptions.
- Результат теста относится только к действительному окружению: GitHub FFmpeg mock ≠ Windows live worker; JSON manifest ≠ доступный MP4; LLM PASS ≠ реальная видеоприёмка.
