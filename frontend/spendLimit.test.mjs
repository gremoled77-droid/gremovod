import test from 'node:test';
import assert from 'node:assert/strict';
import {initialLimit, limitAllowed, limitNeedsConfirm} from './src/spendLimit.ts';

test('лимит по умолчанию — $2, а при большей оценке — ближайший доллар вверх', () => {
  assert.equal(initialLimit(0.07), '2');
  assert.equal(initialLimit(2), '2');
  assert.equal(initialLimit(3.2), '4');
});

test('выше $2 нужна галочка, ниже оценки нельзя', () => {
  assert.equal(limitNeedsConfirm('2'), false);
  assert.equal(limitNeedsConfirm('2.01'), true);
  assert.equal(limitAllowed(0.5, '2', false), true);
  assert.equal(limitAllowed(0.5, '5', false), false);
  assert.equal(limitAllowed(0.5, '5', true), true);
  assert.equal(limitAllowed(1.5, '1', true), false);
  assert.equal(limitAllowed(0.5, '', true), false);
  assert.equal(limitAllowed(0.5, 'abc', true), false);
});
