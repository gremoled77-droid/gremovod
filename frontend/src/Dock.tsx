import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {useSharedActivity} from './ActivityContext';
import WaitingTray from './WaitingTray';

type Budget = {
  project_limit_usd: number;
  daily_limit_usd: number;
  project_reserved_usd: number;
  daily_reserved_usd: number;
};
const STATUS: Record<string, string> = {
  queued: 'в очереди',
  running: 'идёт',
  saving: 'сохраняется',
  done: 'готово',
  failed: 'ошибка',
  attention: 'нужна проверка',
  waiting_external: 'ждёт картинку',
  cancelled: 'отменено',
};
const ACTIVE = new Set(['queued', 'running', 'saving', 'waiting_external']);

export const countActive = (items: {status: string}[]) => items.filter(i => ACTIVE.has(i.status)).length;

/** Правая панель: очередь заданий и расход. Остаётся доступной на любом этапе. */
export default function Dock({projectId, onClose}: {projectId: string; onClose: () => void}) {
  const {items} = useSharedActivity();
  const [budget, setBudget] = useState<Budget | null>(null);
  useEffect(() => {
    if (!projectId) return;
    let alive = true;
    const load = () =>
      void apiFetch('/api/budgets/' + encodeURIComponent(projectId))
        .then(r => (r.ok ? r.json() : null))
        .then(d => alive && d && setBudget(d))
        .catch(() => undefined);
    load();
    const t = window.setInterval(load, 15000);
    return () => {
      alive = false;
      window.clearInterval(t);
    };
  }, [projectId, items.length]);
  const bar = (used: number, limit: number) => Math.min(100, limit > 0 ? (used / limit) * 100 : 0);
  return (
    <aside className="dock" aria-label="Очередь и бюджет">
      <div className="dock-head">
        <b>Очередь и бюджет</b>
        <button aria-label="Закрыть" onClick={onClose}>
          ×
        </button>
      </div>
      {budget && (
        <div className="dock-budget">
          <div>
            <span>Проект</span>
            <b>
              ${budget.project_reserved_usd.toFixed(2)} / ${budget.project_limit_usd.toFixed(2)}
            </b>
            <i style={{width: bar(budget.project_reserved_usd, budget.project_limit_usd) + '%'}} />
          </div>
          <div>
            <span>Сегодня</span>
            <b>
              ${budget.daily_reserved_usd.toFixed(2)} / ${budget.daily_limit_usd.toFixed(2)}
            </b>
            <i style={{width: bar(budget.daily_reserved_usd, budget.daily_limit_usd) + '%'}} />
          </div>
        </div>
      )}
      <WaitingTray />
      <div className="dock-list">
        {items.slice(0, 30).map(i => (
          <div key={i.id} className={'dock-item st-' + i.status}>
            <b>{i.model}</b>
            <span>{STATUS[i.status] || i.status}</span>
            <small>{i.prompt.slice(0, 70)}</small>
          </div>
        ))}
        {!items.length && <p className="muted">Заданий пока нет. Запусти генерацию на этапе «Кадры».</p>}
      </div>
    </aside>
  );
}
