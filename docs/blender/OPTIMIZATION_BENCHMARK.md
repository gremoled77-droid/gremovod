# Оптимизация: NOT_MEASURED

Рендеров в этой сессии нет: `BLOCKED_G1`. Времена, peak memory, geometry hashes и
speedup = `null`, не ноль. Установленные addons не доказывают ускорение или сохранение канона.

`scripts/blender/benchmark_render.py` создаёт четыре строки **плана**, а не выполняет
benchmark: Workbench и Cycles CPU low для 960×540 / 540×960, 192 кадра / 8 секунд.
Реализован только candidate Workbench scene source; Cycles preset не реализован.
Сравнение разных engines не доказывает эффект оптимизации.

После G1/G2 отдельно замерить baseline и одну оптимизацию **в одном engine** на одном
master SHA, camera trajectory, fps, resolution, samples/seed и наборе кадров. Зафиксировать
Blender/build, CPU/GPU/driver, фактический render device, wall time каждого кадра/всего
прогона, peak memory, triangles/draw calls, размеры файлов и свободный диск до/после.
Warm-up отделить от measured runs. Повторить ограниченное число раз при достаточном диске.

Безопасные кандидаты: отключение тяжёлых эффектов, Workbench для previz, уменьшение
samples с визуальной проверкой. MustardSimplify/model-optimizer пробовать только на
копии; сравнить vertex/transforms/bounds/landmarks, оба борта, пропорции/двери/колёса.
Asset Validator сравнить с собственным QA; никакой автоматический APPROVED.
При изменении protected geometry — FAIL, экономию времени не принимать.

GTX 950 2 GB и около 4.6 GB свободного C: на первом аудите — ограничение пилота;
GPU support/пиковая память не измерены. Начать с CPU/одного кадра в изолированной среде,
затем first/mid/last. Не заявлять возможность полного 192-кадрового render заранее.
