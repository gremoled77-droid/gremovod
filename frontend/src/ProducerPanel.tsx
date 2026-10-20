import {apiFetch} from './api';
import {useState} from 'react';
import {
  ProducerCatalog,
  ProducerChoice,
  ProducerInput,
  ProducerQuote,
  availabilityNote,
  choiceForProvider,
  estimateBody,
  formatUsd,
  isRunnable,
  makeRequestId,
  modelLabel,
  modelsForProvider,
  providerLabel,
  runBody,
} from './producerModel';

type ProducerResult = {
  stage: string;
  model: {id: string; label: string; provider: string; paid: boolean};
  cost_usd: number;
  estimated_usd: number;
  external_calls: number;
  logline?: string;
};

type Props = {
  projectId: string;
  idea: string;
  characterIds?: string[];
  catalog: ProducerCatalog;
  choice: ProducerChoice;
  onChoice: (choice: ProducerChoice) => void;
};

/** Текст ошибки: детали бывают строкой или объектом с code/message. */
export function errorText(data: any): string {
  const detail = data?.detail ?? data;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail.message === 'string') return detail.message;
  if (detail && typeof detail.code === 'string') return detail.code;
  return 'Запрос не выполнен';
}

export default function ProducerPanel({
  projectId,
  idea,
  characterIds,
  catalog,
  choice,
  onChoice,
}: Props) {
  const [quote, setQuote] = useState<(ProducerQuote & {choice: ProducerChoice}) | null>(null);
  const [result, setResult] = useState<ProducerResult | null>(null);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const models = modelsForProvider(catalog, choice.provider);
  const note = availabilityNote(catalog, choice);
  const runnable = isRunnable(catalog, choice) && !!idea.trim() && !!projectId;
  const quoteIsCurrent = !!quote && quote.choice.provider === choice.provider && quote.choice.model === choice.model;

  const input = (): ProducerInput => ({projectId, idea, characterIds});

  const estimate = async () => {
    setBusy(true);
    setError('');
    setResult(null);
    setStatus('Считаю оценку…');
    try {
      const response = await apiFetch('/api/producer/estimate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(estimateBody(input(), choice)),
      });
      const data = await response.json();
      if (!response.ok) throw Error(errorText(data));
      setQuote({...data, choice});
      setStatus(data.mode === 'mock' ? 'MOCK: локальная структура, расходов нет' : 'Оценка готова');
    } catch (e: any) {
      setQuote(null);
      setStatus('');
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  const run = async () => {
    if (!quote || !quoteIsCurrent) return;
    setBusy(true);
    setError('');
    setStatus('Выполняю этап…');
    try {
      const response = await apiFetch('/api/producer/run', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(runBody(input(), choice, quote, makeRequestId())),
      });
      const data = await response.json();
      if (!response.ok) throw Error(errorText(data));
      setResult(data);
      setStatus('Этап выполнен');
    } catch (e: any) {
      setStatus('');
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="sc-step">
      <div className="rf-head">
        <span className="rf-step">П</span>
        <div>
          <h3>Этап «Продюсер»</h3>
          <small>Идея → сценарная структура. Модель выбираешь ты, платный запуск — только после оценки</small>
        </div>
      </div>

      <div className="param-grid">
        <label>
          Провайдер
          <select
            value={choice.provider}
            onChange={e => {
              const next = choiceForProvider(catalog, e.target.value, choice.model);
              onChoice(next);
              setQuote(null);
              setResult(null);
            }}
          >
            {catalog.providers.map(p => (
              <option key={p.id} value={p.id}>
                {providerLabel(catalog, p.id)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Модель
          <select
            value={choice.model}
            onChange={e => {
              onChoice({...choice, model: e.target.value});
              setQuote(null);
              setResult(null);
            }}
          >
            {models.length === 0 && <option value="">— моделей у провайдера нет —</option>}
            {models.map(m => (
              <option key={m.id} value={m.id}>
                {modelLabel(m)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {note && (
        <p className="muted" role="status">
          {note}
        </p>
      )}

      <div className="rf-actions">
        <button className="secondary" disabled={busy || !runnable} onClick={estimate}>
          {busy && !quoteIsCurrent ? 'Считаю…' : 'Оценить стоимость'}
        </button>
        {quoteIsCurrent && quote.mode === 'paid' && (
          <button className="primary" disabled={busy} onClick={run}>
            {busy ? 'Выполняю…' : 'Подтвердить и запустить (≈ ' + formatUsd(quote.estimated_usd) + ')'}
          </button>
        )}
        {quoteIsCurrent && quote.mode === 'mock' && (
          <button className="primary" disabled={busy} onClick={run}>
            {busy ? 'Выполняю…' : 'Запустить локально (MOCK, бесплатно)'}
          </button>
        )}
      </div>

      {!idea.trim() && <small className="muted">Сначала напиши идею ролика на экране «Идея».</small>}
      {status && (
        <p className="muted" role="status">
          {status}
        </p>
      )}
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}

      {result && (
        <div className="ag-result">
          <p>
            <b>Модель выполнения:</b> {result.model.label} ({result.model.id}) · провайдер{' '}
            {result.model.provider} · {result.model.paid ? 'платный вызов' : 'без расхода'} · факт{' '}
            {formatUsd(result.cost_usd)}
          </p>
          {result.logline && <p className="muted">Логлайн: {result.logline}</p>}
        </div>
      )}
    </article>
  );
}
