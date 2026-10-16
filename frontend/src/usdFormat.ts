/** Малые суммы (доли цента за LLM-запрос) показываем с точностью до миллионных, чтобы не терять их как $0.0000. */
export const smallUsd = (value: number) =>
  '$' + (value === 0 ? '0' : value < 0.01 ? value.toFixed(6) : value.toFixed(4));
