/** Листы героя и вариации локации: наборы ракурсов, промпты запросов пакета и чтение подписи ракурса из промпта. */
import type {WorldFields} from './characterPrompt';

export type Shot = {key: string; label: string; prompt: string};

export const HERO_SHOTS: Shot[] = [
  {key: 'front', label: 'Анфас', prompt: 'Вид строго спереди, герой в полный рост, нейтральная поза.'},
  {key: 'profile', label: 'Профиль', prompt: 'Вид строго сбоку, профиль, герой в полный рост.'},
  {key: 'three_quarter', label: '3/4', prompt: 'Поворот в три четверти, герой в полный рост.'},
  {key: 'back', label: 'Со спины', prompt: 'Вид сзади, герой в полный рост.'},
  {key: 'full', label: 'Полный рост', prompt: 'Полный рост, вид спереди, обувь и руки видны целиком.'},
  {key: 'neutral', label: 'Нейтральная эмоция', prompt: 'Крупный план лица, нейтральное выражение.'},
  {key: 'joy', label: 'Радость', prompt: 'Крупный план лица, искренняя улыбка, радость.'},
  {key: 'anger', label: 'Злость', prompt: 'Крупный план лица, гнев, нахмуренные брови.'},
  {key: 'surprise', label: 'Удивление', prompt: 'Крупный план лица, удивление, поднятые брови.'},
  {key: 'sad', label: 'Грусть', prompt: 'Крупный план лица, грусть, опущенный взгляд.'},
];
export const HERO_DEFAULT = ['front', 'profile', 'three_quarter', 'back', 'full', 'neutral', 'joy', 'anger'];

export const LOCATION_SHOTS: Shot[] = [
  {key: 'wide', label: 'Общий план', prompt: 'Общий план всего места, широкий угол.'},
  {key: 'medium', label: 'Средний план', prompt: 'Средний план, камера ближе к центру места.'},
  {key: 'reverse', label: 'Обратная точка', prompt: 'То же место с противоположной стороны.'},
  {key: 'detail', label: 'Деталь', prompt: 'Крупно характерная деталь места.'},
  {key: 'door', label: 'Из двери или окна', prompt: 'Вид из дверного или оконного проёма наружу.'},
  {key: 'night', label: 'Другое время суток', prompt: 'То же место в другое время суток, свет меняется.'},
];
export const LOCATION_DEFAULT = ['wide', 'medium', 'reverse', 'detail'];

export const MAX_SHEET = 12;

const clean = (v?: string) => (v || '').trim().replace(/\s+/g, ' ');

/** Запрос вариации локации: описание, паспорт мира и угол обзора. */
export function locationShotPrompt(
  name: string,
  description: string,
  world: WorldFields | undefined,
  shot: Shot
) {
  const lines = [
    `Вариации локации «${clean(name) || 'Место'}»: то же место, без людей и надписей.`,
    clean(description) ? `Описание: ${clean(description)}.` : '',
    clean(world?.look) ? `Стиль мира: ${clean(world?.look)}.` : '',
    clean(world?.palette) ? `Палитра: ${clean(world?.palette)}.` : '',
    clean(world?.lighting) ? `Освещение: ${clean(world?.lighting)}.` : '',
    `Ракурс: ${shot.label}. ${shot.prompt}`,
    'Архитектура и предметы как на референсе.',
  ];
  return lines.filter(Boolean).join('\n');
}

/** Подпись ракурса из промпта запроса («Ракурс: Анфас. …»); пусто, если строки нет. */
export function readShotLabel(prompt: string | undefined): string {
  const m = (prompt || '').match(/Ракурс:\s*([^.\n]+)/);
  return m ? m[1].trim() : '';
}

/** Принадлежит ли промпт листу героя или вариациям локации с этим именем. */
export function belongsToSheet(prompt: string | undefined, kind: 'hero' | 'location', name: string): boolean {
  const head = kind === 'hero' ? `Лист персонажа «${clean(name)}»` : `Вариации локации «${clean(name)}»`;
  return (prompt || '').includes(head) && !!readShotLabel(prompt);
}

/** Выбранные ракурсы по порядку набора, не больше MAX_SHEET. */
export function pickShots(all: Shot[], keys: string[]): Shot[] {
  return all.filter(s => keys.includes(s.key)).slice(0, MAX_SHEET);
}

/** Сумма оценок пакета, без накопления ошибки float. */
export function batchTotal(items: {usd: number}[]): number {
  return Math.round(items.reduce((a, b) => a + b.usd, 0) * 1e6) / 1e6;
}
