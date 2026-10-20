# Git, ветки и кандидатный SHA

Снимок GitHub на 21.10.2026 (МСК): **68 remote-веток, 33 открытых PR**. Проверены также 58 локальных веток и реестр 44 worktree. Полная семантическая приёмка всех патчей — PARTIAL.

- main: `4b1c1b297c0dd1966e3376ece213722210fdee29`.
- mavis/work: `57cac59ca790d380d8e68f2f6db82674ca142e92`.
- `git rev-list --left-right --count main...mavis/work`: **0 / 129**.
- Аудиторская ветка создана в независимом clone, исходные worktree и их index не менялись. Fetch обновлял только refs аудиторской копии; force-push не выполнялся.

## Почему база PR — mavis/work

В ней объединены P0/Astra fixes, общий ledger media+LLM+P0+n8n, Producer и N34/N35. Это наиболее полная из предметно просмотренных интеграций, но не доказанная самая проверенная сборка всех веток. main отстаёт; Codex beta и QA sandbox расходятся по UI/контрактам. Автоматическое слияние исключено.

## Значимые разработки и пересечения

| Ветка / SHA | Что есть и что нельзя потерять | Рекомендация |
|---|---|---|
| minimax/p0-astra-fixes @89dfd11 | уже ancestor mavis; P0 signing/evidence/overrun/reconcile | не повторять merge/реализацию; отдельно проверить реальный dispatch |
| minimax/MM-001-llm-ledger @f9f810f | локальная, 2 файла; valid_tokens/actual_cost и негативные tests на старой базе | адаптировать validator/tests к GA-01; не копировать весь llm_guard |
| minimax/mm-002-dispatch @07a2c51 | только MM-002_REVIEW.md от 89dfd11, реализации нет | старое ТЗ на общий счётчик частично устарело |
| minimax/paid-llm-guard @26ef242 | локальная альтернативная LLM-охрана, 7 файлов от старого main | сохранить negative tests, сравнить с нынешним provider/reserve, не переносить main целиком |
| minimax/skill-catalog @5e64c69 | локальный каталог/проверка ссылок/tests, 2 коммита сверх mavis | read-only review, не писать каталог заново; runtime integration ещё не доказана |
| codex/beta-generation-fixes @e316bf5 | 3 commits, 89 changed files от merge-base: GenerateButton/WaitingTray/imageJobs/imageRoutes/screens | отдельный UI-review; конфликтующая форма App/StageNav и старые компоненты |
| codex/work @2d4d94e | Story Plan, shot direction, media viewer и исследования; 29 patch-distinct commits | сравнить существующие story_plan/StoryPlanBoard по поведению, не считать все 29 новыми функциями |
| claude/work @ee90238 | 29 patch-distinct commits относительно mavis, исторические реализации и исследования | предметный review, не blanket merge и не удаление |
| integration/n8n @ce23d7e | альтернативная QA/skills история, 57 patch-distinct commits | сверить текущий qa_reviews/evidence; live deployment UNKNOWN |
| feature/qa-text-audit-fixes @3979390 | qa_text_precheck + app/security/sandbox tests, 77 patch-distinct commits; полного модуля в mavis нет | отдельный text-only QA кандидат после auth/spend review; не FINAL_MEDIA |
| autopilot/work @aeae111 | локальный аудит main@4b1c1b2 и .autopilot tooling; runtime fixes отсутствуют | старый исследовательский отчёт; его числа/coverage не являются текущими доказательствами |
| research #50–53 | только новые исследования поверх mavis | просмотр предложений; не approved requirements |

`git cherry +` означает различие патча, а не доказанную уникальность функции. Для названных веток сравнивались ancestry, stat, commit subjects и целевые модули; все строки старых diff целиком не приняты.

## Полный remote-инвентарь

Колонки: **left / right** — commits только в базе / только в ветке. Правый 0 против mavis подтверждает включённую ancestry, но не разрешает удаление. Для остальных веток вне предметного списка выше выполнен inventory, не полная code review.

