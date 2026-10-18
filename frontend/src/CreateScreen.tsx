import {useEffect, useMemo, useState} from 'react';
import {apiFetch} from './api';
import {loadCreateDraft, saveCreateDraft} from './createDraft';
import GenerationReview, {type GenerationRequest} from './GenerationReview';
import {type ActivityItem} from './useActivity';
import {useSharedActivity} from './ActivityContext';
import Lightbox from './Lightbox';
import FrameActions from './FrameActions';
import CinemaInfo from './CinemaInfo';
import GenerateButton, {useEstimate} from './GenerateButton';
import {copyText, openQueue} from './imageRoutes';
import {
  buildReplaceInFramePrompt,
  buildReplaceInVideoPrompt,
  replacementRefs,
} from './replaceCharacterPrompt';
import {AddReferenceModal, LocationModal} from './FrameSources';
import CameraFramePanel from './CameraFramePanel';
import PriceTable, {cents, useModelRange, useOptionPrices} from './PriceTable';

type OptionSpec = {
  values?: (string | number)[];
  default?: string | number;
  min?: number;
  max?: number;
};
type Spec = {
  kind: string;
  launch_enabled?: boolean;
  prompt_only?: boolean;
  options?: Record<string, OptionSpec>;
  variants?: Record<string, unknown>;
  api_refs?: number;
  provider?: string;
  page_urls?: Record<string, string>;
};
type LibAsset = {
  id: string;
  url: string;
  thumbnail_url: string | null;
  provider_reference_url?: string | null;
  filename?: string;
  metadata: {kind?: string; favorite?: boolean};
};
type Hero = {id: string; name: string; assetId?: string};

const LABELS: Record<string, string> = {
  'seedream-5-pro': 'Seedream 5 Pro',
  'seedream-5-lite': 'Seedream 5 Lite',
  'seedream-5-lite-less-restriction': 'Seedream 5 Lite · less restriction',
  'seedream-5-pro-less-restriction': 'Seedream 5 Pro · less restriction',
  'gpt-image-2': 'GPT Image 2.0',
  'gpt-image-2.5': 'GPT Image 2.5',
  'nano-banana-2.1': 'Nano Banana 2.1',
  'qwen-image-2.1': 'Qwen Image 2.1',
};
/** Модели, у которых в карточке можно выбрать вариант; остальные id из LABELS показываются отдельными боксами. */
const FAMILIES: Record<string, string[]> = {
  'seedream-5-pro': ['seedream-5-pro', 'seedream-5-pro-less-restriction'],
  'seedream-5-lite': ['seedream-5-lite', 'seedream-5-lite-less-restriction'],
};
const MEMBERS = new Set(Object.values(FAMILIES).flat());
const ORDER = Object.keys(LABELS).filter(id => !MEMBERS.has(id) || id in FAMILIES);
const VARIANT_NAMES: Record<string, string> = {
  'seedream-5-pro': 'Pro',
  'seedream-5-pro-less-restriction': 'Pro · less restriction',
  'seedream-5-lite': 'Lite',
  'seedream-5-lite-less-restriction': 'Lite · less restriction',
};
/** Названия API-сервисов; новый сервис добавляется сюда и в каталог бэкенда (provider, page_urls). */
const PROVIDERS: Record<string, string> = {piapi: 'PiAPI'};

async function json(r: Response) {
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw Error(typeof d.detail === 'string' ? d.detail : 'Запрос не выполнен');
  return d;
}

type TempItem = {asset_id: string; days_left: number; expired: boolean; protected: string};

/** Серая «i» в кружке: страница модели у её API-сервиса (ссылка берётся из каталога бэкенда). */
function ModelInfo({spec}: {spec: Spec}) {
  const provider = spec.provider || 'piapi';
  const url = spec.page_urls?.[provider];
  const name = PROVIDERS[provider] || provider;
  return url ? (
    <a
      className="cs-info"
      href={url}
      target="_blank"
      rel="noreferrer"
      title={`Страница модели на ${name}`}
      aria-label={`Страница модели на ${name}`}
      onClick={e => e.stopPropagation()}
      onKeyDown={e => e.stopPropagation()}
    >
      i
    </a>
  ) : (
    <span className="cs-info off" title={`Ссылка на страницу модели у ${name} пока не задана`}>
      i
    </span>
  );
}

