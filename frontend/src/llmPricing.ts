/** Цены LLM на PiAPI, USD за 1 млн токенов (страница piapi.ai/docs/llm-api/completions, акционные). */
export const LLM_MODELS: Record<string, {label: string; input: number; output: number}> = {
  'gpt-5.6-luna': {label: 'GPT-5.6 Luna', input: 0.02, output: 0.12},
  'gpt-5.6-terra': {label: 'GPT-5.6 Terra', input: 0.2, output: 1.2},
  'gpt-5.6-sol': {label: 'GPT-5.6 Sol', input: 0.5, output: 3},
};
export const LLM_MAX_TOKENS = 2000;

/** Верхняя оценка: вход ≈ 1 токен на 2.5 символа русского текста, выход — весь лимит max_tokens. */
export function llmEstimate(model: string, inputChars: number, maxTokens = LLM_MAX_TOKENS): number {
  const price = LLM_MODELS[model];
  if (!price) return 0;
  const inputTokens = Math.ceil(inputChars / 2.5) + 50;
  return (inputTokens * price.input + maxTokens * price.output) / 1_000_000;
}
