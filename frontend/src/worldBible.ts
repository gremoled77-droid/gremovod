/** «Мир» из задания ролика: системный промпт для LLM, разбор JSON-ответа и слияние с уже заполненными полями. */
export const WORLD_FIELDS = [
  ['look', 'Визуальный стиль'],
  ['environment', 'Архитектура и среда'],
  ['time', 'Время суток и сезон'],
  ['tech', 'Уровень технологий'],
  ['textures', 'Фактуры и материалы'],
  ['palette', 'Палитра'],
  ['lighting', 'Освещение'],
  ['camera', 'Камера и оптика'],
  ['mood', 'Настроение'],
  ['rules', 'Неизменные правила'],
  ['avoid', 'Что запрещено'],
] as const;
export type WorldKey = (typeof WORLD_FIELDS)[number][0];
export type World = Record<WorldKey, string>;

export const WORLD_SYSTEM = `Ты арт-директор мультсериала. По заданию ролика составь «Паспорт мира» (10–15 строк, якорь единого стиля для всех сцен): короткие конкретные описания для промптов генерации картинок и видео.
Верни ТОЛЬКО JSON без пояснений и без markdown, ровно с такими ключами (значения — строки на русском, 1–3 предложения, без воды):
${WORLD_FIELDS.map(([k, label]) => `"${k}": ${label}`).join('\n')}
Правила: не придумывай новых героев, если их нет в задании; не пиши названия моделей и технические параметры API; в "avoid" перечисли, чего не должно быть в кадре.`;

/** Достаёт JSON из ответа, даже если модель обернула его в ```json или добавила текст вокруг. */
export function parseWorld(text: string): Partial<World> {
  const start = text.indexOf('{'),
    end = text.lastIndexOf('}');
  if (start < 0 || end <= start) throw Error('Ответ модели не похож на JSON');
  let raw: unknown;
  try {
    raw = JSON.parse(text.slice(start, end + 1));
  } catch {
    throw Error('Не удалось разобрать JSON из ответа модели');
  }
  const out: Partial<World> = {};
  for (const [k] of WORLD_FIELDS) {
    const v = (raw as Record<string, unknown>)?.[k];
    if (typeof v === 'string' && v.trim()) out[k] = v.trim();
  }
  if (!Object.keys(out).length) throw Error('В ответе модели нет полей мира');
  return out;
}

/** Пустые поля заполняются сразу; занятые, где ответ отличается, попадают в conflicts для вопроса «заменить?». */
export function mergeWorld(current: Partial<World> | undefined, next: Partial<World>) {
  const fill: Partial<World> = {},
    conflicts: Partial<World> = {};
  for (const [k] of WORLD_FIELDS) {
    const v = next[k];
    if (!v) continue;
    const old = (current?.[k] || '').trim();
    if (!old) fill[k] = v;
    else if (old !== v) conflicts[k] = v;
  }
  return {fill, conflicts};
}

/** Паспорт мира одним куском: по строке на заполненное поле. Вставляется в другие инструменты как якорь стиля. */
export function passportText(world: Partial<World> | undefined): string {
  return WORLD_FIELDS.map(([k, label]) => ({label, value: (world?.[k] || '').trim().replace(/\s+/g, ' ')}))
    .filter(f => f.value)
    .map(f => `${f.label}: ${f.value}`)
    .join('\n');
}
