/** Лимит запуска по умолчанию и порог, выше которого нужна отдельная галочка. */
export const DEFAULT_LIMIT_USD = 2;
export const SAFE_LIMIT_USD = 2;
export const LIMIT_PRESETS = [0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 50];

/** Подпись быстрой суммы: центы — «25¢», доллары — «$2». */
export const presetLabel = (v: number) => (v < 1 ? Math.round(v * 100) + '¢' : '$' + v);
export const LIMIT_SLIDER_MAX = 50;

/** Стартовое значение: $2, а если оценка больше — ближайший доллар вверх. */
export function initialLimit(total: number): string {
  return String(Math.max(DEFAULT_LIMIT_USD, Math.ceil(total || 0)));
}

export function limitNeedsConfirm(limit: string | number): boolean {
  return Number(limit) > SAFE_LIMIT_USD;
}

/** Лимит годится для запуска: число, не меньше оценки, а выше $2 — только с галочкой. */
export function limitAllowed(total: number, limit: string | number, highConfirmed: boolean): boolean {
  const n = Number(limit);
  if (limit === '' || !Number.isFinite(n) || n <= 0 || n < total) return false;
  return !limitNeedsConfirm(n) || highConfirmed;
}
