import type {Edge, Node} from '@xyflow/react';

export type NodeKind = 'text' | 'reference' | 'image' | 'video' | 'audio' | 'llm';
export type Step = {
  nodeId: string;
  model: string;
  prompt: string;
  options: Record<string, string | number>;
  refAssetIds: string[];
  waitFor: string[]; // узлы-генерации, результат которых нужен как референс
};
export type LlmStep = {
  nodeId: string;
  model: string;
  system: string;
  sources: string[]; // текстовые узлы и другие LLM-узлы, из которых собирается вход
};
/** Дополнительные данные для сборки промптов: готовые ответы LLM и узлы, которые запустятся первыми. */
export type PlanExtras = {llm?: Record<string, string>; pendingLlm?: string[]};

export const DEFAULT_LLM_SYSTEM =
  'Ты помощник режиссёра мультсериала. Перепиши идею в подробный промпт для генерации кадра: кто, где, что делает, свет, камера, настроение. Отвечай только текстом промпта, на русском.';
export const PENDING_LLM_TEXT = '[текст от LLM-узла]';

const data = (n: Node) => (n.data || {}) as Record<string, any>;

/** Порядок «слева направо»: по горизонтали, затем по вертикали. */
const byPosition = (a: Node, b: Node) => a.position.x - b.position.x || a.position.y - b.position.y;

export function upstream(nodeId: string, nodes: Node[], edges: Edge[]) {
  const ids = new Set(edges.filter(e => e.target === nodeId).map(e => e.source));
  return nodes.filter(n => ids.has(n.id)).sort(byPosition);
}

/** Есть ли цикл: тогда запускать нельзя. */
export function hasCycle(nodes: Node[], edges: Edge[]) {
  const state = new Map<string, number>();
  const next = (id: string) => edges.filter(e => e.source === id).map(e => e.target);
  const visit = (id: string): boolean => {
    if (state.get(id) === 1) return true;
    if (state.get(id) === 2) return false;
    state.set(id, 1);
    if (next(id).some(visit)) return true;
    state.set(id, 2);
    return false;
  };
  return nodes.some(n => visit(n.id));
}

/** Проверка соединения: что во что можно подавать. */
export function canConnect(source?: Node, target?: Node) {
  if (!source || !target || source.id === target.id) return false;
  const s = data(source).kind as NodeKind;
  const t = data(target).kind as NodeKind;
  if (t === 'llm') return s === 'text' || s === 'llm';
  if (t === 'image' || t === 'video')
    return s === 'text' || s === 'llm' || s === 'reference' || s === 'image';
  return false;
}

/** Текст узла-источника: свой текст, ответ LLM или заглушка, если LLM запустится в этом же запуске. */
function textOf(n: Node, extras: PlanExtras): string {
  const d = data(n);
  if (d.kind === 'text') return String(d.text || '').trim();
  if (d.kind === 'llm') {
    const out = String(extras.llm?.[n.id] ?? d.output ?? '').trim();
    if (out) return out;
    return extras.pendingLlm?.includes(n.id) ? PENDING_LLM_TEXT : '';
  }
  return '';
}

/** Сборка шагов LLM-узлов: сначала те, от которых зависят другие. */
export function buildLlmSteps(nodes: Node[], edges: Edge[]): {steps: LlmStep[]; problems: string[]} {
  if (hasCycle(nodes, edges)) return {steps: [], problems: ['В схеме есть цикл. Убери замкнутую связь.']};
  const problems: string[] = [];
  const llm = nodes.filter(n => data(n).kind === 'llm').sort(byPosition);
  const steps: LlmStep[] = llm.map(node => {
    const d = data(node);
    const sources = upstream(node.id, nodes, edges)
      .filter(n => data(n).kind === 'text' || data(n).kind === 'llm')
      .map(n => n.id);
    if (!d.model) problems.push(`«${d.title || node.id}»: не выбрана модель`);
    if (!sources.length) problems.push(`«${d.title || node.id}»: не подключён текст с идеей`);
    return {
      nodeId: node.id,
      model: String(d.model || ''),
      system: String(d.system || DEFAULT_LLM_SYSTEM),
      sources,
    };
  });
  const ordered: LlmStep[] = [];
  const done = new Set<string>();
  const ids = new Set(steps.map(s => s.nodeId));
  while (ordered.length < steps.length) {
    const ready = steps.find(s => !done.has(s.nodeId) && s.sources.every(id => !ids.has(id) || done.has(id)));
    if (!ready) break;
    ordered.push(ready);
    done.add(ready.nodeId);
  }
  return {steps: ordered, problems};
}

/** Вход LLM-шага: тексты источников по порядку; ответы предыдущих LLM-узлов берутся из outputs. */
export function llmInput(step: LlmStep, nodes: Node[], outputs: Record<string, string>): string {
  return step.sources
    .map(id => nodes.find(n => n.id === id))
    .filter((n): n is Node => !!n)
    .map(n => textOf(n, {llm: outputs}))
    .filter(Boolean)
    .join('\n\n');
}

export function buildSteps(
  nodes: Node[],
  edges: Edge[],
  results: Record<string, string>,
  extras: PlanExtras = {}
): {steps: Step[]; problems: string[]} {
  const problems: string[] = [];
  if (hasCycle(nodes, edges)) return {steps: [], problems: ['В схеме есть цикл. Убери замкнутую связь.']};
  const steps: Step[] = [];
  for (const node of nodes.filter(n => data(n).kind === 'image').sort(byPosition)) {
    const d = data(node);
    const inputs = upstream(node.id, nodes, edges);
    const prompt = inputs
      .filter(n => data(n).kind === 'text' || data(n).kind === 'llm')
      .map(n => textOf(n, extras))
      .filter(Boolean)
      .join('\n\n');
    if (!d.model) problems.push(`«${d.title || node.id}»: не выбрана модель`);
    if (!prompt) {
      const silent = inputs.some(n => data(n).kind === 'llm');
      problems.push(
        silent
          ? `«${d.title || node.id}»: у подключённого LLM-узла ещё нет текста — запусти его`
          : `«${d.title || node.id}»: не подключён текст с промптом`
      );
    }
    const refAssetIds: string[] = [];
    const waitFor: string[] = [];
    for (const n of inputs) {
      const nd = data(n);
      if (nd.kind === 'reference' && nd.asset_id) refAssetIds.push(String(nd.asset_id));
      if (nd.kind === 'image') {
        if (results[n.id]) refAssetIds.push(results[n.id]);
        else waitFor.push(n.id);
      }
    }
    steps.push({
      nodeId: node.id,
      model: String(d.model || ''),
      prompt,
      options: d.options || {},
      refAssetIds,
      waitFor,
    });
  }
  return {steps, problems};
}
