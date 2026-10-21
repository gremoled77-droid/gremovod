import test from 'node:test';
import assert from 'node:assert/strict';
import {estimateLlm, runLlm} from './llmAsk.ts';

/** Окно LML-запросов студии: тело запроса и ответ сервера без сети. */
const requests = [];

const CARD = {
  reference: {
    provider: 'kie',
    model: 'gpt-6-luna',
    kind: 'exact_model',
    cost_usd: 0.0003,
    status: 'estimated',
    rate_source: 'https://kie.ai/gpt-6-sol-and-luna',
    rate_as_of: '2026-10-20',
    rate_verified: true,
  },
  execution: {provider: 'kie', model: 'gpt-6-luna', status: 'paid'},
  actual: {cost_usd: null, status: 'estimated', max_cost_usd: 0.0003},
};

globalThis.window = {
  setTimeout,
  clearTimeout,
  fetch: async (url, init) => {
    const body = init && init.body ? JSON.parse(init.body) : null;
    requests.push({url: String(url), body});
    if (String(url) === '/api/session')
      return new Response(JSON.stringify({token: 'session-token'}), {status: 200});
    if (String(url) === '/api/llm/estimate')
      return new Response(
        JSON.stringify({quote_token: 'quote-1', estimated_usd: 0.0003, model: 'gpt-5.6-sol', ...CARD}),
        {status: 200}
      );
    if (String(url) === '/api/llm/chat')
      return new Response(
        JSON.stringify({
          choices: [{message: {role: 'assistant', content: 'Ответ студии'}}],
          cost_usd: 0.0002,
          ...CARD,
        }),
        {status: 200}
      );
    return new Response(JSON.stringify({detail: 'нет такого адреса'}), {status: 404});
  },
};

const MESSAGES = [{role: 'user', content: 'привет'}];

test('оценка окна LLM уходит с задачей и режимом маршрутизации, без провайдера', async () => {
  const quote = await estimateLlm('project-1', 'gpt-5.6-sol', MESSAGES, 'editorial');
  const request = requests.find(item => item.url === '/api/llm/estimate');
  assert.ok(request, 'оценка должна уйти на /api/llm/estimate');
  assert.equal(request.body.route_mode, 'auto');
  assert.equal(request.body.task, 'editorial');
  assert.equal(request.body.allow_free, true);
  assert.equal(request.body.provider, undefined);
  assert.equal(quote.task, 'editorial');
});

test('вызов окна LLM уходит с той же задачей и режимом, без провайдера', async () => {
  const quote = await estimateLlm('project-1', 'gpt-5.6-sol', MESSAGES, 'editorial');
  const result = await runLlm(quote);
  const request = requests.find(item => item.url === '/api/llm/chat');
  assert.ok(request, 'вызов должен уйти на /api/llm/chat');
  assert.equal(request.body.route_mode, 'auto');
  assert.equal(request.body.task, 'editorial');
  assert.equal(request.body.task, quote.task);
  assert.equal(request.body.allow_free, true);
  assert.equal(request.body.provider, undefined);
  assert.equal(result.text, 'Ответ студии');
});
