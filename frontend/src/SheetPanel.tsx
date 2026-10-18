import {localReference} from './localReference';
import {useEffect, useMemo, useState, type ReactNode} from 'react';
import {apiFetch, responseJson} from './api';
import BatchReview, {type BatchItem} from './BatchReview';
import GenerateButton, {useEstimate} from './GenerateButton';
import {belongsToSheet, MAX_SHEET, pickShots, readShotLabel, type Shot} from './sheetShots';

type Spec = {
  kind: string;
  launch_enabled?: boolean;
  api_refs?: number;
  options?: Record<string, {values?: (string | number)[]; default?: string | number}>;
};
type Asset = {
  id: string;
  provider_reference_url?: string | null;
  metadata: {kind?: string; request?: {payload?: {input?: {prompt?: string}}}};
};
const thumb = (id: string) => `/api/library/${id}/thumbnail`;
const promptOf = (a: Asset) => a.metadata.request?.payload?.input?.prompt;

/** Пакет ракурсов (лист героя или вариации локации): выбор набора, общая оценка и подтверждение, плитки результатов с подписями. */
export default function SheetPanel({
  kind,
  name,
  title,
  shots,
  defaults,
  aspect,
  defaultModel,
  projectId,
  ensureProject,
  referenceAssetId,
  buildPrompt,
  revision,
  actions,
}: {
  kind: 'hero' | 'location';
  name: string;
  title: string;
  shots: Shot[];
  defaults: string[];
  aspect: string;
  defaultModel: string;
  projectId: string;
  ensureProject: () => Promise<string>;
  referenceAssetId?: string;
  buildPrompt: (shot: Shot) => string;
  revision: number;
  actions: (selected: string[], done: () => void) => ReactNode;
}) {
  const [specs, setSpecs] = useState<Record<string, Spec>>({}),
    [library, setLibrary] = useState<Asset[]>([]),
    [model, setModel] = useState(defaultModel),
    [keys, setKeys] = useState<string[]>(defaults),
    [batch, setBatch] = useState<BatchItem[] | null>(null),
    [picked, setPicked] = useState<string[]>([]),
    [error, setError] = useState(''),
    [note, setNote] = useState(''),
    [busy, setBusy] = useState(false),
    [poll, setPoll] = useState(0);
  useEffect(() => {
    let active = true;
    void apiFetch('/api/model-specs')
      .then(responseJson)
      .then(s => active && setSpecs(s))
      .catch(e => active && setError(String(e)));
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    let active = true;
    if (projectId)
      void apiFetch('/api/library?project_id=' + encodeURIComponent(projectId))
        .then(responseJson)
        .then(
          (rows: Asset[]) => active && setLibrary(rows.filter(x => (x.metadata.kind || 'image') === 'image'))
        )
        .catch(e => active && setError(String(e)));
    return () => {
      active = false;
    };
  }, [projectId, revision, poll]);
  useEffect(() => {
    if (!note.startsWith('Пакет запущен')) return;
    const timer = setInterval(() => setPoll(n => n + 1), 8000);
    return () => clearInterval(timer);
  }, [note]);
  const models = useMemo(
    () => Object.entries(specs).filter(([, s]) => s.kind === 'image' && s.launch_enabled),
    [specs]
  );
  useEffect(() => {
    if (models.length && !models.some(([id]) => id === model)) setModel(models[0][0]);
  }, [models, model]);
  const chosen = pickShots(shots, keys);
  const results = library.filter(a => belongsToSheet(promptOf(a), kind, name));
  const sheetOptions = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(specs[model]?.options || {})
          .filter(([, s]) => s.default !== undefined)
          .map(([k, s]) => [
            k,
            k === 'aspect_ratio' && s.values?.includes(aspect) ? aspect : (s.default as string | number),
          ])
      ) as Record<string, string | number>,
    [specs, model, aspect]
  );
  const estimate = useEstimate(specs[model] ? chosen.map(() => ({model, options: sheetOptions})) : []);
  const start = async () => {
    setError('');
    setNote('');
    if (!chosen.length) return setError('Выбери хотя бы один ракурс');
    setBusy(true);
    try {
      const pid = projectId || (await ensureProject());
      const spec = specs[model];
      let urls: string[] = [];
      if (referenceAssetId && (spec?.api_refs ?? 0) > 0) {
        urls = [
          library.find(a => a.id === referenceAssetId)?.provider_reference_url ||
            localReference(referenceAssetId),
        ];
      }
      const options = sheetOptions;
      setBatch(
        chosen.map(shot => ({
          label: shot.label,
          request: {
            project_id: pid,
            model_id: model,
            prompt: buildPrompt(shot),
            options,
            reference_urls: urls,
          },
        }))
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel sheet">
      <h3>
        {title} · {name}
      </h3>
      <div className="sheet-shots" role="group" aria-label="Ракурсы">
        {shots.map(s => (
          <label key={s.key}>
            <input
              type="checkbox"
              checked={keys.includes(s.key)}
              onChange={e =>
                setKeys(k =>
                  e.target.checked ? (k.length < MAX_SHEET ? [...k, s.key] : k) : k.filter(x => x !== s.key)
                )
              }
            />
            {s.label}
          </label>
        ))}
      </div>
      <div className="sheet-row">
        <label>
          Модель
          <select value={model} onChange={e => setModel(e.target.value)}>
            {(models.length ? models.map(([id]) => id) : [defaultModel]).map(id => (
              <option key={id} value={id}>
                {id}
                {id === defaultModel ? ' (по умолчанию)' : ''}
              </option>
            ))}
          </select>
        </label>
        <GenerateButton
          projectId={projectId}
          busy={busy}
          disabled={!chosen.length}
          estimate={estimate}
          count={chosen.length}
          onApi={start}
          job={async () => {
            if (!chosen.length) return 'Выбери хотя бы один ракурс';
            const pid = projectId || (await ensureProject());
            return chosen.map(shot => ({
              projectId: pid,
              prompt: buildPrompt(shot),
              target: model,
              referenceAssetIds: referenceAssetId ? [referenceAssetId] : [],
            }));
          }}
          onNotice={setNote}
          onError={setError}
        />
      </div>
      {!referenceAssetId && (
        <p className="muted">
          Образа-референса пока нет: картинки получатся без привязки к внешности. Сначала сделай или загрузи
          образ.
        </p>
      )}
      {error && <p role="alert">{error}</p>}
      {note && <p className="muted">{note}</p>}
      {results.length > 0 && (
        <>
          <h4>Результат: {results.length}</h4>
          <div className="sheet-results" aria-label="Результаты пакета">
            {results.map(a => (
              <label key={a.id} className={'sheet-tile' + (picked.includes(a.id) ? ' on' : '')}>
                <img src={thumb(a.id)} alt="" loading="lazy" />
                <small>{readShotLabel(promptOf(a))}</small>
                <input
                  type="checkbox"
                  checked={picked.includes(a.id)}
                  onChange={() =>
                    setPicked(p => (p.includes(a.id) ? p.filter(x => x !== a.id) : [...p, a.id]))
                  }
                />
              </label>
            ))}
          </div>
          <div className="chips">{actions(picked, () => setPicked([]))}</div>
        </>
      )}
      {batch && (
        <BatchReview
          items={batch}
          onClose={() => setBatch(null)}
          onSubmitted={n => {
            setBatch(null);
            setNote(`Пакет запущен: ${n}. Готовые картинки появятся ниже сами.`);
          }}
        />
      )}
    </section>
  );
}
