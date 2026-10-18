import type {Mode} from './screens';
/** Открываемые по ссылке экраны; скрытые до беты (Рилсы, Сцена, Допилить, Агенты) — нет. */
export const MODES: Mode[] = [
  'home',
  'studio',
  'styles',
  'characters',
  'storyboard',
  'create',
  'video',
  'audio',
  'files',
  'economics',
  'graph',
  'archive',
  'connections',
  'settings',
];
export function readWorkspaceRoute(hash: string): {projectId: string; mode: Mode} | null {
  const match = hash.match(/^#\/project\/([a-zA-Z0-9_-]{1,100})\/([a-z]+)$/);
  return match && MODES.includes(match[2] as Mode) ? {projectId: match[1], mode: match[2] as Mode} : null;
}
export function workspaceHash(projectId: string, mode: Mode) {
  return /^[a-zA-Z0-9_-]{1,100}$/.test(projectId) ? `#/project/${projectId}/${mode}` : '';
}
