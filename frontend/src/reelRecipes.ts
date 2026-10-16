export type RecipeField = {key: string; label: string; default: string; hint?: string};
export type RefSlot = {n: number; role: string; required: boolean; note: string};
export type RecipeStep = {
  title: string;
  kind: 'image' | 'video';
  model: string;
  duration?: number;
  aspect_ratio?: string;
  prompt: string;
};
export type Look = {label: string; text: string};
export type Recipe = {
  id: string;
  title: string;
  emoji: string;
  family: string;
  kind: string;
  difficulty: string;
  hook: string;
  duration: number;
  aspect_ratio: string;
  resolution: string;
  audio: boolean;
  looks: string[];
  ref_slots: RefSlot[];
  fields: RecipeField[];
  beats: {t: string; text: string}[];
  why: string[];
  pitfalls: string[];
  source: string;
  steps: RecipeStep[];
  builtin: boolean;
  verified_at: string | null;
  estimate_usd: Record<string, number>;
};

export const KIND_LABEL: Record<string, string> = {
  one_take: 'один дубль',
  two_step: 'картинка → видео',
  chain: 'цепочка клипов',
  custom: 'свой',
};

export function defaultValues(recipe: Recipe): Record<string, string> {
  const values: Record<string, string> = {};
  for (const f of recipe.fields) values[f.key] = f.default;
  if (recipe.looks.length) values.look = recipe.looks[0];
  return values;
}

/** Подставляет {{поле}} значениями формы; {{look}} заменяется текстом выбранного стиля. */
export function fillPrompt(template: string, values: Record<string, string>, looks: Record<string, Look>) {
  return template.replace(/\{\{(\w+)\}\}/g, (whole, key: string) => {
    if (key === 'look') return looks[values.look]?.text ?? whole;
    const value = values[key];
    return value === undefined ? whole : value.trim();
  });
}

export function filterRecipes(recipes: Recipe[], family: string, query: string) {
  const q = query.trim().toLowerCase();
  return recipes.filter(
    r =>
      (family === 'all' || r.family === family) &&
      (!q || (r.title + ' ' + r.hook + ' ' + r.family).toLowerCase().includes(q))
  );
}

export const money = (v: number | undefined) => '$' + (v ?? 0).toFixed(2);
