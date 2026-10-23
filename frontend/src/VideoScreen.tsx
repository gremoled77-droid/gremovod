import {useEffect, useMemo, useState} from 'react';
import {X} from 'lucide-react';
import {apiFetch} from './api';
import {modelLabel, videoModelIds} from './modelCatalog';
import {useSharedActivity} from './ActivityContext';
import FrameActions from './FrameActions';
import CameraFramePanel from './CameraFramePanel';
import GenerationReview, {type GenerationRequest} from './GenerationReview';
import {AddReferenceModal, LibraryPickModal, LocationModal} from './FrameSources';
import {cents, price} from './PriceTable';
import {modePrompt, seedanceCost, usesSource, VIDEO_MODES, type VideoMode} from './videoMode';

type OptionSpec = {values?: (string | number)[]; default?: string | number; min?: number; max?: number};
type Spec = {
  kind: string;
  launch_enabled?: boolean;
  label?: string;
  ui_order?: number;
  prompt_only?: boolean;
  options?: Record<string, OptionSpec>;
  resolution?: string[];
  aspect_ratio?: string[];
  duration_min?: number;
  duration_max?: number;
  max_refs?: number;
  provider?: string;
  page_urls?: Record<string, string>;
  price_per_second_usd?: Record<string, number>;
};
type LibAsset = {
  id: string;
  url: string;
  thumbnail_url: string | null;
  provider_reference_url?: string | null;
  filename?: string;
  metadata: {kind?: string; favorite?: boolean};
};

const PROVIDERS: Record<string, string> = {piapi: 'PiAPI'};
const MOVE_ONLY = ['move' as const];
const draftKey = (projectId: string) => `studio:video-draft:v1:${projectId}`;

type Draft = {
  prompt: string;
  base: string;
  finish: string;
  clip: string;
  mode: VideoMode;
  back: boolean;
  refs: string[];
  model: string;
  values: Record<string, string | number>;
};

function loadDraft(projectId: string): Partial<Draft> {
  try {
    return JSON.parse(localStorage.getItem(draftKey(projectId)) || '{}') as Partial<Draft>;
  } catch {
    return {};
  }
}

async function json(r: Response) {
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw Error(typeof d.detail === 'string' ? d.detail : 'Запрос не выполнен');
  return d;
}

/** Параметры видеомодели: из spec.options или из плоских полей каталога (Seedance). */
function optionsOf(spec?: Spec): Record<string, OptionSpec> {
  if (!spec) return {};
  if (spec.options) return spec.options;
  const out: Record<string, OptionSpec> = {};
  if (spec.resolution) out.resolution = {values: spec.resolution, default: spec.resolution[0]};
  if (spec.duration_min !== undefined)
    out.duration = {min: spec.duration_min, max: spec.duration_max, default: 5};
  if (spec.aspect_ratio) out.aspect_ratio = {values: spec.aspect_ratio, default: spec.aspect_ratio[0]};
  return out;
}

export default function VideoScreen(props: {projectId: string; world?: string}) {
  return <VideoScreenBody key={props.projectId} {...props} />;
}

