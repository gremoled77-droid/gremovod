/** Звуковые заметки кадра: типы, рекомендуемые уровни, форматы и счётчики для бейджей. */
export type CueKind = 'voice' | 'ambience' | 'sfx' | 'music';
export type Cue = {
  id: string;
  frame_id: string;
  kind: CueKind;
  text: string;
  hero_node_id: string | null;
  level_db: number;
  start_s: number;
  duration_s: number | null;
  file_id: string | null;
  filename: string | null;
  url: string | null;
  status: 'plan' | 'file';
};
export type FrameSound = {
  frame_id: string;
  frame: string;
  frame_number: number;
  scene_id: string;
  scene: string;
  scene_number: number;
  cues: Cue[];
};

export const KINDS: {id: CueKind; label: string; hint: string}[] = [
  {id: 'voice', label: 'Реплика', hint: 'голос героя, около 0 дБ'},
  {id: 'ambience', label: 'Атмосфера', hint: 'фон мира, около −20 дБ'},
  {id: 'sfx', label: 'SFX', hint: 'звук действия, около −6 дБ'},
  {id: 'music', label: 'Музыка', hint: 'саундтрек, около −12 дБ'},
];
export const DEFAULT_LEVEL: Record<CueKind, number> = {voice: 0, ambience: -20, sfx: -6, music: -12};
export const kindLabel = (kind: CueKind) => KINDS.find(k => k.id === kind)?.label || kind;

/** Тот же формат, что принимает сервер: латиница, цифры, «_» и «-», до 100 знаков. */
export const voiceIdOk = (id: string) => /^[A-Za-z0-9_-]{1,100}$/.test(id.trim());

/** Заметок и заметок с файлом у кадра: «звук: 2 из 3». */
export function soundCount(cues: Pick<Cue, 'status'>[]): {done: number; all: number} {
  return {done: cues.filter(c => c.status === 'file').length, all: cues.length};
}

export function soundLabel(cues: Pick<Cue, 'status'>[]): string {
  const {done, all} = soundCount(cues);
  return all ? `звук: ${done} из ${all}` : 'звука нет';
}

/** Сводка по сцене: сколько кадров имеют хотя бы одну заметку и сколько заметок уже с файлами. */
export function sceneSound(frames: {cues: Pick<Cue, 'status'>[]}[]): {
  framesWith: number;
  frames: number;
  done: number;
  all: number;
} {
  const done = frames.reduce((n, f) => n + soundCount(f.cues).done, 0);
  const all = frames.reduce((n, f) => n + f.cues.length, 0);
  return {framesWith: frames.filter(f => f.cues.length).length, frames: frames.length, done, all};
}

/** «−6 дБ» с настоящим минусом и без хвоста «.0». */
export const levelLabel = (db: number) => `${db < 0 ? '−' : db > 0 ? '+' : ''}${Math.abs(db)} дБ`;
