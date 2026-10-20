export type N8nAllowance = {role: string; cap_usd: number; model?: string; note?: string};
export type N8nRoleRow = {role: string; cap: string; model: string; note: string};

export function capUsd(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed) || parsed < 0) return null;
  return Math.round(parsed * 1e6) / 1e6;
}

export function roleRows(allowances: N8nAllowance[]): N8nRoleRow[] {
  return [...allowances]
    .sort((a, b) => a.role.localeCompare(b.role))
    .map(a => ({role: a.role, cap: String(a.cap_usd), model: a.model ?? '', note: a.note ?? ''}));
}

export function newRoleRow(rows: N8nRoleRow[], role: string, cap: string): N8nRoleRow | null {
  const name = role.trim().toUpperCase();
  if (!name || !/^[A-Z0-9_.-]{1,32}$/.test(name)) return null;
  if (rows.some(r => r.role === name)) return null;
  return {role: name, cap: cap.trim(), model: '', note: ''};
}

export function changedRows(
  rows: N8nRoleRow[],
  saved: N8nAllowance[]
): {role: string; cap_usd: number; model: string; note: string}[] {
  const before = new Map(saved.map(a => [a.role, a.cap_usd]));
  const out: {role: string; cap_usd: number; model: string; note: string}[] = [];
  for (const row of rows) {
    const parsed = capUsd(row.cap);
    if (parsed === null) continue;
    const previous = before.get(row.role);
    if (previous === undefined || Math.abs(previous - parsed) > 1e-9)
      out.push({role: row.role, cap_usd: parsed, model: row.model, note: row.note});
  }
  return out;
}
