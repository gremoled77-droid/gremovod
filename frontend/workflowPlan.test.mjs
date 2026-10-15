import test from 'node:test';
import assert from 'node:assert/strict';
import {buildSteps, canConnect, hasCycle} from './src/workflowPlan.ts';

const n = (id, x, data) => ({id, position: {x, y: 0}, data});
const e = (source, target) => ({id: source + target, source, target});

test('промпт и референсы собираются слева направо, зависимый шаг ждёт', () => {
  const nodes = [
    n('t', 0, {kind: 'text', text: 'Грэм у такси'}),
    n('r', 10, {kind: 'reference', asset_id: 'a1'}),
    n('i1', 100, {kind: 'image', model: 'seedream-5-lite', title: 'Кадр'}),
    n('i2', 200, {kind: 'image', model: 'gpt-image-2.5', title: 'Правка'}),
  ];
  const edges = [e('t', 'i1'), e('r', 'i1'), e('i1', 'i2'), e('t', 'i2')];
  const {steps, problems} = buildSteps(nodes, edges, {});
  assert.deepEqual(problems, []);
  assert.equal(steps[0].prompt, 'Грэм у такси');
  assert.deepEqual(steps[0].refAssetIds, ['a1']);
  assert.deepEqual(steps[1].waitFor, ['i1']);
  const ready = buildSteps(nodes, edges, {i1: 'res1'}).steps[1];
  assert.deepEqual(ready.refAssetIds, ['res1']);
  assert.deepEqual(ready.waitFor, []);
});

test('цикл и недопустимые соединения отклоняются', () => {
  const a = n('a', 0, {kind: 'image', model: 'x'});
  const b = n('b', 1, {kind: 'image', model: 'x'});
  assert.equal(hasCycle([a, b], [e('a', 'b'), e('b', 'a')]), true);
  assert.equal(buildSteps([a, b], [e('a', 'b'), e('b', 'a')], {}).steps.length, 0);
  assert.equal(canConnect(n('t', 0, {kind: 'text'}), a), true);
  assert.equal(canConnect(a, n('t', 0, {kind: 'text'})), false);
});

test('без текста и модели — понятные проблемы', () => {
  const {problems} = buildSteps([n('i', 0, {kind: 'image', title: 'Кадр'})], [], {});
  assert.equal(problems.length, 2);
});
