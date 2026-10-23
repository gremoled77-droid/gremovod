/** Статус кадра на доске: фото, видео и счётчик сцены. «Генерируется» приходит из ленты заданий постановки. */
export type StatusFile = {id: string; kind: string};
export type StatusSelection = {selected_image_file_id: string | null; selected_video_file_id: string | null};

export type FrameStatus = {
  photo: 'none' | 'latest' | 'approved';
  video: 'none' | 'pending' | 'takes' | 'main';
  takes: number;
};

/** Задание ещё идёт или его результат ещё сохраняется в папку кадра. */
export const ACTIVE = new Set(['queued', 'running', 'saving']);

/** Кадры, у которых в ленте постановки есть незавершённое задание на видео. */
export function generatingFrames(
  items: {kind: string; status: string; node_id?: string | null}[]
): Set<string> {
  return new Set(
    items.flatMap(i => (i.kind === 'video' && ACTIVE.has(i.status) && i.node_id ? [i.node_id] : []))
  );
}

export function frameStatus(
  files: StatusFile[],
  selection: StatusSelection,
  generating: boolean
): FrameStatus {
  const images = files.filter(f => f.kind === 'image').length;
  const takes = files.filter(f => f.kind === 'video').length;
  const photo = selection.selected_image_file_id ? 'approved' : images ? 'latest' : 'none';
  const video = selection.selected_video_file_id ? 'main' : generating ? 'pending' : takes ? 'takes' : 'none';
  return {photo, video, takes};
}

export const photoLabel = (s: FrameStatus) =>
  ({none: 'нет фото', latest: 'фото не утверждено', approved: 'фото ✓'})[s.photo];

export const videoLabel = (s: FrameStatus) =>
  s.video === 'main'
    ? `видео ✓ (${s.takes})`
    : s.video === 'pending'
      ? 'видео генерируется…'
      : s.video === 'takes'
        ? `видео: ${s.takes} без выбора`
        : 'видео нет';

/** Сколько кадров сцены уже имеют главное видео. */
export function sceneVideoCount(frames: {selection: StatusSelection}[]): {done: number; all: number} {
  return {done: frames.filter(f => !!f.selection.selected_video_file_id).length, all: frames.length};
}
