import {useEffect, useMemo, useRef, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import type {Identity, WorldFields} from './characterPrompt';
import GenerationReview, {type GenerationRequest} from './GenerationReview';
import {buildFramePrompt, defaultFrameTitles} from './framePrompt';
import {loadTarget, sendFrames, type BoardTarget} from './sendToBoard';

type Hero = {id: string; name: string; identity: Identity; working_asset_id?: string};
type Asset = {id: string; provider_reference_url?: string | null; metadata: {kind?: string}};
type OptionSpec = {values?: (string | number)[]; default?: string | number};
type Spec = {kind: string; launch_enabled?: boolean; api_refs?: number; options?: Record<string, OptionSpec>};
const DEFAULT_MODEL = 'gpt-image-2.5';
const thumb = (id: string) => `/api/library/${id}/thumbnail`;

/** «Сборка кадра»: локация + герои → варианты кадра → выбор → «Отправить в раскадровку». Платные запуски только через оценку цены. */
export default function FrameBuilder({
  projectId,
  ensureProject,
  heroes,
  world,
  brief,
  locationAssetIds,
  revision,
  onSent,
}: {
  projectId: string;
  ensureProject: () => Promise<string>;
  heroes: Hero[];
  world?: WorldFields;
  brief: string;
  locationAssetIds: string[];
  revision: number;
  onSent: () => void;
}) {
  const [specs, setSpecs] = useState<Record<string, Spec>>({}),
    [library, setLibrary] = useState<Asset[]>([]),
    [model, setModel] = useState(DEFAULT_MODEL),
    [locationId, setLocationId] = useState(''),
    [heroIds, setHeroIds] = useState<string[]>([]),
    [action, setAction] = useState(''),
    [prompt, setPrompt] = useState(''),
    [edited, setEdited] = useState(false),
    [count, setCount] = useState(2),
    [queue, setQueue] = useState<GenerationRequest[]>([]),
    [picked, setPicked] = useState<string[]>([]),
    [error, setError] = useState(''),
    [note, setNote] = useState(''),
    [busy, setBusy] = useState(false),
    [polling, setPolling] = useState(0),
    [dialog, setDialog] = useState(false);
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
        .then((rows: Asset[]) => {
          if (active) setLibrary(rows.filter(x => (x.metadata.kind || 'image') === 'image'));
        })
        .catch(e => active && setError(String(e)));
    return () => {
      active = false;
    };
  }, [projectId, revision, polling]);
  useEffect(() => {
    if (!note.startsWith('Задание запущено')) return;
    const timer = setInterval(() => setPolling(n => n + 1), 8000);
    return () => clearInterval(timer);
  }, [note]);
  const models = useMemo(
    () => Object.entries(specs).filter(([, s]) => s.kind === 'image' && s.launch_enabled),
    [specs]
  );
  useEffect(() => {
    if (models.length && !models.some(([id]) => id === model)) setModel(models[0][0]);
  }, [models, model]);
  const chosen = heroes.filter(h => heroIds.includes(h.id));
  const auto = useMemo(
    () =>
      buildFramePrompt({
        brief: action || brief,
        heroes: chosen.map(h => ({name: h.name, identity: h.identity})),
        location: locationId ? 'как на референсе локации' : '',
        world,
      }),
    [action, brief, heroIds, locationId, world, heroes] // eslint-disable-line react-hooks/exhaustive-deps
  );
  useEffect(() => {
    if (!edited) setPrompt(auto);
  }, [auto, edited]);
  const refAssets = [
    ...chosen.map(h => h.working_asset_id).filter((x): x is string => !!x),
    ...(locationId ? [locationId] : []),
  ];
  const locationFirst = [
    ...library.filter(a => locationAssetIds.includes(a.id)),
    ...library.filter(a => !locationAssetIds.includes(a.id)),
  ];
  const cloudUrl = async (id: string) => {
    const known = library.find(a => a.id === id)?.provider_reference_url;
    if (known) return known;
    const r = await responseJson(
      await apiFetch(`/api/library/${id}/upload-reference`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({approved: true, provider: 'tempfile'}),
      })
    );
    return r.url as string;
  };
  const start = async () => {
    setError('');
    setNote('');
    if (!prompt.trim()) return setError('Опиши, что происходит в кадре');
    if (!chosen.length && !locationId) return setError('Выбери хотя бы героя или локацию');
    setBusy(true);
    try {
      const pid = projectId || (await ensureProject());
      const spec = specs[model],
        limit = spec?.api_refs ?? 0;
      const urls = await Promise.all(refAssets.slice(0, limit).map(cloudUrl));
      const options = Object.fromEntries(
        Object.entries(spec?.options || {})
          .filter(([, s]) => s.default !== undefined)
          .map(([k, s]) => [
            k,
            k === 'aspect_ratio' && s.values?.includes('16:9') ? '16:9' : (s.default as string | number),
          ])
      );
      setQueue(
        Array.from({length: count}, () => ({
          project_id: pid,
          model_id: model,
          prompt,
          options,
          reference_urls: urls,
        }))
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const toggle = (id: string) => setPicked(p => (p.includes(id) ? p.filter(x => x !== id) : [...p, id]));
  return (
    <section className="panel fb">
      <h3>Сборка кадра</h3>
      <p className="muted">
        Выбери локацию и героев, опиши кадр, сделай несколько вариантов и отправь лучшие в раскадровку.
      </p>
      <h4>1. Локация</h4>
      <div className="fb-strip" aria-label="Локация">
        {locationFirst.slice(0, 16).map(a => (
          <button
            key={a.id}
            className={'fb-tile' + (a.id === locationId ? ' on' : '')}
            aria-pressed={a.id === locationId}
            onClick={() => setLocationId(a.id === locationId ? '' : a.id)}
          >
            <img src={thumb(a.id)} alt="" loading="lazy" />
            {locationAssetIds.includes(a.id) && <small>вложение</small>}
          </button>
        ))}
        {!library.length && <p className="muted">В библиотеке пока нет картинок.</p>}
      </div>
      <h4>2. Герои</h4>
      <div className="fb-heroes">
        {heroes.filter(h => h.working_asset_id).length ? (
          heroes
            .filter(h => h.working_asset_id)
            .map(h => (
              <label key={h.id}>
                <input
                  type="checkbox"
                  checked={heroIds.includes(h.id)}
                  onChange={e =>
                    setHeroIds(ids => (e.target.checked ? [...ids, h.id] : ids.filter(x => x !== h.id)))
                  }
                />
                <img src={thumb(h.working_asset_id!)} alt="" />
                {h.name}
              </label>
            ))
        ) : (
          <p className="muted">
            У героев пока нет рабочего образа. Сделай его выше, в «Сгенерировать героя».
          </p>
        )}
      </div>
      <h4>3. Что в кадре</h4>
      <label>
        Что происходит
        <input
          value={action}
          placeholder="Например: Грэм смотрит в окно такси, ночь, дождь"
          onChange={e => setAction(e.target.value)}
        />
      </label>
      <label>
        Промпт кадра
        <textarea
          rows={6}
          value={prompt}
          onChange={e => {
            setPrompt(e.target.value);
            setEdited(true);
          }}
        />
      </label>
      <div className="fb-row">
        <label>
          Модель
          <select value={model} onChange={e => setModel(e.target.value)}>
            {(models.length ? models.map(([id]) => id) : [DEFAULT_MODEL]).map(id => (
              <option key={id} value={id}>
                {id}
                {id === DEFAULT_MODEL ? ' (по умолчанию)' : ''}
              </option>
            ))}
          </select>
        </label>
        <label>
          Вариантов
          <select value={count} onChange={e => setCount(Number(e.target.value))}>
            {[1, 2, 3, 4].map(n => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <button className="primary" disabled={busy} onClick={() => void start()}>
          {busy ? 'Готовлю…' : 'Сгенерировать: оценка и подтверждение'}
        </button>
        <button
          disabled={!edited}
          onClick={() => {
            setEdited(false);
            setPrompt(auto);
          }}
        >
          Собрать промпт заново
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      {note && <p className="muted">{note}</p>}
      <p className="muted">
        Образы героев и локация уйдут моделью как референсы: перед запуском их копии загружаются во временное
        хранилище по ссылке. Каждый вариант подтверждается отдельно, после оценки цены.
      </p>
      <h4>4. Варианты · последние картинки библиотеки</h4>
      <div className="fb-strip" aria-label="Варианты кадров">
        {library.slice(0, 12).map(a => (
          <label key={a.id} className={'fb-tile' + (picked.includes(a.id) ? ' on' : '')}>
            <img src={thumb(a.id)} alt="" loading="lazy" />
            <input type="checkbox" checked={picked.includes(a.id)} onChange={() => toggle(a.id)} />
          </label>
        ))}
      </div>
      <div className="fb-send">
        <button className="primary fb-yellow" disabled={!picked.length} onClick={() => setDialog(true)}>
          Отправить в раскадровку{picked.length ? ` (${picked.length})` : ''}
        </button>
      </div>
      {queue[0] && (
        <GenerationReview
          request={queue[0]}
          onClose={() => setQueue([])}
          onSubmitted={() => {
            setQueue(q => q.slice(1));
            setNote('Задание запущено. Готовые картинки появятся в «Вариантах» (обновляются сами).');
          }}
        />
      )}
      {dialog && (
        <SendDialog
          projectId={projectId}
          assets={picked}
          heroNodeIds={chosen.map(h => h.id)}
          onClose={() => setDialog(false)}
          onSent={() => {
            setDialog(false);
            setPicked([]);
            onSent();
          }}
        />
      )}
    </section>
  );
}

function SendDialog({
  projectId,
  assets,
  heroNodeIds,
  onClose,
  onSent,
}: {
  projectId: string;
  assets: string[];
  heroNodeIds: string[];
  onClose: () => void;
  onSent: () => void;
}) {
  const [target, setTarget] = useState<BoardTarget | null | undefined>(undefined),
    [scene, setScene] = useState('new'),
    [sceneTitle, setSceneTitle] = useState(''),
    [titles, setTitles] = useState<string[]>([]),
    [location, setLocation] = useState(''),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false),
    requestId = useRef(crypto.randomUUID());
  useEffect(() => {
    let active = true;
    void loadTarget(projectId)
      .then(t => {
        if (!active) return;
        setTarget(t);
        if (t) setSceneTitle(`Сцена ${t.scenes.length + 1}`);
      })
      .catch(e => {
        if (active) {
          setTarget(null);
          setError(e instanceof Error ? e.message : String(e));
        }
      });
    return () => {
      active = false;
    };
  }, [projectId]);
  const existing = target?.scenes.find(s => s.id === scene);
  useEffect(() => {
    if (!target) return;
    const names = existing ? existing.frames.map(f => f.title) : [];
    setTitles(defaultFrameTitles(names, assets.length));
  }, [target, existing, assets.length]);
  const send = async () => {
    if (!target) return;
    setBusy(true);
    setError('');
    try {
      const castNodes = target.characterNodes
        .filter(n => n.character_id && heroNodeIds.includes(n.character_id))
        .map(n => n.id);
      await sendFrames(
        target,
        {
          ...(existing ? {scene_id: existing.id} : {scene_title: sceneTitle.trim()}),
          frames: assets.map((asset_id, i) => ({asset_id, title: titles[i]?.trim() || `Кадр ${i + 1}`})),
          character_node_ids: castNodes,
          location_node_id: location || null,
        },
        requestId.current
      );
      onSent();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Отправить в раскадровку">
      <section className="panel">
        <h3>Отправить в раскадровку</h3>
        {target === undefined && <p className="muted">Ищу серию…</p>}
        {target === null && (
          <p role="alert">{error || 'У проекта нет серии. Создай общий проект и серию в «Раскадровке».'}</p>
        )}
        {target && (
          <>
            <p className="muted">
              Серия: <b>{target.seriesTitle}</b> · кадров: {assets.length}
            </p>
            <label>
              Сцена
              <select value={scene} onChange={e => setScene(e.target.value)}>
                <option value="new">Новая сцена</option>
                {target.scenes.map(s => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </select>
            </label>
            {!existing && (
              <label>
                Название новой сцены
                <input value={sceneTitle} onChange={e => setSceneTitle(e.target.value)} />
              </label>
            )}
            <label>
              Локация сцены
              <select value={location} onChange={e => setLocation(e.target.value)}>
                <option value="">Не менять</option>
                {target.locationNodes.map(l => (
                  <option key={l.id} value={l.id}>
                    {l.title}
                  </option>
                ))}
              </select>
            </label>
            <div className="fb-titles">
              {assets.map((id, i) => (
                <label key={id}>
                  <img src={thumb(id)} alt="" />
                  <input
                    value={titles[i] || ''}
                    aria-label={`Название кадра ${i + 1}`}
                    onChange={e => setTitles(t => t.map((x, j) => (j === i ? e.target.value : x)))}
                  />
                </label>
              ))}
            </div>
            {error && <p role="alert">{error}</p>}
          </>
        )}
        <div className="chips">
          <button
            className="primary"
            disabled={busy || !target || (!existing && !sceneTitle.trim())}
            onClick={() => void send()}
          >
            {busy ? 'Отправляю…' : 'Отправить'}
          </button>
          <button onClick={onClose}>Отмена</button>
        </div>
      </section>
    </div>
  );
}
