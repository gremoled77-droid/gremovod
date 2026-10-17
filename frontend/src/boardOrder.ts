/** Сдвигает элемент списка на delta позиций; null, если сдвиг невозможен. */
export function moveItem<T>(ids: T[], index: number, delta: number): T[] | null {
  const target = index + delta;
  if (index < 0 || index >= ids.length || target < 0 || target >= ids.length || delta === 0) return null;
  const next = ids.slice();
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

/** Меняет состав выбранных id: добавляет или убирает один id, не дублируя. */
export function toggleId(ids: string[], id: string, on: boolean): string[] {
  const without = ids.filter(x => x !== id);
  return on ? [...without, id] : without;
}
