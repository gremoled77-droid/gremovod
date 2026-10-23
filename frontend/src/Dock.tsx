import {useEffect, useState} from 'react';
import {Check, RefreshCw, TimerOff, Trash2} from 'lucide-react';
import {apiFetch} from './api';
import {useSharedActivity} from './ActivityContext';
import {KIND_LABELS, modelLabel} from './modelLabels';
import Lightbox from './Lightbox';
import GenerationReview, {type GenerationRequest} from './GenerationReview';
import {recallRequest} from './jobRequests';

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
const FAILED = new Set(['failed', 'attention', 'cancelled']);
const ACTIVE = new Set(['queued', 'running', 'saving', 'waiting_external']);
// Как FINAL_JOB_STATUSES в backend/main.py: остальные задания API ещё ждут ответа и блокируют такой же запрос.
const FINAL_RAW = new Set(['completed', 'failed', 'cancelled', 'canceled', 'succeeded', 'done', 'expired']);

export const countActive = (items: {status: string}[]) => items.filter(i => ACTIVE.has(i.status)).length;

/** Правая панель: очередь заданий и расход. Остаётся доступной на любом этапе. */
export default function Dock({projectId, onClose}: {projectId: string; onClose: () => void}) {
  const {items} = useSharedActivity();
  const [budget, setBudget] = useState<Budget | null>(null),
    [view, setView] = useState(-1),
    [retry, setRetry] = useState<GenerationRequest | null>(null),
    [error, setError] = useState('');
  const shown = items.slice(0, 30);
  const gallery = shown.filter(i => i.status === 'done' && i.kind === 'image' && i.asset_ids[0]);
  const hide = async (id: string) => {
    setError('');
    const r = await apiFetch(`/api/activity/${id}/hide`, {method: 'POST'});
    if (!r.ok) setError('Не удалось убрать задание');
  };
  const stopWaiting = async (id: string) => {
    const ok = window.confirm(
      'Снять ожидание? Только если в истории PiAPI задачи нет или она с ошибкой. Задание станет ошибкой, резерв бюджета освободится, такой же запрос можно будет отправить снова.'
    );
    if (!ok) return;
    setError('');
    const r = await apiFetch(`/api/jobs/${id}/stop-waiting`, {method: 'POST'});
    if (!r.ok) setError('Не удалось снять ожидание');
  };
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
      <div className="dock-list">
        {error && <p role="alert">{error}</p>}
        {shown.map(i => {
          const thumb = i.status === 'done' && i.kind === 'image' ? i.asset_ids[0] : '';
          const saved = FAILED.has(i.status) ? recallRequest(i.id) : null;
          const stuck = i.source === 'api' && !FINAL_RAW.has(i.raw_status.toLowerCase());
          const stop = (
            <button
              title="Снять ожидание (после проверки истории PiAPI)"
              aria-label="Снять ожидание"
              onClick={() => void stopWaiting(i.id)}
            >
              <TimerOff size={15} />
            </button>
          );
          return (
            <div key={i.id} className={'dock-item st-' + i.status}>
              <b>{modelLabel(i.model)}</b>
              {thumb ? (
                <button
                  className="dock-thumb"
                  aria-label="Открыть результат"
                  onClick={() => setView(gallery.findIndex(g => g.id === i.id))}
                >
                  <img src={`/api/library/${thumb}/thumbnail`} alt="" loading="lazy" />
                  <Check size={14} aria-label="готово" />
                </button>
              ) : i.status === 'done' ? (
                <span className="dock-ok" title="готово">
                  <Check size={16} />
                </span>
              ) : FAILED.has(i.status) ? (
                <span className="dock-actions">
                  <button
                    title={
                      saved ? 'Обновить: новая оценка цены и подтверждение' : 'Исходные параметры недоступны'
                    }
                    aria-label="Обновить"
                    disabled={!saved}
                    onClick={() => saved && setRetry(saved)}
                  >
                    <RefreshCw size={15} />
                  </button>
                  {stuck ? (
                    stop
                  ) : (
                    <button title="Убрать из очереди" aria-label="Убрать" onClick={() => void hide(i.id)}>
                      <Trash2 size={15} />
                    </button>
                  )}
                </span>
              ) : stuck ? (
                <span className="dock-actions">{stop}</span>
              ) : (
                <span>{STATUS[i.status] || i.status}</span>
              )}
              <small title={i.prompt}>
                {FAILED.has(i.status) || stuck ? (STATUS[i.status] || i.status) + ' · ' : ''}
                {KIND_LABELS[i.kind] || i.kind} · {i.prompt.slice(0, 50)}
              </small>
            </div>
          );
        })}
        {!items.length && <p className="muted">Заданий пока нет. Запусти генерацию на этапе «Кадры».</p>}
      </div>
      {view >= 0 && gallery[view] && (
        <Lightbox
          items={gallery.map(g => ({
            url: `/api/library/${g.asset_ids[0]}/file`,
            title: modelLabel(g.model),
            caption: g.prompt.slice(0, 80),
          }))}
          index={view}
          onIndex={setView}
          onClose={() => setView(-1)}
        />
      )}
      {retry && (
        <GenerationReview request={retry} onClose={() => setRetry(null)} onSubmitted={() => setRetry(null)} />
      )}
    </aside>
  );
}
