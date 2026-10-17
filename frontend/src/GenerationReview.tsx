import {useEffect, useRef, useState} from 'react';
import {apiFetch} from './api';
import LimitPicker from './LimitPicker';
import {initialLimit, limitAllowed} from './spendLimit';

export type GenerationRequest = {
  project_id: string;
  model_id: string;
  prompt: string;
  options: Record<string, string | number | boolean>;
  reference_urls: string[];
  video_urls?: string[];
  audio_urls?: string[];
  node_id?: string;
};
type Estimate = {
  quote_token: string;
  estimated_usd: number;
  images: number;
  source: string;
  verified_at: string;
  note: string;
  lines?: string[];
};

/** Что будет оплачено, одной строкой: длительность или тип задачи Seedance. */
function jobLabel(request: GenerationRequest) {
  if (request.model_id === 'seedance-2.5') {
    if (request.options.draft_task_id) return 'финал 1080p по черновику';
    if (request.options.task === 'edit') return 'правка видео (длина по исходнику)';
    const label = `${request.options.duration || 5} секунд видео`;
    return request.options.draft ? `черновик 480p, ${label}` : label;
  }
  if (request.model_id === 'hunyuan-i2v') return 'одно видео, длительность и размер по умолчанию провайдера';
  return 'одно изображение';
}
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
  const [highOk, setHighOk] = useState(false);
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
        if (active) {
          setEstimate(d);
          setLimit(current => current || initialLimit(d.estimated_usd));
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      active = false;
    };
  }, [request]);
  const submit = async () => {
    if (!estimate || !approved || !limitAllowed(estimate.estimated_usd, limit, highOk) || attempted) return;
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
          PiAPI · {request.model_id} · {jobLabel(request)}
        </p>
        <p className="muted">
          Референсов: картинок {request.reference_urls.length}
          {request.video_urls?.length ? `, видео ${request.video_urls.length}` : ''}
          {request.audio_urls?.length ? `, аудио ${request.audio_urls.length}` : ''}. Задание и ссылки будут
          переданы PiAPI.
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
            {!!estimate.lines?.length && (
              <ul className="muted">
                {estimate.lines.map(line => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            )}
            <p className="muted">
              {estimate.note}{' '}
              <a href={estimate.source} target="_blank" rel="noreferrer">
                Источник цены
              </a>{' '}
              · проверено {estimate.verified_at}
            </p>
            <LimitPicker
              total={estimate.estimated_usd}
              limit={limit}
              onLimit={setLimit}
              highConfirmed={highOk}
              onHighConfirmed={setHighOk}
              disabled={attempted}
            />
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
              !limitAllowed(estimate?.estimated_usd || 0, limit, highOk) ||
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
