import {useEffect, useMemo, useRef, useState} from 'react';
import {apiFetch} from './api';
import {loadCreateDraft, saveCreateDraft} from './createDraft';
import GenerationReview, {type GenerationRequest} from './GenerationReview';
import {type ActivityItem} from './useActivity';
import {useSharedActivity} from './ActivityContext';
import Lightbox, {type LightboxItem} from './Lightbox';
import CinemaInfo from './CinemaInfo';
import {DEFAULT_CHAT_URL, copyTextFor, getChatUrl} from './chatLink';
import {appendBlock} from './visualPlan';

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
};
type LibAsset = {
  id: string;
  url: string;
  thumbnail_url: string | null;
  provider_reference_url?: string | null;
  metadata: {kind?: string; favorite?: boolean};
};
type Hero = {id: string; name: string};

const LABELS: Record<string, string> = {
  'seedream-5-pro': 'Seedream 5 Pro',
  'seedream-5-lite': 'Seedream 5 Fast',
  'gpt-image-2': 'GPT Image 2.0',
  'gpt-image-2.5': 'GPT Image 2.5',
  'nano-banana-2.1': 'Nano Banana 2.1',
  'qwen-image-2.1': 'Qwen Image 2.1',
};
const ORDER = Object.keys(LABELS);

async function json(r: Response) {
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw Error(typeof d.detail === 'string' ? d.detail : 'Запрос не выполнен');
  return d;
}

type TempItem = {asset_id: string; days_left: number; expired: boolean; protected: string};

export default function CreateScreen(props: {projectId: string; heroes: Hero[]}) {
  return <CreateScreenBody key={props.projectId} {...props} />;
}

