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

export function buildCharacterPrompt(name: string, identity: Partial<Identity>, world?: WorldFields): string {
  const line = (label: string, value?: string) => (clean(value) ? `${label}: ${clean(value)}.` : '');
  const forbidden = [clean(identity.negative), clean(world?.avoid)].filter(Boolean).join('; ');
  return [
    `Лист персонажа «${clean(name) || 'Герой'}»: один герой в полный рост, вид спереди, нейтральная поза, чистый однотонный фон, без других людей и надписей.`,
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
