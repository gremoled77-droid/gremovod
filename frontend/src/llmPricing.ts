/** Цены LLM на PiAPI, USD за 1 млн токенов (страница piapi.ai/docs/llm-api/completions, акционные).
 *
 * Это копия реестра backend/model_catalog.py::LLM_MODELS — источника истины.
 * Список нужен синхронно, во время рендера, поэтому бэкенд не подставляется.
 * Соответствие копии реестру проверяет backend/test_llm_registry.py:
 * изменил цену здесь — тест упадёт, если не поправил backend.
 */
export const LLM_MODELS: Record<string, {label: string; input: number; output: number}> = {
  'gpt-5.6-luna': {label: 'GPT-5.6 Luna', input: 0.02, output: 0.12},
  'gpt-5.6-terra': {label: 'GPT-5.6 Terra', input: 0.2, output: 1.2},
  'gpt-5.6-sol': {label: 'GPT-5.6 Sol', input: 0.5, output: 3},
};
export const LLM_MAX_TOKENS = 2000;

/** Верхняя оценка: вход ≈ 1 токен на 2 символа (как в backend llm_guard.estimate_usd), выход — весь лимит max_tokens. */
export function llmEstimate(model: string, inputChars: number, maxTokens = LLM_MAX_TOKENS): number {
  const price = LLM_MODELS[model];
  if (!price) return 0;
  const inputTokens = Math.ceil(inputChars / 2) + 50;
  return (inputTokens * price.input + maxTokens * price.output) / 1_000_000;
}

/** Для экрана «Идея»: те же модели плюс GPT-6 Astra (дорогая, только для сценария и промптов). */
export const IDEA_LLM_MODELS: Record<string, {label: string; input: number; output: number}> = {
  ...LLM_MODELS,
  'gpt-6-astra': {label: 'GPT-6 Astra', input: 2, output: 10},
};
export function ideaEstimate(model: string, inputChars: number, maxTokens = LLM_MAX_TOKENS): number {
  const price = IDEA_LLM_MODELS[model];
  if (!price) return 0;
  const inputTokens = Math.ceil(inputChars / 2) + 40;
  return (inputTokens * price.input + maxTokens * price.output) / 1_000_000;
}