| Ветка | SHA | main → ветка | mavis → ветка |
|---|---|---|---|
| `chatgpt/n8n-web-skill-sync-20261019` | `81a9c81d67b1d62f8c068db088849ad5e24abb04` | 21 / 2 | 150 / 2 |
| `claude/cli-skill-global-setup-56ca43` | `6733cd9c3bc6aade9ed9872e237b018ba69c0e41` | 29 / 0 | 158 / 0 |
| `claude/convert-to-skill-10d251` | `89d189627bbc19b259189073d609fcc0b37b14e1` | 33 / 1 | 162 / 1 |
| `claude/cyberpunk-neon-street-image-8e3bd6` | `aa56a66f1e722c76807afd666f19c58d6407017c` | 33 / 2 | 162 / 2 |
| `claude/design-loop-skill-ea56fd` | `cce9a9ddb6bff055310e4ae724991e46da8b9ff5` | 33 / 1 | 162 / 1 |
| `claude/exciting-elbakyan-156f4b` | `ab1214f157118e86827705f3cf91ceea69b32108` | 72 / 0 | 201 / 0 |
| `claude/generate-command` | `08597c1a85e8007aa5ea0cab2d9428e52c288649` | 118 / 3 | 247 / 3 |
| `claude/mckee-storytelling-skills-353bdc` | `c50886006fb995297256a1b0a69d288c42d14282` | 76 / 1 | 205 / 1 |
| `claude/motion-frameworks-skills-9f0e7f` | `f7476e4ef5e43a91ff60c7142e192a6fc2b7879d` | 33 / 1 | 162 / 1 |
| `claude/motion-tools-docs` | `5474a70bac7f4f39356cbdbcdbda7b7dbdd126d6` | 21 / 0 | 150 / 0 |
| `claude/project-audit-speedup-plan-937d17` | `7cfb99ec916a4894eb637ef7c3c2657635d958f1` | 33 / 10 | 162 / 10 |
| `claude/prompts-reels-analysis-b430a7` | `681c39dfc78e5c663a2f83154cf0eedd72a7b2bb` | 133 / 0 | 262 / 0 |
| `claude/strange-lederberg-3deff8` | `98c7c267da5401fc7eddce8e1849f871e4e2f3ee` | 108 / 0 | 237 / 0 |
| `claude/video-montage-skill-analysis-0d8f95` | `8a718cb0088bd2f790ea0795998cdbb9b39c709a` | 33 / 1 | 162 / 1 |
| `claude/work` | `ee9023808efee29ab4209c704ab9e2b3e0f4c1fb` | 55 / 33 | 184 / 33 |
| `claude/workflow-redesign` | `916887095a880e195f092e128dccd9d91868a70a` | 33 / 4 | 162 / 4 |
| `codex/acting-motion-sound` | `4e08ac2aff8f698e2f29332c3bb898879fceea9c` | 5 / 30 | 134 / 30 |
| `codex/acting-notes` | `d46fd81b8adbac8c4db9c32c7a79ffd385d657eb` | 5 / 31 | 134 / 31 |
| `codex/beta-generation-fixes` | `e316bf5b256dfd92030630a03c85f04cffaae2f8` | 33 / 3 | 162 / 3 |
| `codex/claude-checkpoint-2026-10-18` | `88d727b53de6b85ddc6e9b9ba21df655d3d3396a` | 21 / 1 | 150 / 1 |
| `codex/env-audit-20261020` | `d0a0911a209c4f9b22cfc2cf8ceb701cf8b91cd8` | 5 / 2 | 134 / 2 |
| `codex/n8n-api-contract` | `cbecc4acb205da503ca74566f72bd1d5cb48d52e` | 21 / 8 | 150 / 8 |
| `codex/n8n-full-production-spec-20261019` | `cafcbc66f01a2a0be11ea64063a3bd5a473629d7` | 5 / 1 | 133 / 0 |
| `codex/p0-fixes-20261019` | `fc05cafee9e835cbbc49aff73e50520ba638420e` | 5 / 94 | 40 / 0 |
| `codex/review-opus-audit-001` | `ee50fb83eff018346f593c2468750d9cd13ef6d1` | 5 / 6 | 134 / 6 |
| `codex/skills` | `3ae8e452b5cc786bc15d9c83b80bdb7a6f0dee07` | 191 / 1 | 320 / 1 |
| `codex/studio-demo-2026-10-18` | `e84a8f20d0b94672acdfa54c61d4efdf23ff0b31` | 21 / 19 | 150 / 19 |
| `codex/work` | `2d4d94e2181b8fa0b293d5f76b07b78c8d24ec76` | 118 / 31 | 247 / 31 |
| `coordination/agent-roles-handoff-20261019` | `928745552553537f11b16e0fdb568a7654e6cc35` | 5 / 91 | 43 / 0 |
| `docs/aider-n8n-argon-pilot-20261019` | `edd5ffb9c3d9d616237566324c06c85c0f13a409` | 5 / 2 | 134 / 2 |
| `docs/argon-minimax-one-shot-20261019` | `85266bbd6352f6c737b52a09c9c28c412f543e98` | 5 / 3 | 134 / 3 |
| `docs/ed-hooks-acting-director-20261019` | `840f6bd3f72c8bb4fbbf6d4f5ace73bfffda3e9d` | 17 / 16 | 146 / 16 |
| `docs/opus-audit-001` | `998ea461dda63312b2c2ddca47317954b9b59643` | 5 / 5 | 134 / 5 |
| `docs/sound-design-beauchamp-2026-10-19` | `e9a4583c269ec8428a2e03a0439847ab9fee7785` | 21 / 4 | 150 / 4 |
| `docs/williams-motion-acting-20261019` | `5cd35b1f1fb327f2284ebc509ee49a0483edfb53` | 17 / 6 | 146 / 6 |
| `experiment/beta-gateway-first-20261019` | `7e07f684cf89bc1b03f595fc278241c9c8a925a3` | 5 / 10 | 134 / 10 |
| `experiment/manual-argon-review-20261019` | `25b7aa6a6a1ce6bf83d8f4ecade309da5cc718c9` | 5 / 4 | 134 / 4 |
| `experiment/minimax-coder-20261019` | `357ff1e82530bef9844425060243526a918fb409` | 5 / 1 | 134 / 1 |
| `experiment/minimax-kie-argon-bridge-20261019` | `0ac4e916e274b4c75fde75edc1ddd0d5a3e376c1` | 5 / 6 | 134 / 6 |
| `experiment/minimax-kie-argon-bridge-impl-20261020` | `b3183d28a0e22d5414ab7eef70d62543aa991dfa` | 5 / 16 | 134 / 16 |
| `experiment/minimax-observability-20261020` | `051ab3a1182c1ed954b53c9b64f85e8195dbcc91` | 5 / 10 | 134 / 10 |
| `feature/aider-minimax-20261020` | `ec948d2cf87c85b96a54b2884d5c674f5e74e70e` | 5 / 5 | 129 / 0 |
| `feature/minimax-m3-1-flash-20261019` | `c78a94956aee7a6521d7ad882a32d16e69e89ab1` | 5 / 2 | 134 / 2 |
| `feature/n8n-astra-contract-hardening-20261019` | `cb3f1dc376ee925a0ee0c61432cb3e52615a9b31` | 5 / 35 | 99 / 0 |
| `feature/p0-studio-foundation-20261019` | `5206dccda5fa47ad84d3b3d4932297b97b46a33f` | 5 / 67 | 67 / 0 |
| `feature/photo-editor-spec-20261019` | `f02806ee298ffc316c4f700753227193252fdbbe` | 5 / 1 | 134 / 1 |
| `feature/qa-text-audit-fixes-20261019` | `397939027984fef240bc80ee16d651d9996f27a0` | 21 / 77 | 150 / 77 |
| `feature/qa-text-precheck-sandbox-20261019` | `b4b04a763cfa5a90903703faa9a716368f12d383` | 21 / 63 | 150 / 63 |
| `integration/n8n` | `ce23d7e6ed622abdef29f5bc9625b0f25a6a2f77` | 21 / 57 | 150 / 57 |
| `main` | `4b1c1b297c0dd1966e3376ece213722210fdee29` | 0 / 0 | 129 / 0 |
| `mavis/p0-merge-trial` | `d24f3506b9c1c0dc97406f65f6d6531bb810e122` | 0 / 128 | 1 / 0 |
| `mavis/preserve-prod-skills` | `d9c4ac68679e5df927d5b88b8fe74a44913412a0` | 0 / 27 | 103 / 1 |
| `mavis/work` | `57cac59ca790d380d8e68f2f6db82674ca142e92` | 0 / 129 | 0 / 0 |
| `minimax/backend-production-skills-20261020` | `398937442e0264f3628930aab708ab16812ad678` | 5 / 104 | 37 / 7 |
| `minimax/llm-gateway` | `1d6b53adec0a51c1b4aeaa5fc3b1872e7099b616` | 0 / 4 | 129 / 4 |
| `minimax/money-ledger-20261020` | `f92dc5ae404ae45a1e725955a3822d19061090cd` | 0 / 12 | 123 / 6 |
| `minimax/n8n-scenario-dispatch-20261020` | `d88349bbbda5f86718c6fa386b3141061da3dde8` | 0 / 27 | 103 / 1 |
| `minimax/p0-astra-fixes-20261020` | `89dfd11269e231a2e6dc446f768b4bdcd3e6d02e` | 5 / 97 | 37 / 0 |
| `minimax/p0-authz-core` | `556f406dfafdfdf1fed602024c4352af3668c6f8` | 5 / 95 | 40 / 1 |
| `minimax/p0-budget-authz` | `c082829b11b968965600bdaf87c137b1485a0fa2` | 5 / 97 | 39 / 2 |
| `minimax/producer-model-picker-20261020` | `61f9559e2b9ba2e2aea88f3fdba5f3711eb27eb9` | 0 / 27 | 103 / 1 |
| `research/channel-business-model-20261020` | `ffe1317610d589051b2852c0e9744e33671d44b5` | 0 / 133 | 0 / 4 |
| `research/gemini-ladybug-workflow-20261020` | `e2f9f95ed3df67c0db2b2a64b0a7cfbf5f623c0a` | 0 / 133 | 0 / 4 |
| `research/production-economics-2026-10-20` | `7898b6f3c89dd0eb47d9f9a58f03f20ea2d678bf` | 0 / 1 | 129 / 1 |
| `research/story-chain-scepka-20261020` | `23a83f251a63143cfa37f5530ee4f170931e5e2a` | 0 / 132 | 0 / 3 |
| `research/video-editing-master-prompt-20261020` | `3a9cf18a4b6d29b8ad518a2491e5697b8fca984b` | 0 / 131 | 0 / 2 |
| `test/minimax-aider-found-footage-20261020-0330` | `af0c26d34a3e43c8ca7a67fd64783cfb4d57d8f8` | 7 / 2 | 136 / 2 |
| `test/minimax-aider-smoke-20261020-030447` | `2a8e914de92a53b993453bf874136157d7d4998a` | 7 / 2 | 136 / 2 |

