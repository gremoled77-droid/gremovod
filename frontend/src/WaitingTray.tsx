import {useEffect, useRef, useState} from 'react';
import {useSharedActivity} from './ActivityContext';
import {
  attachExternalResult,
  cancelCodexJob,
  cancelExternalJob,
  copyText,
  openChatApp,
  loadExternalJob,
  type ExternalJobDetails,
} from './imageRoutes';

/** Each card owns its paste/file destination. Removing it or switching project cancels the listener. */
function ExternalCard({
  id,
  summary,
  reset,
  paste,
  setPaste,
}: {
  id: string;
  summary: string;
  reset: () => void;
  paste: boolean;
  setPaste: (active: boolean) => void;
}) {
  const [details, setDetails] = useState<ExternalJobDetails | null>(null);
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const locked = useRef(false);
  const fileInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    let active = true;
    setError('');
    void loadExternalJob(id)
      .then(d => {
        if (active) setDetails(d);
      })
      .catch(e => {
        if (active) setError(String(e));
      });
    return () => {
      active = false;
    };
  }, [id, revision]);

  const act = async (action: () => Promise<void>) => {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError('');
    try {
      await action();
      setPaste(false);
      reset();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      locked.current = false;
      setBusy(false);
    }
  };

  useEffect(() => {
    if (!paste || busy) return;
    const onPaste = (event: ClipboardEvent) => {
      if (event.defaultPrevented) return;
      const file = Array.from(event.clipboardData?.files || []).find(f => f.type.startsWith('image/'));
      if (file) {
        event.preventDefault();
        void act(() => attachExternalResult(id, file));
      }
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [paste, busy, id]);

  return (
    <div className="waiting-card">
      <b>Ждём картинку из ChatGPT</b>
      <small>{summary.slice(0, 90)}</small>
      {!details && (
        <button disabled={busy} onClick={() => setRevision(v => v + 1)}>
          Загрузить полное задание
        </button>
      )}
      {details && (
        <details>
          <summary>Полный промпт и референсы</summary>
          <textarea aria-label="Полный промпт для ChatGPT" readOnly rows={7} value={details.copy_text} />
          {details.references.length > 0 && <p>Скачай и приложи изображения в чат в этом порядке:</p>}
          {details.references.map(ref => (
            <p key={ref.asset_id}>
              <a href={ref.file_url} target="_blank" rel="noreferrer">
                Референс {ref.index} — {ref.role}
              </a>{' '}
              <a href={ref.file_url} download>
                Скачать
              </a>
            </p>
          ))}
        </details>
      )}
      <div className="waiting-actions">
        <button
          disabled={!details || busy}
          onClick={() =>
            void copyText(details!.copy_text).then(ok =>
              setNote(ok ? 'Полный промпт скопирован.' : 'Выдели полный текст выше и скопируй вручную.')
            )
          }
        >
          Копировать полный промпт
        </button>
        <button disabled={busy} onClick={openChatApp}>
          Открыть чат
        </button>
        <button disabled={busy} className={paste ? 'primary' : ''} onClick={() => setPaste(!paste)}>
          {paste ? 'Жду Ctrl+V…' : 'Вставить результат'}
        </button>
        <button disabled={busy} onClick={() => fileInput.current?.click()}>
          Загрузить результат…
        </button>
        <button
          disabled={busy}
          className="waiting-cancel"
          onClick={() => void act(() => cancelExternalJob(id))}
        >
          Отменить
        </button>
      </div>
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        hidden
        onChange={event => {
          const file = event.target.files?.[0];
          event.target.value = '';
          if (file) void act(() => attachExternalResult(id, file));
        }}
      />
      {busy && <p role="status">Сохраняется…</p>}
      {note && <p role="status">{note}</p>}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}

/** Activity summaries are for display only; the full request comes from the external-job endpoint. */
export default function WaitingTray() {
  const {items, reset} = useSharedActivity();
  const [pasteFor, setPasteFor] = useState('');
  const [error, setError] = useState('');
  const chat = items.filter(i => i.source === 'external' && i.status === 'waiting_external');
  const codex = items.filter(
    i => i.source === 'native' && i.kind === 'image' && ['queued', 'running'].includes(i.status)
  );
  if (!chat.length && !codex.length && !error) return null;
  return (
    <section className="waiting-tray" aria-label="Ждём картинку">
      {chat.map(j => (
        <ExternalCard
          key={j.id}
          id={j.id}
          summary={j.prompt}
          reset={reset}
          paste={pasteFor === j.id}
          setPaste={active => setPasteFor(active ? j.id : '')}
        />
      ))}
      {codex.map(j => (
        <div key={j.id} className="waiting-card">
          <b>Codex {j.status === 'queued' ? '· в очереди' : '· обрабатывает'}</b>
          <small>{j.prompt.slice(0, 90)}</small>
          {j.status === 'queued' && (
            <button
              className="waiting-cancel"
              onClick={() => {
                setError('');
                void cancelCodexJob(j.id)
                  .then(reset)
                  .catch(e => setError(String(e)));
              }}
            >
              Отменить
            </button>
          )}
        </div>
      ))}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