function VideoScreenBody({projectId, world = ''}: {projectId: string; world?: string}) {
  const [restored] = useState(() => loadDraft(projectId));
  const {items, error: feedError, reset} = useSharedActivity();
  const [specs, setSpecs] = useState<Record<string, Spec>>({});
  const [library, setLibrary] = useState<LibAsset[]>([]);
  const [prompt, setPrompt] = useState(restored.prompt ?? '');
  const [base, setBase] = useState(restored.base ?? '');
  const [finish, setFinish] = useState(restored.finish ?? '');
  const [clip, setClip] = useState(restored.clip ?? '');
  const [clipSec, setClipSec] = useState<number | null>(null);
  const [mode, setMode] = useState<VideoMode>(restored.mode ?? 'new');
  const [back, setBack] = useState(restored.back ?? false);
  const [refs, setRefs] = useState<string[]>(restored.refs ?? []);
  const [model, setModel] = useState(restored.model ?? 'seedance-2.5');
  const [values, setValues] = useState<Record<string, string | number>>(restored.values ?? {});
  const [source, setSource] = useState<'' | 'hero' | 'location' | 'base' | 'finish' | 'clip'>('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [request, setRequest] = useState<GenerationRequest | null>(null);
  const [cost, setCost] = useState<number | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(
        draftKey(projectId),
        JSON.stringify({prompt, base, finish, clip, mode, back, refs, model, values})
      );
    } catch {
      /* без черновика экран работает */
    }
  }, [projectId, prompt, base, finish, clip, mode, back, refs, model, values]);

  const loadLibrary = async () => {
    if (projectId)
      setLibrary(await json(await apiFetch('/api/library?project_id=' + encodeURIComponent(projectId))));
  };
  useEffect(() => {
    void (async () => {
      try {
        setSpecs(await json(await apiFetch('/api/model-specs')));
      } catch (e) {
        setError(String(e));
      }
    })();
  }, []);
  useEffect(() => {
    void loadLibrary().catch(e => setError(String(e)));
  }, [projectId, items]);

  const byId = useMemo(() => Object.fromEntries(library.map(a => [a.id, a])), [library]);
  const frames = library.filter(a => (a.metadata.kind || 'image') === 'image');
  const models = videoModelIds(specs).filter(id => specs[id]?.launch_enabled);
  const spec = specs[model];
  const schema = optionsOf(spec);
  const value = (key: string) => values[key] ?? schema[key]?.default;
  const current = Object.fromEntries(Object.keys(schema).map(k => [k, value(k)])) as Record<
    string,
    string | number
  >;
  const isSeedance = model === 'seedance-2.5';
  const activeMode: VideoMode = isSeedance ? mode : 'new';
  const fromClip = usesSource(activeMode);
  const refLimit = spec?.max_refs ?? 1;
  const total = (base ? 1 : 0) + (activeMode === 'frames' && finish ? 1 : 0) + refs.length;
  const maxRefs = Math.max(0, refLimit - total + refs.length);
  const videos = library.filter(a => a.metadata.kind === 'video');
  const rateUsd = isSeedance ? spec?.price_per_second_usd?.[String(value('resolution'))] : undefined;
  const sec = Number(value('duration') ?? 0);
  const outSec = activeMode === 'edit' ? (clipSec ?? 0) : sec;
  const signature = JSON.stringify([model, current, activeMode, clipSec]);

  /** Длину исходного ролика читает браузер: сервер файлы не измеряет. */
  useEffect(() => {
    setClipSec(null);
    const a = clip ? byId[clip] : undefined;
    if (!a) return;
    const probe = document.createElement('video');
    probe.preload = 'metadata';
    probe.onloadedmetadata = () =>
      setClipSec(Number.isFinite(probe.duration) ? Math.round(probe.duration * 10) / 10 : null);
    probe.src = a.url;
    return () => {
      probe.onloadedmetadata = null;
      probe.removeAttribute('src');
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clip, !!byId[clip]]);

  useEffect(() => {
    if (!spec) return;
    if (rateUsd !== undefined) {
      setCost(
        fromClip && clipSec === null ? null : seedanceCost(rateUsd, outSec, fromClip ? (clipSec ?? 0) : 0)
      );
      return;
    }
    let live = true;
    setCost(null);
    void price(model, current).then(p => live && setCost(p));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, spec]);

  const results = items.filter(i => i.kind === 'video' && i.status !== 'waiting_external');
  const pending = items.filter(
    i =>
      ['queued', 'running', 'processing', 'saving'].includes(i.status) &&
      i.kind === 'video' &&
      !i.asset_ids.length
  );

  const addRef = (id: string) =>
    setRefs(r => (r.includes(id) || id === base || id === finish || r.length >= maxRefs ? r : [...r, id]));
  const trash = async (id: string) => {
    if (!window.confirm('Убрать ролик из библиотеки? Он хранится в корзине 30 дней и восстанавливается.'))
      return;
    try {
      await json(await apiFetch(`/api/library/${id}/trash`, {method: 'POST'}));
      setNotice('Ролик убран в корзину на 30 дней.');
      await loadLibrary();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  /** Цепочка клипов: последний кадр ролика становится кадром-основой следующего. */
  const continueFrom = async (videoId: string) => {
    setError('');
    setBusy(true);
    try {
      const frame = await json(await apiFetch(`/api/library/${videoId}/last-frame`, {method: 'POST'}));
      await loadLibrary();
      setBase(frame.id);
      setNotice('Последний кадр ролика поставлен кадром-основой. Опиши продолжение.');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const favorite = async (id: string, value: boolean) => {
    try {
      await json(
        await apiFetch(`/api/library/${id}/favorite`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({favorite: value}),
        })
      );
      await loadLibrary();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  const cloudUrl = async (assetId: string) => {
    const a = byId[assetId];
    if (a?.provider_reference_url?.startsWith('https://')) return a.provider_reference_url;
    const r = await json(
      await apiFetch(`/api/library/${assetId}/upload-reference`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({approved: true, provider: 'tempfile'}),
      })
    );
    return r.url as string;
  };

  const start = async () => {
    setError('');
    setNotice('');
    if (!prompt.trim()) return setError('Опиши, что происходит в ролике');
    if (!isSeedance && total > 1) return setError('Эта модель принимает один кадр');
    if (activeMode === 'frames' && (!base || !finish)) return setError('Выбери стартовый и финишный кадры');
    if (fromClip) {
      if (!clip) return setError('Выбери исходный ролик');
      if (clipSec === null) return setError('Длина ролика ещё не определена, подожди секунду');
      if (clipSec > 30) return setError('Исходный ролик длиннее 30 секунд');
      if (activeMode === 'edit' && clipSec < 4)
        return setError('Для правки ролик должен быть не короче 4 секунд');
    }
    setBusy(true);
    try {
      const ids = fromClip
        ? []
        : [base, ...(activeMode === 'frames' ? [finish] : []), ...refs].filter(Boolean);
      const urls = await Promise.all(ids.map(cloudUrl));
      const videoUrls = fromClip ? [await cloudUrl(clip)] : [];
      const options: Record<string, string | number> = {...current};
      if (fromClip) {
        options.aspect_ratio = 'adaptive';
        options.task = activeMode;
        options.video_seconds = clipSec as number;
        if (activeMode === 'edit') delete options.duration;
      }
      setRequest({
        project_id: projectId,
        model_id: model,
        prompt: isSeedance ? modePrompt(activeMode, prompt, {hasBase: !!base, back}) : prompt.trim(),
        options,
        reference_urls: urls,
        ...(videoUrls.length ? {video_urls: videoUrls} : {}),
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const thumb = (id: string, remove: () => void, label?: string) => {
    const a = byId[id];
    return (
      <span key={id} className="vs-ref" title={label}>
        {a ? <img src={a.thumbnail_url || a.url} alt="" /> : <i />}
        <button type="button" aria-label="Убрать" onClick={remove}>
          <X size={12} />
        </button>
      </span>
    );
  };

  const provider = spec?.provider || 'piapi';
  const pageUrl = spec?.page_urls?.[provider];
  const range = (key: string) => schema[key];
  const rate = rateUsd !== undefined ? Math.round(rateUsd * 1000) / 10 : null;

  return (
    <section className="video-screen vs">
      <div className="vs-form">
        {notice && (
          <div className="notice" role="status">
            {notice}
          </div>
        )}
        {(error || feedError) && (
          <div className="alert" role="alert">
            {error || feedError}
          </div>
        )}

        {isSeedance && (
          <div className="vs-modes" role="tablist" aria-label="Режим ролика">
            {VIDEO_MODES.map(m => (
              <button
                key={m.id}
                type="button"
                role="tab"
                aria-selected={activeMode === m.id}
                className={activeMode === m.id ? 'on' : ''}
                onClick={() => setMode(m.id)}
              >
                {m.label}
              </button>
            ))}
          </div>
        )}

        {fromClip ? (
          <div className="vs-block">
            <b>Исходный ролик</b>
            <small className="muted">
              {activeMode === 'edit'
                ? 'длина результата равна длине исходника'
                : 'формат результата берётся из исходника'}
            </small>
            <div className="vs-row">
              {clip && byId[clip] ? (
                <video className="vs-clip" src={byId[clip].url} controls preload="metadata" />
              ) : (
                <button type="button" className="vs-add" onClick={() => setSource('clip')}>
                  Выбрать ролик
                </button>
              )}
              {clip && (
                <button type="button" onClick={() => setSource('clip')}>
                  Заменить
                </button>
              )}
              {clip && (
                <span className="vs-seconds">
                  {clipSec === null ? 'считаю длину…' : String(clipSec).replace('.', ',') + ' с'}
                </span>
              )}
            </div>
            {activeMode === 'extend' && (
              <div className="vs-row vs-dir" role="radiogroup" aria-label="Направление">
                <label>
                  <input type="radio" name="dir" checked={!back} onChange={() => setBack(false)} /> вперёд
                </label>
                <label>
                  <input type="radio" name="dir" checked={back} onChange={() => setBack(true)} /> назад
                </label>
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="vs-block">
              <b>{activeMode === 'frames' ? 'Старт' : 'Кадр-основа'}</b>
              <small className="muted">
                {activeMode === 'frames' ? 'первый кадр ролика' : 'с него начинается ролик'}
              </small>
              <div className="vs-row">
                {base ? (
                  thumb(base, () => setBase(''), 'Кадр-основа')
                ) : (
                  <button type="button" className="vs-add" onClick={() => setSource('base')}>
                    Выбрать кадр
                  </button>
                )}
                {base && (
                  <button type="button" onClick={() => setSource('base')}>
                    Заменить
                  </button>
                )}
              </div>
            </div>
            {activeMode === 'frames' && (
              <>
                <div className="vs-block">
                  <b>Финиш</b>
                  <small className="muted">последний кадр ролика (подсказка для модели)</small>
                  <div className="vs-row">
                    {finish ? (
                      thumb(finish, () => setFinish(''), 'Финиш')
                    ) : (
                      <button type="button" className="vs-add" onClick={() => setSource('finish')}>
                        Выбрать кадр
                      </button>
                    )}
                    {finish && (
                      <button type="button" onClick={() => setSource('finish')}>
                        Заменить
                      </button>
                    )}
                  </div>
                </div>
              </>
            )}
            <div className="vs-block">
              <b>Референсы</b>
              <div className="vs-row">
                {refs.map(id => thumb(id, () => setRefs(r => r.filter(x => x !== id))))}
                <button
                  type="button"
                  className="vs-add"
                  disabled={total >= refLimit || !isSeedance}
                  title={
                    isSeedance
                      ? 'Добавить персонажа или загрузить свой референс'
                      : 'Эта модель принимает только кадр-основу'
                  }
                  onClick={() => setSource('hero')}
                >
                  ＋
                </button>
                <button
                  type="button"
                  disabled={total >= refLimit || !isSeedance}
                  title="Выбрать готовую локацию"
                  onClick={() => setSource('location')}
                >
                  Локация
                </button>
                <span className="muted vs-count">
                  {total} из {refLimit}
                </span>
              </div>
            </div>
          </>
        )}

        <label className="vs-block">
          <b>Промпт</b>
          <textarea
            rows={6}
            value={prompt}
            placeholder="Что происходит в ролике: действие, настроение, звук. Движение камеры выбирается ниже."
            onChange={e => setPrompt(e.target.value)}
          />
        </label>

        <CameraFramePanel
          prompt={prompt}
          onPrompt={update => setPrompt(update)}
          categories={MOVE_ONLY}
          defaultOpen
          title="Движение камеры"
          hint="одно движение на ролик"
        />

        <div className="vs-block">
          <div className="vs-model">
            <b>Модель</b>
            <select value={model} onChange={e => setModel(e.target.value)}>
              {models.map(id => (
                <option key={id} value={id}>
                  {specs[id].label || id}
                </option>
              ))}
            </select>
            {pageUrl && (
              <a
                className="cs-info"
                href={pageUrl}
                target="_blank"
                rel="noreferrer"
                title={`Страница модели у ${PROVIDERS[provider] || provider}`}
              >
                i
              </a>
            )}
          </div>
          <div className="vs-opts">
            {range('resolution')?.values && (
              <label>
                Качество
                <select
                  value={String(value('resolution'))}
                  onChange={e => setValues(v => ({...v, resolution: e.target.value}))}
                >
                  {range('resolution').values!.map(v => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
            )}
            {range('aspect_ratio')?.values && !fromClip && (
              <label>
                Формат
                <select
                  value={String(value('aspect_ratio'))}
                  onChange={e => setValues(v => ({...v, aspect_ratio: e.target.value}))}
                >
                  {range('aspect_ratio').values!.map(v => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
            )}
            {range('duration')?.min !== undefined && activeMode !== 'edit' && (
              <label className="vs-length">
                Длина: {sec} с
                <input
                  type="range"
                  min={range('duration').min}
                  max={range('duration').max}
                  value={sec}
                  onChange={e => setValues(v => ({...v, duration: Number(e.target.value)}))}
                />
              </label>
            )}
          </div>
        </div>

        <div className="vs-run">
          <span className="vs-price">
            {cost === null ? '…' : '≈ ' + cents(cost)}
            {rate !== null && (
              <small className="muted">
                {' '}
                {String(rate).replace('.', ',')} ¢/с × {outSec} с
                {fromClip && clipSec
                  ? ` + ${String(rate / 2).replace('.', ',')} ¢/с × ${clipSec} с входа`
                  : ''}
              </small>
            )}
          </span>
          <button className="primary" disabled={busy || !projectId} onClick={() => void start()}>
            {busy ? 'Готовлю…' : 'Оценить и запустить'}
          </button>
        </div>
        <small className="muted">Перед отправкой покажу точную цену и попрошу подтверждение.</small>
      </div>

      <div className="vs-results cs-results">
        {pending.map(i => (
          <div key={i.id} className="cs-card cs-spin">
            <div className="cs-spinner" />
            <small>{modelLabel(specs, i.model)} · в работе…</small>
          </div>
        ))}
        {results.flatMap(item =>
          item.asset_ids.map(aid => {
            const a = byId[aid];
            if (!a) return null;
            return (
              <div key={item.id + aid} className="cs-card cs-result vs-result">
                <video src={a.url} controls />
                <FrameActions
                  className="cs-result-actions"
                  favorite={!!a.metadata.favorite}
                  onFavorite={() => void favorite(aid, !a.metadata.favorite)}
                  downloadUrl={a.url}
                  downloadName={a.filename}
                  onTrash={() => void trash(aid)}
                />
                <div className="cs-cap">
                  <div>
                    <b>{modelLabel(specs, item.model)}</b>
                    <small>{item.status}</small>
                  </div>
                  <div className="cs-row">
                    <button
                      disabled={busy}
                      title="Сохранить последний кадр ролика и начать с него следующий"
                      onClick={() => void continueFrom(aid)}
                    >
                      Продолжить →
                    </button>
                    <button
                      title="Подставить промпт и модель"
                      onClick={() => {
                        setPrompt(item.prompt);
                        if (specs[item.model]) setModel(item.model);
                      }}
                    >
                      ↻
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
        {!results.length && !pending.length && (
          <p className="muted vs-empty">Здесь появятся готовые ролики с плеером.</p>
        )}
      </div>

      {source === 'base' && (
        <LibraryPickModal
          title="Кадр-основа"
          assets={frames}
          onPick={setBase}
          onClose={() => setSource('')}
        />
      )}
      {source === 'finish' && (
        <LibraryPickModal
          title="Финишный кадр"
          assets={frames}
          onPick={setFinish}
          onClose={() => setSource('')}
        />
      )}
      {source === 'clip' && (
        <LibraryPickModal
          title="Исходный ролик"
          assets={videos}
          video
          onPick={setClip}
          onClose={() => setSource('')}
        />
      )}
      {source === 'hero' && (
        <AddReferenceModal
          projectId={projectId}
          refs={refs}
          onAdd={addRef}
          onUploaded={id => {
            addRef(id);
            void loadLibrary();
          }}
          onClose={() => setSource('')}
        />
      )}
      {source === 'location' && (
        <LocationModal
          projectId={projectId}
          refs={refs}
          world={world}
          onAdd={addRef}
          onCreate={brief => setPrompt(cur => (cur.trim() ? cur.trimEnd() + '\n\n' + brief : brief))}
          onClose={() => setSource('')}
        />
      )}
      {request && (
        <GenerationReview
          key={request.model_id + request.prompt.length}
          request={request}
          onClose={() => setRequest(null)}
          onSubmitted={() => {
            setRequest(null);
            reset();
            setNotice('Ролик отправлен. Он появится справа, когда провайдер закончит.');
          }}
        />
      )}
    </section>
  );
}
