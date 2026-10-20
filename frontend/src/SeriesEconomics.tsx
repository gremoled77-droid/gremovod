import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import {budgetLines, type BudgetSummary} from './llmDisplay';
import {smallUsd} from './usdFormat';
type Summary = {
  actual_usd_known: number;
  reserved_usd: number;
  unknown_cost_count: number;
  attempts: number;
  used_generations: number;
  success_percent: number | null;
  limit_usd: number | null;
  chat_api_equivalent_usd: number;
  llm?: {
    calls: number;
    usd: number;
    estimated_usd: number;
    actual_cost_usd?: number;
    reserved_usd?: number;
    unknown_cost_usd?: number;
    reference_cost_usd?: number;
  };
};
export default function SeriesEconomics({pid, sid}: {pid: string; sid: string}) {
  const [data, setData] = useState<Summary | null>(null),
    [limit, setLimit] = useState(''),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false),
    [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    void apiFetch(`/api/productions/${pid}/series/${sid}/economics`)
      .then(responseJson)
      .then(d => {
        if (live) {
          setData(d);
          setLimit(d.limit_usd === null ? '' : String(d.limit_usd));
          setError('');
        }
      })
      .catch(e => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
    };
  }, [pid, sid, tick]);
  // Разбивка LLM та же, что в API: факт, резерв, неизвестные списания и неденежный ориентир.
  const llm: BudgetSummary = {
    actual_cost_usd: data?.llm?.actual_cost_usd ?? 0,
    reserved_usd: data?.llm?.reserved_usd ?? 0,
    unknown_cost_usd: data?.llm?.unknown_cost_usd ?? 0,
    reference_cost_usd: data?.llm?.reference_cost_usd ?? 0,
    calls: data?.llm?.calls ?? 0,
  };
  return (
    <details>
      <summary>Экономика и бюджет серии</summary>
      {error && <p role="alert">{error}</p>}
      {data && (
        <>
          <p>
            Подтверждено: <b>${data.actual_usd_known.toFixed(3)}</b> · неизвестных сумм:{' '}
            {data.unknown_cost_count}. Резерв по оценкам: ${data.reserved_usd.toFixed(3)}.
          </p>
          <p>
            LLM-запросы кадров серии: <b>{smallUsd(data.llm?.usd ?? 0)}</b> ({data.llm?.calls ?? 0} вызовов).
            Входят в проверку лимита серии. Запросы из общего проекта сюда не попадают.
          </p>
          <ul style={{margin: '4px 0 8px', paddingLeft: 18}}>
            {budgetLines(llm).map(line => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p>
            Завершённых попыток: {data.attempts} · использовано: {data.used_generations} · выход годных:{' '}
            {data.success_percent === null ? '—' : data.success_percent + '%'}.
          </p>
          <p className="muted">
            Эквивалент ChatGPT по API: ≈ ${data.chat_api_equivalent_usd.toFixed(3)}, в реальные расходы не
            включён. Общие затраты на создание библиотеки персонажей и локаций между сериями автоматически не
            распределяются.
          </p>
          <label>
            Лимит серии, USD · пусто — отдельный лимит не задан
            <input
              type="number"
              min="0"
              max="100000"
              step="0.01"
              value={limit}
              disabled={busy}
              onChange={e => setLimit(e.target.value)}
            />
          </label>
          <button
            disabled={busy}
            onClick={() => {
              void (async () => {
                setBusy(true);
                try {
                  await responseJson(
                    await apiFetch(`/api/productions/${pid}/series/${sid}/budget`, {
                      method: 'PUT',
                      headers: {'Content-Type': 'application/json'},
                      body: JSON.stringify({limit_usd: limit === '' ? null : Number(limit)}),
                    })
                  );
                  setTick(t => t + 1);
                } catch (e) {
                  setError(String(e));
                } finally {
                  setBusy(false);
                }
              })();
            }}
          >
            Сохранить лимит серии
          </button>
          <p className="muted">
            Лимит проверяется сервером до оплаты. Лимиты отдельного кадра и суток также продолжают
            действовать.
          </p>
        </>
      )}
    </details>
  );
}
