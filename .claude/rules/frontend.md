---
paths:
  - "frontend/**"
---

# Frontend

- React 18 + TypeScript + Vite 6, `@xyflow/react` для узлов воркфлоу.
  Порядок типов и сборки: `npm run build` = `tsc --noEmit && vite build`.
- Тесты: `npm test` из `frontend/` (встроенный раннер Node, `node --test`).
  Скрипт `npm test` не требует установленного `node_modules`, но `npm run build`
  требует — в новом worktree сначала `npm ci` в папке `frontend/`.
- Стиль: `frontend/.prettierrc.json` — одинарные кавычки, ширина 110, без пробелов
  в скобках объектов. Форматирование `npx prettier --write <файлы>`.
- Экраны нового дизайна получают класс на `<main>` (`home-main`, `create-main`,
  `storyboard-main`): он скрывает старую боковую панель и снимает `margin:auto`.
  Для нового экрана делать так же.
- Макеты нового вида — `docs/design/` (Main, Board, Mobile, Workflow), видение и
  алгоритм ролика — `docs/VISION_AND_ALGORITHM.md`.
- UI проверяется в браузере на `http://127.0.0.1:5173`, а не только сборкой.
  Экран «Ворклоу/Узлы» и телефонная версия ещё не перенесены в новый вид — это
  текущая очередь, см. `TODO.md`.
