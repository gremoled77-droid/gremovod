import {useEffect, useRef, useState} from 'react';
import {apiFetch} from './api';

export type GenerationRequest = {
  project_id: string;
  model_id: string;
  prompt: string;
  options: Record<string, string | number>;
  reference_urls: string[];
  node_id?: string;
};
type Estimate = {
  quote_token: string;
  estimated_usd: number;
  images: number;
  source: string;
  verified_at: string;
  note: string;
};
export default function GenerationReview({
  request,
  onClose,
  onSubmitted,
}: {
  request: GenerationRequest;
  onClose: () => void;
  onSubmitted: () => void;
}) {
  const [estimate, setEstimate] = useState<Estimate | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [approved, setApproved] = useState(false);
  const [limit, setLimit] = useState('');
  const [attempted, setAttempted] = useState(false);
  const requestId = useRef(crypto.randomUUID());
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const r = await apiFetch('/api/model-jobs/estimate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(request),
        });
        const d = await r.json();
        if (!r.ok) throw Error(typeof d.detail === 'string' ? d.detail : 'Не удалось оценить запуск');
        if (active) setEstimate(d);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      active = false;
    };
  }, [request]);
  const submit = async () => {
    if (!estimate || !approved || Number(limit) < estimate.estimated_usd || attempted) return;
    setBusy(true);
    setAttempted(true);
    setError('');
    try {
      const r = await apiFetch('/api/model-jobs', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          ...request,
          quote_token: estimate.quote_token,
          approved: true,
          max_cost_usd: Number(limit),
          request_id: requestId.current,
        }),
      });
      const d = await r.json();
      if (!r.ok) throw Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail));
      onSubmitted();
    } catch (e) {
      setError(
        (e instanceof Error ? e.message : String(e)) +
          ' Проверь очередь и историю провайдера перед новым запуском.'
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="modal-backdrop">
      <section
        className="panel generation-review"
        role="dialog"
        aria-modal="true"
        aria-labelledby="generation-title"
      >
        <h2 id="generation-title">Подтверждение генерации</h2>
        <p>
          PiAPI · {request.model_id} ·{' '}
          {request.model_id === 'seedance-2.5'
            ? `${request.options.duration || 5} секунд видео`
            : request.model_id === 'hunyuan-i2v'
              ? 'одно видео, длительность и размер по умолчанию провайдера'
              : 'одно изображение'}
        </p>
        <p className="muted">
          Референсов: {request.reference_urls.length}. Задание и ссылки будут переданы PiAPI.
        </p>
        <details>
          <summary>Проверить промпт и настройки</summary>
          <pre>{request.prompt}</pre>
          <p>
            {Object.entries(request.options)
              .map(([k, v]) => `${k}: ${v}`)
              .join(' · ') || 'Настройки по умолчанию'}
          </p>
        </details>
        {estimate && (
          <>
            <p>
              Оценка: <b>${estimate.estimated_usd.toFixed(3)}</b>
            </p>
            <p className="muted">
              {estimate.note}{' '}
              <a href={estimate.source} target="_blank" rel="noreferrer">
                Источник цены
              </a>{' '}
              · проверено {estimate.verified_at}
            </p>
            <label>
              Мой лимит на этот запуск, USD
              <input
                type="number"
                min={estimate.estimated_usd}
                max="100"
                step="0.001"
                value={limit}
                onChange={e => setLimit(e.target.value)}
                placeholder="Укажи сумму"
                disabled={attempted}
              />
            </label>
            <label className="inline-checkbox">
              <input
                type="checkbox"
                checked={approved}
                onChange={e => setApproved(e.target.checked)}
                disabled={attempted}
              />{' '}
              Подтверждаю платный запуск в пределах указанного лимита
            </label>
          </>
        )}
        {error && (
          <div className="alert" role="alert">
            {error}
          </div>
        )}
        <div className="chips">
          <button
            className="primary"
            disabled={
              !estimate ||
              !approved ||
              !Number.isFinite(Number(limit)) ||
              Number(limit) < (estimate?.estimated_usd || 0) ||
              busy ||
              attempted
            }
            onClick={submit}
          >
            {busy ? 'Отправляется…' : 'Подтвердить и запустить'}
          </button>
          <button onClick={onClose} disabled={busy}>
            Закрыть
          </button>
        </div>
      </section>
    </div>
  );
}
