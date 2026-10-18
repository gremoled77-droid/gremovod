import {useEffect, useRef, useState} from 'react';
import {useSharedActivity} from './ActivityContext';
import {attachExternalResult, cancelCodexJob, cancelExternalJob, copyText, openChatApp} from './imageRoutes';

/**
 * Лоток ожидания: всё, что ушло в ChatGPT или Codex и ещё не вернулось картинкой.
 * Один на всё приложение (правая панель «Очередь»), вместо отдельных блоков на каждом экране.
 */
export default function WaitingTray() {
  const {items, reset} = useSharedActivity();
  const [pasteFor, setPasteFor] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');
  const fileFor = useRef('');
  const fileInput = useRef<HTMLInputElement>(null);
  const chat = items.filter(i => i.source === 'external' && i.status === 'waiting_external');
  const codex = items.filter(
    i => i.source === 'native' && i.kind === 'image' && ['queued', 'running'].includes(i.status)
  );

  const attach = async (jobId: string, file: File) => {
    setError('');
    try {
      await attachExternalResult(jobId, file);
      setPasteFor('');
      setNote('Картинка сохранена в библиотеку проекта.');
      reset();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  const act = async (fn: () => Promise<void>) => {
    setError('');
    try {
      await fn();
      reset();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    if (!pasteFor) return;
    const onPaste = (ev: ClipboardEvent) => {
      const file = Array.from(ev.clipboardData?.files || []).find(f => f.type.startsWith('image/'));
      if (file) {
        ev.preventDefault();
        void attach(pasteFor, file);
      }
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [pasteFor]);

  if (!chat.length && !codex.length && !note && !error) return null;
  return (
    <section className="waiting-tray" aria-label="Ждём картинку">
      {chat.map(j => (
        <div key={j.id} className="waiting-card">
          <b>Ждём картинку из ChatGPT</b>
          <small>{j.prompt.slice(0, 90)}</small>
          <div className="waiting-actions">
            <button
              onClick={() =>
                void copyText(j.prompt).then(ok =>
                  setNote(ok ? 'Промпт скопирован.' : 'Не удалось скопировать.')
                )
              }
            >
              Промпт
            </button>
            <button onClick={openChatApp}>Открыть чат</button>
            <button className={pasteFor === j.id ? 'primary' : ''} onClick={() => setPasteFor(j.id)}>
              {pasteFor === j.id ? 'Жду Ctrl+V…' : 'Вставить'}
            </button>
            <button
              onClick={() => {
                fileFor.current = j.id;
                fileInput.current?.click();
              }}
            >
              Файл…
            </button>
            <button className="waiting-cancel" onClick={() => void act(() => cancelExternalJob(j.id))}>
              Отменить
            </button>
          </div>
        </div>
      ))}
      {codex.map(j => (
        <div key={j.id} className="waiting-card">
          <b>Codex {j.status === 'queued' ? '· в очереди' : '· рисует'}</b>
          <small>{j.prompt.slice(0, 90)}</small>
          {j.status === 'queued' && (
            <div className="waiting-actions">
              <button className="waiting-cancel" onClick={() => void act(() => cancelCodexJob(j.id))}>
                Отменить
              </button>
            </div>
          )}
        </div>
      ))}
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        hidden
        onChange={e => {
          const file = e.target.files?.[0];
          e.target.value = '';
          if (file && fileFor.current) void attach(fileFor.current, file);
        }}
      />
      {note && <p className="muted">{note}</p>}
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