## Локальные refs, отличающиеся от GitHub

| Ветка | SHA | Состояние |
|---|---|---|
| `autopilot/work` | `aeae111fa104ca6c4cbd02178d9bd0e3e89fd7f5` | Имя отсутствует в remote |
| `backup/pre-rebuild-20261019` | `80a8b4796ad76ebc068df68feb0bdd422f1e38c4` | Имя отсутствует в remote |
| `claude/brown-cinematography` | `ef113d80af4557f677a40dc2769c1ff9a444ebd1` | Имя отсутствует в remote |
| `claude/cli-skill-global-setup-56ca43` | `18131a73c0b3529265cc683aa1f6ac7f0b6f9a83` | SHA отличается от remote |
| `claude/eager-neumann-2f99a7` | `1043b864c4047d8276e1591fb352fd011b96aa01` | Имя отсутствует в remote |
| `claude/gracious-joliot-e1b85a` | `2d8ce52db75b5700f9fec1f363eba531f7b74864` | Имя отсутствует в remote |
| `claude/grem-graham-development-23563d` | `4dcf3f7b004932dd5af7eb528507bd3582aaebc1` | Имя отсутствует в remote |
| `claude/gremovod-design-system-27a093` | `2d8ce52db75b5700f9fec1f363eba531f7b74864` | Имя отсутствует в remote |
| `claude/gustavo-mercado-cinema-skills-35b2e1` | `0069bed56b2fedcaec76edf2bf5f5d370e4ecfa1` | Имя отсутствует в remote |
| `claude/mckee-action` | `7f08cf54284e207cee0c0f694d89be761dddee6a` | Имя отсутствует в remote |
| `claude/project-audit-speedup-plan-937d17` | `26c7e1e5b53fa32ce4706978a1cedcb5c1c0415a` | SHA отличается от remote |
| `claude/prompts-reels-analysis-b430a7` | `7f1d0daad88a3ab4dc08034055fd6b4d50283647` | SHA отличается от remote |
| `claude/recursing-haibt-8b3a25` | `659bb27853b0bccb1c54bc3fe759ad5e536418e5` | Имя отсутствует в remote |
| `claude/seger-script-rewrite` | `cea6df534c32d54f0978cb88b5ca1395dd0b225d` | Имя отсутствует в remote |
| `claude/snyder-save-the-cat` | `5fe7e11f1a215206537aa597918062bf8845c337` | Имя отсутствует в remote |
| `claude/stockman-practical-video` | `355c737cd111d4c8cf4f1a3cd0009454c6b8958c` | Имя отсутствует в remote |
| `codex/qa-text-audit-20261019` | `6a6a11becc6bbd014fdbb1bda7fc2fa473b9c345` | Имя отсутствует в remote |
| `codex/story-board-release` | `714bef056797811aaffb34c4de65a8621cd35e83` | Имя отсутствует в remote |
| `experiment/minimax-aider` | `40ca333796a686acab4f0261381924eaf6a82276` | Имя отсутствует в remote |
| `fix/astra-aider-20261020` | `40ca333796a686acab4f0261381924eaf6a82276` | Имя отсутствует в remote |
| `fix/astra-audit-20261020` | `89dfd11269e231a2e6dc446f768b4bdcd3e6d02e` | Имя отсутствует в remote |
| `integration/n8n` | `a06ab54acf94ce420f681270443f00a0ef276103` | SHA отличается от remote |
| `main` | `40ca333796a686acab4f0261381924eaf6a82276` | SHA отличается от remote |
| `minimax/MM-001-llm-ledger` | `f9f810f1428c5c594d4f1f356b4d56d6bf7f64da` | Имя отсутствует в remote |
| `minimax/mm-002-dispatch-20261020` | `07a2c51a765ebd2eac5a3a1bc1047a871ebb49b0` | Имя отсутствует в remote |
| `minimax/paid-llm-guard` | `26ef2428b407c7b10a80d66fc298f1150693fd3e` | Имя отсутствует в remote |
| `minimax/skill-catalog-20261020` | `5e64c6916b6f84d1fbb04c77a58c74fc198c40fa` | Имя отсутствует в remote |
| `minimax/work` | `a5a5603ad99984232284a7ea9b52df9946ecc671` | Имя отсутствует в remote |
| `worktree-frame-actions` | `95c9c2df3fd753e522cc5f2ca007fccd952b900c` | Имя отсутствует в remote |
| `worktree-idea-world` | `8c8f979258ef7040a83719e80d2bb096bf9ee690` | Имя отсутствует в remote |

