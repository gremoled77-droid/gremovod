/** Статус кадра на доске: фото, видео и счётчик сцены. «Генерируется» помним локально: у кадра свой рабочий проект, общей ленты заданий для него нет. */
export type StatusFile = {id: string; kind: string};
export type StatusSelection = {selected_image_file_id: string | null; selected_video_file_id: string | null};
export type Pending = {since: number; videosBefore: number};

export type FrameStatus = {
  photo: 'none' | 'latest' | 'approved';
  video: 'none' | 'pending' | 'takes' | 'main';
  takes: number;
};

export const PENDING_MS = 15 * 60 * 1000;

export function frameStatus(
  files: StatusFile[],
  selection: StatusSelection,
  pending: Pending | undefined,
  now: number
): FrameStatus {
  const images = files.filter(f => f.kind === 'image').length;
  const takes = files.filter(f => f.kind === 'video').length;
  const photo = selection.selected_image_file_id ? 'approved' : images ? 'latest' : 'none';
  // Задание считается идущим, пока не появилось новое видео и не прошло 15 минут.
  const waiting = !!pending && takes <= pending.videosBefore && now - pending.since < PENDING_MS;
  const video = selection.selected_video_file_id ? 'main' : waiting ? 'pending' : takes ? 'takes' : 'none';
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
