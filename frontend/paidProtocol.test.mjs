import test from 'node:test';
import assert from 'node:assert/strict';
import {paidBody} from './src/paidProtocol.ts';

test('платный запрос несёт подпись, лимит и идентификатор прогона', () => {
  const body = paidBody({usd: 0.25, token: 'sig'}, 'req-1');
  assert.equal(body.approved, true);
  assert.equal(body.quote_token, 'sig');
  assert.equal(body.max_cost_usd, 0.25);
  assert.equal(body.request_id, 'req-1');
});

test('тело платного запроса не затирает поля самого запроса', () => {
  const body = paidBody({usd: 1, token: 't'}, 'r');
  assert.equal(body.approved, true);
  assert.equal(body.request_id, 'r');
});
