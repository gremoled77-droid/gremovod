/** Операторский промпт из 5 слоёв: кто и что делает, окружение и глубина, свет, оптика и камера, стиль и режиссёр.
 *  Собирается локально и бесплатно, на английском «языке оператора», без мусорных слов вроде «8K, masterpiece». */
import type {Identity, WorldFields} from './characterPrompt';

export type Option = {id: string; label: string; text: string};

export const DEPTH: Option[] = [
  {id: 'fg-blur', label: 'Передний план в расфокусе', text: 'out-of-focus foreground element'},
  {id: 'fg-glass', label: 'Стекло с каплями', text: 'rain-streaked glass in the foreground'},
  {
    id: 'fg-silhouette',
    label: 'Силуэт на переднем плане',
    text: 'dark foreground silhouette framing the subject',
  },
  {id: 'bg-depth', label: 'Глубокий фон', text: 'layered background with clear depth'},
  {id: 'bg-bokeh', label: 'Фон боке', text: 'background reduced to soft bokeh lights'},
];
export const ATMOSPHERE: Option[] = [
  {id: 'smoke', label: 'Дым', text: 'drifting smoke'},
  {id: 'rain', label: 'Капли и дождь', text: 'rain and water droplets in the air'},
  {id: 'fog', label: 'Туман', text: 'low fog'},
  {id: 'dust', label: 'Пыль в свете', text: 'dust motes catching the light'},
  {id: 'steam', label: 'Пар', text: 'rising steam'},
  {id: 'snow', label: 'Снег', text: 'falling snow'},
];
export const LIGHT_KEY: Option[] = [
  {id: 'rembrandt', label: 'Рембрандт', text: 'Rembrandt lighting'},
  {id: 'window', label: 'Мягкий свет из окна', text: 'soft window light from camera left'},
  {id: 'rim', label: 'Контровой', text: 'rim light separating the subject from the background'},
  {id: 'volumetric', label: 'Объёмный свет', text: 'volumetric light through haze'},
  {id: 'practical', label: 'Свет ламп и неона', text: 'practical lamp and neon light sources'},
  {id: 'overcast', label: 'Пасмурный рассеянный', text: 'soft overcast diffused light'},
];
export const LIGHT_TEMP: Option[] = [
  {id: 'warm', label: 'Тёплый 3200K', text: 'warm tungsten colour temperature'},
  {id: 'neutral', label: 'Нейтральный', text: 'neutral daylight colour temperature'},
  {id: 'cool', label: 'Холодный, синий час', text: 'cool blue-hour colour temperature'},
];
export const SHOT: Option[] = [
  {id: 'wide', label: 'Общий', text: 'wide establishing shot'},
  {id: 'full', label: 'Полный рост', text: 'full shot'},
  {id: 'medium', label: 'Средний', text: 'medium shot'},
  {id: 'mcu', label: 'Средне-крупный', text: 'medium close-up'},
  {id: 'close', label: 'Крупный', text: 'close-up'},
  {id: 'hands', label: 'Руки крупно', text: 'insert close-up of the hands and the object they hold'},
];
export const LENS: Option[] = [
  {id: '24', label: '24 мм', text: '24mm lens'},
  {id: '35', label: '35 мм', text: '35mm lens'},
  {id: '50', label: '50 мм', text: '50mm lens'},
  {id: '85', label: '85 мм', text: '85mm lens'},
];
export const APERTURE: Option[] = [
  {id: 'f18', label: 'f/1.8 боке', text: 'f/1.8 shallow depth of field'},
  {id: 'f28', label: 'f/2.8', text: 'f/2.8'},
  {id: 'f56', label: 'f/5.6 резко', text: 'f/5.6 deep focus'},
];
export const CAMERA: Option[] = [
  {id: 'alexa', label: 'Arri Alexa', text: 'shot on Arri Alexa'},
  {id: '16mm', label: '16 мм плёнка', text: '16mm film grain'},
  {id: 'anamorphic', label: 'Анаморф', text: 'anamorphic lens characteristics'},
];

