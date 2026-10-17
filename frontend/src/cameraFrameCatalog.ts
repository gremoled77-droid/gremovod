/** Каталог панели «Камера и кадр»: ракурс, план, движение, свет. Фразы идут в промпт строками FRAME / CAMERA / LIGHT. */
export type FrameCat = 'angle' | 'size' | 'move' | 'light';
export type FrameItem = {id: string; cat: FrameCat; ru: string; en: string};

export const FRAME_CATS: {id: FrameCat; label: string; line: 'FRAME' | 'CAMERA' | 'LIGHT'}[] = [
  {id: 'angle', label: 'Ракурс', line: 'FRAME'},
  {id: 'size', label: 'План', line: 'FRAME'},
  {id: 'move', label: 'Движение', line: 'CAMERA'},
  {id: 'light', label: 'Свет', line: 'LIGHT'},
];

export const FRAME_ITEMS: FrameItem[] = [
  {id: 'eye', cat: 'angle', ru: 'На уровне глаз', en: 'eye-level shot'},
  {id: 'low', cat: 'angle', ru: 'Снизу вверх', en: 'low-angle shot looking up'},
  {id: 'high', cat: 'angle', ru: 'Сверху вниз', en: 'high-angle shot looking down'},
  {id: 'dutch', cat: 'angle', ru: 'Голландский угол', en: 'Dutch tilt'},
  {id: 'ots', cat: 'angle', ru: 'Из-за плеча', en: 'over-the-shoulder shot'},
  {id: 'bird', cat: 'angle', ru: 'Строго сверху', en: "bird's-eye top-down view"},

  {id: 'ecu', cat: 'size', ru: 'Деталь', en: 'extreme close-up on the eyes'},
  {id: 'cu', cat: 'size', ru: 'Крупный', en: 'close-up on the face'},
  {id: 'mcu', cat: 'size', ru: 'Плечевой', en: 'medium close-up'},
  {id: 'ms', cat: 'size', ru: 'Средний', en: 'medium shot'},
  {id: 'ws', cat: 'size', ru: 'Общий', en: 'wide shot showing the environment'},
  {id: 'ews', cat: 'size', ru: 'Дальний', en: 'extreme wide establishing shot'},

  {id: 'static', cat: 'move', ru: 'Статика', en: 'static locked-off camera'},
  {id: 'push', cat: 'move', ru: 'Наезд', en: 'slow push in'},
  {id: 'pull', cat: 'move', ru: 'Отъезд', en: 'slow pull out'},
  {id: 'pan', cat: 'move', ru: 'Панорама', en: 'slow pan to the right'},
  {id: 'tilt', cat: 'move', ru: 'Наклон вверх', en: 'tilt up'},
  {id: 'orbit', cat: 'move', ru: 'Облёт', en: 'orbit around the subject'},
  {id: 'track', cat: 'move', ru: 'Следом', en: 'tracking shot alongside the subject'},
  {id: 'crane', cat: 'move', ru: 'Кран вверх', en: 'crane up'},
  {id: 'hand', cat: 'move', ru: 'С рук', en: 'handheld camera'},

  {id: 'back', cat: 'light', ru: 'Контровой', en: 'backlight with rim light'},
  {id: 'side', cat: 'light', ru: 'Боковой', en: 'hard side light'},
  {id: 'top', cat: 'light', ru: 'Сверху', en: 'top light'},
  {id: 'window', cat: 'light', ru: 'Окно', en: 'soft window light'},
  {id: 'golden', cat: 'light', ru: 'Закат', en: 'golden hour warm light'},
  {id: 'neon', cat: 'light', ru: 'Неон', en: 'neon night light, pink and blue'},
  {id: 'lowkey', cat: 'light', ru: 'Low-key', en: 'low-key dramatic light'},
  {id: 'overcast', cat: 'light', ru: 'Пасмурно', en: 'soft overcast light'},
];

const lineRe = (label: string) => new RegExp('^' + label + ': ?(.*)$', 'm');
const known = new Set(FRAME_ITEMS.map(i => i.en));

/** Фразы каталога, уже стоящие в строках FRAME / CAMERA / LIGHT промпта. */
export function selectedFrameItems(prompt: string): FrameItem[] {
  const out: FrameItem[] = [];
  for (const label of ['FRAME', 'CAMERA', 'LIGHT']) {
    const match = prompt.match(lineRe(label));
    if (!match) continue;
    const parts = match[1].split(/\s*;\s*/);
    for (const item of FRAME_ITEMS) if (parts.includes(item.en)) out.push(item);
  }
  return out;
}

/** Выбор или снятие карточки. В категории ракурса, плана, движения и света активна одна фраза; чужой текст в строке сохраняется. */
export function toggleFrameItem(prompt: string, item: FrameItem): string {
  const cat = FRAME_CATS.find(c => c.id === item.cat)!;
  const sameCat = new Set(FRAME_ITEMS.filter(i => i.cat === item.cat).map(i => i.en));
  const re = lineRe(cat.line);
  const match = prompt.match(re);
  const parts = match ? match[1].split(/\s*;\s*/).filter(Boolean) : [];
  const had = parts.includes(item.en);
  const kept = parts.filter(p => !sameCat.has(p));
  const next = had ? kept : [...kept, item.en];
  const line = next.length ? `${cat.line}: ${next.join('; ')}` : '';
  if (match) {
    const replaced = prompt.replace(re, line);
    return replaced
      .replace(/\n{3,}/g, '\n\n')
      .replace(/^\n+/, '')
      .replace(/\n+$/, '');
  }
  if (!line) return prompt;
  return prompt.trimEnd() ? prompt.trimEnd() + '\n' + line : line;
}

/** Убрать конкретную фразу (крестик на чипе). */
export function removeFrameItem(prompt: string, item: FrameItem): string {
  return selectedFrameItems(prompt).some(i => i.id === item.id) ? toggleFrameItem(prompt, item) : prompt;
}

export const isCatalogPhrase = (phrase: string) => known.has(phrase);
