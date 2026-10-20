/** Каталог выбора модели этапа «Продюсер»: разбор ответа бэкенда, выбор и тела запросов.
 *
 * Источник правды — бэкенд (`GET /api/producer/options`): реестр моделей и честная
 * доступность провайдеров. Копии реестра во фронтенде нет, поэтому цена и состав
 * моделей не могут разойтись с сервером, а провайдер без ключа приходит с честным
 * «недоступен», а не с обещанием платного запуска.
 */

export type ProducerModel = {
  id: string;
  label: string;
  provider: string;
  price_in: number;
  price_out: number;
  scopes: string[];
};

export type ProducerProvider = {
  id: string;
  name: string;
  available: boolean;
  status: string;
  message: string;
  models: string[];
};

export type ProducerCatalog = {
  providers: ProducerProvider[];
  models: ProducerModel[];
  default: {provider: string; model: string};
};

export type ProducerChoice = {provider: string; model: string};

/** Режим по умолчанию: локальный MOCK. Платный провайдер выбирается руками. */
export const DEFAULT_CHOICE: ProducerChoice = {provider: 'mock', model: 'mock-producer'};

export type ProducerInput = {
  projectId: string;
  idea: string;
  characterIds?: string[];
  referenceIds?: string[];
  world?: Record<string, string>;
  durationSeconds?: number;
  constraints?: string[];
};

export type ProducerQuote = {mode: string; estimated_usd: number; quote_token: string};

function requiredText(value: unknown, field: string): string {
  if (typeof value !== 'string' || !value)
    throw Error('Каталог этапа «Продюсер»: поле ' + field + ' ожидается непустой строкой');
  return value;
}

/** Разбор ответа `/api/producer/options`. Битый ответ — понятная ошибка, а не пустой каталог. */
export function parseCatalog(raw: unknown): ProducerCatalog {
  if (!raw || typeof raw !== 'object')
    throw Error('Каталог этапа «Продюсер»: ответ сервера не разобран');
  const data = raw as Record<string, any>;
  if (!Array.isArray(data.providers) || !Array.isArray(data.models))
    throw Error('Каталог этапа «Продюсер»: сервер не прислал провайдеров или модели');
  if (!data.providers.length || !data.models.length)
    throw Error('Каталог этапа «Продюсер»: сервер не прислал провайдеров или модели');
  const models: ProducerModel[] = data.models.map((item: any) => ({
    id: requiredText(item?.id, 'models[].id'),
    label: requiredText(item?.label, 'models[].label'),
    provider: requiredText(item?.provider, 'models[].provider'),
    price_in: Number(item?.price_in ?? 0),
    price_out: Number(item?.price_out ?? 0),
    scopes: Array.isArray(item?.scopes) ? item.scopes.map(String) : [],
  }));
  const providers: ProducerProvider[] = data.providers.map((item: any) => ({
    id: requiredText(item?.id, 'providers[].id'),
    name: requiredText(item?.name, 'providers[].name'),
    available: item?.available === true,
    status: typeof item?.status === 'string' ? item.status : 'unknown',
    message: typeof item?.message === 'string' ? item.message : '',
    models: Array.isArray(item?.models) ? item.models.map(String) : [],
  }));
  const rawDefault = (data.default ?? {}) as Record<string, unknown>;
  return {
    providers,
    models,
    default: {
      provider: typeof rawDefault.provider === 'string' ? rawDefault.provider : 'mock',
      model: typeof rawDefault.model === 'string' ? rawDefault.model : 'mock-producer',
    },
  };
}

export function providerById(catalog: ProducerCatalog, id: string): ProducerProvider | undefined {
  return catalog.providers.find(p => p.id === id);
}

export function modelsForProvider(catalog: ProducerCatalog, providerId: string): ProducerModel[] {
  const provider = providerById(catalog, providerId);
  if (!provider) return [];
  return provider.models
    .map(id => catalog.models.find(m => m.id === id))
    .filter((model): model is ProducerModel => !!model);
}

/** Выбор по умолчанию: провайдер и модель, которые сервер назвал дефолтными. */
export function defaultsFor(catalog: ProducerCatalog): ProducerChoice {
  const provider = providerById(catalog, catalog.default.provider)
    ? catalog.default.provider
    : catalog.providers[0]?.id ?? '';
  const models = modelsForProvider(catalog, provider);
  const model = models.some(m => m.id === catalog.default.model)
    ? catalog.default.model
    : models[0]?.id ?? catalog.default.model;
  return {provider, model};
}

/** Смена провайдера: модель остаётся, только если новый провайдер её обслуживает. */
export function choiceForProvider(
  catalog: ProducerCatalog,
  providerId: string,
  current?: string
): ProducerChoice {
  const models = modelsForProvider(catalog, providerId);
  const model =
    current && models.some(m => m.id === current) ? current : models[0]?.id ?? '';
  return {provider: providerId, model};
}

/** Можно ли запускать: провайдер доступен и модель есть у этого провайдера. */
export function isRunnable(catalog: ProducerCatalog, choice: ProducerChoice): boolean {
  const provider = providerById(catalog, choice.provider);
  if (!provider || !provider.available) return false;
  return modelsForProvider(catalog, choice.provider).some(m => m.id === choice.model);
}

/** Честная строка о доступности: без ключа обещать платный запуск нельзя. */
export function availabilityNote(catalog: ProducerCatalog, choice: ProducerChoice): string {
  const provider = providerById(catalog, choice.provider);
  if (!provider) return 'Провайдер не найден в каталоге.';
  if (!provider.available)
    return 'Провайдер недоступен: ' + (provider.message || 'ключ не настроен на сервере');
  return provider.message || '';
}

export function providerLabel(catalog: ProducerCatalog, providerId: string): string {
  const provider = providerById(catalog, providerId);
  if (!provider) return providerId;
  return provider.available ? provider.name : provider.name + ' — недоступен';
}

export function modelLabel(model: ProducerModel): string {
  const price = model.price_in + model.price_out;
  return model.label + ' · $' + price.toFixed(2) + '/1M токенов';
}

export function formatUsd(value: number): string {
  return '$' + (Number(value) || 0).toFixed(4);
}

export function estimateBody(input: ProducerInput, choice: ProducerChoice) {
  return {
    project_id: input.projectId,
    idea: input.idea,
    character_ids: input.characterIds ?? [],
    reference_ids: input.referenceIds ?? [],
    world: input.world ?? {},
    duration_seconds: input.durationSeconds ?? 60,
    constraints: input.constraints ?? [],
    provider: choice.provider,
    model: choice.model,
  };
}

export function runBody(
  input: ProducerInput,
  choice: ProducerChoice,
  quote: ProducerQuote,
  requestId: string
) {
  return {
    ...estimateBody(input, choice),
    approved: true,
    quote_token: quote.quote_token,
    max_cost_usd: quote.estimated_usd,
    request_id: requestId,
  };
}

/** Идентификатор запроса: защита от повторной оплаты, длина не меньше 8 символов. */
export function makeRequestId(): string {
  return 'producer-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10);
}
