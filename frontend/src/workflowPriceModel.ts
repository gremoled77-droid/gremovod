import type {Edge, Node} from '@xyflow/react';
import {llmEstimate} from './llmPricing.ts';
import {buildLlmSteps, buildSteps, llmInput} from './workflowPlan.ts';

export type PriceRequest = {
  nodeId: string;
  model: string;
  prompt: string;
  options: Record<string, string | number>;
  refs: number;
};

/** Какие узлы можно оценить сейчас: у них выбрана модель и есть текст (ответ LLM заменяется заглушкой). */
export function priceRequests(nodes: Node[], edges: Edge[], results: Record<string, string>): PriceRequest[] {
  const llmIds = nodes.filter(n => n.data?.kind === 'llm').map(n => n.id);
  const outputs: Record<string, string> = {};
  for (const n of nodes) if (n.data?.kind === 'llm' && n.data.output) outputs[n.id] = String(n.data.output);
  return buildSteps(nodes, edges, results, {llm: outputs, pendingLlm: llmIds})
    .steps.filter(s => s.model && s.prompt)
    .map(s => ({
      nodeId: s.nodeId,
      model: s.model,
      prompt: s.prompt,
      options: s.options,
      refs: s.refAssetIds.length + s.waitFor.length,
    }));
}

/** Цены LLM-узлов считаются по таблице тарифов, остальные — серверной оценкой без запуска. */
export function llmPrices(nodes: Node[], edges: Edge[]): Record<string, number> {
  const outputs: Record<string, string> = {};
  for (const n of nodes) if (n.data?.kind === 'llm' && n.data.output) outputs[n.id] = String(n.data.output);
  const result: Record<string, number> = {};
  for (const s of buildLlmSteps(nodes, edges).steps) {
    if (s.model) result[s.nodeId] = llmEstimate(s.model, llmInput(s, nodes, outputs).length + 600);
  }
  return result;
}