## Worktree и чужие изменения

Прочитан porcelain status с untracked filenames; в таблице только число записей, без содержимого файлов. Dirty не означает дефект. Остальные dirty-деревья построчно не проверялись.

| Worktree | Ветка | HEAD | Записей status |
|---|---|---|---|
| `C:/AI_Workflow_Studio` | `fix/astra-aider-20261020` | `40ca333796a686acab4f0261381924eaf6a82276` | 37 |
| `C:/AI_Workflow_Studio/.claude/worktrees/cli-skill-global-setup-56ca43` | `claude/cli-skill-global-setup-56ca43` | `18131a73c0b3529265cc683aa1f6ac7f0b6f9a83` | 6 |
| `C:/AI_Workflow_Studio/.claude/worktrees/convert-to-skill-10d251` | `claude/convert-to-skill-10d251` | `89d189627bbc19b259189073d609fcc0b37b14e1` | 0 |
| `C:/AI_Workflow_Studio/.claude/worktrees/cyberpunk-neon-street-image-8e3bd6` | `claude/workflow-redesign` | `916887095a880e195f092e128dccd9d91868a70a` | 0 |
| `C:/AI_Workflow_Studio/.claude/worktrees/design-loop-skill-ea56fd` | `claude/design-loop-skill-ea56fd` | `cce9a9ddb6bff055310e4ae724991e46da8b9ff5` | 0 |
| `C:/AI_Workflow_Studio/.claude/worktrees/eager-neumann-2f99a7` | `claude/eager-neumann-2f99a7` | `1043b864c4047d8276e1591fb352fd011b96aa01` | 4 |
| `C:/AI_Workflow_Studio/.claude/worktrees/exciting-elbakyan-156f4b` | `claude/exciting-elbakyan-156f4b` | `ab1214f157118e86827705f3cf91ceea69b32108` | 0 |
| `C:/AI_Workflow_Studio/.claude/worktrees/frame-actions` | `worktree-frame-actions` | `95c9c2df3fd753e522cc5f2ca007fccd952b900c` | 0 |
| `C:/AI_Workflow_Studio/.claude/worktrees/gracious-joliot-e1b85a` | `claude/gracious-joliot-e1b85a` | `2d8ce52db75b5700f9fec1f363eba531f7b74864` | 1 |
| `C:/AI_Workflow_Studio/.claude/worktrees/grem-graham-development-23563d` | `claude/grem-graham-development-23563d` | `4dcf3f7b004932dd5af7eb528507bd3582aaebc1` | 0 |
| `C:/AI_Workflow_Studio/.claude/worktrees/gremovod-design-system-27a093` | `claude/gremovod-design-system-27a093` | `2d8ce52db75b5700f9fec1f363eba531f7b74864` | 23 |
| `C:/AI_Workflow_Studio/.claude/worktrees/gustavo-mercado-cinema-skills-35b2e1` | `claude/gustavo-mercado-cinema-skills-35b2e1` | `0069bed56b2fedcaec76edf2bf5f5d370e4ecfa1` | 0 |
| `C:/AI_Workflow_Studio/.claude/worktrees/idea-world` | `worktree-idea-world` | `8c8f979258ef7040a83719e80d2bb096bf9ee690` | 0 |
| `C:/AI_Workflow_Studio/.claude/worktrees/mckee-storytelling-skills-353bdc` | `claude/mckee-storytelling-skills-353bdc` | `c50886006fb995297256a1b0a69d288c42d14282` | 0 |
| `C:/AI_Workflow_Studio/.claude/worktrees/motion-frameworks-skills-9f0e7f` | `claude/motion-tools-docs` | `5474a70bac7f4f39356cbdbcdbda7b7dbdd126d6` | 0 |
| `C:/AI_Workflow_Studio/.claude/worktrees/project-audit-speedup-plan-937d17` | `claude/project-audit-speedup-plan-937d17` | `26c7e1e5b53fa32ce4706978a1cedcb5c1c0415a` | 0 |
| `C:/AI_Workflow_Studio/.claude/worktrees/prompts-reels-analysis-b430a7` | `claude/prompts-reels-analysis-b430a7` | `7f1d0daad88a3ab4dc08034055fd6b4d50283647` | 0 |
| `C:/AI_Workflow_Studio/.claude/worktrees/recursing-haibt-8b3a25` | `claude/stockman-practical-video` | `355c737cd111d4c8cf4f1a3cd0009454c6b8958c` | 0 |
| `C:/AI_Workflow_Studio/.claude/worktrees/strange-lederberg-3deff8` | `claude/strange-lederberg-3deff8` | `98c7c267da5401fc7eddce8e1849f871e4e2f3ee` | 0 |
| `C:/AI_Workflow_Studio/.claude/worktrees/video-montage-skill-analysis-0d8f95` | `claude/video-montage-skill-analysis-0d8f95` | `8a718cb0088bd2f790ea0795998cdbb9b39c709a` | 0 |
| `C:/AI_Workflow_Studio/.worktrees/aider-minimax` | `feature/aider-minimax-20261020` | `ec948d2cf87c85b96a54b2884d5c674f5e74e70e` | 0 |
| `C:/AI_Workflow_Studio/.worktrees/astra-audit-20261020` | `fix/astra-audit-20261020` | `89dfd11269e231a2e6dc446f768b4bdcd3e6d02e` | 59 |
| `C:/AI_Workflow_Studio/.worktrees/autopilot` | `autopilot/work` | `aeae111fa104ca6c4cbd02178d9bd0e3e89fd7f5` | 0 |
| `C:/AI_Workflow_Studio/.worktrees/claude` | `claude/work` | `ee9023808efee29ab4209c704ab9e2b3e0f4c1fb` | 1 |
| `C:/AI_Workflow_Studio/.worktrees/claude-checkpoint` | `codex/claude-checkpoint-2026-10-18` | `88d727b53de6b85ddc6e9b9ba21df655d3d3396a` | 0 |
| `C:/AI_Workflow_Studio/.worktrees/codex` | `codex/work` | `2d4d94e2181b8fa0b293d5f76b07b78c8d24ec76` | 4 |
| `C:/AI_Workflow_Studio/.worktrees/mavis` | `mavis/work` | `57cac59ca790d380d8e68f2f6db82674ca142e92` | 18 |
| `C:/AI_Workflow_Studio/.worktrees/minimax` | `feature/minimax-m3-1-flash-20261019` | `c78a94956aee7a6521d7ad882a32d16e69e89ab1` | 0 |
| `C:/AI_Workflow_Studio/.worktrees/minimax-aider-found-footage-20261020-0330` | `test/minimax-aider-found-footage-20261020-0330` | `af0c26d34a3e43c8ca7a67fd64783cfb4d57d8f8` | 1 |
| `C:/AI_Workflow_Studio/.worktrees/minimax-aider-smoke-20261020-030447` | `test/minimax-aider-smoke-20261020-030447` | `2a8e914de92a53b993453bf874136157d7d4998a` | 1 |
| `C:/AI_Workflow_Studio/.worktrees/minimax-llm-guard` | `minimax/paid-llm-guard` | `26ef2428b407c7b10a80d66fc298f1150693fd3e` | 8 |
| `C:/AI_Workflow_Studio/.worktrees/minimax-p0-review-20261020` | `minimax/p0-astra-fixes-20261020` | `89dfd11269e231a2e6dc446f768b4bdcd3e6d02e` | 0 |
| `C:/AI_Workflow_Studio/.worktrees/minimax-skill-catalog` | `minimax/skill-catalog-20261020` | `5e64c6916b6f84d1fbb04c77a58c74fc198c40fa` | 0 |
| `C:/AI_Workflow_Studio/.worktrees/minimax-work` | `minimax/work` | `a5a5603ad99984232284a7ea9b52df9946ecc671` | 0 |
| `C:/AI_Workflow_Studio/.worktrees/n8n-api` | `codex/n8n-api-contract` | `cbecc4acb205da503ca74566f72bd1d5cb48d52e` | 0 |
| `C:/AI_Workflow_Studio/.worktrees/p0-trial` | `mavis/p0-merge-trial` | `d24f3506b9c1c0dc97406f65f6d6531bb810e122` | 0 |
| `C:/AI_Workflow_Studio/.worktrees/qa-text-audit-20261019` | `codex/qa-text-audit-20261019` | `6a6a11becc6bbd014fdbb1bda7fc2fa473b9c345` | 0 |
| `C:/AI_Workflow_Studio/.worktrees/story-board-release` | `codex/story-board-release` | `714bef056797811aaffb34c4de65a8621cd35e83` | 0 |
| `C:/AI_Workflow_Studio/.worktrees/studio-demo` | `codex/studio-demo-2026-10-18` | `e84a8f20d0b94672acdfa54c61d4efdf23ff0b31` | 0 |
| `C:/Users/BLOWKA/.codex/worktrees/acting-motion-sound/AI_Workflow_Studio` | `codex/acting-notes` | `d46fd81b8adbac8c4db9c32c7a79ffd385d657eb` | 0 |
| `C:/Users/BLOWKA/.codex/worktrees/beta-generation-fixes/AI_Workflow_Studio` | `codex/beta-generation-fixes` | `e316bf5b256dfd92030630a03c85f04cffaae2f8` | 0 |
| `C:/Users/BLOWKA/.minimax/sessions/mvs_a6a0aa97cc3847fb9291947242d79cf2/workspace/MM-001-llm-ledger` | `minimax/MM-001-llm-ledger` | `f9f810f1428c5c594d4f1f356b4d56d6bf7f64da` | 0 |
| `C:/Users/BLOWKA/.minimax/sessions/mvs_a6a0aa97cc3847fb9291947242d79cf2/workspace/MM-002-dispatch` | `minimax/mm-002-dispatch-20261020` | `07a2c51a765ebd2eac5a3a1bc1047a871ebb49b0` | 0 |
| `C:/Users/BLOWKA/Documents/!GREM TAXI/outputs/n8n-full-spec-git` | `codex/n8n-full-production-spec-20261019` | `cafcbc66f01a2a0be11ea64063a3bd5a473629d7` | 1 |

