/** Промпт для генерации героя: описание героя + «Библия мира». Пустые поля пропускаются. */
export type Identity = {
  species: string;
  face: string;
  hair: string;
  eyes: string;
  costume: string;
  negative: string;
};
export type WorldFields = Partial<
  Record<'look' | 'palette' | 'lighting' | 'camera' | 'environment' | 'rules' | 'avoid', string>
>;

const clean = (v?: string) => (v || '').trim().replace(/\s+/g, ' ');

export function worldFilled(world?: WorldFields) {
  return !!clean(world?.look);
}

/** purpose: если задан (листы по ракурсам), кадровку и позу в первой строке не навязываем: их задаёт строка «Ракурс». */
export function buildCharacterPrompt(
  name: string,
  identity: Partial<Identity>,
  world?: WorldFields,
  purpose?: string
): string {
  const line = (label: string, value?: string) => (clean(value) ? `${label}: ${clean(value)}.` : '');
  const forbidden = [clean(identity.negative), clean(world?.avoid)].filter(Boolean).join('; ');
  const title = clean(name) || 'Герой';
  return [
    purpose
      ? `Лист персонажа «${title}» (${purpose}): один герой, чистый однотонный фон, без других людей и надписей.`
      : `Лист персонажа «${title}»: один герой в полный рост, вид спереди, нейтральная поза, чистый однотонный фон, без других людей и надписей.`,
    line('Вид', identity.species),
    line('Лицо', identity.face),
    line('Причёска', identity.hair),
    line('Глаза', identity.eyes),
    line('Одежда', identity.costume),
    line('Стиль мира', world?.look),
    line('Палитра', world?.palette),
    line('Освещение', world?.lighting),
    line('Неизменные правила', world?.rules),
    forbidden ? `Запрещено: ${forbidden}.` : '',
  ]
    .filter(Boolean)
    .join('\n');
}

/** Запрос листа героя: описание и мир, ракурс или эмоция. Рабочий образ идёт референсом, лицо не меняется. */
export function heroShotPrompt(
  name: string,
  identity: Partial<Identity>,
  world: WorldFields | undefined,
  shot: {label: string; prompt: string}
): string {
  return `${buildCharacterPrompt(name, identity, world, 'лист героя для сохранения внешности')}
Ракурс: ${shot.label}. ${shot.prompt}
Внешность как на референсе.`;
}
