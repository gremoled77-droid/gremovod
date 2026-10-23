import {useEffect, useRef, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import {readLocal, writeLocal} from './localDrafts';

export type AssistantCard = {action: string; label: string; node_id: string; note: string; paid: boolean};
type Message = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  node_id: string | null;
  node_title: string | null;
  cards: AssistantCard[];
};

/** Помощник внизу: сообщения со ссылками на кадры и карточки следующих шагов. Свёрнут по умолчанию. */
export default function AssistantDock({
  pid,
  frameId,
  onCard,
  onFrame,
}: {
  pid: string;
  frameId: string;
  onCard: (card: AssistantCard) => void;
  onFrame: (frameId: string) => void;
}) {
  const [open, setOpen] = useState(() => readLocal('studio:assistant-open', false)),
    [messages, setMessages] = useState<Message[]>([]),
    [text, setText] = useState(''),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    writeLocal('studio:assistant-open', open);
  }, [open]);
  useEffect(() => {
    if (!open) return;
    let live = true;
    void apiFetch(`/api/productions/${encodeURIComponent(pid)}/assistant`)
      .then(responseJson)
      .then(list => {
        if (live) setMessages(list);
      })
      .catch(e => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
    };
  }, [pid, open]);
  useEffect(() => {
    // Ничего не возвращаем: в новых браузерах scrollIntoView возвращает Promise, а React ждёт функцию очистки.
    end.current?.scrollIntoView({block: 'nearest'});
  }, [messages]);
  const send = async () => {
    if (!text.trim()) return;
    setBusy(true);
    setError('');
    try {
      const pair: Message[] = await responseJson(
        await apiFetch(`/api/productions/${encodeURIComponent(pid)}/assistant`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({text, node_id: frameId || null}),
        })
      );
      setMessages(m => [...m, ...pair]);
      setText('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  if (!open)
    return (
      <button type="button" className="assistant-tab" onClick={() => setOpen(true)} aria-expanded={false}>
        ▴ Помощник
      </button>
    );
  return (
    <section className="assistant-dock" aria-label="Помощник">
      <header>
        <b>Помощник</b>
        <small className="muted">
          {frameId ? 'по кадру в фокусе' : 'выбери кадр на доске'} · без LLM, бесплатно
        </small>
        <button type="button" aria-label="Свернуть помощника" onClick={() => setOpen(false)}>
          ▾
        </button>
      </header>
      <div className="assistant-log" role="log">
        {!messages.length && (
          <p className="muted">Спроси «что дальше?» — предложу шаги по выбранному кадру.</p>
        )}
        {messages.map(m => (
          <div key={m.id} className={'assistant-msg ' + m.role}>
            {m.node_id && m.node_title && (
              <button type="button" className="assistant-ref" onClick={() => onFrame(m.node_id!)}>
                {m.node_title}
              </button>
            )}
            <p>{m.text}</p>
            {!!m.cards.length && (
              <div className="assistant-cards">
                {m.cards.map((c, i) => (
                  <button
                    key={i}
                    type="button"
                    className={c.paid ? 'primary' : ''}
                    title={c.note}
                    disabled={c.action === 'watch'}
                    onClick={() => onCard(c)}
                  >
                    {c.label}
                    {c.paid && <small> · платно, цена перед запуском</small>}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        <div ref={end} />
      </div>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      <form
        onSubmit={e => {
          e.preventDefault();
          void send();
        }}
      >
        <input
          aria-label="Сообщение помощнику"
          value={text}
          maxLength={2000}
          onChange={e => setText(e.target.value)}
          placeholder="Что дальше по кадру?"
        />
        <button type="submit" disabled={busy || !text.trim()}>
          Отправить
        </button>
      </form>
    </section>
  );
}
