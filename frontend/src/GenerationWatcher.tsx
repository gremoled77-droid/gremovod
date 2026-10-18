import {useEffect, useRef, useState} from 'react';
import {apiFetch} from './api';
import {type ActivityItem} from './useActivity';
import {useSharedActivity} from './ActivityContext';

/** Интервалы опроса провайдера, мс. Потом подберём под конкретные модели через MODEL_POLL_MS. */
export const POLL_MS = {image: 5000, video: 15000};
export const MODEL_POLL_MS: Record<string, number> = {};

const LABELS: Record<string, string> = {
  'seedream-5-pro': 'Seedream 5 Pro',
  'seedream-5-lite': 'Seedream 5 Lite',
  'gpt-image-2': 'GPT Image 2.0',
  'gpt-image-2.5': 'GPT Image 2.5',
  'nano-banana-2.1': 'Nano Banana 2.1',
  'qwen-image-2.1': 'Qwen Image 2.1',
  'kie-seedream-5-pro': 'Seedream 5 Pro (KIE)',
  'kie-qwen-image-2.1': 'Qwen Image 2.1 (KIE)',
  'seedance-2.5': 'Seedance 2.5',
  'minimax-h3': 'MiniMax H3',
};
const ACTIVE = new Set(['queued', 'running', 'saving']);
const pollEvery = (item: ActivityItem) =>
  MODEL_POLL_MS[item.model] ?? (item.kind === 'video' ? POLL_MS.video : POLL_MS.image);

type Toast = {key: string; kind: 'ok' | 'bad'; title: string; text: string};

/** Невидимый наблюдатель: опрашивает API по активным заданиям и показывает пузырьки о готовности. */
export default function GenerationWatcher({projectId, onOpen}: {projectId: string; onOpen: () => void}) {
  const {items, reset} = useSharedActivity();
  const [toasts, setToasts] = useState<Toast[]>([]);
  const previous = useRef<Record<string, string> | null>(null);
  const lastPoll = useRef<Record<string, number>>({});
  const inFlight = useRef(new Set<string>());
  const itemsRef = useRef<ActivityItem[]>([]);
  itemsRef.current = items;

  // Опрос: раз в секунду смотрим, у каких активных заданий подошёл срок.
  useEffect(() => {
    if (!projectId) return;
    const timer = window.setInterval(() => {
      const now = Date.now();
      for (const item of itemsRef.current) {
        if (item.source !== 'api' || !ACTIVE.has(item.status) || inFlight.current.has(item.id)) continue;
        if (now - (lastPoll.current[item.id] || 0) < pollEvery(item)) continue;
        lastPoll.current[item.id] = now;
        inFlight.current.add(item.id);
        void apiFetch('/api/activity/refresh/' + encodeURIComponent(item.id), {method: 'POST'})
          .then(r => (r.ok ? reset() : undefined))
          .catch(() => undefined)
          .finally(() => inFlight.current.delete(item.id));
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [projectId]);

  // Пузырьки: только на переходах «шло → готово/ошибка», не на первой загрузке.
  useEffect(() => {
    const now: Record<string, string> = Object.fromEntries(items.map(i => [i.id, i.status]));
    if (previous.current) {
      const fresh: Toast[] = [];
      for (const item of items) {
        const before = previous.current[item.id];
        if (!before || !ACTIVE.has(before) || ACTIVE.has(item.status)) continue;
        const name = LABELS[item.model] || item.model;
        if (item.status === 'done')
          fresh.push({key: item.id, kind: 'ok', title: `${name}: готово`, text: item.prompt.slice(0, 60)});
        else if (item.status === 'failed' || item.status === 'attention')
          fresh.push({
            key: item.id,
            kind: 'bad',
            title: `${name}: ${item.status === 'failed' ? 'ошибка' : 'нужна проверка'}`,
            text: 'Открой «Создать», чтобы посмотреть подробности',
          });
      }
      if (fresh.length) setToasts(t => [...t, ...fresh]);
    }
    previous.current = now;
  }, [items]);

  useEffect(() => {
    if (!toasts.length) return;
    const timer = window.setTimeout(() => setToasts(t => t.slice(1)), 9000);
    return () => window.clearTimeout(timer);
  }, [toasts]);

  if (!toasts.length) return null;
  return (
    <div className="toast-stack" role="status" aria-live="polite">
      {toasts.map(t => (
        <div
          key={t.key}
          className={'toast toast-' + t.kind}
          onClick={() => {
            onOpen();
            setToasts(x => x.filter(y => y.key !== t.key));
          }}
        >
          <b>{t.title}</b>
          <span>{t.text}</span>
          <button
            aria-label="Закрыть"
            onClick={e => {
              e.stopPropagation();
              setToasts(x => x.filter(y => y.key !== t.key));
            }}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
