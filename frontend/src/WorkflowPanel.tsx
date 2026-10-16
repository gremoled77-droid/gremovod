import {useMemo, useRef, useState, type CSSProperties} from 'react';
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
import {useSharedActivity} from './ActivityContext';
import {buildSteps, canConnect, type NodeKind, type Step} from './workflowPlan';

type Graph = {nodes: Node[]; edges: Edge[]};
type Lib = {id: string; url: string; thumbnail_url: string | null; provider_reference_url?: string | null};

const KINDS: {kind: NodeKind; label: string; enabled: boolean; hint: string; color: string}[] = [
  {kind: 'text', label: 'Текст', enabled: true, hint: 'Промпт для узла «Изображение»', color: '#5ec4b6'},
  {kind: 'reference', label: 'Референс', enabled: true, hint: 'Картинка из библиотеки', color: '#6ea8fe'},
  {kind: 'image', label: 'Изображение', enabled: true, hint: 'Генерация моделью', color: '#6ea8fe'},
  {kind: 'video', label: 'Видео', enabled: false, hint: 'Появится на этапе видео', color: '#b18cff'},
  {kind: 'audio', label: 'Аудио', enabled: false, hint: 'Появится на этапе видео', color: '#f2b134'},
];
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
  'seedream-5-lite': 'Seedream 5 Fast',
  'seedream-5-pro': 'Seedream 5 Pro',
  'gpt-image-2': 'GPT Image 2.0',
  'gpt-image-2.5': 'GPT Image 2.5',
  'nano-banana-2.1': 'Nano Banana 2.1',
  'qwen-image-2.1': 'Qwen Image 2.1',
};

/** Колонка по типу (вход слева, результат справа); новые узлы встают под уже стоящими в колонке. */
const COLUMN_X: Record<NodeKind, number> = {text: 40, reference: 40, image: 380, video: 720, audio: 380};
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
  run: (ids: string[]) => void;
};
let ctxRef: Ctx | null = null;

