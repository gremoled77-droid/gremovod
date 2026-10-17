import {useEffect, useState} from 'react';
import {apiFetch} from './api';

type Rule = {values?: (string | number)[]; default?: string | number};
type Spec = {
  kind: string;
  options?: Record<string, Rule>;
  verified_at?: string;
  launch_enabled?: boolean;
  prompt_only?: boolean;
};
type Row = {label: string; prices: (number | null)[]};
type Table = {id: string; cols: string[]; rows: Row[]; verified?: string; note?: string};

const ROW_KEYS = ['variant', 'quality'];
const PRICE_KEYS = ['variant', 'quality', 'size', 'resolution'];

const combos = (dims: [string, (string | number)[]][]): Record<string, string | number>[] =>
  dims.reduce<Record<string, string | number>[]>(
    (acc, [key, values]) => acc.flatMap(o => values.map(v => ({...o, [key]: v}))),
    [{}]
  );

const cache = new Map<string, Promise<number | null>>();
/** Цена одной картинки по сухому прогону на сервере (сеть не трогает); повторы берутся из памяти. */
export function price(model: string, options: Record<string, string | number>): Promise<number | null> {
  const key = JSON.stringify([model, options]);
  let hit = cache.get(key);
  if (!hit) {
    hit = (async () => {
      try {
        const r = await apiFetch('/api/model-jobs/preview', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({model_id: model, prompt: 'price', options, reference_urls: []}),
        });
        if (!r.ok) return null;
        const usd = Number((await r.json()).estimated_usd);
        return Number.isFinite(usd) ? usd : null;
      } catch {
        return null;
      }
    })();
    cache.set(key, hit);
  }
  return hit;
}

export const cents = (usd: number | null) =>
  usd === null ? '—' : String(Math.round(usd * 1000) / 10).replace('.', ',') + ' ¢';
const fmt = cents;

/** Цена каждого значения параметров размера, качества и варианта при текущем выборе остальных. */
export function useOptionPrices(
  model: string,
  schema: Record<string, Rule> | undefined,
  current: Record<string, string | number>
) {
  const [prices, setPrices] = useState<Record<string, Record<string, number | null>>>({});
  const signature = JSON.stringify([model, current]);
  useEffect(() => {
    let live = true;
    void (async () => {
      const out: Record<string, Record<string, number | null>> = {};
      for (const key of PRICE_KEYS) {
        const values = schema?.[key]?.values;
        if (!values) continue;
        out[key] = {};
        for (const v of values) out[key][String(v)] = await price(model, {...current, [key]: v});
      }
      if (live) setPrices(out);
    })();
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);
  return prices;
}

/** Диапазон цен модели по всем размерам, качествам и вариантам: «0,4–6 ¢» или одна цена, как у Qwen. */
export function useModelRange(model: string, schema: Record<string, Rule> | undefined) {
  const [range, setRange] = useState('');
  useEffect(() => {
    let live = true;
    void (async () => {
      const dims = PRICE_KEYS.filter(k => schema?.[k]?.values?.length).map(
        k => [k, schema![k].values!] as [string, (string | number)[]]
      );
      const found: number[] = [];
      for (const o of combos(dims)) {
        const p = await price(model, o);
        if (p !== null) found.push(p);
      }
      if (!live || !found.length) return;
      const lo = Math.min(...found);
      const hi = Math.max(...found);
      setRange(lo === hi ? cents(lo) : cents(lo).replace(' ¢', '') + '–' + cents(hi));
    })();
    return () => {
      live = false;
    };
  }, [model, schema]);
  return range;
}

/** Цены за одну картинку по каждой модели, размеру и качеству. Считает сервер по тем же формулам, что и оценка перед запуском; сети не трогает. */
export default function PriceTable({
  specs,
  labels,
  models,
}: {
  specs: Record<string, Spec>;
  labels: Record<string, string>;
  models: string[];
}) {
  const [open, setOpen] = useState(false);
  const [tables, setTables] = useState<Table[] | null>(null);

  useEffect(() => {
    if (!open || tables) return;
    let live = true;
    void (async () => {
      const out: Table[] = [];
      for (const id of models) {
        const spec = specs[id];
        if (!spec || spec.kind !== 'image') continue;
        const schema = spec.options || {};
        const has = (k: string) => !!schema[k]?.values?.length;
        const rowDims = ROW_KEYS.filter(has);
        const colDim = rowDims.length && has('size') ? 'size' : null;
        const lineDims = rowDims.length
          ? rowDims
          : PRICE_KEYS.filter(k => has(k) && k !== 'variant' && k !== 'quality').slice(0, 1);
        const colValues = colDim ? schema[colDim].values!.map(String) : [''];
        const rows: Row[] = [];
        for (const line of combos(
          lineDims.map(k => [k, schema[k].values!] as [string, (string | number)[]])
        )) {
          const prices: (number | null)[] = [];
          for (const col of colValues) prices.push(await price(id, colDim ? {...line, [colDim]: col} : line));
          rows.push({label: lineDims.map(k => line[k]).join(' · ') || 'цена за картинку', prices});
        }
        // Одинаковая цена при любом качестве (GPT Image 2.5 без суффикса): одна строка вместо трёх.
        const merged: Row[] = [];
        for (const row of rows) {
          const head = row.label.split(' · ')[0];
          const same =
            rowDims.length > 1
              ? merged.find(m => m.label.startsWith(head + ' ·') || m.label === head)
              : undefined;
          if (same && JSON.stringify(same.prices) === JSON.stringify(row.prices)) {
            same.label = head;
          } else merged.push(row);
        }
        out.push({
          id,
          cols: colDim ? colValues : [''],
          rows: merged,
          verified: spec.verified_at,
          note: spec.launch_enabled === false ? 'запуск выключен' : undefined,
        });
        if (!live) return;
      }
      if (live) setTables(out);
    })();
    return () => {
      live = false;
    };
  }, [open, tables, specs, models]);

  return (
    <details className="cs-prices" open={open} onToggle={e => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>Цены PiAPI по моделям</summary>
      {open && !tables && <small className="muted">Считаю…</small>}
      {tables?.map(t => (
        <div key={t.id} className="cs-price-model">
          <b>
            {labels[t.id] || t.id}
            {t.verified && <em> · проверено {t.verified}</em>}
            {t.note && <em> · {t.note}</em>}
          </b>
          <div className="cs-price-scroll">
            <table>
              {t.cols.length > 1 || t.cols[0] ? (
                <thead>
                  <tr>
                    <th />
                    {t.cols.map(c => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
              ) : null}
              <tbody>
                {t.rows.map(r => (
                  <tr key={r.label}>
                    <td>{r.label}</td>
                    {r.prices.map((p, i) => (
                      <td key={i}>{fmt(p)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
      {tables && (
        <small className="muted">
          Цена за одну картинку, из каталога студии. Перед запуском оценка пересчитывается и требует
          подтверждения; фактическое списание определяет PiAPI.
        </small>
      )}
    </details>
  );
}
