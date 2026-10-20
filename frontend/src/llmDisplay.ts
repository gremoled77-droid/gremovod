/** Подписи денег LLM: карточка вызова, окно подтверждения, сводка бюджета.
 * Чистые функции без React, без сети, без DOM.
 *
 * Деньги считает сервер: функции этого модуля только подписывают то, что пришло в ответе.
 * Ноль не подставляется никогда — неизвестное списание пишется словами, а не числом. */

import {smallUsd} from './usdFormat.ts';

/** Карточка вызова: ориентир по тарифу Kie/PiAPI, кто выполнил, что списано на самом деле. */
export type LlmCard = {
  reference: {
    provider: string | null;
    model: string | null;
    kind: string;
    cost_usd: number | null;
    status: string;
    rate_source: string | null;
    rate_as_of: string | null;
    rate_verified: boolean;
  };
  execution: {provider: string; model: string; status: string};
  actual: {cost_usd: number | null; status: string; max_cost_usd: number | null};
};

/** Сводка расходов LLM: четыре величины раздельными строками (interfaces.md §11). */
export type BudgetSummary = {
  actual_cost_usd: number;
  reserved_usd: number;
  unknown_cost_usd: number;
  reference_cost_usd: number;
  calls: number;
};

const PROVIDER_TITLES: Record<string, string> = {
  kie: 'Kie.ai',
  piapi: 'PiAPI',
  openrouter: 'OpenRouter',
  minimax: 'MiniMax',
  deepseek: 'DeepSeek',
};

/** Слова, которые пишутся по-своему: GPT, MiniMax, DeepSeek. */
const WORD_TITLES: Record<string, string> = {
  gpt: 'GPT',
  ai: 'AI',
  llm: 'LLM',
  glm: 'GLM',
  qwen: 'Qwen',
  minimax: 'MiniMax',
  deepseek: 'DeepSeek',
  claude: 'Claude',
  gemini: 'Gemini',
  llama: 'Llama',
  haiku: 'Haiku',
  sonnet: 'Sonnet',
  opus: 'Opus',
  flash: 'Flash',
  free: 'Free',
  paid: 'Paid',
};

const isNumber = (part: string) => /^\d+(?:\.\d+)?$/.test(part);

/** Название провайдера для подписи: Kie.ai, PiAPI, OpenRouter. */
export function providerTitle(provider: string | null | undefined): string {
  const key = (provider || '').trim().toLowerCase();
  if (!key) return '';
  return PROVIDER_TITLES[key] || key.charAt(0).toUpperCase() + key.slice(1);
}

function word(part: string): string {
  const key = part.toLowerCase();
  if (WORD_TITLES[key]) return WORD_TITLES[key];
  if (/^[a-z]/.test(part)) return part.charAt(0).toUpperCase() + part.slice(1);
  return part;
}

/** Читаемое имя модели: gpt-6-luna → «GPT-6 Luna», minimax/minimax-m3.1-flash:free → «MiniMax M3.1 Flash Free».
 * Идентификатор, который прочитать не удалось, отдаётся как есть — ничего не выдумывается. */
export function modelLabel(model: string | null | undefined): string {
  const raw = (model || '').trim();
  if (!raw) return '';
  const withoutProvider = raw.includes('/') ? raw.slice(raw.lastIndexOf('/') + 1) : raw;
  const [idPart, ...tags] = withoutProvider.split(':');
  const id = idPart || withoutProvider;
  const parts = id.split('-').filter(Boolean);
  if (!parts.length) return raw;
  if (parts.length === 1 && !WORD_TITLES[parts[0].toLowerCase()]) return raw;
  const chunks: {kind: 'word' | 'number'; text: string; joined?: boolean}[] = [];
  for (const part of parts) {
    if (isNumber(part)) {
      const last = chunks[chunks.length - 1];
      if (last && last.kind === 'number') last.text += '.' + part;
      else chunks.push({kind: 'number', text: part});
    } else {
      chunks.push({kind: 'word', text: part});
    }
  }
  const merged: typeof chunks = [];
  for (const chunk of chunks) {
    const last = merged[merged.length - 1];
    if (chunk.kind === 'number' && last && last.kind === 'word' && !last.joined && last.text.length <= 4) {
      last.text = word(last.text) + '-' + chunk.text;
      last.joined = true;
      continue;
    }
    merged.push({...chunk});
  }
  const text = merged.map(chunk => (chunk.kind === 'word' ? word(chunk.text) : chunk.text)).join(' ');
  const suffix = tags.filter(Boolean).map(word).join(' ');
  return [text, suffix].filter(Boolean).join(' ');
}

