import {useCallback, useEffect, useState, type ReactNode} from 'react';
import FrameSoundTab from './FrameSoundTab';
import {loadSound, type SoundContext} from './soundApi';
import VoicesTab from './VoicesTab';

const TABS = [
  {id: 'voices', label: 'Голоса'},
  {id: 'frames', label: 'Звук по кадрам'},
  {id: 'refs', label: 'Референсы голоса'},
] as const;
type Tab = (typeof TABS)[number]['id'];

/** Экран «Звук»: библиотека голосов, звуковые заметки кадров и прежний Audio Lab. */
export default function SoundScreen({projectId, audioLab}: {projectId: string; audioLab: ReactNode}) {
  const [tab, setTab] = useState<Tab>('voices'),
    [ctx, setCtx] = useState<SoundContext | null>(null),
    [loaded, setLoaded] = useState(false),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false);
  const reload = useCallback(async () => {
    try {
      setCtx(projectId ? await loadSound(projectId) : null);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoaded(true);
    }
  }, [projectId]);
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
    <section className="panel snd">
      <div className="panel-title">
        <h2>Звук</h2>
      </div>
      <div className="chips" role="tablist" aria-label="Разделы звука">
        {TABS.map(t => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            className={tab === t.id ? 'primary' : ''}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {error && <p role="alert">{error}</p>}
      {busy && <p className="muted">Сохраняю…</p>}
      {tab === 'refs' ? (
        audioLab
      ) : !loaded ? (
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
