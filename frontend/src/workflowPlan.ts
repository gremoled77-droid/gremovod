import type {Edge, Node} from '@xyflow/react';

export type NodeKind = 'text' | 'reference' | 'image' | 'video' | 'audio';
export type Step = {
  nodeId: string;
  model: string;
  prompt: string;
  options: Record<string, string | number>;
  refAssetIds: string[];
  waitFor: string[]; // узлы-генерации, результат которых нужен как референс
};

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
  if (t === 'image' || t === 'video') return s === 'text' || s === 'reference' || s === 'image';
  return false;
}

export function buildSteps(
  nodes: Node[],
  edges: Edge[],
  results: Record<string, string>
): {steps: Step[]; problems: string[]} {
  const problems: string[] = [];
  if (hasCycle(nodes, edges)) return {steps: [], problems: ['В схеме есть цикл. Убери замкнутую связь.']};
  const steps: Step[] = [];
  for (const node of nodes.filter(n => data(n).kind === 'image').sort(byPosition)) {
    const d = data(node);
    const inputs = upstream(node.id, nodes, edges);
    const prompt = inputs
      .filter(n => data(n).kind === 'text')
      .map(n => String(data(n).text || '').trim())
      .filter(Boolean)
      .join('\n\n');
    if (!d.model) problems.push(`«${d.title || node.id}»: не выбрана модель`);
    if (!prompt) problems.push(`«${d.title || node.id}»: не подключён текст с промптом`);
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