/** Карточка из ответа сервера: недостающие поля остаются пустыми, ничего не додумывается. */
export function cardFrom(payload: unknown): LlmCard {
  const raw = (payload || {}) as Record<string, unknown>;
  const ref = (raw.reference || {}) as Record<string, unknown>;
  const execution = (raw.execution || {}) as Record<string, unknown>;
  const actual = (raw.actual || {}) as Record<string, unknown>;
  const num = (value: unknown): number | null =>
    typeof value === 'number' && Number.isFinite(value) ? value : null;
  const str = (value: unknown): string | null =>
    typeof value === 'string' && value.trim() ? value : null;
  return {
    reference: {
      provider: str(ref.provider),
      model: str(ref.model),
      kind: typeof ref.kind === 'string' && ref.kind ? ref.kind : 'unavailable',
      cost_usd: num(ref.cost_usd),
      status: typeof ref.status === 'string' && ref.status ? ref.status : 'unavailable',
      rate_source: str(ref.rate_source),
      rate_as_of: str(ref.rate_as_of),
      rate_verified: ref.rate_verified === true,
    },
    execution: {
      provider: typeof execution.provider === 'string' ? execution.provider : '',
      model: typeof execution.model === 'string' ? execution.model : '',
      status: typeof execution.status === 'string' ? execution.status : 'paid',
    },
    actual: {
      cost_usd: num(actual.cost_usd),
      status: typeof actual.status === 'string' && actual.status ? actual.status : 'unknown',
      max_cost_usd: num(actual.max_cost_usd),
    },
  };
}

/** Тарифный ориентир: провайдер, модель-ориентир, сумма с шестью знаками и дата тарифа. */
export function referenceLine(card: LlmCard): string {
  const ref = card.reference;
  if (!ref || ref.kind === 'unavailable' || ref.status === 'unavailable' || ref.cost_usd === null) {
    return 'Тариф не подтверждён';
  }
  const provider = providerTitle(ref.provider);
  const model = modelLabel(ref.model);
  const sign = ref.status === 'confirmed' ? '=' : '≈';
  const asOf = ref.rate_as_of ? ` (тариф от ${ref.rate_as_of})` : '';
  const head = provider && model ? `По тарифу ${provider} — ${model}` : `По тарифу ${provider || model}`;
  return `${head}: ${sign} ${smallUsd(ref.cost_usd)}${asOf}`;
}

/** Пометка под тарифом: другая модель, подтверждение тарифа или его отсутствие. */
export function referenceNote(card: LlmCard): string {
  const ref = card.reference;
  if (!ref || ref.kind === 'unavailable' || ref.status === 'unavailable' || ref.cost_usd === null) return '';
  if (ref.kind === 'reference_model') return '(другая модель, сравнение по объёму токенов)';
  if (ref.rate_verified) return '(тариф подтверждён)';
  return '(тариф не подтверждён вживую)';
}

/** Кто выполнил вызов: провайдер и модель. */
export function executionLine(card: LlmCard): string {
  const execution = card.execution;
  const provider = providerTitle(execution?.provider);
  const model = modelLabel(execution?.model);
  if (!provider && !model) return 'Исполнитель неизвестен';
  return `Исполняет: ${provider}${model ? ` — ${model}` : ''}`;
}

/** Статус маршрута: бесплатный, платный или неизвестное списание. */
export function statusLine(card: LlmCard): string {
  const actual = card.actual?.status || '';
  const execution = card.execution?.status || '';
  if (actual === 'unknown') return 'Неизвестное списание';
  if (actual === 'free' || execution === 'free') return 'Бесплатный API';
  return 'Платный';
}

