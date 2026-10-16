import {useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import './visualPlan.css';

type Cut = {score: number; label: string} | null;
type Row = {
  order: number;
  scene: number;
  frame: number;
  title: string;
  video: string;
  duration: number | null;
  sector_cut: string | null;
  image_cut: Cut;
};
type EditList = {
  summary: {
    shots: number;
    with_video: number;
    cuts: number;
    total_seconds: number | null;
    average_seconds: number | null;
    cuts_per_minute: number | null;
  };
  warnings: string[];
  rows: Row[];
};

/** Список для монтажа в CapCut: порядок, файлы, длительности, склейки; CSV для скачивания. */
export default function EditListPanel({pid, sid}: {pid: string; sid: string}) {
  const url = `/api/productions/${pid}/series/${sid}/edit-list`;
  const [data, setData] = useState<EditList | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError('');
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const sharp = (data?.rows || [])
    .filter(r => r.image_cut && r.image_cut.score >= 0.5)
    .sort((a, b) => (b.image_cut?.score || 0) - (a.image_cut?.score || 0))
    .slice(0, 5);
  return (
    <section className="vp-graph" aria-label="Список для монтажа">
      <div className="vp-head">
        <h3>Список для монтажа (CapCut)</h3>
      </div>
      <p className="muted">
        Кадры по порядку: видео, длительность, склейки по сектору внимания и по картинке. Анализ локальный и
        бесплатный.
      </p>
      <button
        type="button"
        disabled={busy}
        onClick={() => void run(async () => setData(await responseJson(await apiFetch(url))))}
      >
        {busy ? 'Считаю…' : data ? 'Пересчитать' : 'Собрать список'}
      </button>{' '}
      <button
        type="button"
        disabled={busy}
        onClick={() =>
          void run(async () => {
            const response = await apiFetch(url + '?format=csv');
            if (!response.ok) throw new Error(await response.text());
            const link = document.createElement('a');
            link.href = URL.createObjectURL(await response.blob());
            link.download = 'edit-list.csv';
            link.click();
            setTimeout(() => URL.revokeObjectURL(link.href), 5000);
          })
        }
      >
        Скачать CSV
      </button>
      {error && (
        <p role="alert" className="vp-err">
          {error}
        </p>
      )}
      {data && (
        <>
          <p className="vp-legend">
            Кадров {data.summary.shots}, с видео {data.summary.with_video}, склеек {data.summary.cuts}
            {data.summary.total_seconds !== null && `, хронометраж ${data.summary.total_seconds} с`}
            {data.summary.average_seconds !== null && `, средний кадр ${data.summary.average_seconds} с`}
            {data.summary.cuts_per_minute !== null && `, ${data.summary.cuts_per_minute} склеек в минуту`}
          </p>
          {data.warnings.map(w => (
            <p key={w} className="vp-warn" role="status">
              {w}
            </p>
          ))}
          {!!sharp.length && (
            <details>
              <summary>Резкие склейки по картинке: {sharp.length}</summary>
              <ul className="vp-jumps">
                {sharp.map(r => (
                  <li key={r.order}>
                    {r.scene}.{r.frame} → следующий: {r.image_cut?.label} (
                    {Math.round((r.image_cut?.score || 0) * 100)}%). Резкая склейка добавляет напряжение; для
                    спокойной сцены выровняй тон и цвет.
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
    </section>
  );
}
