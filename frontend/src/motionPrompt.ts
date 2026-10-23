/** Промпт анимации: камера + субъект + действие + окружение + свет, принцип минимального движения и защита от «морфинга».
 *  Собирается локально и бесплатно на английском, без мусорных слов качества. */
import {stripJunk} from './operatorPrompt.ts';

export type Option = {id: string; label: string; text: string};

export const CAMERA_MOVES: Option[] = [
  {id: 'static', label: 'Статика', text: 'locked-off static camera'},
  {id: 'push', label: 'Наезд', text: 'push in'},
  {id: 'pull', label: 'Отъезд', text: 'pull out'},
  {id: 'orbit', label: 'Облёт', text: 'orbit around the subject'},
  {id: 'handheld', label: 'С рук', text: 'handheld camera shake'},
  {id: 'pan', label: 'Панорама', text: 'pan'},
  {id: 'tilt', label: 'Наклон вверх', text: 'tilt up'},
  {id: 'ramp', label: 'Ускорение', text: 'speed ramp'},
];
export const SPEEDS: Option[] = [
  {id: 'slow', label: 'медленно', text: 'slow'},
  {id: 'medium', label: 'средне', text: 'moderate'},
  {id: 'fast', label: 'быстро', text: 'fast'},
];
export const AMPLITUDES: Option[] = [
  {id: 'small', label: 'малая', text: 'very subtle'},
  {id: 'medium', label: 'средняя', text: 'gentle'},
  {id: 'large', label: 'большая', text: 'pronounced'},
];
export const ACTIONS: Option[] = [
  {id: 'breathe', label: 'Лёгкое дыхание', text: 'subtle breathing'},
  {id: 'glance', label: 'Взгляд в сторону', text: 'eyes glance to the side'},
  {id: 'lips', label: 'Дрожание губ', text: 'slight lip tremble'},
  {id: 'blink', label: 'Медленное моргание', text: 'slow blink'},
  {id: 'head', label: 'Лёгкий наклон головы', text: 'a small tilt of the head'},
  {id: 'hands', label: 'Пальцы на руле', text: 'fingers tapping on the steering wheel'},
];
export const SCENERY: Option[] = [
  {id: 'steam', label: 'Пар от кружки', text: 'steam rising from the mug'},
  {id: 'hair', label: 'Ветер в волосах', text: 'wind moving the hair'},
  {id: 'rain', label: 'Капли по стеклу', text: 'raindrops sliding down the glass'},
  {id: 'fog', label: 'Дрейф тумана', text: 'slow drifting fog'},
  {id: 'lights', label: 'Мерцание огней', text: 'distant lights flickering'},
];
export const LIGHT_SHIFT: Option[] = [
  {id: 'shift', label: 'Лёгкая смена света', text: 'light gently shifting'},
  {id: 'flicker', label: 'Мерцание лампы', text: 'a lamp flickering softly'},
  {id: 'passing', label: 'Свет проезжающей машины', text: 'headlights of a passing car sweeping across'},
];

export type Motion = {
  camera: string;
  speed: string;
  amplitude: string;
  action: string[];
  actionNote: string; // свободный текст про действие
  scenery: string[];
  sceneryNote: string;
  light: string[];
  minimal: boolean; // принцип минимального движения
  noMorph: boolean; // держать внешность
};
export const EMPTY_MOTION: Motion = {
  camera: 'push',
  speed: 'slow',
  amplitude: 'small',
  action: ['breathe'],
  actionNote: '',
  scenery: [],
  sceneryNote: '',
  light: [],
  minimal: true,
  noMorph: true,
};

const clean = (v?: string) => stripJunk((v || '').trim().replace(/\s+/g, ' '));
const pick = (list: Option[], ids: string[]) =>
  ids.map(id => list.find(o => o.id === id)?.text).filter((t): t is string => !!t);
const one = (list: Option[], id: string) => list.find(o => o.id === id)?.text || '';

export type MotionContext = {heroes: {name: string; look?: string}[]};

/** Итоговый абзац: камера, субъект с действием, окружение, свет, затем страховки. */
export function buildMotionPrompt(m: Motion, ctx: MotionContext): string {
  const cameraBase = one(CAMERA_MOVES, m.camera);
  const amplitude = m.minimal ? 'very subtle' : one(AMPLITUDES, m.amplitude);
  const camera =
    m.camera === 'static'
      ? cameraBase
      : [
          [one(SPEEDS, m.speed), cameraBase].filter(Boolean).join(' '),
          amplitude && `${amplitude} camera movement`,
        ]
          .filter(Boolean)
          .join(', ');
  const who = ctx.heroes
    .map(h => (h.look ? `${clean(h.name)} (${clean(h.look)})` : clean(h.name)))
    .filter(Boolean)
    .join(' and ');
  const doing = [...pick(ACTIONS, m.action), clean(m.actionNote)].filter(Boolean).join(', ');
  const subject = [who, doing].filter(Boolean).join(': ');
  const scenery = [...pick(SCENERY, m.scenery), clean(m.sceneryNote)].filter(Boolean).join(', ');
  const light = pick(LIGHT_SHIFT, m.light).join(', ');
  const guard = [
    m.noMorph ? 'maintain subject consistency, no morphing' : '',
    m.minimal ? 'minimal motion, the framing stays stable' : '',
  ]
    .filter(Boolean)
    .join(', ');
  return [camera, subject, scenery, light, guard]
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .map(part => (/[.!?]$/.test(part) ? part : part + '.'))
    .join(' ');
}

// «Тяжёлые» действия, которые нейросеть плохо тянет в одном коротком шоте.
const HEAVY =
  /(встал|встаёт|встает|поднялся|повернул|поворачива|вышел|выход|уходит|ушёл|убега|бежит|побежал|прыга|упал|падает|уехал|уезжает|stands? up|gets? up|turns? around|walks? away|runs?\b|jumps?\b|exits?\b|gets? out|drives? off|falls?\b)/gi;
const CHAIN = /(\bзатем\b|\bпотом\b|\bпосле этого\b|\bпосле чего\b|\bи затем\b|\band then\b|\bthen\b|→|->)/gi;

export type Overload = {warn: boolean; reasons: string[]};

/** Предупреждение, если описано слишком много действий для одного шота. Запуск не блокируется. */
export function overload(m: Motion): Overload {
  const text = `${m.actionNote} ${m.sceneryNote}`;
  const reasons: string[] = [];
  const heavy = new Set((text.match(HEAVY) || []).map(x => x.toLowerCase().slice(0, 5)));
  if (heavy.size >= 2) reasons.push('несколько крупных действий подряд (встать, повернуться, выйти)');
  if ((text.match(CHAIN) || []).length >= 1 && heavy.size >= 1)
    reasons.push('цепочка «затем… потом…»: нейросеть лучше держит одно состояние');
  if (m.action.length + (m.actionNote.trim() ? 1 : 0) > 3)
    reasons.push('больше трёх действий героя в одном шоте');
  return {warn: reasons.length > 0, reasons};
}

/** Seedance 2.5 читает первый референс по тегу: добавляем его, чтобы фото считалось стартовым кадром. */
export function withFramePrefix(model: string, prompt: string): string {
  return model === 'seedance-2.5'
    ? `@image1 is the opening frame, keep its subject and composition exactly. ${prompt}`.trim()
    : prompt;
}
