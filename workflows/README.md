# GremoVOD — исходники семи физических n8n-модулей

В каталоге сохранены **ровно 7 JSON-экспортов из фактических n8n draft workflow** (`WF_00..WF_06`). Экспорт сделан из версии MOCK от 19.10.2026; credentials и секретов нет, `active=false`. Эти файлы — **точка версии для Argon и Codex**, а не работающий production.

| Имя файла | Исходный ID n8n | Статус |
|---|---|---|
| `WF_00_Core_Infra.json` | `j8Xqv8GQHjfJ5fVI` | MOCK parent, 6 Execute Sub-workflow |
| `WF_01_Writers_Room.json` | `ojYcjohXuJG6QEF7` | MOCK child |
| `WF_02_Canon_And_Images.json` | `O6nukP9aeAA8jY8o` | MOCK child |
| `WF_03_Audio_Factory.json` | `Xq1PbgUKrPazypI6` | MOCK child |
| `WF_04_Video_And_LipSync.json` | `E7mHOPGX1g21KSx1` | MOCK child |
| `WF_05_Assembly_And_Critics.json` | `cjX3LH2bFeVGVy6f` | MOCK child |
| `WF_06_Repair_Router.json` | `AzJ5so5Hl5ysx60d` | MOCK child |

**ВАЖНО при импорте:** `WF_00_Core_Infra.json` содержит шесть безопасных маркеров `REPLACE_WITH_IMPORTED_WF_0n_ID` вместо реальных ID. Сначала импортировать шесть дочерних JSON, затем подставить новые ID в копию родителя и проверить вручную в отдельном проекте/инстансе. Пока placeholders не заменены, импортированный родитель **не должен запускаться**. Оригинальные облачные workflow не изменялись.

В кодовых узлах сейчас только `mock://` URI, 3 искусственных шота и 3 условные дорожки. Это **JSON-фикстуры, не фактические MP4/PNG/голоса**. Настоящий FFmpeg-тест проводится отдельно в `tools/mock_media_pilot.py` через GitHub Actions. `final_release_approved=false`, реальные provider HTTP и мультимодальный QA не работают.

**Рабочий процесс Argon:** получает подтверждённые схемы Codex, меняет только назначенные файлы `workflows/**`, `integrations/n8n/**` в своей ветке, запускает validators и бесплатный n8n smoke test, сохраняет execution ID и handoff. Никаких API-ключей, credential IDs или платных вызовов в экспортах.

Сверять `integrations/n8n/WF_00_WF_06_MANIFEST.json` и `docs/specs/n8n-production-2026-10-19/nodes.json`. Если экспорт и облачный draft расходятся, фиксировать разницу, не перезаписывать молча.
