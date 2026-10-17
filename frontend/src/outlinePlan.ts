/** План сцен и кадров от GPT: системный промпт, разбор JSON, текст заметки кадра и запрос к серверу. */
export type Shot = {change: string; visible: string; audio: string; camera: string};
export type OutlineScene = {title: string; shots: Shot[]};
export type Outline = {scenes: OutlineScene[]};

export const MAX_SHOTS = 12;

export function outlineSystem(shots: number, scenes: number) {
  return `Ты режиссёр-постановщик короткого ролика. По заданию и «Паспорту мира» разбей историю на ${scenes} ${scenes === 1 ? 'сцену' : 'сцен'}, в каждой по ${shots} кадров (завязка, препятствие, кульминация, финал).
Каждый кадр несёт изменение состояния и описывается коротко.
Верни ТОЛЬКО JSON без пояснений и без markdown такого вида:
{"scenes":[{"title":"Название сцены","shots":[{"change":"одно предложение: что меняется в этом кадре","visible":"что видно в кадре","audio":"что слышно","camera":"как движется камера"}]}]}
Правила: все значения на русском; не придумывай героев и локации, которых нет в списке; название сцены до 60 символов; в "change" ровно одно предложение.`;
}

const clean = (v: unknown) => (typeof v === 'string' ? v.trim().replace(/\s+/g, ' ') : '');

/** Достаёт JSON из ответа (в том числе из ```json и с текстом вокруг) и проверяет форму плана. */
export function parseOutline(text: string): Outline {
  const start = text.indexOf('{'),
    end = text.lastIndexOf('}');
  if (start < 0 || end <= start) throw Error('Ответ не похож на JSON');
  let raw: {scenes?: unknown};
  try {
    raw = JSON.parse(text.slice(start, end + 1));
  } catch {
    throw Error('Не удалось разобрать JSON из ответа');
  }
  if (!Array.isArray(raw.scenes) || !raw.scenes.length) throw Error('В ответе нет сцен');
  const scenes: OutlineScene[] = raw.scenes.map((s: {title?: unknown; shots?: unknown}, i: number) => {
    const list = Array.isArray(s.shots) ? s.shots : [];
    const shots = list
      .slice(0, MAX_SHOTS)
      .map((x: Partial<Record<keyof Shot, unknown>>) => ({
        change: clean(x.change),
        visible: clean(x.visible),
        audio: clean(x.audio),
        camera: clean(x.camera),
      }))
      .filter(x => x.change);
    if (!shots.length) throw Error(`В сцене ${i + 1} нет кадров с полем «change»`);
    return {title: clean(s.title).slice(0, 75) || `Сцена ${i + 1}`, shots};
  });
  return {scenes};
}

/** Заметка кадра: четыре строки, пустые пропускаются. */
export function shotNotes(shot: Shot): string {
  return [
    ['Изменение', shot.change],
    ['Видно', shot.visible],
    ['Слышно', shot.audio],
    ['Камера', shot.camera],
  ]
    .filter(([, v]) => v.trim())
    .map(([k, v]) => `${k}: ${v.trim()}`)
    .join('\n');
}

/** Строка «Изменение: …» из заметки кадра для показа на карточке. */
export function changeOf(notes: string | undefined): string {
  const m = (notes || '').match(/^Изменение:\s*(.+)$/m);
  return m ? m[1].trim() : '';
}

/** Тело запроса к серверу: названия кадров «Кадр N» внутри сцены. Нумерация идёт заново в каждой сцене. */
export function outlineBody(plan: Outline) {
  return plan.scenes.map(s => ({
    title: s.title.trim(),
    frames: s.shots.map((shot, i) => ({title: `Кадр ${i + 1}`, notes: shotNotes(shot)})),
  }));
}

/** Пользовательская часть запроса: задание, паспорт мира и имена героев проекта. */
export function outlineUser(input: {brief: string; passport: string; heroes: string[]}): string {
  return [
    `Задание ролика:\n${input.brief.trim()}`,
    input.passport.trim() ? `Паспорт мира:\n${input.passport.trim()}` : '',
    input.heroes.length ? `Герои проекта: ${input.heroes.join(', ')}` : '',
  ]
    .filter(Boolean)
    .join('\n\n');
}
