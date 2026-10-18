import {apiFetch, responseJson} from './api';
import {LLM_MAX_TOKENS} from './llmPricing';

export type Msg = {role: 'system' | 'user'; content: string};
export type LlmQuote = {token: string; usd: number; projectId: string; model: string; messages: Msg[]};

const post = (body: unknown) => ({
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(body),
});

/** Шаг 1 платного вызова LLM: бесплатная подписанная оценка цены. Без неё сервер не отправит запрос. */
export async function estimateLlm(projectId: string, model: string, messages: Msg[]): Promise<LlmQuote> {
  const q = await responseJson(
    await apiFetch(
      '/api/llm/estimate',
      post({project_id: projectId, model, messages, max_tokens: LLM_MAX_TOKENS})
    )
  );
  return {token: q.quote_token, usd: q.estimated_usd, projectId, model, messages};
}

/** Шаг 2: запуск после подтверждения. Возвращает текст ответа и списанную сумму. */
export async function runLlm(quote: LlmQuote): Promise<{text: string; cost: number | null}> {
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
        max_cost_usd: quote.usd,
        request_id: crypto.randomUUID(),
      })
    )
  );
  const cost = Number(answer.cost_usd);
  return {
    text: String(answer.choices?.[0]?.message?.content || ''),
    cost: Number.isFinite(cost) ? cost : null,
  };
}
