import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import {cardFrom, type LlmCard} from './llmDisplay';
import {LLM_MAX_TOKENS} from './llmPricing';

export type Msg = {role: 'system' | 'user'; content: string};
export type LlmQuote = {
  token: string;
  usd: number;
  projectId: string;
  model: string;
  messages: Msg[];
  reference: LlmCard['reference'];
  execution: LlmCard['execution'];
  actual: LlmCard['actual'];
};
export type LlmResult = {text: string; cost: number | null; card: LlmCard};

const post = (body: unknown) => ({
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(body),
});

/** Карточка вызова из оценки: те же поля, что пришли от сервера. */
export function cardOf(quote: LlmQuote): LlmCard {
  return cardFrom(quote);
}

/** Шаг 1 платного вызова LLM: бесплатная подписанная оценка цены. Без неё сервер не отправит запрос.
 * Прежние поля на месте; добавлены поля карточки — итоговые суммы считает сервер. */
export async function estimateLlm(projectId: string, model: string, messages: Msg[]): Promise<LlmQuote> {
  const q = await responseJson(
    await apiFetch(
      '/api/llm/estimate',
      post({project_id: projectId, model, messages, max_tokens: LLM_MAX_TOKENS})
    )
  );
  const card = cardFrom(q);
  return {
    token: q.quote_token,
    usd: q.estimated_usd,
    projectId,
    model,
    messages,
    reference: card.reference,
    execution: card.execution,
    actual: card.actual,
  };
}

/** Шаг 2: запуск после подтверждения. Возвращает текст ответа, списанную сумму и карточку вызова.
 * maxCostUsd — максимальный одобренный расход; по умолчанию равен оценке. */
export async function runLlm(quote: LlmQuote, maxCostUsd?: number): Promise<LlmResult> {
  const answer = await responseJson(
    await apiFetch(
      '/api/llm/chat',
      post({
        provider: 'piapi',
        project_id: quote.projectId,
        model: quote.model,
        max_tokens: LLM_MAX_TOKENS,
        messages: quote.messages,
        approved: true,
        quote_token: quote.token,
        max_cost_usd: Number.isFinite(maxCostUsd) ? maxCostUsd : quote.usd,
        request_id: crypto.randomUUID(),
      })
    )
  );
  const raw = answer.cost_usd;
  const cost = raw === null || raw === undefined ? null : Number(raw);
  return {
    text: String(answer.choices?.[0]?.message?.content || ''),
    cost: cost !== null && Number.isFinite(cost) ? cost : null,
    card: cardFrom(answer),
  };
}
