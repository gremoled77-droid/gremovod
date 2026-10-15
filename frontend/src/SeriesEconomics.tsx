import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
type Summary = {
  actual_usd_known: number;
  reserved_usd: number;
  unknown_cost_count: number;
  attempts: number;
  used_generations: number;
  success_percent: number | null;
  limit_usd: number | null;
  chat_api_equivalent_usd: number;
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
