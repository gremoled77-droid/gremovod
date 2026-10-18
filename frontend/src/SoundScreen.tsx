import {useCallback, useEffect, useState} from 'react';
import FrameSoundTab from './FrameSoundTab';
import {loadSound, type SoundContext} from './soundApi';
import VoicesTab from './VoicesTab';
import {writeLocal} from './localDrafts';

const TABS = [
  {id: 'voices', label: 'Голоса'},
  {id: 'frames', label: 'Звук по кадрам'},
] as const;
type Tab = (typeof TABS)[number]['id'];

/** Экран «Звук»: библиотека голосов и звуковые заметки кадров. */
export default function SoundScreen({projectId}: {projectId: string}) {
  const [tab, setTab] = useState<Tab>('voices'),
    [sid, setSid] = useState(''),
    [ctx, setCtx] = useState<SoundContext | null>(null),
    [loaded, setLoaded] = useState(false),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const reload = useCallback(async () => {
    try {
      setCtx(projectId ? await loadSound(projectId, sid) : null);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoaded(true);
    }
  }, [projectId, sid]);
  useEffect(() => {
    void reload();
  }, [reload]);
  const run = (fn: () => Promise<void>) => {
    setBusy(true);
    setError('');
    fn()
      .catch(e => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setBusy(false));
  };
  return (
    <section className="snd">
      {!!ctx?.series.length && (
        <label>
          Серия
          <select
            value={ctx.sid}
            onChange={e => {
              setSid(e.target.value);
              writeLocal('studio:board-location', {pid: ctx.pid, sid: e.target.value});
            }}
          >
            {ctx.series.map(s => (
              <option key={s.id} value={s.id}>
                {s.title}
              </option>
            ))}
          </select>
        </label>
      )}
      <div className="world-tabs" role="tablist" aria-label="Разделы звука">
        {TABS.map(t => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            className={tab === t.id ? 'on' : ''}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      {busy && <p className="muted">Сохраняю…</p>}
      {!loaded ? (
        <p className="muted">Загружаю…</p>
      ) : !ctx ? (
        <p className="muted">
          Для проекта ещё нет постановки. Отправьте кадры в раскадровку, затем вернитесь сюда.
        </p>
      ) : tab === 'voices' ? (
        <VoicesTab
          pid={ctx.pid}
          voices={ctx.voices}
          heroes={ctx.heroes}
          onChanged={() => void reload()}
          run={run}
        />
      ) : (
        <FrameSoundTab ctx={ctx} onChanged={() => void reload()} run={run} />
      )}
    </section>
  );
}
