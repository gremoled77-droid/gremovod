import type {Edge, Node} from '@xyflow/react';

export type NodeKind = 'text' | 'reference' | 'image' | 'video' | 'audio' | 'llm' | 'file';
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

/** Видеомодели узла «Видео»: параметры совпадают с каталогом бэкенда (оценку и проверку делает сервер). */
export const VIDEO_MODELS: Record<
  string,
  {
    label: string;
    maxRefs: number;
    resolutions: string[];
    durationMin: number;
    durationMax: number;
    aspects: string[];
  }
> = {
  'minimax-h3': {
    label: 'MiniMax H3',
    maxRefs: 1,
    resolutions: ['480p', '768p', '1080p'],
    durationMin: 5,
    durationMax: 15,
    aspects: ['16:9', '9:16', '1:1'],
  },
  'seedance-2.5': {
    label: 'Seedance 2.5',
    maxRefs: 30,
    resolutions: ['480p', '720p', '1080p'],
    durationMin: 4,
    durationMax: 30,
    aspects: ['16:9', '9:16', '4:3', '3:4', '21:9', '1:1', 'adaptive'],
  },
};
export function videoDefaults(model: string): Record<string, string | number> {
  const m = VIDEO_MODELS[model];
  return m ? {resolution: m.resolutions[0], duration: m.durationMin, aspect_ratio: m.aspects[0]} : {};
}

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

/** Тип данных на портах: цвет связи и совместимость. */
export type PortType = 'text' | 'image' | 'audio' | 'video';
export const PORT_COLOR: Record<PortType, string> = {
  text: '#5ec4b6',
  image: '#6ea8fe',
  audio: '#f2b134',
  video: '#b18cff',
};
export const PORT_LABEL: Record<PortType, string> = {
  text: 'текст',
  image: 'изображение',
  audio: 'аудио',
  video: 'видео',
};

/** Что узел отдаёт на выход. */
export function outPort(kind: NodeKind): PortType | null {
  if (kind === 'text' || kind === 'llm' || kind === 'file') return 'text';
  if (kind === 'reference' || kind === 'image') return 'image';
  if (kind === 'audio') return 'audio';
  if (kind === 'video') return 'video';
  return null;
}
/** Типы, которые узел принимает на вход (по порту на тип). Аудио не принимает никто: модели студии его не получают. */
export function inPorts(kind: NodeKind): PortType[] {
  if (kind === 'llm') return ['text'];
  if (kind === 'image' || kind === 'video') return ['text', 'image'];
  return [];
}

/** Часть каталога моделей (/api/model-specs), нужная для проверки входов. */
export type ModelSpecLite = {
  kind?: string;
  launch_enabled?: boolean;
  max_refs?: number;
  api_refs?: number;
  options?: Record<string, {values?: (string | number)[]; default?: string | number}>;
};
/** Сколько референсов-картинок принимает модель; null — лимит неизвестен. */
export function refLimit(model: string, specs?: Record<string, ModelSpecLite>): number | null {
  if (VIDEO_MODELS[model]) return VIDEO_MODELS[model].maxRefs;
  const s = specs?.[model];
  if (!s) return null;
  return s.api_refs ?? s.max_refs ?? null;
}

/** Достижим ли узел `to` из `from` по связям. */
function reaches(from: string, to: string, edges: Edge[]) {
  const seen = new Set<string>();
  const stack = [from];
  while (stack.length) {
    const id = stack.pop()!;
    if (id === to) return true;
    if (seen.has(id)) continue;
    seen.add(id);
    for (const e of edges) if (e.source === id) stack.push(e.target);
  }
  return false;
}

/** Проверка соединения с причиной отказа: типы портов, повтор, цикл, лимит референсов модели. */
export function checkConnection(
  source: Node | undefined,
  target: Node | undefined,
  nodes: Node[],
  edges: Edge[],
  specs?: Record<string, ModelSpecLite>,
  targetHandle?: string | null
): {ok: boolean; reason: string} {
  const no = (reason: string) => ({ok: false, reason});
  if (!source || !target) return no('Узел не найден');
  if (source.id === target.id) return no('Нельзя соединить узел с самим собой');
  const sk = data(source).kind as NodeKind;
  const tk = data(target).kind as NodeKind;
  const out = outPort(sk);
  if (!out) return no('У этого узла нет выхода');
  if (!inPorts(tk).length) return no('У этого узла нет входов');
  if (sk === 'file' && tk !== 'llm') return no('Файл подаётся только в узел LLM');
  if (!inPorts(tk).includes(out))
    return no(
      out === 'audio'
        ? 'Аудио не принимает ни одна модель студии'
        : `Узел «${data(target).title || tk}» не принимает ${PORT_LABEL[out]}`
    );
  if (targetHandle && targetHandle !== 'in-' + out)
    return no(`Тип не совпадает: сюда нельзя подать ${PORT_LABEL[out]}`);
  if (edges.some(e => e.source === source.id && e.target === target.id)) return no('Такая связь уже есть');
  if (reaches(target.id, source.id, edges)) return no('Связь замкнёт цикл');
  if (out === 'image') {
    const limit = refLimit(String(data(target).model || ''), specs);
    const used = edges.filter(
      e =>
        e.target === target.id && outPort(data(nodes.find(n => n.id === e.source) || target).kind) === 'image'
    ).length;
    if (limit !== null && used >= limit) return no(`Модель принимает референсов не больше ${limit}`);
  }
  return {ok: true, reason: ''};
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
  if (d.kind === 'file') {
    const text = String(d.excerpt || '').trim();
    return text
      ? `[Файл: ${d.name || d.title}]
${text}`
      : '';
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
      .filter(n => ['text', 'llm', 'file'].includes(data(n).kind))
      .map(n => n.id);
    if (!d.model) problems.push(`«${d.title || node.id}»: не выбрана модель`);
    if (!sources.length) problems.push(`«${d.title || node.id}»: не подключён текст с идеей`);
    else if (upstream(node.id, nodes, edges).every(n => data(n).kind === 'file' && !data(n).excerpt))
      problems.push(`«${d.title || node.id}»: у подключённых файлов нет текста (PDF не читается)`);
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
  for (const node of nodes
    .filter(n => data(n).kind === 'image' || data(n).kind === 'video')
    .sort(byPosition)) {
    const d = data(node);
    const video = data(node).kind === 'video';
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
    if (video && d.model && !VIDEO_MODELS[d.model])
      problems.push(`«${d.title || node.id}»: модель не поддерживается узлом «Видео»`);
    if (video && VIDEO_MODELS[d.model] && refAssetIds.length + waitFor.length > VIDEO_MODELS[d.model].maxRefs)
      problems.push(
        `«${d.title || node.id}»: ${VIDEO_MODELS[d.model].label} принимает референсов не больше ${VIDEO_MODELS[d.model].maxRefs}`
      );
    steps.push({
      nodeId: node.id,
      model: String(d.model || ''),
      prompt,
      options: video ? {...videoDefaults(String(d.model || '')), ...(d.options || {})} : d.options || {},
      refAssetIds,
      waitFor,
    });
  }
  return {steps, problems};
}

/** Короткая проверка типов без контекста схемы (лимиты моделей и повторы проверяет checkConnection). */
export const canConnect = (source?: Node, target?: Node) =>
  checkConnection(
    source,
    target,
    [source, target].filter((n): n is Node => !!n),
    []
  ).ok;
