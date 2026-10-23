import {rememberRequest} from './jobRequests';
import {useEffect, useRef, useState} from 'react';
import {apiFetch} from './api';
import type {GenerationRequest} from './GenerationReview';
import LimitPicker from './LimitPicker';
import {initialLimit, limitAllowed} from './spendLimit';
import {batchTotal} from './sheetShots';

export type BatchItem = {label: string; request: GenerationRequest};
type Quote = {quote_token: string; estimated_usd: number};
type State = 'wait' | 'sent' | 'failed';

const json = async (r: Response) => {
  const d = await r.json();
  if (!r.ok) throw Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail));
  return d;
};
const post = (url: string, body: unknown) =>
  apiFetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});

/** Пакетный запуск: оценка каждого запроса, общая сумма, одно подтверждение и общий лимит. Сервер проверяет каждую задачу отдельно. */
export default function BatchReview({
  items,
  onClose,
  onSubmitted,
}: {
  items: BatchItem[];
  onClose: () => void;
  onSubmitted: (sent: number) => void;
}) {
  const [quotes, setQuotes] = useState<Quote[] | null>(null),
    [states, setStates] = useState<State[]>(() => items.map(() => 'wait')),
    [error, setError] = useState(''),
    [approved, setApproved] = useState(false),
    [limit, setLimit] = useState(''),
    [highOk, setHighOk] = useState(false),
    [busy, setBusy] = useState(false);
  const ids = useRef(items.map(() => crypto.randomUUID()));
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const out: Quote[] = [];
        for (const item of items) {
          out.push(await json(await post('/api/model-jobs/estimate', item.request)));
          if (!active) return;
        }
        setQuotes(out);
        setLimit(current => current || initialLimit(batchTotal(out.map(q => ({usd: q.estimated_usd})))));
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      active = false;
    };
  }, [items]);
  const total = quotes ? batchTotal(quotes.map(q => ({usd: q.estimated_usd}))) : 0;
  const sentCount = states.filter(s => s === 'sent').length;
  const submit = async () => {
    if (!quotes || !approved || !limitAllowed(total, limit, highOk)) return;
    setBusy(true);
    setError('');
    for (let i = 0; i < items.length; i++) {
      if (states[i] === 'sent') continue;
      try {
        await json(
          await post('/api/model-jobs', {
            ...items[i].request,
            quote_token: quotes[i].quote_token,
            approved: true,
            max_cost_usd: quotes[i].estimated_usd,
            request_id: ids.current[i],
          })
        );
        rememberRequest(ids.current[i], items[i].request);
        setStates(s => s.map((x, j) => (j === i ? 'sent' : x)));
      } catch (e) {
        setStates(s => s.map((x, j) => (j === i ? 'failed' : x)));
        setError(
          `«${items[i].label}»: ${e instanceof Error ? e.message : String(e)} Остальные не отправлены. Проверь очередь и историю провайдера перед новым запуском.`
        );
        setBusy(false);
        return;
      }
    }
    setBusy(false);
    onSubmitted(items.length);
  };
  return (
    <div className="modal-backdrop">
      <section
        className="panel generation-review"
        role="dialog"
        aria-modal="true"
        aria-label="Пакетный запуск"
      >
        <h2>Пакетный запуск · {items.length} картинок</h2>
        <p className="muted">
          PiAPI · {[...new Set(items.map(i => i.request.model_id))].join(', ')}. Задание и ссылки будут
          переданы PiAPI.
        </p>
        <ul className="batch-list">
          {items.map((item, i) => (
            <li key={i}>
              <span>
                {states[i] === 'sent' ? '✓ ' : states[i] === 'failed' ? '✗ ' : ''}
                {item.label} · реф: {item.request.reference_urls.length}
              </span>
              <b>{quotes ? `$${quotes[i].estimated_usd.toFixed(3)}` : '…'}</b>
            </li>
          ))}
        </ul>
        {quotes && (
          <>
            <p>
              Итого: <b>${total.toFixed(3)}</b>
            </p>
            <LimitPicker
              total={total}
              limit={limit}
              onLimit={setLimit}
              highConfirmed={highOk}
              onHighConfirmed={setHighOk}
              disabled={busy}
            />
            <label className="inline-checkbox">
              <input
                type="checkbox"
                checked={approved}
                disabled={busy}
                onChange={e => setApproved(e.target.checked)}
              />{' '}
              Подтверждаю платный пакет в пределах указанного лимита
            </label>
          </>
        )}
        {!quotes && !error && <p className="muted">Считаю цену каждого запроса…</p>}
        {error && (
          <div className="alert" role="alert">
            {error}
          </div>
        )}
        <div className="chips">
          <button
            className="primary"
            disabled={!quotes || !approved || !limitAllowed(total, limit, highOk) || busy}
            onClick={() => void submit()}
          >
            {busy
              ? `Отправляется… ${sentCount} из ${items.length}`
              : sentCount
                ? 'Продолжить с оставшихся'
                : 'Подтвердить и запустить пакет'}
          </button>
          <button onClick={onClose} disabled={busy}>
            Закрыть
          </button>
        </div>
      </section>
    </div>
  );
}
