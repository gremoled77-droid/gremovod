export type VideoDraft = {
  prompt: string;
  base: string;
  refs: string[];
  model: string;
  values: Record<string, string | number>;
};

type DraftStorage = Pick<Storage, 'getItem' | 'setItem'>;

export const videoDraftKey = (projectId: string) => `studio:video-draft:v1:${projectId}`;

/** Черновик экрана «Видео»: модель, промпт и кадры переживают перезагрузку страницы и загрузку оригинала в облако. */
export function loadVideoDraft(projectId: string, storage?: DraftStorage): Partial<VideoDraft> {
  try {
    const parsed = JSON.parse((storage ?? localStorage).getItem(videoDraftKey(projectId)) || '{}');
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

export function saveVideoDraft(projectId: string, draft: VideoDraft, storage?: DraftStorage) {
  try {
    (storage ?? localStorage).setItem(videoDraftKey(projectId), JSON.stringify(draft));
  } catch {
    /* без черновика экран работает */
  }
}
