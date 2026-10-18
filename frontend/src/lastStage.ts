/** Последний рабочий этап проекта (в этом браузере): «Старт» предлагает вернуться именно туда. */
import {readLocal, writeLocal} from './localDrafts';
import {screenOf, type Mode} from './screens';

const key = (projectId: string) => 'studio:last-stage:' + projectId;

export function rememberStage(projectId: string, mode: Mode) {
  const screen = screenOf(mode);
  if (!projectId || !['stage', 'tool', 'service'].includes(screen.group)) return;
  if (mode === 'settings' || mode === 'connections') return;
  writeLocal(key(projectId), mode);
}

export function lastStage(projectId: string): Mode {
  const mode = readLocal<Mode>(key(projectId), 'studio');
  return screenOf(mode).mode === mode && screenOf(mode).group !== 'hidden' ? mode : 'studio';
}
