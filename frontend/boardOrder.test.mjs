import test from 'node:test';
import assert from 'node:assert/strict';
import {moveItem, toggleId} from './src/boardOrder.ts';

test('сдвиг элемента вверх и вниз', () => {
  assert.deepEqual(moveItem(['a', 'b', 'c'], 1, -1), ['b', 'a', 'c']);
  assert.deepEqual(moveItem(['a', 'b', 'c'], 1, 1), ['a', 'c', 'b']);
});

test('за границы списка и без сдвига ничего не меняется', () => {
  assert.equal(moveItem(['a', 'b'], 0, -1), null);
  assert.equal(moveItem(['a', 'b'], 1, 1), null);
  assert.equal(moveItem(['a', 'b'], 0, 0), null);
  assert.equal(moveItem(['a', 'b'], 5, -1), null);
});

test('исходный список не мутируется', () => {
  const ids = ['a', 'b'];
  moveItem(ids, 0, 1);
  assert.deepEqual(ids, ['a', 'b']);
});

test('состав: добавление без дублей и удаление', () => {
  assert.deepEqual(toggleId(['a'], 'b', true), ['a', 'b']);
  assert.deepEqual(toggleId(['a', 'b'], 'b', true), ['a', 'b']);
  assert.deepEqual(toggleId(['a', 'b'], 'a', false), ['b']);
  assert.deepEqual(toggleId(['a'], 'x', false), ['a']);
});