/** Фактический платёж: что списали на самом деле. Неизвестное списание — не ноль. */
export function actualLine(card: LlmCard): string {
  const actual = card.actual;
  const status = actual?.status || '';
  if (status === 'free') return 'Бесплатный API';
  if (status === 'not_charged') return 'Списания не было';
  if (status === 'unknown' || actual?.cost_usd === null || actual?.cost_usd === undefined) {
    return 'Реальный платёж: неизвестно';
  }
  return `Реальный платёж: ${smallUsd(actual.cost_usd)}`;
}

/** Строки карточки в зафиксированном порядке: тариф, исполнитель, статус, фактический платёж. */
export function cardLines(card: LlmCard): string[] {
  return [referenceLine(card), executionLine(card), statusLine(card), actualLine(card)];
}

/** Ожидаемый реальный платёж до согласия: по тарифу исполнителя, а не по ориентиру. */
export function expectedPaymentLine(card: LlmCard): string {
  const actual = card.actual;
  const amount = actual?.cost_usd ?? actual?.max_cost_usd ?? null;
  if (amount === null || amount === undefined) return 'Ожидаемый реальный платёж: неизвестно';
  return `Ожидаемый реальный платёж: ${smallUsd(amount)}`;
}

/** Максимальный одобренный расход исполняющего API — потолок, который владелец разрешает. */
export function maxApprovedLine(limitUsd: number | null | undefined): string {
  if (limitUsd === null || limitUsd === undefined || !Number.isFinite(limitUsd)) {
    return 'Максимальный одобренный расход: не задан';
  }
  return `Максимальный одобренный расход: ${smallUsd(limitUsd)}`;
}

/** Деньги окна подтверждения платного вызова в зафиксированном порядке. */
export type ApprovalMoney = {
  /** Тарифный ориентир: первым его видит владелец. */
  reference: string;
  /** Ожидаемый реальный платёж по тарифу исполнителя. */
  expectedPayment: string;
  /** Максимальный одобренный расход исполняющего API. */
  maxApproved: string;
  /** Все три строки в том порядке, в котором они идут до согласия. */
  lines: string[];
};

/** Деньги окна подтверждения: ориентир, ожидаемый реальный платёж, максимальный одобренный расход.
 *
 * Порядок зафиксирован здесь, а не в разметке: владелец обязан увидеть ориентир первым, а обе
 * суммы — до согласия (R49). */
export function approvalMoney(card: LlmCard, limitUsd: number | null | undefined): ApprovalMoney {
  const reference = referenceLine(card);
  const expectedPayment = expectedPaymentLine(card);
  const maxApproved = maxApprovedLine(limitUsd);
  return {reference, expectedPayment, maxApproved, lines: [reference, expectedPayment, maxApproved]};
}

/** Экспозиция LLM: сколько денег занято под вызовы — факт, резервы и неизвестные списания.
 *
 * Это не «фактически потрачено»: та величина живёт в сводке бюджета отдельной строкой. */
export function exposureLine(title: string, usd: number, calls: number): string {
  return `Экспозиция ${title} (факт + резервы + неизвестные списания): ${smallUsd(usd)} (${calls} вызовов)`;
}

/** Сноска панели лимитов: что считается лимитом и что в него входит. */
export function limitsFootnote(): string {
  return 'Лимиты общие для студии и проверяются сервером. Учёт идёт по оценкам до отправки, включая '
    + 'неопределённые и неудачные запросы; это не подтверждение списаний провайдера. Работа агента '
    + 'в чате Codex пишется в те же вызовы LLM и занимает те же лимиты. Ноль запрещает новые '
    + 'платные генерации.';
}

/** Сводка бюджета: четыре величины раздельными строками, ориентир помечен как неденежный. */
export function budgetLines(summary: BudgetSummary): string[] {
  return [
    `Фактически потрачено: ${smallUsd(summary.actual_cost_usd)}`,
    `Зарезервировано: ${smallUsd(summary.reserved_usd)}`,
    `Неизвестные списания / нужна сверка: ${smallUsd(summary.unknown_cost_usd)}`,
    `Эквивалент по Kie/PiAPI (не деньги): ${smallUsd(summary.reference_cost_usd)}`,
  ];
}
