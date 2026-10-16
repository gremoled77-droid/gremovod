import {useMemo, useRef, useState} from 'react';
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

const KINDS: {kind: NodeKind; label: string; enabled: boolean; hint: string}[] = [
  {kind: 'text', label: 'Текст', enabled: true, hint: 'Промпт'},
  {kind: 'reference', label: 'Референс', enabled: true, hint: 'Картинка из библиотеки'},
  {kind: 'image', label: 'Изображение', enabled: true, hint: 'Генерация моделью'},
  {kind: 'video', label: 'Видео', enabled: false, hint: 'Появится на этапе видео'},
  {kind: 'audio', label: 'Аудио', enabled: false, hint: 'Появится на этапе видео'},
];
const IMAGE_MODELS: Record<string, string> = {
  'seedream-5-lite': 'Seedream 5 Fast',
  'seedream-5-pro': 'Seedream 5 Pro',
  'gpt-image-2': 'GPT Image 2.0',
  'gpt-image-2.5': 'GPT Image 2.5',
  'nano-banana-2.1': 'Nano Banana 2.1',
  'qwen-image-2.1': 'Qwen Image 2.1',
};

async function json(r: Response) {
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw Error(typeof d.detail === 'string' ? d.detail : 'Запрос не выполнен');
  return d;
}

type Ctx = {
  patch: (id: string, p: Record<string, unknown>) => void;
  results: Record<string, string>;
  status: Record<string, string>;
  library: Lib[];
  run: (ids: string[]) => void;
};
let ctxRef: Ctx | null = null;

function Block({id, data}: {id: string; data: Record<string, any>}) {
  const ctx = ctxRef!;
  const lib = ctx.library.find(a => a.id === data.asset_id);
  const out = ctx.results[id] ? ctx.library.find(a => a.id === ctx.results[id]) : undefined;
  return (
    <div className={'flow-node flow-' + data.kind}>
      {data.kind !== 'text' && data.kind !== 'reference' && <Handle type="target" position={Position.Left} />}
      <b>{data.title}</b>
      {data.kind === 'text' && (
        <textarea
          className="nodrag"
          rows={3}
          value={data.text || ''}
          onChange={e => ctx.patch(id, {text: e.target.value})}
        />
      )}
      {data.kind === 'reference' && (
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
          {lib && <img src={lib.thumbnail_url || lib.url} alt="" width={96} />}
        </>
      )}
      {data.kind === 'image' && (
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
          {out && <img src={out.thumbnail_url || out.url} alt="" width={140} />}
          <small>{ctx.status[id] || (out ? 'готово' : 'не запускался')}</small>
          <button className="nodrag" onClick={() => ctx.run([id])}>
            {out ? '↻ Перегенерировать' : '▶ Запустить'}
          </button>
        </>
      )}
      {(data.kind === 'video' || data.kind === 'audio') && <small>Будет добавлено на этапе видео</small>}
      {data.kind !== 'reference' && data.kind !== 'text' ? null : null}
      {(data.kind === 'text' || data.kind === 'reference' || data.kind === 'image') && (
        <Handle type="source" position={Position.Right} />
      )}
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

  ctxRef = {patch, results, status, library, run: ids => void prepare(ids)};

  const add = (kind: NodeKind, label: string) =>
    onChange(g => ({
      ...g,
      nodes: [
        ...g.nodes,
        {
          id: crypto.randomUUID(),
          type: 'studio',
          position: {x: 80 + g.nodes.length * 40, y: 80 + (g.nodes.length % 5) * 120},
          data: {kind, title: label},
        },
      ],
    }));

  return (
    <section className="panel graph-panel">
      <div className="panel-title">
        <div>
          <h2>Воркфлоу</h2>
          <p className="muted">
            Собери цепочку: текст и референсы подключаются к узлу «Изображение». Каждый запуск идёт только
            после оценки и подтверждения.
          </p>
        </div>
        <button className="primary" disabled={running || !projectId} onClick={() => void prepare()}>
          {running ? 'Выполняется…' : '▶ Запустить всё'}
        </button>
      </div>
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      <div className="flow-layout" style={{display: 'flex', gap: 12}}>
        <aside className="flow-console" style={{minWidth: 150}}>
          {KINDS.map(k => (
            <button key={k.kind} disabled={!k.enabled} title={k.hint} onClick={() => add(k.kind, k.label)}>
              ＋ {k.label}
            </button>
          ))}
        </aside>
        <div className="flow-wrap" style={{flexGrow: 1}}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
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
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
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