Основной `C:/AI_Workflow_Studio` фактически находится на `fix/astra-aider-20261020@40ca333`, хотя AGENTS описывает root как main. В нём есть незакоммиченные llm_guard/main/security/release_artifacts и UI. Прочитаны общий stat и целевые llm_guard/security diffs. Helpers task_identity/task_request_id уже есть в этом dirty llm_guard (строки 237/250); они не входят в кандидатный SHA, не приняты и не копировались. 13 путей diff stat против 14 tracked status entries объясняются staged+unstaged release_artifacts.

## Открытые PR

| PR | Head | Base | Draft | SHA |
|---|---|---|---|---|
| [#53](https://github.com/gremoled77-droid/gremovod/pull/53) | `research/gemini-ladybug-workflow-20261020` | `mavis/work` | true | `e2f9f95ed3df67c0db2b2a64b0a7cfbf5f623c0a` |
| [#52](https://github.com/gremoled77-droid/gremovod/pull/52) | `research/channel-business-model-20261020` | `mavis/work` | true | `ffe1317610d589051b2852c0e9744e33671d44b5` |
| [#51](https://github.com/gremoled77-droid/gremovod/pull/51) | `research/story-chain-scepka-20261020` | `mavis/work` | true | `23a83f251a63143cfa37f5530ee4f170931e5e2a` |
| [#50](https://github.com/gremoled77-droid/gremovod/pull/50) | `research/video-editing-master-prompt-20261020` | `mavis/work` | true | `3a9cf18a4b6d29b8ad518a2491e5697b8fca984b` |
| [#42](https://github.com/gremoled77-droid/gremovod/pull/42) | `research/production-economics-2026-10-20` | `main` | true | `7898b6f3c89dd0eb47d9f9a58f03f20ea2d678bf` |
| [#41](https://github.com/gremoled77-droid/gremovod/pull/41) | `minimax/p0-astra-fixes-20261020` | `minimax/p0-budget-authz` | true | `89dfd11269e231a2e6dc446f768b4bdcd3e6d02e` |
| [#40](https://github.com/gremoled77-droid/gremovod/pull/40) | `test/minimax-aider-found-footage-20261020-0330` | `main` | true | `af0c26d34a3e43c8ca7a67fd64783cfb4d57d8f8` |
| [#39](https://github.com/gremoled77-droid/gremovod/pull/39) | `codex/review-opus-audit-001` | `docs/opus-audit-001` | true | `ee50fb83eff018346f593c2468750d9cd13ef6d1` |
| [#38](https://github.com/gremoled77-droid/gremovod/pull/38) | `test/minimax-aider-smoke-20261020-030447` | `main` | true | `2a8e914de92a53b993453bf874136157d7d4998a` |
| [#37](https://github.com/gremoled77-droid/gremovod/pull/37) | `docs/opus-audit-001` | `main` | true | `998ea461dda63312b2c2ddca47317954b9b59643` |
| [#36](https://github.com/gremoled77-droid/gremovod/pull/36) | `codex/env-audit-20261020` | `main` | false | `d0a0911a209c4f9b22cfc2cf8ceb701cf8b91cd8` |
| [#35](https://github.com/gremoled77-droid/gremovod/pull/35) | `experiment/minimax-observability-20261020` | `main` | true | `051ab3a1182c1ed954b53c9b64f85e8195dbcc91` |
| [#34](https://github.com/gremoled77-droid/gremovod/pull/34) | `experiment/minimax-kie-argon-bridge-impl-20261020` | `experiment/minimax-kie-argon-bridge-20261019` | true | `b3183d28a0e22d5414ab7eef70d62543aa991dfa` |
| [#33](https://github.com/gremoled77-droid/gremovod/pull/33) | `experiment/minimax-kie-argon-bridge-20261019` | `experiment/manual-argon-review-20261019` | true | `0ac4e916e274b4c75fde75edc1ddd0d5a3e376c1` |
| [#32](https://github.com/gremoled77-droid/gremovod/pull/32) | `feature/minimax-m3-1-flash-20261019` | `main` | true | `c78a94956aee7a6521d7ad882a32d16e69e89ab1` |
| [#31](https://github.com/gremoled77-droid/gremovod/pull/31) | `docs/argon-minimax-one-shot-20261019` | `main` | true | `85266bbd6352f6c737b52a09c9c28c412f543e98` |
| [#29](https://github.com/gremoled77-droid/gremovod/pull/29) | `minimax/p0-budget-authz` | `codex/p0-fixes-20261019` | true | `c082829b11b968965600bdaf87c137b1485a0fa2` |
| [#25](https://github.com/gremoled77-droid/gremovod/pull/25) | `experiment/minimax-coder-20261019` | `main` | true | `357ff1e82530bef9844425060243526a918fb409` |
| [#23](https://github.com/gremoled77-droid/gremovod/pull/23) | `docs/aider-n8n-argon-pilot-20261019` | `main` | true | `edd5ffb9c3d9d616237566324c06c85c0f13a409` |
| [#22](https://github.com/gremoled77-droid/gremovod/pull/22) | `experiment/manual-argon-review-20261019` | `main` | true | `25b7aa6a6a1ce6bf83d8f4ecade309da5cc718c9` |
| [#20](https://github.com/gremoled77-droid/gremovod/pull/20) | `experiment/beta-gateway-first-20261019` | `main` | true | `7e07f684cf89bc1b03f595fc278241c9c8a925a3` |
| [#19](https://github.com/gremoled77-droid/gremovod/pull/19) | `coordination/agent-roles-handoff-20261019` | `feature/p0-studio-foundation-20261019` | true | `928745552553537f11b16e0fdb568a7654e6cc35` |
| [#18](https://github.com/gremoled77-droid/gremovod/pull/18) | `feature/p0-studio-foundation-20261019` | `feature/n8n-astra-contract-hardening-20261019` | true | `5206dccda5fa47ad84d3b3d4932297b97b46a33f` |
| [#17](https://github.com/gremoled77-droid/gremovod/pull/17) | `feature/n8n-astra-contract-hardening-20261019` | `codex/n8n-full-production-spec-20261019` | true | `cb3f1dc376ee925a0ee0c61432cb3e52615a9b31` |
| [#16](https://github.com/gremoled77-droid/gremovod/pull/16) | `codex/acting-notes` | `codex/acting-motion-sound` | false | `d46fd81b8adbac8c4db9c32c7a79ffd385d657eb` |
| [#15](https://github.com/gremoled77-droid/gremovod/pull/15) | `codex/acting-motion-sound` | `main` | false | `4e08ac2aff8f698e2f29332c3bb898879fceea9c` |
| [#14](https://github.com/gremoled77-droid/gremovod/pull/14) | `feature/photo-editor-spec-20261019` | `main` | true | `f02806ee298ffc316c4f700753227193252fdbbe` |
| [#11](https://github.com/gremoled77-droid/gremovod/pull/11) | `docs/williams-motion-acting-20261019` | `main` | false | `5cd35b1f1fb327f2284ebc509ee49a0483edfb53` |
| [#10](https://github.com/gremoled77-droid/gremovod/pull/10) | `docs/ed-hooks-acting-director-20261019` | `main` | true | `840f6bd3f72c8bb4fbbf6d4f5ace73bfffda3e9d` |
| [#9](https://github.com/gremoled77-droid/gremovod/pull/9) | `docs/sound-design-beauchamp-2026-10-19` | `main` | false | `e9a4583c269ec8428a2e03a0439847ab9fee7785` |
| [#8](https://github.com/gremoled77-droid/gremovod/pull/8) | `feature/qa-text-audit-fixes-20261019` | `integration/n8n` | true | `397939027984fef240bc80ee16d651d9996f27a0` |
| [#7](https://github.com/gremoled77-droid/gremovod/pull/7) | `codex/n8n-api-contract` | `integration/n8n` | true | `cbecc4acb205da503ca74566f72bd1d5cb48d52e` |
| [#6](https://github.com/gremoled77-droid/gremovod/pull/6) | `chatgpt/n8n-web-skill-sync-20261019` | `main` | true | `81a9c81d67b1d62f8c068db088849ad5e24abb04` |

Connector search_prs вернул первую страницу 20 items; для полного списка использован REST pulls per_page=100: 33. В таблицу не входит создаваемый этим аудитом PR.

## CI, protections и качество процесса — P1-04

- В кандидатном .github/workflows — agent-coordination, agent-scope-guard, n8n-astra-pilot. Полного Studio backend+frontend/build check нет.
- [scope predicate:15](https://github.com/gremoled77-droid/gremovod/blob/57cac59ca790d380d8e68f2f6db82674ca142e92/.github/workflows/agent-scope-guard.yml#L15) не включает minimax/*, mavis/*, audit/*. Для task-веток MiniMax защита зон не подтверждается.
- Последние research #50–53 scope jobs skipped. n8n pilot run [39354333179](https://github.com/gremoled77-droid/gremovod/actions/runs/39354333179) success на **89dfd11**, не на текущем кандидате.
- REST check-runs для 57cac59 вернул пустой check_runs. Green старого узкого suite не означает green всей Studio.
- REST branches: protected=false; rulesets: []. Подробный protection endpoint main/mavis вернул **401**. Effective required checks/review restrictions — **UNKNOWN**; отсутствие полного CI в коде подтверждено отдельно.
- Repository settings, роли и required checks не менялись. Предложения изменения настроек требуют отдельного решения.

## Что можно принять / отложить / удалить

Можно принять этот **срез доказательств** и направить GA-01 на исправление. Уже включённые P0 patches сохранять. UI beta, text-precheck, skill catalog принимать отдельными scoped review после сверки текущей базы. Research/agent tooling отложить до потребности пилота. Старые ancestor-ветки и дубли docs — только кандидаты на архивирование после согласования, ничего не удалено.
