/** Промпт кадра: задание ролика, «Библия мира», герои и локация. Пустые части пропускаются. */
import type {Identity, WorldFields} from './characterPrompt';

export type FrameHero = {name: string; identity: Partial<Identity>};

const clean = (v?: string) => (v || '').trim().replace(/\s+/g, ' ');

export function buildFramePrompt(input: {
  brief: string;
  heroes: FrameHero[];
  location?: string;
  world?: WorldFields;
}): string {
  const {brief, heroes, location, world} = input;
  const who = heroes
    .map(h => {
      const look = [clean(h.identity.species), clean(h.identity.costume)].filter(Boolean).join(', ');
      return look ? `${clean(h.name)} (${look})` : clean(h.name);
    })
    .filter(Boolean);
  const line = (label: string, value?: string) => (clean(value) ? `${label}: ${clean(value)}.` : '');
  const forbidden = clean(world?.avoid);
  return [
    line('Кадр', brief),
    who.length ? `В кадре: ${who.join('; ')}. Внешность героев строго как на референсах.` : '',
    line('Место', location),
    line('Стиль мира', world?.look),
    line('Палитра', world?.palette),
    line('Освещение', world?.lighting),
    line('Камера', world?.camera),
    line('Неизменные правила', world?.rules),
    forbidden ? `Запрещено: ${forbidden}.` : '',
  ]
    .filter(Boolean)
    .join('\n');
}

/** Названия кадров по умолчанию: «Кадр N», нумерация продолжается после уже существующих, повторов нет. */
export function defaultFrameTitles(existing: string[], count: number): string[] {
  const taken = new Set(existing.map(t => t.trim().toLowerCase()));
  const out: string[] = [];
  for (let n = existing.length + 1; out.length < count; n++) {
    const title = `Кадр ${n}`;
    if (!taken.has(title.toLowerCase())) out.push(title);
  }
  return out;
}
