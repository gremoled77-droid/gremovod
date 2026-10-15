import {useEffect, useRef, useState} from 'react';
import {apiFetch} from './api';

export type ActivityItem = {
  id: string;
  source: 'api' | 'external' | 'native';
  kind: string;
  provider: string;
  model: string;
  status: string;
  raw_status: string;
  created_at: string;
  prompt: string;
  asset_ids: string[];
  node_id?: string | null;
  delivery?: {state: string} | null;
};

/** Один долгий запрос вместо набора таймеров: сервер отвечает при изменении или через ~25 с. */
export default function useActivity(projectId: string) {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [error, setError] = useState('');
  const kick = useRef<() => void>(() => undefined);
  useEffect(() => {
    if (!projectId) {
      setItems([]);
      return;
    }
    let alive = true;
    let version = '';
    const controller = new AbortController();
    const loop = async () => {
      while (alive) {
        try {
          const r = await apiFetch(
            `/api/activity?project_id=${encodeURIComponent(projectId)}&since=${version}&wait=20`,
            {signal: controller.signal}
          );
          if (!r.ok) throw Error('Лента заданий недоступна');
          const d = await r.json();
          if (!alive) return;
          version = d.version;
          if (d.changed) setItems(d.items);
          setError('');
        } catch (e) {
          if (!alive) return;
          setError(e instanceof Error ? e.message : String(e));
          await new Promise(res => window.setTimeout(res, 4000));
        }
      }
    };
    kick.current = () => {
      version = '';
    };
    void loop();
    return () => {
      alive = false;
      controller.abort();
    };
  }, [projectId]);
  return {items, error, reset: () => kick.current()};
}