/** Цена или диапазон цен в заголовке бокса: видна, даже когда модель выключена. */
function ModelRange({id, schema}: {id: string; schema: Record<string, OptionSpec> | undefined}) {
  const range = useModelRange(id, schema);
  return range ? <> · {range}</> : null;
}

function ModelOptions({
  id,
  schema,
  current,
  onChange,
}: {
  id: string;
  schema: Record<string, OptionSpec>;
  current: Record<string, string | number>;
  onChange: (key: string, value: string | number) => void;
}) {
  const prices = useOptionPrices(id, schema, current);
  const priced = ['variant', 'quality', 'size', 'resolution'].some(k => schema[k]?.values);
  const flat = useModelRange(id, schema);
  return (
    <div className="cs-model-opts">
      {!priced && flat && (
        <label>
          <span>цена за картинку</span>
          <b className="cs-flat-price">{flat}</b>
        </label>
      )}
      {Object.entries(schema).map(([key, sp]) => (
        <label key={key}>
          <span>{key}</span>
          {sp.values ? (
            <select value={String(current[key])} onChange={e => onChange(key, e.target.value)}>
              {sp.values.map(v => {
                const p = prices[key]?.[String(v)];
                return (
                  <option key={String(v)} value={String(v)}>
                    {String(v)}
                    {p !== undefined && p !== null ? ' · ' + cents(p) : ''}
                  </option>
                );
              })}
            </select>
          ) : (
            <input
              type="number"
              min={sp.min}
              max={sp.max}
              value={Number(current[key])}
              onChange={e => onChange(key, Number(e.target.value))}
            />
          )}
        </label>
      ))}
    </div>
  );
}

export default function CreateScreen(props: {projectId: string; heroes: Hero[]; world?: string}) {
  return <CreateScreenBody key={props.projectId} {...props} />;
}

