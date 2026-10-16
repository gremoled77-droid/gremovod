/** Editable inputs only. Paid requests, approvals and queued submissions are never restored. */
export type CreateDraft = {
  prompt: string;
  selected: string[];
  options: Record<string, Record<string, string | number>>;
  refs: string[];
  videoModel: string;
  motion: string;
  videoOptions: Record<string, string | number>;
};
type Store = Pick<Storage, 'getItem' | 'setItem'>;
const object = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === 'object' && !Array.isArray(value);
const strings = (value: unknown, fallback: string[]) =>
  Array.isArray(value) && value.every(v => typeof v === 'string') ? [...new Set(value)] : fallback;
function parameters(value: unknown): Record<string, string | number> {
  if (!object(value)) return {};
  return Object.fromEntries(
    Object.entries(value).filter(
      ([, v]) => typeof v === 'string' || (typeof v === 'number' && Number.isFinite(v))
    )
  ) as Record<string, string | number>;
}
export function emptyCreateDraft(): CreateDraft {
  return {
    prompt: '',
    selected: ['seedream-5-lite'],
    options: {},
    refs: [],
    videoModel: 'seedance-2.5',
    motion: '',
    videoOptions: {},
  };
}
const key = (projectId: string) => 'studio:create-draft:v1:' + projectId;
export function loadCreateDraft(projectId: string, storage?: Store): CreateDraft {
  const fallback = emptyCreateDraft();
  if (!projectId) return fallback;
  try {
    const raw = (storage ?? window.localStorage).getItem(key(projectId));
    const saved: unknown = raw ? JSON.parse(raw) : null;
    if (!object(saved) || saved.version !== 1 || saved.projectId !== projectId || !object(saved.draft))
      return fallback;
    const d = saved.draft;
    return {
      prompt: typeof d.prompt === 'string' ? d.prompt : '',
      selected: strings(d.selected, fallback.selected),
      options: object(d.options)
        ? Object.fromEntries(Object.entries(d.options).map(([model, opts]) => [model, parameters(opts)]))
        : {},
      refs: strings(d.refs, []),
      videoModel: typeof d.videoModel === 'string' ? d.videoModel : fallback.videoModel,
      motion: typeof d.motion === 'string' ? d.motion : '',
      videoOptions: parameters(d.videoOptions),
    };
  } catch {
    return fallback;
  }
}
export function saveCreateDraft(projectId: string, draft: CreateDraft, storage?: Store): boolean {
  if (!projectId) return true;
  try {
    const {prompt, selected, options, refs, videoModel, motion, videoOptions} = draft;
    (storage ?? window.localStorage).setItem(
      key(projectId),
      JSON.stringify({
        version: 1,
        projectId,
        draft: {prompt, selected, options, refs, videoModel, motion, videoOptions},
      })
    );
    return true;
  } catch {
    return false;
  }
}
