import type {Mode} from './StageNav';
export const MODES: Mode[] = [
  'home',
  'studio',
  'styles',
  'characters',
  'storyboard',
  'create',
  'video',
  'audio',
  'reels',
  'files',
  'economics',
  'graph',
  'scene',
  'refine',
  'agents',
  'connections',
  'settings',
  'archive',
];
const ID = /^[a-zA-Z0-9_-]{1,100}$/;
/** Адрес рабочего места: проект, инструмент и необязательный кадр в фокусе. */
export function readWorkspaceRoute(hash: string): {projectId: string; mode: Mode; frameId: string} | null {
  const match = hash.match(
    /^#\/project\/([a-zA-Z0-9_-]{1,100})\/([a-z]+)(?:\/frame\/([a-zA-Z0-9_-]{1,100}))?$/
  );
  return match && MODES.includes(match[2] as Mode)
    ? {projectId: match[1], mode: match[2] as Mode, frameId: match[3] || ''}
    : null;
}
export function workspaceHash(projectId: string, mode: Mode, frameId = '') {
  if (!ID.test(projectId)) return '';
  return `#/project/${projectId}/${mode}` + (ID.test(frameId) ? `/frame/${frameId}` : '');
}
