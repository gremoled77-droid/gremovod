import {apiFetch} from './api.ts';
import {cardFrom, type LlmCard} from './llmDisplay.ts';
import {LLM_MAX_TOKENS} from './llmPricing.ts';

export type Msg = {role: 'system' | 'user'; content: string};
/** Роль работы в реестре маршрутов: окно студии говорит серверу, какая задача ему нужна.
 * Провайдера клиент не выбирает — маршрут выбирает сервер по реестру владельца. */
export type LlmTask = 'simple' | 'editorial' | 'coding' | 'backup';
export type LlmQuote = {
  token: string;
  usd: number;
  projectId: string;
  model: string;
  messages: Msg[];
  task: LlmTask;
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

/** Ответ сервера с текстом ошибки: тот же разбор, что в панели чата. */
async function responseJson(r: Response) {
  const d = await r.json();
  if (!r.ok) throw Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail));
  return d;
}

/** Карточка вызова из оценки: те же поля, что пришли от сервера. */
export function cardOf(quote: LlmQuote): LlmCard {
  return cardFrom(quote);
}

/** Шаг 1 платного вызова LLM: бесплатная подписанная оценка цены. Без неё сервер не отправит запрос.
 * Прежние поля на месте; добавлены поля карточки — итоговые суммы считает сервер.
 * task — роль работы в реестре: сервер сам выбирает маршрут (mode 'auto'), клиент провайдера не задаёт. */
export async function estimateLlm(
  projectId: string,
  model: string,
  messages: Msg[],
  task: LlmTask = 'simple'
): Promise<LlmQuote> {
  const q = await responseJson(
    await apiFetch(
      '/api/llm/estimate',
      post({
        project_id: projectId,
        model,
        messages,
        max_tokens: LLM_MAX_TOKENS,
        route_mode: 'auto',
        task,
        allow_free: true,
      })
    )
  );
  const card = cardFrom(q);
  return {
    token: q.quote_token,
    usd: q.estimated_usd,
    projectId,
    model,
    messages,
    task,
    reference: card.reference,
    execution: card.execution,
    actual: card.actual,
  };
}

/** Шаг 2: запуск после подтверждения. Возвращает текст ответа, списанную сумму и карточку вызова.
 * maxCostUsd — максимальный одобренный расход; по умолчанию равен оценке.
 * Задача и режим маршрутизации — те же, что в оценке: маршрут выбирает сервер. */
export async function runLlm(quote: LlmQuote, maxCostUsd?: number): Promise<LlmResult> {
  const answer = await responseJson(
    await apiFetch(
      '/api/llm/chat',
      post({
        project_id: quote.projectId,
        model: quote.model,
        max_tokens: LLM_MAX_TOKENS,
        messages: quote.messages,
        approved: true,
        quote_token: quote.token,
        max_cost_usd: Number.isFinite(maxCostUsd) ? maxCostUsd : quote.usd,
        request_id: crypto.randomUUID(),
        route_mode: 'auto',
        task: quote.task,
        allow_free: true,
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
