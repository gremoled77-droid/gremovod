import {useEffect, useMemo, useRef, useState} from 'react';
import type {Edge, Node} from '@xyflow/react';
import {apiFetch} from './api';
import {llmPrices, priceRequests, type PriceRequest} from './workflowPriceModel.ts';

const keyOf = (r: PriceRequest) => JSON.stringify([r.model, r.prompt, r.options, r.refs]);

/** Цена каждого узла и сумма по графу; обновляется спустя паузу после правок, повторы берутся из памяти. */
export function useNodePrices(
  projectId: string,
  nodes: Node[],
  edges: Edge[],
  results: Record<string, string>
) {
  const cache = useRef(new Map<string, number | null>());
  const [version, setVersion] = useState(0);
  const requests = useMemo(() => priceRequests(nodes, edges, results), [nodes, edges, results]);
  const llm = useMemo(() => llmPrices(nodes, edges), [nodes, edges]);

  useEffect(() => {
    if (!projectId) return;
    const missing = requests.filter(r => !cache.current.has(keyOf(r)));
    if (!missing.length) return;
    const timer = window.setTimeout(async () => {
      for (const r of missing) {
        const key = keyOf(r);
        if (cache.current.has(key)) continue;
        let usd: number | null = null;
        try {
          const response = await apiFetch('/api/model-jobs/estimate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              project_id: projectId,
              model_id: r.model,
              prompt: r.prompt,
              options: r.options,
              reference_urls: Array.from(
                {length: r.refs},
                (_, i) => `https://example.invalid/price-${i}.png`
              ),
              node_id: r.nodeId,
            }),
          });
          if (response.ok) usd = Number((await response.json()).estimated_usd);
        } catch {
          usd = null;
        }
        cache.current.set(key, Number.isFinite(usd) ? usd : null);
        setVersion(v => v + 1);
      }
    }, 700);
    return () => {
      window.clearTimeout(timer);
    };
  }, [projectId, requests]);

  return useMemo(() => {
    const prices: Record<string, number | null> = {...llm};
    for (const r of requests) prices[r.nodeId] = cache.current.get(keyOf(r)) ?? null;
    const known = Object.values(prices).filter((v): v is number => typeof v === 'number');
    return {
      prices,
      total: known.reduce((a, b) => a + b, 0),
      pending: Object.values(prices).some(v => v === null),
    };
    // version нужен, чтобы пересчитать после ответа сервера
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requests, llm, version]);
}
