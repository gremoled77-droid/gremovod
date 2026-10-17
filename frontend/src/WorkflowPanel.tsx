import {createContext, useContext, useEffect, useMemo, useRef, useState, type CSSProperties} from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  Handle,
  Position,
  type Node,
  type Edge,
} from '@xyflow/react';
import {apiFetch} from './api';
import LimitPicker from './LimitPicker';
import {initialLimit, limitAllowed} from './spendLimit';
import {useSharedActivity} from './ActivityContext';
import {
  DEFAULT_LLM_SYSTEM,
  buildLlmSteps,
  buildSteps,
  canConnect,
  llmInput,
  type LlmStep,
  type NodeKind,
  type Step,
  VIDEO_MODELS,
} from './workflowPlan';
import {useNodePrices} from './workflowPrices';
import {LLM_MAX_TOKENS, LLM_MODELS, llmEstimate} from './llmPricing';
import {missingAssetIds} from './workflowLibrary';

type Graph = {nodes: Node[]; edges: Edge[]};
type Lib = {
  id: string;
  url: string;
  thumbnail_url: string | null;
  provider_reference_url?: string | null;
  metadata?: {kind?: string; original_name?: string; excerpt?: string; size?: number};
};
const libKind = (a: Lib) => a.metadata?.kind || 'image';
const ACCEPT: Record<string, string> = {
  image: '.png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp',
  audio: '.mp3,.wav,.m4a,audio/mpeg,audio/wav,audio/mp4',
  file: '.txt,.md,.srt,.json,.pdf',
};

const KINDS: {kind: NodeKind; label: string; enabled: boolean; hint: string; color: string}[] = [
  {kind: 'video', label: 'Видео', enabled: true, hint: 'MiniMax H3, Seedance 2.5', color: '#b18cff'},
  {kind: 'image', label: 'Image', enabled: true, hint: '6 моделей PiAPI', color: '#6ea8fe'},
  {kind: 'audio', label: 'Аудио', enabled: true, hint: 'Аудио-референс', color: '#f2b134'},
  {kind: 'text', label: 'Текст', enabled: true, hint: 'Промпт, реплика', color: '#5ec4b6'},
  {kind: 'llm', label: 'LLM', enabled: true, hint: 'ИИ пишет или улучшает текст', color: '#5ec4b6'},
  {kind: 'reference', label: 'Референс', enabled: true, hint: 'Картинка из библиотеки', color: '#6ea8fe'},
  {kind: 'file', label: 'Файл', enabled: true, hint: 'Документ: txt, md, srt, json, pdf', color: '#9aa4b2'},
];
const MENU_KINDS: NodeKind[] = ['video', 'image', 'audio', 'text', 'llm'];
const KIND_COLOR = Object.fromEntries(KINDS.map(k => [k.kind, k.color])) as Record<string, string>;
const STATUS_LABEL: Record<string, string> = {
  done: 'готово',
  running: 'генерируется',
  queued: 'в очереди',
  pending: 'в очереди',
  failed: 'ошибка',
  error: 'ошибка',
};
const IMAGE_MODELS: Record<string, string> = {
  'seedream-5-lite': 'Seedream 5 Lite',
  'seedream-5-pro': 'Seedream 5 Pro',
  'gpt-image-2': 'GPT Image 2.0',
  'gpt-image-2.5': 'GPT Image 2.5',
  'nano-banana-2.1': 'Nano Banana 2.1',
  'qwen-image-2.1': 'Qwen Image 2.1',
};

/** Колонка по типу (вход слева, результат справа); новые узлы встают под уже стоящими в колонке. */
const COLUMN_X: Record<NodeKind, number> = {
  text: 40,
  reference: 40,
  file: 40,
  llm: 330,
  image: 620,
  video: 900,
  audio: 40,
};
function slot(kind: NodeKind, nodes: Node[]) {
  const x = COLUMN_X[kind];
  const below = nodes.filter(n => Math.abs(n.position.x - x) < 160).map(n => n.position.y);
  return {x, y: below.length ? Math.max(...below) + 300 : 40};
}
async function json(r: Response) {
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw Error(typeof d.detail === 'string' ? d.detail : 'Запрос не выполнен');
  return d;
}

