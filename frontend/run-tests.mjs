// Запускает тесты frontend и подставляет корректный интерпретатор Python.
//
// Часть тестов (directorState) обращается к backend через Python-подпроцесс.
// Backend — неявный namespace-пакет, поэтому интерпретатору нужны fastapi и
// остальные зависимости из backend/requirements.txt.
//
// Раньше интерпретатор выбирался только внутри самого теста: сначала
// STUDIO_PYTHON, затем поиск .venv вверх по дереву, затем системный python3.
// В рабочей копии git, расположенной не под корнем студии, .venv не
// находится, и подставляется системный python3 без fastapi — тесты падают
// с ModuleNotFoundError. Здесь выбор вынесен в общий скрипт запуска, чтобы
// порядок разрешения был одинаковым для всех проверок.
//
// Порядок разрешения:
//   1. STUDIO_PYTHON            — явное переопределение.
//   2. frontend/.studio-python  — локальный указатель на интерпретатор (вне Git).
//   3. .venv проекта или любого родителя — канонический корень и его worktree.
//   4. иначе ничего не подставляется, поведение как раньше.

import { spawn } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontendDir = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(frontendDir, '..');

const VENV_CANDIDATES = ['.venv/Scripts/python.exe', '.venv/bin/python'];

function findVenvPython(from) {
  for (let dir = resolve(from); ; dir = dirname(dir)) {
    for (const relative of VENV_CANDIDATES) {
      const candidate = join(dir, relative);
      if (existsSync(candidate)) return candidate;
    }
    if (dirname(dir) === dir) return null;
  }
}

function fromPointerFile() {
  const pointer = join(frontendDir, '.studio-python');
  if (!existsSync(pointer)) return null;
  const value = readFileSync(pointer, 'utf8').trim();
  return value && existsSync(value) ? value : null;
}

function resolvePython() {
  const explicit = process.env.STUDIO_PYTHON;
  if (explicit && existsSync(explicit)) return explicit;
  return fromPointerFile() || findVenvPython(projectRoot);
}

const python = resolvePython();
const env = { ...process.env };
if (python) env.STUDIO_PYTHON = python;

const args = ['--experimental-strip-types', '--test', ...process.argv.slice(2)];
const child = spawn(process.execPath, args, { stdio: 'inherit', env });

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
