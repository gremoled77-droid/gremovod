/** Результаты узлов (по ленте заданий), которых ещё нет в загруженной библиотеке: по ним нужно обновить библиотеку. */
export function missingAssetIds(results: Record<string, string>, library: {id: string}[]): string[] {
  const known = new Set(library.map(a => a.id));
  return [...new Set(Object.values(results))].filter(id => id && !known.has(id)).sort();
}
