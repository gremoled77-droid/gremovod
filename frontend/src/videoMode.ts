/** Режимы экрана «Видео» для Seedance 2.5: новый ролик, кадр → кадр (подсказка в промпте), правка и продление. */
export type VideoMode = 'new' | 'frames' | 'edit' | 'extend';

export const VIDEO_MODES: {id: VideoMode; label: string}[] = [
  {id: 'new', label: 'Новый ролик'},
  {id: 'frames', label: 'Кадр → кадр'},
  {id: 'edit', label: 'Править'},
  {id: 'extend', label: 'Продлить'},
];

export const FRAMES_HINT = '@image1 is the first frame of the video, @image2 is the last frame of the video.';

/** Правка и продление работают по исходному ролику; формат у них только adaptive. */
export const usesSource = (mode: VideoMode) => mode === 'edit' || mode === 'extend';

/** Строка роли в начале промпта. Теги, которые автор уже поставил сам, не дублируются. */
export function modePrompt(mode: VideoMode, prompt: string, opts: {hasBase: boolean; back: boolean}): string {
  const text = prompt.trim();
  if (mode === 'frames') return /@image2/i.test(text) ? text : `${FRAMES_HINT}\n${text}`;
  if (mode === 'edit') return /@video1/i.test(text) ? text : `Edit @video1: ${text}`;
  if (mode === 'extend')
    return /@video1/i.test(text) ? text : `Extend @video1 ${opts.back ? 'backward' : 'forward'}: ${text}`;
  return opts.hasBase && !/@image1/i.test(text) ? `@image1 is the first frame of the video.\n${text}` : text;
}

/** Выход по ставке за секунду плюс половина ставки за секунды входного видео (cost_seedance_25 на сервере). */
export function seedanceCost(ratePerSecond: number, outSeconds: number, inputVideoSeconds: number): number {
  return Math.round((ratePerSecond * outSeconds + (ratePerSecond / 2) * inputVideoSeconds) * 1000) / 1000;
}
