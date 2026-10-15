// Three-way merge: accept disjoint edits; stop when both changed the same value.
export function mergeProject<T>(base: T, local: T, remote: T, path = ''): {value: T; conflicts: string[]} {
  const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
  if (same(local, base)) return {value: remote, conflicts: []};
  if (same(remote, base) || same(local, remote)) return {value: local, conflicts: []};
  const object = (x: unknown): x is Record<string, unknown> =>
    !!x && typeof x === 'object' && !Array.isArray(x);
  if (object(base) && object(local) && object(remote)) {
    const result: Record<string, unknown> = {},
      conflicts: string[] = [];
    for (const key of new Set([...Object.keys(base), ...Object.keys(local), ...Object.keys(remote)])) {
      const merged = mergeProject(base[key], local[key], remote[key], path ? path + '.' + key : key);
      if (merged.value !== undefined) result[key] = merged.value;
      conflicts.push(...merged.conflicts);
    }
    return {value: result as T, conflicts};
  }
  return {value: local, conflicts: [path || 'проект']};
}