export type Layers = {
  subject: string; // слой 1: что происходит
  environment: string; // слой 2: свободный текст про место
  depth: string[];
  atmosphere: string[];
  lightKey: string[]; // слой 3
  lightTemp: string;
  lightNote: string; // мотивация источника
  shot: string; // слой 4
  lens: string;
  aperture: string;
  camera: string;
  director: string; // слой 5, необязательно
};
export const EMPTY_LAYERS: Layers = {
  subject: '',
  environment: '',
  depth: [],
  atmosphere: [],
  lightKey: [],
  lightTemp: '',
  lightNote: '',
  shot: '',
  lens: '',
  aperture: '',
  camera: '',
  director: '',
};

// Мусорные слова качества: они не управляют кадром, лишь шумят в запросе.
const JUNK =
  /\b(8k|4k|2k|uhd|hd|masterpiece|best quality|ultra[- ]?detailed|hyper[- ]?realistic|trending on artstation)\b[,.]?/gi;

export function stripJunk(text: string): string {
  return text
    .replace(JUNK, '')
    .replace(/(?:\s*,\s*){2,}/g, ', ')
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+([,.])/g, '$1')
    .replace(/^[,\s]+|[,\s]+$/g, '');
}

const clean = (v?: string) => stripJunk((v || '').trim().replace(/\s+/g, ' '));
const pick = (list: Option[], ids: string[]) =>
  ids.map(id => list.find(o => o.id === id)?.text).filter((t): t is string => !!t);
const one = (list: Option[], id: string) => list.find(o => o.id === id)?.text || '';

export type OperatorContext = {
  heroes: {name: string; identity: Partial<Identity>}[];
  world?: WorldFields;
};

/** Итоговый промпт: по строке на слой, пустые слои пропускаются. */
export function buildOperatorPrompt(layers: Layers, ctx: OperatorContext): string {
  const who = ctx.heroes
    .map(h => {
      const look = [clean(h.identity.species), clean(h.identity.costume)].filter(Boolean).join(', ');
      return look ? `${clean(h.name)} (${look})` : clean(h.name);
    })
    .filter(Boolean)
    .join('; ');
  const subject = [
    clean(layers.subject),
    who ? `Subject: ${who}, appearance exactly as in the references` : '',
  ]
    .filter(Boolean)
    .join('. ');
  const environment = [
    clean(layers.environment),
    ...pick(DEPTH, layers.depth),
    ...pick(ATMOSPHERE, layers.atmosphere),
  ]
    .filter(Boolean)
    .join(', ');
  const light = [
    ...pick(LIGHT_KEY, layers.lightKey),
    one(LIGHT_TEMP, layers.lightTemp),
    clean(layers.lightNote),
  ]
    .filter(Boolean)
    .join(', ');
  const optics = [
    one(SHOT, layers.shot),
    one(LENS, layers.lens),
    one(APERTURE, layers.aperture),
    one(CAMERA, layers.camera),
  ]
    .filter(Boolean)
    .join(', ');
  const style = [
    clean(ctx.world?.look),
    clean(ctx.world?.palette),
    clean(layers.director) && `Directed by ${clean(layers.director)}`,
  ]
    .filter(Boolean)
    .join('. ');
  const avoid = clean(ctx.world?.avoid);
  const lines: [string, string][] = [
    ['Scene', subject],
    ['Environment', environment],
    ['Light', light],
    ['Camera', optics],
    ['Style', style],
    ['Avoid', avoid],
  ];
  return lines
    .filter(([, v]) => v)
    .map(([k, v]) => `${k}: ${v}.`.replace(/\.\.$/, '.'))
    .join('\n');
}

export const layersEmpty = (l: Layers) =>
  JSON.stringify({...l, subject: l.subject.trim()}) === JSON.stringify(EMPTY_LAYERS);
