/** Общий протокол платного LLM-вызова: оценка → подпись → подтверждение.
 *
 * Правило одно для всех платных маршрутов: без подписи оценки, без лимита
 * стоимости и без request_id запрос не проходит. Дублировать это в разных
 * компонентах нельзя — расхождение здесь означает неучтённый расход.
 */
export type Quote = {usd: number; token: string};

export type PaidBody = {
  approved: true;
  quote_token: string;
  max_cost_usd: number;
  request_id: string;
};

/** Часть тела платного запроса: подпись, лимит и идентификатор идемпотентности. */
export function paidBody(quote: Quote, requestId: string): PaidBody {
  return {
    approved: true,
    quote_token: quote.token,
    max_cost_usd: quote.usd,
    request_id: requestId,
  };
}

/** Идентификатор прогона: повтор того же id не оплачивается дважды. */
export function newRequestId(): string {
  return crypto.randomUUID();
}