function CreateScreenBody({
  projectId,
  heroes,
  world = '',
}: {
  projectId: string;
  heroes: Hero[];
  world?: string;
}) {
  const [restored] = useState(() => loadCreateDraft(projectId));
  const [draftSaved, setDraftSaved] = useState(true);
  const {items, error: feedError, reset} = useSharedActivity();
  const [specs, setSpecs] = useState<Record<string, Spec>>({});
  const [library, setLibrary] = useState<LibAsset[]>([]);
  const [prompt, setPrompt] = useState(restored.prompt);
  async function addVisualRules() {
    setError('');
    try {
      const data = await json(await apiFetch(`/api/projects/${projectId}/visual-rules-prompt`));
      if (!data.prompt)
        return setError(
          'Для этого проекта визуальные правила не заданы: открой серию или сцену в раскадровке.'
        );
      setPrompt(current =>
        current.includes('VISUAL RULES') ? current : current.trimEnd() + '\n\n' + data.prompt
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }
  const [source, setSource] = useState<'' | 'hero' | 'location'>('');
  const [selected, setSelected] = useState<string[]>(restored.selected);
  const [pick, setPick] = useState<Record<string, string>>({});
  const [options, setOptions] = useState<Record<string, Record<string, string | number>>>(restored.options);
  const [refs, setRefs] = useState<string[]>(restored.refs);
  const [queue, setQueue] = useState<GenerationRequest[]>([]);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [animate, setAnimate] = useState('');
  const [view, setView] = useState<{
    entries: {id: string; kind?: string; title?: string}[];
    index: number;
  } | null>(null);
  const [videoModel, setVideoModel] = useState(restored.videoModel);
  const [motion, setMotion] = useState(restored.motion);
  const [videoOptions, setVideoOptions] = useState<Record<string, string | number>>(restored.videoOptions);
  /** Расширенные поля Seedance 2.5: ссылки на видео и аудио, тип задачи, черновик. */
  const [seedance, setSeedance] = useState({
    task: 'reference',
    videos: '',
    audios: '',
    videoSeconds: '',
    audioSeconds: '',
    draft: false,
    draftTaskId: '',
  });
  const [tab, setTab] = useState<'results' | 'favorites' | 'temp'>('results');
  const [temp, setTemp] = useState<TempItem[]>([]);
  const [wouldRemove, setWouldRemove] = useState<string[] | null>(null);

  useEffect(() => {
    setDraftSaved(
      saveCreateDraft(projectId, {prompt, selected, options, refs, videoModel, motion, videoOptions})
    );
  }, [projectId, prompt, selected, options, refs, videoModel, motion, videoOptions]);

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

  useEffect(() => {
    if (tab !== 'temp' || !projectId) return;
    void apiFetch('/api/library/temp?project_id=' + encodeURIComponent(projectId))
      .then(json)
      .then(d => setTemp(d.items))
      .catch(e => setError(String(e)));
  }, [tab, projectId, library.length]);
  const cleanup = async (approved: boolean) => {
    try {
      const d = await json(
        await apiFetch('/api/library/cleanup', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({project_id: projectId, approved}),
        })
      );
      if (approved) {
        setWouldRemove(null);
        setNotice(`Убрано в корзину: ${d.removed.length}. Файлы хранятся 30 дней и восстанавливаются.`);
        await loadLibrary();
      } else setWouldRemove(d.would_remove);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const models = ORDER.filter(id => specs[id]);
  const optionValue = (model: string, key: string, spec: OptionSpec) =>
    options[model]?.[key] ?? (spec.default as string | number);
  const optionsFor = (model: string) =>
    Object.fromEntries(
      Object.entries(specs[model]?.options || {}).map(([k, s]) => [k, optionValue(model, k, s)])
    ) as Record<string, string | number>;
  const estimate = useEstimate(
    selected.filter(m => specs[m]).map(model => ({model, options: optionsFor(model)}))
  );
  const byId = useMemo(() => Object.fromEntries(library.map(a => [a.id, a])), [library]);
  const images = library.filter(a => (a.metadata.kind || 'image') === 'image');

  const trashAsset = async (id: string) => {
    if (!window.confirm('Убрать файл из библиотеки? Он хранится в корзине 30 дней и восстанавливается.'))
      return;
    try {
      await json(await apiFetch(`/api/library/${id}/trash`, {method: 'POST'}));
      setRefs(r => r.filter(x => x !== id));
      setNotice('Файл убран в корзину на 30 дней.');
      await loadLibrary();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  const toggleRef = (id: string) => setRefs(r => (r.includes(id) ? r.filter(x => x !== id) : [...r, id]));
  /** «Править в GPT Image»: кадр становится первым референсом, модель — GPT Image 2.5. */
  const editAsset = (id: string) => {
    setRefs(r => [id, ...r.filter(x => x !== id)]);
    setSelected(['gpt-image-2.5']);
    setPrompt(p => p.trim() || 'Отредактируй изображение: ');
    setView(null);
    setNotice('Кадр прикреплён референсом для правки. Опиши, что изменить, и проверь цену.');
  };
  /** Действия над кадром одинаковы в плитках, карточках результатов и просмотре. */
  const actionsFor = (id: string, kind: string = 'image') => {
    const a = byId[id];
    return {
      favorite: !!a?.metadata.favorite,
      onFavorite: () => void favorite(id, !a?.metadata.favorite),
      onEdit: kind === 'image' ? () => editAsset(id) : undefined,
      onRef: kind === 'image' ? () => toggleRef(id) : undefined,
      refActive: refs.includes(id),
      onAnimate:
        kind === 'image'
          ? () => {
              setView(null);
              setAnimate(id);
            }
          : undefined,
      downloadUrl: a?.url,
      downloadName: a?.filename,
      onTrash: () => void trashAsset(id),
    };
  };

  const toggle = (id: string) => setSelected(s => (s.includes(id) ? s.filter(x => x !== id) : [...s, id]));

  /** Кнопка «Заменить героя»: ставит промпт замены и референсы (кадр, герой). Запуск обычный: цена и подтверждение. */
  const replaceHero = (frameId: string, heroId: string) => {
    const hero = heroes.find(h => h.id === heroId);
    if (!hero?.assetId)
      return setError(`У героя «${hero?.name ?? ''}» нет рабочего образа: добавь его в «Мир → Персонажи»`);
    setError('');
    setPrompt(buildReplaceInFramePrompt());
    setRefs(replacementRefs(frameId, hero.assetId));
    setNotice(
      `Замена героя на «${hero.name}»: референсы (кадр, герой) и промпт поставлены. Выбери модель справа и запусти, цена и подтверждение как обычно.`
    );
  };

  const ensureCloudUrl = async (assetId: string) => {
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

  /** Параметры видеомодели: из spec.options или из плоских полей старых спецификаций. */
  const videoSpec = (id: string): Record<string, OptionSpec> => {
    const spec = specs[id] as (Spec & Record<string, any>) | undefined;
    if (!spec) return {};
    if (spec.options) return spec.options;
    return {
      resolution: {values: spec.resolution, default: spec.resolution?.[0]},
      duration: {min: spec.duration_min, max: spec.duration_max, default: spec.duration_min},
      aspect_ratio: {values: spec.aspect_ratio, default: spec.aspect_ratio?.[0]},
    };
  };
  /** Цепочка клипов: последний кадр видео становится первым кадром следующего. */
  const continueFrom = async (videoAssetId: string) => {
    setError('');
    setBusy(true);
    try {
      const frame = await json(await apiFetch(`/api/library/${videoAssetId}/last-frame`, {method: 'POST'}));
      await loadLibrary();
      setAnimate(frame.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const startAnimate = async () => {
    setError('');
    if (!motion.trim()) return setError('Опиши движение в кадре');
    setBusy(true);
    try {
      const url = await ensureCloudUrl(animate);
      const opts = Object.fromEntries(
        Object.entries(videoSpec(videoModel)).map(([k, sp]) => [k, videoOptions[k] ?? sp.default])
      ) as Record<string, string | number | boolean>;
      const request: GenerationRequest = {
        project_id: projectId,
        model_id: videoModel,
        prompt: motion,
        options: opts,
        reference_urls: [url],
      };
      if (videoModel === 'seedance-2.5') {
        const lines = (text: string) =>
          text
            .split('\n')
            .map(line => line.trim())
            .filter(Boolean);
        const videos = lines(seedance.videos);
        const audios = lines(seedance.audios);
        if (seedance.draftTaskId.trim()) {
          // Финал по черновику: промпт, референсы и длительность берутся из черновика.
          request.options = {draft_task_id: seedance.draftTaskId.trim(), resolution: '1080p'};
          request.reference_urls = [];
        } else {
          if (seedance.task !== 'reference') request.options.task = seedance.task;
          if (seedance.draft) {
            request.options.draft = true;
            request.options.resolution = '480p';
          }
          if (videos.length) request.video_urls = videos;
          if (audios.length) request.audio_urls = audios;
          if (videos.length && !Number(seedance.videoSeconds)) {
            throw Error('Укажи суммарную длину видео-референсов в секундах (до 30)');
          }
          if (audios.length && !Number(seedance.audioSeconds)) {
            throw Error('Укажи суммарную длину аудио-референсов в секундах (до 30)');
          }
          if (videos.length) request.options.video_seconds = Number(seedance.videoSeconds);
          if (audios.length) request.options.audio_seconds = Number(seedance.audioSeconds);
        }
      }
      setQueue([request]);
      setAnimate('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const start = async () => {
    setError('');
    if (!prompt.trim()) return setError('Напиши промпт');
    const apiModels = selected;
    if (!apiModels.length) return setError('Выбери хотя бы одну модель');
    setBusy(true);
    try {
      const urls = await Promise.all(refs.map(ensureCloudUrl));
      setQueue(
        apiModels.map(model => ({
          project_id: projectId,
          model_id: model,
          prompt,
          options: optionsFor(model),
          reference_urls: urls,
        }))
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const copyPrompt = async (text: string) => {
    const ok = await copyText(text);
    setNotice(ok ? 'Промпт скопирован.' : 'Не удалось скопировать — выдели и скопируй промпт вручную.');
  };

  const favorite = async (id: string, on: boolean) => {
    try {
      await json(
        await apiFetch(`/api/library/${id}/favorite`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({favorite: on}),
        })
      );
      await loadLibrary();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const toHero = async (assetId: string, characterId: string) => {
    try {
      await json(
        await apiFetch(`/api/library/${assetId}/to-character`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            project_id: projectId,
            character_id: characterId,
          }),
        })
      );
      setNotice('Добавлено в референсы персонажа');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const regenerate = (item: ActivityItem) => {
    setPrompt(item.prompt);
    if (specs[item.model]) setSelected([item.model]);
    setNotice('Промпт и модель подставлены. Нажми «Создать», чтобы отправить повторно.');
  };

  const waiting = items.filter(i => i.status === 'waiting_external');
  const results = items.filter(
    i => (i.kind === 'image' || i.kind === 'video') && i.status !== 'waiting_external'
  );
  // Крутилка только у заданий, которые действительно в работе: отменённые и завершённые без файла её не получают.
  const pending = items.filter(
    i =>
      ['queued', 'running', 'processing', 'saving'].includes(i.status) &&
      (i.kind === 'image' || i.kind === 'video') &&
      !i.asset_ids.length
  );
  const shownImages = tab === 'favorites' ? images.filter(a => a.metadata.favorite) : images;
  const total = selected.length;

  const openResult = (aid: string) => {
    const list = results.flatMap(it =>
      it.asset_ids
        .filter(x => byId[x])
        .map(x => ({id: x, kind: it.kind, title: LABELS[it.model] || it.model}))
    );
    setView({
      entries: list,
      index: Math.max(
        0,
        list.findIndex(x => x.id === aid)
      ),
    });
  };

  const modelCard = (base: string) => {
    const family = FAMILIES[base];
    const id = family ? (family.find(m => selected.includes(m)) ?? pick[base] ?? base) : base;
    const on = selected.includes(id);
    const o = specs[id]?.options;
    const choose = (next: string) => {
      setPick(p => ({...p, [base]: next}));
      setSelected(s => s.map(x => (x === id ? next : x)));
    };
    return (
      <div key={id} className={'cs-model' + (on ? ' on' : '')}>
        <div
          role="button"
          tabIndex={0}
          className="cs-model-head"
          onClick={() => toggle(id)}
          onKeyDown={e => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              toggle(id);
            }
          }}
          aria-pressed={on}
        >
          <span>
            <b>
              {LABELS[id]}
              <ModelInfo spec={specs[id]} />
            </b>
            <small>
              {PROVIDERS[specs[id].provider || 'piapi'] || specs[id].provider}
              {specs[id].launch_enabled === false ? ' · проверяется' : ''}
              <ModelRange id={id} schema={specs[id].options} />
            </small>
          </span>
          <em>{on ? 'вкл' : 'выкл'}</em>
        </div>
        {on && family && (
          <label className="cs-variant">
            <span>модель</span>
            <select value={id} onChange={e => choose(e.target.value)}>
              {family
                .filter(m => specs[m])
                .map(m => (
                  <option key={m} value={m}>
                    {VARIANT_NAMES[m] || m}
                    {specs[m].launch_enabled === false ? ' · не проверена' : ''}
                  </option>
                ))}
            </select>
          </label>
        )}
        {on && o && (
          <ModelOptions
            id={id}
            schema={o}
            current={Object.fromEntries(
              Object.entries(o).map(([key, sp]) => [key, optionValue(id, key, sp)])
            )}
            onChange={(key, value) => setOptions(p => ({...p, [id]: {...p[id], [key]: value}}))}
          />
        )}
      </div>
    );
  };

  return (
    <section className="create-screen cs">
      <aside className="cs-refs">
        <div className="cs-head">
          <b>Референсы</b>
          <span className="muted">{refs.length} выбрано</span>
        </div>
        {refs.length > 0 && (
          <div className="cs-grid2">
            {refs.map(id => {
              const a = byId[id];
              return (
                <div key={id} className="cs-tile on">
                  {a && <img src={a.thumbnail_url || a.url} alt="" />}
                  <button
                    type="button"
                    className="cs-x"
                    aria-label="Убрать из запроса"
                    title="Убрать из запроса (файл остаётся в библиотеке)"
                    onClick={() => toggleRef(id)}
                  >
                    ×
                  </button>
                </div>
              );
            })}
          </div>
        )}
        <div className="cs-head">
          <b className="muted">Библиотека</b>
          <span className="cs-tabs">
            <button className={tab !== 'favorites' ? 'active' : ''} onClick={() => setTab('results')}>
              все
            </button>
            <button className={tab === 'favorites' ? 'active' : ''} onClick={() => setTab('favorites')}>
              ♥
            </button>
          </span>
        </div>
        <div className="cs-grid2 cs-scroll">
          {shownImages.slice(0, 60).map(a => (
            <div key={a.id} className={'cs-tile' + (refs.includes(a.id) ? ' on' : '')}>
              <button
                type="button"
                className="cs-pick"
                onClick={() => toggleRef(a.id)}
                title="Добавить/убрать референс"
              >
                <img src={a.thumbnail_url || a.url} alt="" />
              </button>
              <button
                type="button"
                className="cs-x cs-zoom"
                aria-label="Открыть крупно"
                title="Открыть крупно"
                onClick={() => {
                  const list = shownImages.slice(0, 60);
                  setView({
                    entries: list.map(x => ({id: x.id, title: x.id})),
                    index: list.findIndex(x => x.id === a.id),
                  });
                }}
              >
                ⤢
              </button>
              {a.metadata.favorite && (
                <span className="cs-fav-badge" aria-hidden="true">
                  ♥
                </span>
              )}
              <FrameActions
                small
                className="cs-tile-actions"
                {...actionsFor(a.id)}
                onRef={undefined}
                onAnimate={undefined}
              />
            </div>
          ))}
          {!shownImages.length && <span className="muted">Пока нет изображений</span>}
        </div>
        <div className="cs-temp">
          <button onClick={() => setTab('temp')} className={tab === 'temp' ? 'active' : ''}>
            Временные (7 дней)
          </button>
        </div>
        {tab === 'temp' && (
          <div className="cs-tempbox">
            <p className="muted">
              Без сердечка и без использования уходят через 7 дней в корзину (ещё 30 дней хранятся).
            </p>
            <div className="cs-temp-list">
              {temp.map(t => (
                <span key={t.asset_id} title={t.protected || ''}>
                  {byId[t.asset_id] && (
                    <img src={byId[t.asset_id].thumbnail_url || byId[t.asset_id].url} alt="" />
                  )}
                  <small>
                    {t.protected ? 'используется' : t.expired ? 'просрочен' : `${t.days_left} дн.`}
                  </small>
                </span>
              ))}
            </div>
            <button onClick={() => cleanup(false)}>Показать, что будет убрано</button>
            {wouldRemove && (
              <button className="primary" disabled={!wouldRemove.length} onClick={() => cleanup(true)}>
                Убрать в корзину: {wouldRemove.length}
              </button>
            )}
          </div>
        )}
      </aside>

      <div className="cs-main">
        {!draftSaved && (
          <div className="alert" role="alert">
            Браузер не сохранил черновик. Скопируй промпт перед уходом со страницы.
          </div>
        )}
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
        <div className="cs-results">
          {waiting.length > 0 && (
            <div className="cs-card cs-wait">
              <b>Ждём картинку из ChatGPT: {waiting.length}</b>
              <small>Верни готовую картинку в «Очереди» справа: Ctrl+V или файл.</small>
              <button onClick={openQueue}>Открыть очередь</button>
            </div>
          )}
          {pending.map(i => (
            <div key={i.id} className="cs-card cs-spin">
              <div className="cs-spinner" />
              <small>{LABELS[i.model] || i.model} · в работе…</small>
            </div>
          ))}
          {results.flatMap(item =>
            item.asset_ids.map(aid => {
              const a = byId[aid];
              if (!a) return null;
              return (
                <div key={item.id + aid} className="cs-card cs-result">
                  {item.kind === 'video' ? (
                    <video src={a.url} controls />
                  ) : (
                    <img
                      src={a.thumbnail_url || a.url}
                      alt=""
                      className="cs-zoomable"
                      title="Открыть крупно"
                      onClick={() => openResult(aid)}
                    />
                  )}
                  <FrameActions className="cs-result-actions" {...actionsFor(aid, item.kind)} />
                  <div className="cs-cap">
                    <div>
                      <b>{LABELS[item.model] || item.model}</b>
                      <small>{item.status}</small>
                    </div>
                    <div className="cs-row">
                      {item.kind === 'video' && (
                        <button
                          disabled={busy}
                          title="Сохранить последний кадр клипа и начать с него следующий клип"
                          onClick={() => void continueFrom(aid)}
                        >
                          Продолжить →
                        </button>
                      )}
                      <button onClick={() => regenerate(item)} title="Подставить промпт и модель">
                        ↻
                      </button>
                      {item.kind === 'image' && (
                        <select
                          value=""
                          title="Подставить героя вместо персонажа в этом кадре (кадр и герой станут референсами)"
                          onChange={e => e.target.value && replaceHero(aid, e.target.value)}
                        >
                          <option value="">Заменить героя ▾</option>
                          {heroes.map(h => (
                            <option key={h.id} value={h.id} disabled={!h.assetId}>
                              {h.name}
                              {h.assetId ? '' : ' (нет образа)'}
                            </option>
                          ))}
                        </select>
                      )}
                      {item.kind === 'video' && (
                        <button
                          title="Скопировать промпт замены героя в видео (Kling 3.0 Omni: исходное видео и картинка героя)"
                          onClick={() => void copyPrompt(buildReplaceInVideoPrompt())}
                        >
                          Промпт замены героя
                        </button>
                      )}
                      <select value="" onChange={e => e.target.value && toHero(aid, e.target.value)}>
                        <option value="">В героя ▾</option>
                        {heroes.map(h => (
                          <option key={h.id} value={h.id}>
                            {h.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>
              );
            })
          )}
          {!results.length && !waiting.length && !pending.length && (
            <div className="cs-empty muted">
              Здесь появятся результаты. Напиши промпт ниже и выбери модели справа.
            </div>
          )}
        </div>

        <div className="cs-prompt">
          <textarea
            rows={3}
            value={prompt}
            placeholder="Опиши кадр: кто, где, свет, ракурс…"
            onChange={e => setPrompt(e.target.value)}
          />
          <CameraFramePanel
            prompt={prompt}
            onPrompt={setPrompt}
            extra={
              <div className="cf-extra">
                <button
                  disabled={!projectId}
                  aria-label="Добавить персонажа или референс"
                  title="Добавить персонажа или загрузить свой референс"
                  onClick={() => setSource('hero')}
                >
                  ＋
                </button>
                <button
                  disabled={!projectId}
                  title="Выбрать готовую локацию или создать новую по мотивам мира"
                  onClick={() => setSource('location')}
                >
                  Локация
                </button>
                <button
                  disabled={!projectId}
                  title="Добавить в промпт визуальные правила серии, локации и героев этого кадра"
                  onClick={() => void addVisualRules()}
                >
                  ＋ Правила серии
                </button>
                <CinemaInfo topic="composition" />
                <CinemaInfo topic="lens" />
              </div>
            }
          />
          <div className="cs-row">
            <span className="muted">
              {refs.length} реф. · {total} {total === 1 ? 'модель' : 'моделей'}
            </span>
            <span className="cs-spacer" />
            <GenerateButton
              projectId={projectId}
              busy={busy}
              disabled={!projectId}
              estimate={estimate}
              count={selected.length}
              onApi={start}
              job={() =>
                prompt.trim()
                  ? {
                      projectId,
                      prompt,
                      target: selected.find(id => specs[id]) || 'gpt-image-2.5',
                      referenceAssetIds: refs,
                    }
                  : 'Напиши промпт'
              }
              onNotice={setNotice}
              onError={setError}
            />
          </div>
        </div>
      </div>

      <aside className="cs-models">
        <div className="cs-head">
          <b>Модели</b>
        </div>
        {models.map(modelCard)}
        <PriceTable specs={specs} labels={LABELS} models={Object.keys(LABELS)} />
        <div className="cs-note">
          Перед отправкой покажу точную цену и попрошу подтверждение. Ручная попытка в ChatGPT стоит $0 по
          API.
        </div>
      </aside>

      {source === 'hero' && (
        <AddReferenceModal
          projectId={projectId}
          refs={refs}
          onAdd={id => setRefs(r => (r.includes(id) ? r : [...r, id]))}
          onUploaded={id => {
            setRefs(r => (r.includes(id) ? r : [...r, id]));
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
          onAdd={id => setRefs(r => (r.includes(id) ? r : [...r, id]))}
          onCreate={brief => {
            setPrompt(cur => (cur.trim() ? cur.trimEnd() + '\n\n' + brief : brief));
            setNotice(
              'Промпт локации добавлен: выбери модель и сгенерируй, результат появится в библиотеке.'
            );
          }}
          onClose={() => setSource('')}
        />
      )}
      {view && (
        <Lightbox
          items={view.entries.map(e => ({
            url: byId[e.id]?.url || '',
            kind: e.kind,
            title: e.title,
            ...actionsFor(e.id, e.kind),
          }))}
          index={view.index}
          onIndex={i => setView(v => (v ? {...v, index: i} : v))}
          onClose={() => setView(null)}
        />
      )}
      {animate && (
        <div className="modal-backdrop">
          <section className="panel generation-review" role="dialog" aria-modal="true">
            <h2>Оживить кадр</h2>
            {byId[animate] && (
              <img src={byId[animate].thumbnail_url || byId[animate].url} alt="" width={160} />
            )}
            <label>
              Модель
              <select
                value={videoModel}
                onChange={e => {
                  setVideoModel(e.target.value);
                  setVideoOptions({});
                }}
              >
                {['seedance-2.5', 'minimax-h3']
                  .filter(id => specs[id])
                  .map(id => (
                    <option key={id} value={id}>
                      {id === 'seedance-2.5' ? 'Seedance 2.5' : 'MiniMax H3'}
                      {specs[id].launch_enabled === false ? ' (проверяется)' : ''}
                    </option>
                  ))}
              </select>
            </label>
            <label>
              Что должно происходить
              <textarea rows={3} value={motion} onChange={e => setMotion(e.target.value)} />
            </label>
            {Object.entries(videoSpec(videoModel)).map(([key, sp]) => (
              <label key={key}>
                {key}
                {sp.values ? (
                  <select
                    value={String(videoOptions[key] ?? sp.default)}
                    onChange={e => setVideoOptions(o => ({...o, [key]: e.target.value}))}
                  >
                    {sp.values.map(v => (
                      <option key={String(v)} value={String(v)}>
                        {String(v)}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="number"
                    min={sp.min}
                    max={sp.max}
                    value={Number(videoOptions[key] ?? sp.default)}
                    onChange={e => setVideoOptions(o => ({...o, [key]: Number(e.target.value)}))}
                  />
                )}
              </label>
            ))}
            {videoModel === 'seedance-2.5' && (
              <details>
                <summary>Видео, аудио, правка и черновик (Seedance 2.5)</summary>
                <label>
                  Тип задачи
                  <select
                    value={seedance.task}
                    onChange={e => setSeedance(s => ({...s, task: e.target.value}))}
                  >
                    <option value="reference">Генерация по референсам</option>
                    <option value="edit">Правка видео (In @video1, change …)</option>
                    <option value="extend">Продление видео (Extend @video1 forward: …)</option>
                  </select>
                </label>
                <label>
                  Ссылки на видео-референсы (https, по одной в строке; тег @video1, @video2…)
                  <textarea
                    rows={2}
                    value={seedance.videos}
                    onChange={e => setSeedance(s => ({...s, videos: e.target.value}))}
                  />
                </label>
                <label>
                  Суммарная длина видео, секунд (до 30)
                  <input
                    type="number"
                    min={0}
                    max={30}
                    value={seedance.videoSeconds}
                    onChange={e => setSeedance(s => ({...s, videoSeconds: e.target.value}))}
                  />
                </label>
                <label>
                  Ссылки на аудио-референсы (https, по одной в строке; тег @audio1…)
                  <textarea
                    rows={2}
                    value={seedance.audios}
                    onChange={e => setSeedance(s => ({...s, audios: e.target.value}))}
                  />
                </label>
                <label>
                  Суммарная длина аудио, секунд (до 30)
                  <input
                    type="number"
                    min={0}
                    max={30}
                    value={seedance.audioSeconds}
                    onChange={e => setSeedance(s => ({...s, audioSeconds: e.target.value}))}
                  />
                </label>
                <label className="inline-checkbox">
                  <input
                    type="checkbox"
                    checked={seedance.draft}
                    onChange={e => setSeedance(s => ({...s, draft: e.target.checked}))}
                  />{' '}
                  Черновик (только 480p, дешевле; финал 1080p делается отдельно)
                </label>
                <label>
                  Финал по черновику: ID задачи-черновика (остальные поля игнорируются)
                  <input
                    value={seedance.draftTaskId}
                    onChange={e => setSeedance(s => ({...s, draftTaskId: e.target.value}))}
                  />
                </label>
                <p className="muted">
                  Длину референсов сервис не измеряет, её называешь ты: от неё зависит цена. Цена и раскладка
                  будут в окне подтверждения.
                </p>
              </details>
            )}
            <div className="chips">
              <button className="primary" disabled={busy} onClick={() => void startAnimate()}>
                {busy ? 'Готовлю…' : 'Дальше: оценка и подтверждение'}
              </button>
              <button onClick={() => setAnimate('')}>Отмена</button>
            </div>
          </section>
        </div>
      )}
      {queue[0] && (
        <GenerationReview
          key={`${queue[0].model_id}-${queue.length}`}
          request={queue[0]}
          onClose={() => setQueue([])}
          onSubmitted={() => {
            setQueue(q => q.slice(1));
            reset();
          }}
        />
      )}
    </section>
  );
}
