# Blender offline P0

См. `docs/blender/BLENDER_P0_RUNBOOK.md` и `IMPLEMENTATION_STATUS.md`.
Все текущие CLI безопасно ограничены offline: validator, preflight, planner,
benchmark template и skill dry-run. `scene_build.py` не является host entry point:
он подготовлен только для будущего isolated launcher и ещё не проверен в Blender.

Dependencies: `requirements-blender.txt`; test dependencies: `requirements-blender-test.txt`.
Данные JSON, `.blend`, PNG/MP4 и логи хранить только в игнорируемом runtime.
Не передавать process argv, Python, executable или file URLs из provider/HTTP payload.
Не считать hash binding confirm token; отправка должна использовать existing budget flow.