type Ctx = {
  patch: (id: string, p: Record<string, unknown>) => void;
  remove: (id: string) => void;
  results: Record<string, string>;
  status: Record<string, string>;
  library: Lib[];
  prices: Record<string, number | null>;
  run: (ids: string[]) => void;
  upload: (accept: string, done: (asset: Lib) => void) => void;
};
// Контекст, а не глобальная переменная: узлы перерисовываются, когда меняется библиотека или результаты.
/** Цена с нужной точностью: копейки LLM видны, крупные суммы без лишних знаков. */
const formatPrice = (usd: number) =>
  usd < 0.01 ? usd.toFixed(4) : usd < 1 ? usd.toFixed(3) : usd.toFixed(2);

const WfCtx = createContext<Ctx | null>(null);

function Block({id, data, selected}: {id: string; data: Record<string, any>; selected?: boolean}) {
  const ctx = useContext(WfCtx)!;
  const kind = String(data.kind) as NodeKind;
  const color = KIND_COLOR[kind] || '#8b8f99';
  const lib = ctx.library.find(a => a.id === data.asset_id);
  const out = ctx.results[id] ? ctx.library.find(a => a.id === ctx.results[id]) : undefined;
  const state = ctx.status[id] || (out || (kind === 'llm' && data.output) ? 'done' : '');
  const accepts = kind === 'image' || kind === 'video' || kind === 'llm';
  const emits = ['text', 'reference', 'image', 'llm', 'audio', 'file'].includes(kind);
  const images = ctx.library.filter(a => libKind(a) === 'image');
  const audios = ctx.library.filter(a => libKind(a) === 'audio');
  return (
    <div
      className={'wf-node wf-' + kind + (selected ? ' sel' : '') + (state ? ' st-' + state : '')}
      style={{'--kc': color} as CSSProperties}
    >
      {accepts && <Handle type="target" position={Position.Left} className="wf-handle" />}
      <header className="wf-node-head">
        <i className="wf-dot" />
        <b>{data.title}</b>
        {kind === 'image' && data.model && <span className="wf-model">{IMAGE_MODELS[data.model]}</span>}
        {kind === 'video' && data.model && (
          <span className="wf-model">{VIDEO_MODELS[data.model]?.label || data.model}</span>
        )}
        {kind === 'llm' && data.model && (
          <span className="wf-model">{LLM_MODELS[data.model]?.label || data.model}</span>
        )}
        <button className="wf-node-x nodrag" title="Убрать узел из схемы" onClick={() => ctx.remove(id)}>
          ×
        </button>
      </header>
      <div className="wf-node-body">
        {kind === 'text' && (
          <>
            <textarea
              className="nodrag"
              rows={4}
              placeholder="Опиши кадр: кто, где, что делает, свет, камера…"
              value={data.text || ''}
              onChange={e => ctx.patch(id, {text: e.target.value})}
            />
            <small>{(data.text || '').length} симв.</small>
          </>
        )}
        {kind === 'llm' && (
          <>
            <select
              className="nodrag"
              value={data.model || ''}
              onChange={e => ctx.patch(id, {model: e.target.value})}
            >
              <option value="">Модель…</option>
              {Object.entries(LLM_MODELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v.label}
                </option>
              ))}
            </select>
            <textarea
              className="nodrag"
              rows={3}
              placeholder={DEFAULT_LLM_SYSTEM}
              title="Инструкция модели"
              value={data.system || ''}
              onChange={e => ctx.patch(id, {system: e.target.value})}
            />
            <textarea
              className="nodrag"
              rows={4}
              placeholder="Ответ появится здесь; его можно поправить руками"
              value={data.output || ''}
              onChange={e => ctx.patch(id, {output: e.target.value})}
            />
          </>
        )}
        {kind === 'reference' && (
          <>
            <select
              className="nodrag"
              value={data.asset_id || ''}
              onChange={e => ctx.patch(id, {asset_id: e.target.value})}
            >
              <option value="">Выбери картинку</option>
              {images.map(a => (
                <option key={a.id} value={a.id}>
                  {a.metadata?.original_name || a.id.slice(0, 8)}
                </option>
              ))}
            </select>
            {lib ? (
              <img className="wf-thumb" src={lib.thumbnail_url || lib.url} alt="" />
            ) : (
              <div className="wf-empty">нет картинки</div>
            )}
            <button
              className="nodrag wf-up"
              onClick={() =>
                ctx.upload(ACCEPT.image, a =>
                  ctx.patch(id, {asset_id: a.id, title: a.metadata?.original_name || data.title})
                )
              }
            >
              ＋ Загрузить картинку
            </button>
          </>
        )}
        {kind === 'audio' && (
          <>
            <select
              className="nodrag"
              value={data.asset_id || ''}
              onChange={e => ctx.patch(id, {asset_id: e.target.value})}
            >
              <option value="">Выбери аудио</option>
              {audios.map(a => (
                <option key={a.id} value={a.id}>
                  {a.metadata?.original_name || a.id.slice(0, 8)}
                </option>
              ))}
            </select>
            {lib ? (
              <audio className="nodrag wf-audio" controls preload="none" src={lib.url} />
            ) : (
              <div className="wf-empty">нет аудио</div>
            )}
            <button
              className="nodrag wf-up"
              onClick={() =>
                ctx.upload(ACCEPT.audio, a =>
                  ctx.patch(id, {asset_id: a.id, title: a.metadata?.original_name || data.title})
                )
              }
            >
              ＋ Загрузить аудио
            </button>
            <small>Пока хранится как референс: модели студии звук на вход не принимают.</small>
          </>
        )}
        {kind === 'file' && (
          <>
            <div className="wf-file">
              <b>{data.name || 'файл не выбран'}</b>
              <small>
                {data.excerpt
                  ? `${String(data.excerpt).length} симв. текста уйдут в LLM, если подключить`
                  : 'текст не извлечён (PDF хранится как справочный файл)'}
              </small>
            </div>
            <button
              className="nodrag wf-up"
              onClick={() =>
                ctx.upload(ACCEPT.file, a =>
                  ctx.patch(id, {
                    asset_id: a.id,
                    name: a.metadata?.original_name,
                    excerpt: a.metadata?.excerpt || '',
                    title: a.metadata?.original_name || data.title,
                  })
                )
              }
            >
              ＋ Загрузить файл
            </button>
            {lib && (
              <a className="nodrag" href={lib.url} target="_blank" rel="noreferrer">
                Открыть ↗
              </a>
            )}
          </>
        )}
        {kind === 'image' && (
          <>
            <select
              className="nodrag"
              value={data.model || ''}
              onChange={e => ctx.patch(id, {model: e.target.value})}
            >
              <option value="">Модель…</option>
              {Object.entries(IMAGE_MODELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            {out ? (
              <img className="wf-thumb" src={out.thumbnail_url || out.url} alt="" />
            ) : (
              <div className="wf-empty">результат появится здесь</div>
            )}
          </>
        )}
        {kind === 'video' && (
          <>
            <select
              className="nodrag"
              value={data.model || ''}
              onChange={e => ctx.patch(id, {model: e.target.value, options: {}})}
            >
              <option value="">Модель…</option>
              {Object.entries(VIDEO_MODELS).map(([k, v]) => (
                <option key={k} value={k}>
                  {v.label}
                </option>
              ))}
            </select>
            {VIDEO_MODELS[data.model] && (
              <div className="wf-opts nodrag">
                <select
                  title="Разрешение"
                  value={data.options?.resolution || VIDEO_MODELS[data.model].resolutions[0]}
                  onChange={e => ctx.patch(id, {options: {...data.options, resolution: e.target.value}})}
                >
                  {VIDEO_MODELS[data.model].resolutions.map(v => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
                <select
                  title="Формат"
                  value={data.options?.aspect_ratio || VIDEO_MODELS[data.model].aspects[0]}
                  onChange={e => ctx.patch(id, {options: {...data.options, aspect_ratio: e.target.value}})}
                >
                  {VIDEO_MODELS[data.model].aspects.map(v => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
                <input
                  type="number"
                  title="Секунд"
                  min={VIDEO_MODELS[data.model].durationMin}
                  max={VIDEO_MODELS[data.model].durationMax}
                  value={data.options?.duration || VIDEO_MODELS[data.model].durationMin}
                  onChange={e =>
                    ctx.patch(id, {options: {...data.options, duration: Number(e.target.value)}})
                  }
                />
              </div>
            )}
            {out ? (
              <video className="wf-thumb nodrag" controls preload="metadata" src={out.url} />
            ) : (
              <div className="wf-empty">ролик появится здесь</div>
            )}
          </>
        )}
      </div>
      {(kind === 'image' || kind === 'llm' || kind === 'video') && (
        <footer className="wf-node-foot">
          <span className={'wf-chip ' + (state ? 'st-' + state : '')}>
            {STATUS_LABEL[state] || state || 'не запускался'}
          </span>
          {ctx.prices[id] != null && (
            <span className="wf-price" title="Оценка цены запуска узла">
              {kind === 'llm' ? 'до ' : ''}${formatPrice(ctx.prices[id] as number)}
            </span>
          )}
          <button className="nodrag wf-run" onClick={() => ctx.run([id])}>
            {kind === 'llm'
              ? data.output
                ? '↻ Ещё раз'
                : '▶ Сгенерировать'
              : out
                ? '↻ Ещё раз'
                : '▶ Запустить'}
          </button>
        </footer>
      )}
      {emits && <Handle type="source" position={Position.Right} className="wf-handle" />}
    </div>
  );
}
const types = {studio: Block};

export default function WorkflowPanel({
  projectId,
  nodes,
  edges,
  onChange,
}: {
  projectId: string;
  nodes: Node[];
  edges: Edge[];
  onChange: (update: (graph: Graph) => Graph) => void;
}) {
  const {items, reset} = useSharedActivity();
  const [library, setLibrary] = useState<Lib[]>([]);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const [review, setReview] = useState<{
    steps: Step[];
    llmSteps: LlmStep[];
    estimates: Record<string, number>;
    total: number;
  } | null>(null);
  const [limit, setLimit] = useState('');
  const [plusOpen, setPlusOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [approved, setApproved] = useState(false);
  const [highOk, setHighOk] = useState(false);
  const [llmState, setLlmState] = useState<Record<string, string>>({});
  const graph = useRef({nodes, edges});
  graph.current = {nodes, edges};
  const [running, setRunning] = useState(false);
  const loaded = useRef('');

  if (projectId && loaded.current !== projectId) {
    loaded.current = projectId;
    void apiFetch('/api/library?project_id=' + encodeURIComponent(projectId))
      .then(json)
      .then(setLibrary)
      .catch(e => setError(String(e)));
  }
  const refreshLibrary = () =>
    apiFetch('/api/library?project_id=' + encodeURIComponent(projectId))
      .then(json)
      .then(setLibrary);

  const {results, status} = useMemo(() => {
    const results: Record<string, string> = {};
    const status: Record<string, string> = {};
    for (const it of [...items].reverse()) {
      if (!it.node_id) continue;
      status[it.node_id] = it.status;
      if (it.status === 'done' && it.asset_ids[0]) results[it.node_id] = it.asset_ids[0];
    }
    return {results, status};
  }, [items]);

  // Сервер сам сохраняет готовый результат в библиотеку (монитор раз в 30 с), но загруженный список библиотеки
  // устаревает: пока вкладка открыта, подтягиваем новые ассеты, чтобы клип появился в узле без перезагрузки.
  const missing = missingAssetIds(results, library).join(',');
  useEffect(() => {
    if (!missing || !projectId) return;
    let tries = 0;
    const tick = () => {
      tries++;
      void refreshLibrary().catch(() => undefined);
    };
    tick();
    const timer = window.setInterval(() => (tries >= 6 ? window.clearInterval(timer) : tick()), 4000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [missing, projectId]);

  const live = useRef({results, status});
  live.current = {results, status};

  const patch = (id: string, p: Record<string, unknown>) =>
    onChange(g => ({...g, nodes: g.nodes.map(n => (n.id === id ? {...n, data: {...n.data, ...p}} : n))}));

  const cloudUrl = async (assetId: string) => {
    const known = library.find(a => a.id === assetId)?.provider_reference_url;
    if (known) return known;
    const r = await json(
      await apiFetch(`/api/library/${assetId}/upload-reference`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({approved: true, provider: 'tempfile'}),
      })
    );
    return r.url as string;
  };

  const estimate = async (step: Step, urls: string[]) =>
    json(
      await apiFetch('/api/model-jobs/estimate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          project_id: projectId,
          model_id: step.model,
          prompt: step.prompt,
          options: step.options,
          reference_urls: urls,
          node_id: step.nodeId,
        }),
      })
    );

  /** Подготовка запуска: оценка по каждому шагу, показ итога и подтверждение. */
  const prepare = async (onlyIds?: string[]) => {
    setError('');
    const outputs: Record<string, string> = {};
    for (const n of nodes) if (n.data.kind === 'llm' && n.data.output) outputs[n.id] = String(n.data.output);
    const llmPlan = buildLlmSteps(nodes, edges);
    const llmSteps = llmPlan.steps.filter(s => !onlyIds || onlyIds.includes(s.nodeId));
    const plan = buildSteps(nodes, edges, results, {llm: outputs, pendingLlm: llmSteps.map(s => s.nodeId)});
    const steps = plan.steps.filter(s => !onlyIds || onlyIds.includes(s.nodeId));
    const titleOf = (id: string) => String(nodes.find(n => n.id === id)?.data.title);
    const selected = [...steps.map(s => s.nodeId), ...llmSteps.map(s => s.nodeId)];
    const problems = [...plan.problems, ...llmPlan.problems].filter(
      p => !onlyIds || selected.some(id => p.includes(titleOf(id)))
    );
    if (problems.length) return setError(problems.join(' · '));
    if (!steps.length && !llmSteps.length)
      return setError('Нет узлов «Image», «Видео» или «LLM» для запуска');
    try {
      const estimates: Record<string, number> = {};
      for (const s of llmSteps) {
        estimates[s.nodeId] = llmEstimate(s.model, llmInput(s, nodes, outputs).length + 600);
      }
      for (const s of steps) {
        const urls = s.waitFor.length ? [] : await Promise.all(s.refAssetIds.map(cloudUrl));
        const placeholders = s.waitFor.map((_, i) => `https://example.invalid/pending-${i}.png`);
        estimates[s.nodeId] = (await estimate(s, [...urls, ...placeholders])).estimated_usd;
      }
      const total = Object.values(estimates).reduce((a, b) => a + b, 0);
      setReview({steps, llmSteps, estimates, total});
      setLimit(initialLimit(total));
      setHighOk(false);
      setApproved(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const wait = (nodeIds: string[]) =>
    new Promise<void>(resolve => {
      const started = Date.now();
      const tick = () => {
        const done = nodeIds.every(
          id => live.current.status[id] === 'done' || Date.now() - started > 10 * 60 * 1000
        );
        if (done) resolve();
        else window.setTimeout(tick, 2000);
      };
      tick();
    });

  const execute = async () => {
    if (!review) return;
    const budget = Number(limit);
    let spent = 0;
    setRunning(true);
    setReview(null);
    try {
      const outs: Record<string, string> = {};
      for (const n of graph.current.nodes)
        if (n.data.kind === 'llm' && n.data.output) outs[n.id] = String(n.data.output);
      for (const step of review.llmSteps) {
        const estimated = review.estimates[step.nodeId] || 0;
        if (spent + estimated > budget) throw Error('Лимит запуска исчерпан, остальные шаги не отправлены');
        const input = llmInput(step, graph.current.nodes, outs);
        if (!input) throw Error('У LLM-узла нет входного текста');
        setLlmState(v => ({...v, [step.nodeId]: 'running'}));
        let lastCost: number | undefined;
        try {
          const messages = [
            {role: 'system', content: step.system},
            {role: 'user', content: input},
          ];
          // Сервер даёт подписанную верхнюю оценку; без неё платный LLM-вызов не выполняется.
          const quote = await json(
            await apiFetch('/api/llm/estimate', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({
                project_id: projectId,
                model: step.model,
                messages,
                max_tokens: LLM_MAX_TOKENS,
              }),
            })
          );
          if (spent + quote.estimated_usd > budget)
            throw Error('Лимит запуска исчерпан, остальные шаги не отправлены');
          const answer = await json(
            await apiFetch('/api/llm/chat', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({
                provider: 'piapi',
                project_id: projectId,
                model: step.model,
                max_tokens: LLM_MAX_TOKENS,
                messages,
                approved: true,
                quote_token: quote.quote_token,
                max_cost_usd: quote.estimated_usd,
                request_id: crypto.randomUUID(),
              }),
            })
          );
          const text = String(answer.choices?.[0]?.message?.content || '').trim();
          if (!text) throw Error('LLM вернул пустой ответ');
          lastCost = Number(answer.cost_usd);
          outs[step.nodeId] = text;
          patch(step.nodeId, {output: text});
          setLlmState(v => ({...v, [step.nodeId]: 'done'}));
        } catch (e) {
          setLlmState(v => ({...v, [step.nodeId]: 'failed'}));
          throw e;
        }
        spent += lastCost !== undefined && Number.isFinite(lastCost) ? lastCost : estimated;
      }
      const fresh = buildSteps(graph.current.nodes, graph.current.edges, live.current.results, {llm: outs});
      const pending = review.steps.map(s => fresh.steps.find(f => f.nodeId === s.nodeId) ?? s);
      if (pending.some(s => !s.prompt)) throw Error('У узла «Image» или «Видео» пустой промпт после LLM');
      const finished = new Set<string>();
      let guard = 0;
      while (pending.length && guard++ < 50) {
        const index = pending.findIndex(s =>
          s.waitFor.every(id => finished.has(id) || live.current.results[id])
        );
        if (index < 0) {
          await wait(pending.flatMap(s => s.waitFor).filter(id => !finished.has(id)));
          continue;
        }
        const step = pending.splice(index, 1)[0];
        const refs = [...step.refAssetIds];
        for (const id of step.waitFor) if (live.current.results[id]) refs.push(live.current.results[id]);
        const urls = await Promise.all(refs.map(cloudUrl));
        const est = await estimate(step, urls);
        if (spent + est.estimated_usd > budget)
          throw Error('Лимит запуска исчерпан, остальные шаги не отправлены');
        await json(
          await apiFetch('/api/model-jobs', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              project_id: projectId,
              model_id: step.model,
              prompt: step.prompt,
              options: step.options,
              reference_urls: urls,
              node_id: step.nodeId,
              quote_token: est.quote_token,
              approved: true,
              max_cost_usd: est.estimated_usd,
              request_id: crypto.randomUUID(),
            }),
          })
        );
        spent += est.estimated_usd;
        finished.add(step.nodeId);
        reset();
        if (pending.some(s => s.waitFor.includes(step.nodeId))) await wait([step.nodeId]);
      }
      setNotice(
        `Запущено шагов: ${review.steps.length + review.llmSteps.length}. Потрачено по оценке: $${spent.toFixed(3)}`
      );
      await refreshLibrary();
    } catch (e) {
      setError((e instanceof Error ? e.message : String(e)) + ' Проверь очередь перед повторным запуском.');
    } finally {
      setRunning(false);
    }
  };

  const remove = (id: string) =>
    onChange(g => ({
      ...g,
      nodes: g.nodes.filter(n => n.id !== id),
      edges: g.edges.filter(e => e.source !== id && e.target !== id),
    }));

  const fileInput = useRef<HTMLInputElement>(null);
  const pending = useRef<{done: (asset: Lib) => void} | null>(null);
  const importFile = async (file: File): Promise<Lib> => {
    const form = new FormData();
    form.append('project_id', projectId);
    form.append('file', file);
    return json(await apiFetch('/api/library/import-reference', {method: 'POST', body: form}));
  };
  /** Выбор файла для конкретного узла: загрузка, затем колбэк с готовым ассетом. */
  const upload = (accept: string, done: (asset: Lib) => void) => {
    if (!fileInput.current || !projectId) return;
    pending.current = {done};
    fileInput.current.accept = accept;
    fileInput.current.multiple = false;
    fileInput.current.click();
  };
  /** Кнопка «＋» сверху справа: любые файлы, для каждого появляется свой узел. */
  const addUploaded = (asset: Lib, fallbackTitle: string) => {
    const kind = libKind(asset);
    const title = asset.metadata?.original_name || fallbackTitle;
    const node: Record<string, unknown> =
      kind === 'audio'
        ? {kind: 'audio', title, asset_id: asset.id}
        : kind === 'document'
          ? {kind: 'file', title, asset_id: asset.id, name: title, excerpt: asset.metadata?.excerpt || ''}
          : {kind: 'reference', title, asset_id: asset.id};
    onChange(g => ({
      ...g,
      nodes: [
        ...g.nodes,
        {id: crypto.randomUUID(), type: 'studio', position: slot(node.kind as NodeKind, g.nodes), data: node},
      ],
    }));
  };
  const onFiles = async (files: File[]) => {
    setError('');
    let added = 0;
    for (const file of files) {
      try {
        const asset = await importFile(file);
        const target = pending.current;
        if (target) target.done(asset);
        else addUploaded(asset, file.name);
        added++;
      } catch (e) {
        setError(`${file.name}: ${e instanceof Error ? e.message : String(e)}`);
        break;
      }
    }
    pending.current = null;
    if (added) {
      setNotice(`Загружено файлов: ${added}`);
      await refreshLibrary();
    }
  };
  const pickMany = (accept: string) => {
    if (!fileInput.current || !projectId) return;
    pending.current = null;
    fileInput.current.accept = accept;
    fileInput.current.multiple = true;
    fileInput.current.click();
    setPlusOpen(false);
  };

  const {prices, total: graphTotal, pending: pricesPending} = useNodePrices(projectId, nodes, edges, results);
  const ctxValue: Ctx = {
    patch,
    remove,
    results,
    status: {...status, ...llmState},
    library,
    prices,
    run: ids => void prepare(ids),
    upload,
  };

  // Цвет связи — по типу узла-источника (только для показа, в схему не пишется)
  const shownEdges = useMemo(
    () =>
      edges.map(e => {
        const kind = String(nodes.find(n => n.id === e.source)?.data?.kind || '');
        return {...e, style: {...e.style, stroke: KIND_COLOR[kind] || '#8b8f99', strokeWidth: 2}};
      }),
    [nodes, edges]
  );

  const add = (kind: NodeKind, label: string) =>
    onChange(g => ({
      ...g,
      nodes: [
        ...g.nodes,
        {
          id: crypto.randomUUID(),
          type: 'studio',
          position: slot(kind, g.nodes),
          data:
            kind === 'llm'
              ? {kind, title: label, model: 'gpt-5.6-luna'}
              : kind === 'video'
                ? {kind, title: label, model: 'minimax-h3'}
                : {kind, title: label},
        },
      ],
    }));

  return (
    <WfCtx.Provider value={ctxValue}>
      <section className="wf">
        <aside className="wf-console">
          <div className="wf-console-head">
            <h2>Воркфлоу</h2>
            <p>Собери цепочку: текст, LLM и референсы подаются в узлы «Image» и «Видео».</p>
          </div>
          <input
            className="wf-search"
            type="search"
            placeholder="Поиск узла…"
            aria-label="Поиск узла"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <div className="wf-console-title">＋ Создать узел</div>
          {MENU_KINDS.map(kind => KINDS.find(k => k.kind === kind)!)
            .filter(
              k =>
                !search.trim() || (k.label + ' ' + k.hint).toLowerCase().includes(search.trim().toLowerCase())
            )
            .map(k => (
              <button
                key={k.kind}
                className="wf-add"
                title={k.hint}
                style={{'--kc': k.color} as CSSProperties}
                onClick={() => add(k.kind, k.label)}
              >
                <i className="wf-dot" />
                <span>
                  <b>{k.label}</b>
                  <small>{k.hint}</small>
                </span>
                <em>＋</em>
              </button>
            ))}
          <div className="wf-console-title">Референсы</div>
          {KINDS.filter(k => k.kind === 'reference' || k.kind === 'file')
            .filter(
              k =>
                !search.trim() || (k.label + ' ' + k.hint).toLowerCase().includes(search.trim().toLowerCase())
            )
            .map(k => (
              <button
                key={k.kind}
                className="wf-add"
                title={k.hint}
                style={{'--kc': k.color} as CSSProperties}
                onClick={() => add(k.kind, k.label)}
              >
                <i className="wf-dot" />
                <span>
                  <b>{k.label}</b>
                  <small>{k.hint}</small>
                </span>
                <em>＋</em>
              </button>
            ))}
          <div className="wf-console-title">Как это работает</div>
          <ol className="wf-help">
            <li>Добавь «Текст» (при желании «LLM») и референсы.</li>
            <li>Добавь «Image» или «Видео», выбери модель.</li>
            <li>Протяни связь от кружка справа к кружку слева.</li>
            <li>«Запустить» — сначала оценка цены и подтверждение.</li>
            <li>Кнопка «＋» сверху справа загружает картинки, аудио и файлы сразу узлами.</li>
          </ol>
          <div className="wf-stat">
            узлов: <b>{nodes.length}</b> · связей: <b>{edges.length}</b>
          </div>
        </aside>
        <div className="wf-stage">
          <div className="wf-bar">
            <div className="wf-legend">
              {KINDS.filter(k => MENU_KINDS.includes(k.kind)).map(k => (
                <span key={k.kind} style={{'--kc': k.color} as CSSProperties}>
                  <i className="wf-dot" />
                  {k.label}
                </span>
              ))}
            </div>
            <div className="wf-plus-wrap">
              <button
                className="wf-plus"
                aria-haspopup="menu"
                aria-expanded={plusOpen}
                title="Загрузить референс: картинка, аудио, файл"
                disabled={!projectId}
                onClick={() => setPlusOpen(v => !v)}
              >
                ＋
              </button>
              {plusOpen && (
                <div className="wf-plus-menu" role="menu">
                  <button role="menuitem" onClick={() => pickMany(ACCEPT.image)}>
                    Картинки-референсы
                  </button>
                  <button role="menuitem" onClick={() => pickMany(ACCEPT.audio)}>
                    Аудио-референсы
                  </button>
                  <button role="menuitem" onClick={() => pickMany(ACCEPT.file)}>
                    Файлы-референсы
                  </button>
                  <button
                    role="menuitem"
                    onClick={() => pickMany([ACCEPT.image, ACCEPT.audio, ACCEPT.file].join(','))}
                  >
                    Всё сразу…
                  </button>
                  <small>Каждый файл появится узлом в схеме.</small>
                </div>
              )}
            </div>
            <input
              ref={fileInput}
              type="file"
              hidden
              onChange={e => {
                const list = Array.from(e.target.files || []);
                e.target.value = '';
                if (list.length) void onFiles(list);
              }}
            />
            <span
              className="wf-total"
              title="Оценка по всем узлам; точная цена и лимит — в окне подтверждения"
            >
              Весь граф: <b>${formatPrice(graphTotal)}</b>
              {pricesPending ? ' …' : ''}
            </span>
            <button className="primary" disabled={running || !projectId} onClick={() => void prepare()}>
              {running ? 'Выполняется…' : '▶ Запустить всё'}
            </button>
          </div>
          {(notice || error) && (
            <div className="wf-banners">
              {notice && (
                <div className="notice" role="status">
                  {notice}
                  <button onClick={() => setNotice('')}>✕</button>
                </div>
              )}
              {error && (
                <div className="alert" role="alert">
                  {error}
                  <button onClick={() => setError('')}>✕</button>
                </div>
              )}
            </div>
          )}
          <div className="wf-canvas">
            <ReactFlow
              nodes={nodes}
              edges={shownEdges}
              colorMode="dark"
              onNodesChange={changes => onChange(g => ({...g, nodes: applyNodeChanges(changes, g.nodes)}))}
              onEdgesChange={changes => onChange(g => ({...g, edges: applyEdgeChanges(changes, g.edges)}))}
              isValidConnection={c =>
                canConnect(
                  nodes.find(n => n.id === c.source),
                  nodes.find(n => n.id === c.target)
                )
              }
              onConnect={c => onChange(g => ({...g, edges: addEdge({...c, animated: true}, g.edges)}))}
              nodeTypes={types}
              fitView
              proOptions={{hideAttribution: true}}
            >
              <Background gap={22} size={1.2} color="#23262e" />
              <Controls showInteractive={false} />
              <MiniMap
                pannable
                zoomable
                maskColor="#0e0f12cc"
                nodeColor={n => KIND_COLOR[String(n.data?.kind)] || '#8b8f99'}
              />
            </ReactFlow>
            {!nodes.length && (
              <div className="wf-hint">
                <b>Схема пуста</b>
                <span>
                  Добавь первый узел слева — например «Текст» с промптом — или нажми «＋» сверху справа и
                  загрузи референсы.
                </span>
              </div>
            )}
          </div>
        </div>
        {review && (
          <div className="modal-backdrop">
            <section className="panel generation-review" role="dialog" aria-modal="true">
              <h2>Запустить всё: подтверждение</h2>
              <ol>
                {review.llmSteps.map(s => (
                  <li key={s.nodeId}>
                    LLM {LLM_MODELS[s.model]?.label || s.model} · текст · до $
                    {review.estimates[s.nodeId].toFixed(4)}
                  </li>
                ))}
                {review.steps.map(s => (
                  <li key={s.nodeId}>
                    {IMAGE_MODELS[s.model] || VIDEO_MODELS[s.model]?.label || s.model} · референсов:{' '}
                    {s.refAssetIds.length + s.waitFor.length}
                    {s.waitFor.length ? ' (после предыдущего шага)' : ''} · $
                    {review.estimates[s.nodeId].toFixed(3)}
                  </li>
                ))}
              </ol>
              <p>
                Итого по оценке: <b>${review.total.toFixed(3)}</b>
              </p>
              <LimitPicker
                total={review.total}
                limit={limit}
                onLimit={setLimit}
                highConfirmed={highOk}
                onHighConfirmed={setHighOk}
              />
              <label className="inline-checkbox">
                <input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)} />{' '}
                Подтверждаю платный запуск в пределах лимита
              </label>
              <div className="chips">
                <button
                  className="primary"
                  disabled={!approved || !limitAllowed(review.total, limit, highOk)}
                  onClick={() => void execute()}
                >
                  Подтвердить и запустить
                </button>
                <button onClick={() => setReview(null)}>Отмена</button>
              </div>
            </section>
          </div>
        )}
      </section>
    </WfCtx.Provider>
  );
}