function Block({id, data, selected}: {id: string; data: Record<string, any>; selected?: boolean}) {
  const ctx = ctxRef!;
  const kind = String(data.kind) as NodeKind;
  const color = KIND_COLOR[kind] || '#8b8f99';
  const lib = ctx.library.find(a => a.id === data.asset_id);
  const out = ctx.results[id] ? ctx.library.find(a => a.id === ctx.results[id]) : undefined;
  const state = ctx.status[id] || (out ? 'done' : '');
  const accepts = kind === 'image' || kind === 'video';
  const emits = kind === 'text' || kind === 'reference' || kind === 'image';
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
        {kind === 'reference' && (
          <>
            <select
              className="nodrag"
              value={data.asset_id || ''}
              onChange={e => ctx.patch(id, {asset_id: e.target.value})}
            >
              <option value="">Выбери картинку</option>
              {ctx.library.map(a => (
                <option key={a.id} value={a.id}>
                  {a.id.slice(0, 8)}
                </option>
              ))}
            </select>
            {lib ? (
              <img className="wf-thumb" src={lib.thumbnail_url || lib.url} alt="" />
            ) : (
              <div className="wf-empty">нет картинки</div>
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
        {(kind === 'video' || kind === 'audio') && <small>Будет добавлено на этапе видео</small>}
      </div>
      {kind === 'image' && (
        <footer className="wf-node-foot">
          <span className={'wf-chip ' + (state ? 'st-' + state : '')}>
            {STATUS_LABEL[state] || state || 'не запускался'}
          </span>
          <button className="nodrag wf-run" onClick={() => ctx.run([id])}>
            {out ? '↻ Ещё раз' : '▶ Запустить'}
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
    estimates: Record<string, number>;
    total: number;
  } | null>(null);
  const [limit, setLimit] = useState('');
  const [approved, setApproved] = useState(false);
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
    const plan = buildSteps(nodes, edges, results);
    const steps = plan.steps.filter(s => !onlyIds || onlyIds.includes(s.nodeId));
    const problems = plan.problems.filter(
      p => !onlyIds || steps.some(s => p.includes(String(nodes.find(n => n.id === s.nodeId)?.data.title)))
    );
    if (problems.length) return setError(problems.join(' · '));
    if (!steps.length) return setError('Нет узлов «Изображение» для запуска');
    try {
      const estimates: Record<string, number> = {};
      for (const s of steps) {
        const urls = s.waitFor.length ? [] : await Promise.all(s.refAssetIds.map(cloudUrl));
        const placeholders = s.waitFor.map((_, i) => `https://example.invalid/pending-${i}.png`);
        estimates[s.nodeId] = (await estimate(s, [...urls, ...placeholders])).estimated_usd;
      }
      setReview({steps, estimates, total: Object.values(estimates).reduce((a, b) => a + b, 0)});
      setLimit('');
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
      const pending = [...review.steps];
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
      setNotice(`Запущено шагов: ${review.steps.length}. Потрачено по оценке: $${spent.toFixed(3)}`);
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

  ctxRef = {patch, remove, results, status, library, run: ids => void prepare(ids)};

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
          data: {kind, title: label},
        },
      ],
    }));

  return (
    <section className="wf">
      <aside className="wf-console">
        <div className="wf-console-head">
          <h2>Воркфлоу</h2>
          <p>Собери цепочку: текст и референсы подаются в узел «Изображение».</p>
        </div>
        <div className="wf-console-title">Создать узел</div>
        {KINDS.map(k => (
          <button
            key={k.kind}
            className="wf-add"
            disabled={!k.enabled}
            title={k.hint}
            style={{'--kc': k.color} as CSSProperties}
            onClick={() => add(k.kind, k.label)}
          >
            <i className="wf-dot" />
            <span>
              <b>{k.label}</b>
              <small>{k.enabled ? k.hint : 'скоро'}</small>
            </span>
            <em>＋</em>
          </button>
        ))}
        <div className="wf-console-title">Как это работает</div>
        <ol className="wf-help">
          <li>Добавь «Текст» и, если нужно, «Референс».</li>
          <li>Добавь «Изображение» и выбери модель.</li>
          <li>Протяни связь от кружка справа к кружку слева.</li>
          <li>«Запустить» — сначала оценка цены и подтверждение.</li>
        </ol>
        <div className="wf-stat">
          узлов: <b>{nodes.length}</b> · связей: <b>{edges.length}</b>
        </div>
      </aside>
      <div className="wf-stage">
        <div className="wf-bar">
          <div className="wf-legend">
            {KINDS.filter(k => k.enabled).map(k => (
              <span key={k.kind} style={{'--kc': k.color} as CSSProperties}>
                <i className="wf-dot" />
                {k.label}
              </span>
            ))}
          </div>
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
              <span>Добавь первый узел слева — например «Текст» с промптом.</span>
            </div>
          )}
        </div>
      </div>
      {review && (
        <div className="modal-backdrop">
          <section className="panel generation-review" role="dialog" aria-modal="true">
            <h2>Запустить всё: подтверждение</h2>
            <ol>
              {review.steps.map(s => (
                <li key={s.nodeId}>
                  {IMAGE_MODELS[s.model] || s.model} · референсов: {s.refAssetIds.length + s.waitFor.length}
                  {s.waitFor.length ? ' (после предыдущего шага)' : ''} · $
                  {review.estimates[s.nodeId].toFixed(3)}
                </li>
              ))}
            </ol>
            <p>
              Итого по оценке: <b>${review.total.toFixed(3)}</b>
            </p>
            <label>
              Мой лимит на весь запуск, USD
              <input
                type="number"
                min={review.total}
                step="0.001"
                value={limit}
                onChange={e => setLimit(e.target.value)}
              />
            </label>
            <label className="inline-checkbox">
              <input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)} />{' '}
              Подтверждаю платный запуск в пределах лимита
            </label>
            <div className="chips">
              <button
                className="primary"
                disabled={!approved || !(Number(limit) >= review.total)}
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
  );
}
