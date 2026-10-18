import test from 'node:test';
import assert from 'node:assert/strict';
import {snapPosition} from './src/workflowSnap.ts';

const other = {x: 100, y: 100, w: 270, h: 300};
const size = {w: 270, h: 200};

test('магнит: узел встаёт ровно под соседом и в одну колонку', () => {
  assert.deepEqual(snapPosition({x: 104, y: 436}, size, [other], 10), {x: 100, y: 440});
});
test('магнит: слева или справа от соседа с зазором колонки', () => {
  assert.deepEqual(snapPosition({x: 445, y: 96}, size, [other], 10), {x: 440, y: 100});
});
test('вне порога узел остаётся где был, оси притягиваются независимо', () => {
  assert.deepEqual(snapPosition({x: 250, y: 700}, size, [other], 10), {x: 250, y: 700});
  assert.deepEqual(snapPosition({x: 103, y: 700}, size, [other], 10), {x: 100, y: 700});
});
test('без соседей позиция не меняется', () => {
  assert.deepEqual(snapPosition({x: 7, y: 9}, size, [], 10), {x: 7, y: 9});
});
