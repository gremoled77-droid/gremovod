import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {readLocal} from './localDrafts';
import type {WorkspaceLocation} from './WorkspaceTrail';

type Issue = {code: string; severity: 'blocking' | 'warning'; message: string};
type Result = {
  relative: string;
  draft: boolean;
  waiting: string[];
  status: string;
  ready_for_montage: boolean;
  counts: {clips: number; audio: number; references: number; vertical: number};
  issues: Issue[];
  verify: {ok: boolean; checked: number; mismatches: string[]};
};

const detail = async (r: Response) => {
  const data = await r.json().catch(() => ({}));
  return typeof data.detail === 'string' ? data.detail : `Ошибка ${r.status}`;
};

/** «Выгрузить в CapCut»: пакет выбранных клипов и звука кадров в папку 03_Монтаж серии; черновик только явно. */
export default function CapCutExport({location}: {location: WorkspaceLocation | null}) {
  const pid = location?.production_id || '';
  const [series, setSeries] = useState<{id: string; title: string; number: number}[]>([]),
    [sid, setSid] = useState(''),
    [busy, setBusy] = useState(false),
    [blocked, setBlocked] = useState(''),
    [error, setError] = useState(''),
    [result, setResult] = useState<Result | null>(null);
  useEffect(() => {
    let live = true;
    setSeries([]);
    if (pid)
      void apiFetch('/api/productions/' + pid)
        .then(r => (r.ok ? r.json() : {nodes: []}))
        .then(tree => {
          if (!live) return;
          const list = tree.nodes.filter((n: {kind: string}) => n.kind === 'series');
          const stored = readLocal<{pid: string; sid: string}>('studio:board-location', {pid: '', sid: ''});
          const preferred = location?.series?.id || (stored.pid === pid ? stored.sid : '');
          setSeries(list);
          setSid(list.some((n: {id: string}) => n.id === preferred) ? preferred : list[0]?.id || '');
        })
        .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [pid, location?.series?.id]);
  const run = async (draft: boolean) => {
    setBusy(true);
    setError('');
    setBlocked('');
    setResult(null);
    try {
      const r = await apiFetch(`/api/productions/${pid}/series/${sid}/capcut`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({draft}),
      });
      if (r.status === 409) setBlocked(await detail(r));
      else if (!r.ok) setError(await detail(r));
      else setResult(await r.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  if (!pid) return <p className="ss-note">Выгрузка появится, когда у проекта будет постановка с сериями.</p>;
  return (
    <div className="capcut-export">
      <div className="chips">
        {series.length > 1 && (
          <select aria-label="Серия для выгрузки" value={sid} onChange={e => setSid(e.target.value)}>
            {series.map(s => (
              <option key={s.id} value={s.id}>
                {s.number}. {s.title}
              </option>
            ))}
          </select>
        )}
        <button className="primary" disabled={busy || !sid} onClick={() => void run(false)}>
          {busy ? 'Собираю пакет…' : 'Выгрузить в CapCut'}
        </button>
        <small className="muted">
          Локально и бесплатно: клипы, звук кадров и лист монтажа в папку 03_Монтаж.
        </small>
      </div>
      {blocked && (
        <div className="alert" role="alert">
          <p>{blocked}</p>
          <button disabled={busy} onClick={() => void run(true)}>
            Собрать черновой пакет
          </button>
        </div>
      )}
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {result && (
        <div className="capcut-result" role="status">
          <p>
            <b>
              {result.draft ? 'Черновой пакет' : 'Пакет'}{' '}
              {result.ready_for_montage ? 'готов к монтажу' : 'собран не полностью'}
            </b>
            : {result.relative}
          </p>
          <p className="muted">
            Клипов {result.counts.clips}, звуковых файлов {result.counts.audio}, референсов{' '}
            {result.counts.references}. Проверка пакета:{' '}
            {result.verify.ok ? `ok, файлов ${result.verify.checked}` : 'есть расхождения'}.
          </p>
          {result.draft && !!result.waiting.length && (
            <p className="muted">Без главного видео: кадры {result.waiting.join(', ')}.</p>
          )}
          {!!(result.issues.length || result.verify.mismatches.length) && (
            <details open={!result.ready_for_montage || !result.verify.ok}>
              <summary>Замечания: {result.issues.length + result.verify.mismatches.length}</summary>
              <ul>
                {result.issues.map((i, n) => (
                  <li key={n} className={i.severity === 'blocking' ? 'vp-warn' : ''}>
                    {i.message}
                  </li>
                ))}
                {result.verify.mismatches.map(m => (
                  <li key={m} className="vp-warn">
                    {m}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
