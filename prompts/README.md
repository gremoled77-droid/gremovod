# GremoVOD — реестр системных промптов (до утверждения Codex)

Эта папка зарезервирована для **Claude Code**. Пока реальные role-specific prompts A0–A8 **не экспортированы** и никакие внешние скиллы не объявлены установленными.

Что реально лежит в репозитории: `skills/gremovod-stage-idea`, `skills/gremovod-screenplay`, `skills/gremovod-dialogue-subtext`, `skills/gremovod-script-rewrite`, `skills/gremovod-character-comedy`, `skills/gremovod-series-development` и киноязыковые навыки. Подключать только *проверенные файлы*, с путём+коммитом+SHA и доступом через S02 read-only.

Предложенные названия `grem`, `generate-fresh-ideas`, `get-more-perspectives`, `match-my-writing-style` отсутствуют в подтверждённом каталоге установленного проекта: можно использовать идеи как редакторские техники, **нельзя** притворяться, что это вызываемые инструменты или утверждённый авторский стиль.

Первый пакет для Claude после ревью Codex: `A1_writer_v1.md`, `A2_director_v1.md`, `A6_requirements_v1.md`, `A7_canon_v1.md`, `A8_craft_v1.md`. Для каждого указать роль, `skill_bundle_hash`, версию канона, формат JSON ответа, запрещённые допущения и тестовые случаи. **Не создавать эти файлы как «готовые», пока source и канон не утверждены.**

Озвучка героев и право на референсы: только `canon/**` утверждённый владельцем; здесь не хранить чужие голоса, медиа и ключи.
