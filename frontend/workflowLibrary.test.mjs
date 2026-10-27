import test from 'node:test';
import assert from 'node:assert/strict';
import {missingAssetIds} from './src/workflowLibrary.ts';

test('готовый результат узла, которого нет в библиотеке, требует обновления', () => {
  const library = [{id: 'a'}, {id: 'b'}];
  assert.deepEqual(missingAssetIds({n1: 'a', n2: 'c'}, library), ['c']);
  assert.deepEqual(missingAssetIds({n1: 'a'}, library), []);
  assert.deepEqual(missingAssetIds({}, []), []);
});

test('повторяющиеся и пустые id не дают лишних обновлений', () => {
  assert.deepEqual(missingAssetIds({n1: 'x', n2: 'x', n3: ''}, []), ['x']);
});