function CreateScreenBody({projectId, heroes}: {projectId: string; heroes: Hero[]}) {
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
  async function addComposition() {
    setError('');
    try {
      const data = await json(await apiFetch(`/api/projects/${projectId}/composition-brief`));
      setPrompt(current => appendBlock(current, data.prompt, 'VISUAL COMPOSITION BRIEF'));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }
  const [selected, setSelected] = useState<string[]>(restored.selected);
  const [options, setOptions] = useState<Record<string, Record<string, string | number>>>(restored.options);
  const [refs, setRefs] = useState<string[]>(restored.refs);
  const [queue, setQueue] = useState<GenerationRequest[]>([]);
  const [notice, setNotice] = useState('');
  const [codexJob, setCodexJob] = useState<{id: string; status: string; message: string} | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const [pasteFor, setPasteFor] = useState('');
  const [animate, setAnimate] = useState('');
  const [view, setView] = useState<{items: LightboxItem[]; index: number} | null>(null);
  const [videoModel, setVideoModel] = useState(restored.videoModel);
  const [motion, setMotion] = useState(restored.motion);
  const [videoOptions, setVideoOptions] = useState<Record<string, string | number>>(restored.videoOptions);
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

  const toggle = (id: string) => setSelected(s => (s.includes(id) ? s.filter(x => x !== id) : [...s, id]));

  const ensureCloudUrl = async (assetId: string) => {
    const a = byId[assetId];
    if (a?.provider_reference_url) return a.provider_reference_url;
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
      ) as Record<string, string | number>;
      setQueue([
        {project_id: projectId, model_id: videoModel, prompt: motion, options: opts, reference_urls: [url]},
      ]);
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
          options: Object.fromEntries(
            Object.entries(specs[model]?.options || {}).map(([k, s]) => [k, optionValue(model, k, s)])
          ) as Record<string, string | number>,
          reference_urls: urls,
        }))
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  /** На телефоне уходим в приложение ChatGPT; на компьютере чат открывается во вкладке рядом. */
  const openChatApp = () => {
    const url = getChatUrl() || DEFAULT_CHAT_URL;
    if (window.matchMedia('(max-width: 700px)').matches) window.location.href = url;
    else window.open(url, '_blank', 'noopener');
  };

  const copyPrompt = async (text: string) => {
    const ok = await navigator.clipboard?.writeText(text).then(
      () => true,
      () => false
    );
    setNotice(ok ? 'Промпт скопирован.' : 'Не удалось скопировать — выдели и скопируй промпт вручную.');
  };

  /** Копирует промпт и создаёт ожидающее внешнее задание; с openChat ещё открывает чат ChatGPT. */
  /** Ставит промпт и референсы в очередь ветки Codex на компьютере: она сама сгенерирует картинку. */
  const toCodex = async () => {
    setError('');
    if (!prompt.trim()) return setError('Напиши промпт');
    try {
      const target = selected.find(id => id.startsWith('gpt-image-')) || 'gpt-image-2.5';
      const job = await json(
        await apiFetch('/api/chatgpt/jobs', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            project_id: projectId,
            target,
            operation: 'generate',
            request_id: crypto.randomUUID().replace(/-/g, ''),
            brief: prompt,
            reference_asset_ids: refs,
          }),
        })
      );
      setCodexJob({id: job.id, status: job.status, message: job.message});
      const chat = await json(await apiFetch('/api/chatgpt/status')).catch(() => null);
      setNotice(
        chat?.worker_online
          ? 'Отправлено в Codex. Картинка появится в библиотеке, когда ветка её сгенерирует.'
          : 'Поставлено в очередь, но ветка Codex сейчас не слушает очередь. Открой её на компьютере и напиши «Продолжай очередь студии».'
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    if (!codexJob || ['completed', 'failed', 'cancelled'].includes(codexJob.status)) return;
    const timer = window.setInterval(() => {
      void apiFetch('/api/chatgpt/jobs?project_id=' + encodeURIComponent(projectId))
        .then(r => (r.ok ? r.json() : []))
        .then((list: {id: string; status: string; message: string}[]) => {
          const current = list.find(j => j.id === codexJob.id);
          if (!current) return;
          setCodexJob({id: current.id, status: current.status, message: current.message});
          if (current.status === 'completed') {
            void loadLibrary();
            setNotice('Codex прислал картинку: она в библиотеке.');
          }
        })
        .catch(() => undefined);
    }, 6000);
    return () => window.clearInterval(timer);
  }, [codexJob, projectId]);

  const external = async (openChat = false) => {
    setError('');
    if (!prompt.trim()) return setError('Напиши промпт');
    const roles = refs.map((_, i) => (i === 0 ? 'главный референс' : 'референс'));
    // Буфер записываем сразу, пока жив жест нажатия: после запроса к серверу телефон его не даст.
    const localText = copyTextFor(prompt, roles);
    const copied = navigator.clipboard
      ? navigator.clipboard.writeText(localText).then(
          () => true,
          () => false
        )
      : Promise.resolve(false);
    try {
      const target = selected.find(id => specs[id]) || 'gpt-image-2.5';
      await json(
        await apiFetch('/api/external-jobs', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            project_id: projectId,
            request_id: crypto.randomUUID().replace(/-/g, ''),
            target,
            prompt,
            service: 'chatgpt',
            references: refs.map((asset_id, i) => ({asset_id, role: roles[i]})),
          }),
        })
      );
      reset();
      const ok = await copied;
      const chat = getChatUrl();
      const where = openChat
        ? chat
          ? 'Открываю твой чат ChatGPT.'
          : 'Ссылка на чат не задана (Настройки), открываю ChatGPT.'
        : 'Сгенерируй в ChatGPT';
      setNotice(
        ok
          ? `Промпт скопирован. ${where} Потом верни картинку кнопкой «Вставить результат» или «Файл…».`
          : `Не удалось скопировать в буфер — скопируй промпт вручную из поля ниже. ${where}`
      );
      if (openChat) openChatApp();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  const attach = async (jobId: string, file: File) => {
    try {
      const form = new FormData();
      form.append('file', file);
      await json(
        await apiFetch(`/api/external-jobs/${jobId}/result`, {
          method: 'POST',
          body: form,
        })
      );
      setPasteFor('');
      reset();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  useEffect(() => {
    if (!pasteFor) return;
    const onPaste = (ev: ClipboardEvent) => {
      const file = Array.from(ev.clipboardData?.files || []).find(f => f.type.startsWith('image/'));
      if (file) void attach(pasteFor, file);
    };
    window.addEventListener('paste', onPaste);
    return () => window.removeEventListener('paste', onPaste);
  }, [pasteFor]);

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
  const pending = items.filter(
    i =>
      i.status !== 'waiting_external' &&
      i.status !== 'completed' &&
      i.status !== 'succeeded' &&
      i.status !== 'failed' &&
      (i.kind === 'image' || i.kind === 'video') &&
      !i.asset_ids.length
  );
  const shownImages = tab === 'favorites' ? images.filter(a => a.metadata.favorite) : images;
  const total = selected.length;

  const openResult = (aid: string) => {
    const list = results.flatMap(it =>
      it.asset_ids
        .filter(x => byId[x])
        .map(x => ({
          id: x,
          url: byId[x].url,
          kind: it.kind,
          title: LABELS[it.model] || it.model,
        }))
    );
    setView({
      items: list,
      index: Math.max(
        0,
        list.findIndex(x => x.id === aid)
      ),
    });
  };

  const modelCard = (id: string) => {
    const on = selected.includes(id);
    const o = specs[id]?.options;
    return (
      <div key={id} className={'cs-model' + (on ? ' on' : '')}>
        <button type="button" className="cs-model-head" onClick={() => toggle(id)} aria-pressed={on}>
          <span>
            <b>{LABELS[id]}</b>
            <small>PiAPI{specs[id].launch_enabled === false ? ' · проверяется' : ''}</small>
          </span>
          <em>{on ? 'вкл' : 'выкл'}</em>
        </button>
        {on && o && (
          <div className="cs-model-opts">
            {Object.entries(o).map(([key, sp]) => (
              <label key={key}>
                <span>{key}</span>
                {sp.values ? (
                  <select
                    value={String(optionValue(id, key, sp))}
                    onChange={e => setOptions(p => ({...p, [id]: {...p[id], [key]: e.target.value}}))}
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
                    value={Number(optionValue(id, key, sp))}
                    onChange={e => setOptions(p => ({...p, [id]: {...p[id], [key]: Number(e.target.value)}}))}
                  />
                )}
              </label>
            ))}
          </div>
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
                    items: list.map(x => ({url: x.url, title: x.id})),
                    index: list.findIndex(x => x.id === a.id),
                  });
                }}
              >
                ⤢
              </button>
              <button
                type="button"
                className={'cs-heart' + (a.metadata.favorite ? ' on' : '')}
                aria-label="Избранное"
                title="Избранное"
                onClick={() => void favorite(a.id, !a.metadata.favorite)}
              >
                {a.metadata.favorite ? '♥' : '♡'}
              </button>
              <button
                type="button"
                className="cs-x cs-trash"
                aria-label="Убрать в корзину"
                title="Убрать из библиотеки (в корзину на 30 дней)"
                onClick={() => void trashAsset(a.id)}
              >
                🗑
              </button>
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
          {waiting.map(j => (
            <div key={j.id} className="cs-card cs-wait">
              <b>Ждём картинку из ChatGPT</b>
              <small>{j.prompt.slice(0, 80)}…</small>
              <ol className="cs-steps">
                <li>
                  <span>Скопировать промпт</span>
                  <button onClick={() => void copyPrompt(j.prompt)}>Промпт</button>
                </li>
                <li>
                  <span>Открыть ChatGPT и сгенерировать</span>
                  <button onClick={openChatApp}>Открыть чат</button>
                </li>
                <li>
                  <span>Вернуть готовую картинку (Ctrl+V, файл или галерея)</span>
                  <div className="cs-row">
                    <button className={pasteFor === j.id ? 'primary' : ''} onClick={() => setPasteFor(j.id)}>
                      {pasteFor === j.id ? 'Жду Ctrl+V…' : 'Вставить'}
                    </button>
                    <button
                      className="primary"
                      onClick={() => {
                        setPasteFor(j.id);
                        fileInput.current?.click();
                      }}
                    >
                      Выбрать из галереи
                    </button>
                  </div>
                </li>
              </ol>
            </div>
          ))}
          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            hidden
            onChange={e => {
              const f = e.target.files?.[0];
              if (f && pasteFor) void attach(pasteFor, f);
              e.target.value = '';
            }}
          />
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
                  <button
                    type="button"
                    className={'cs-heart cs-heart-big' + (a.metadata.favorite ? ' on' : '')}
                    aria-label="Избранное"
                    title="Избранное"
                    onClick={() => void favorite(aid, !a.metadata.favorite)}
                  >
                    {a.metadata.favorite ? '♥' : '♡'}
                  </button>
                  <div className="cs-cap">
                    <div>
                      <b>{LABELS[item.model] || item.model}</b>
                      <small>{item.status}</small>
                    </div>
                    <div className="cs-row">
                      {item.kind === 'image' && <button onClick={() => setAnimate(aid)}>Оживить</button>}
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
                      <button onClick={() => favorite(aid, !a.metadata.favorite)} title="Избранное">
                        {a.metadata.favorite ? '♥' : '♡'}
                      </button>
                      <button onClick={() => toggleRef(aid)} title="Использовать как референс">
                        {refs.includes(aid) ? '✓ реф.' : '+ реф.'}
                      </button>
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

        {codexJob && (
          <div className={'cs-codex-status st-' + codexJob.status} role="status">
            <b>Codex:</b>{' '}
            {(
              {
                queued: 'в очереди',
                preparing: 'готовит промпт',
                generating: 'генерирует',
                completed: 'готово',
                failed: 'ошибка',
                cancelled: 'отменено',
              } as Record<string, string>
            )[codexJob.status] || codexJob.status}
            {codexJob.message ? ` · ${codexJob.message}` : ''}
            {codexJob.status === 'queued' && (
              <button
                onClick={() => {
                  void apiFetch(`/api/chatgpt/jobs/${codexJob.id}/cancel`, {method: 'POST'})
                    .then(() => setCodexJob(null))
                    .catch(e => setError(String(e)));
                }}
              >
                Отменить
              </button>
            )}
            {['completed', 'failed', 'cancelled'].includes(codexJob.status) && (
              <button onClick={() => setCodexJob(null)}>Скрыть</button>
            )}
          </div>
        )}
        <div className="cs-prompt">
          <textarea
            rows={3}
            value={prompt}
            placeholder="Опиши кадр: кто, где, свет, ракурс…"
            onChange={e => setPrompt(e.target.value)}
          />
          <div className="cs-row">
            <span className="muted">
              {refs.length} реф. · {total} {total === 1 ? 'модель' : 'моделей'}
            </span>
            <span className="cs-spacer" />
            <button
              disabled={!projectId}
              title="Добавить в промпт визуальные правила серии, локации и героев этого кадра"
              onClick={() => void addVisualRules()}
            >
              ＋ Визуальные правила
            </button>
            <button
              disabled={!projectId}
              title="Добавить в промпт блок композиции: доминанта, баланс или напряжение, противовес из плана кадра"
              onClick={() => void addComposition()}
            >
              ＋ Композиция
            </button>
            <CinemaInfo topic="composition" />
            <CinemaInfo topic="lens" />
            <button disabled={!projectId} onClick={() => void external()}>
              Скопировать для ChatGPT
            </button>
            <button className="cs-send-codex" disabled={!projectId} onClick={() => void toCodex()}>
              Отправить в Codex
            </button>
            <button className="cs-send-chat" disabled={!projectId} onClick={() => void external(true)}>
              Отправить в ChatGPT
            </button>
            <button className="primary" disabled={busy || !projectId} onClick={start}>
              {busy ? 'Готовлю…' : 'Сгенерировать'}
            </button>
          </div>
        </div>
      </div>

      <aside className="cs-models">
        <div className="cs-head">
          <b>Модели</b>
        </div>
        {models.map(modelCard)}
        <div className="cs-note">
          Перед отправкой покажу точную цену и попрошу подтверждение. Ручная попытка в ChatGPT стоит $0 по
          API.
        </div>
      </aside>

      {view && (
        <Lightbox
          items={view.items}
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
