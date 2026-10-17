import test from 'node:test';
import assert from 'node:assert/strict';
import {checkConnection, outPort, inPorts} from './src/workflowPlan.ts';

const node = (id, kind, extra = {}) => ({id, position: {x: 0, y: 0}, data: {kind, title: id, ...extra}});
const specs = {'gpt-image-2': {api_refs: 2}, 'seedream-5-pro': {max_refs: 10}};

test('порты по типам данных', () => {
  assert.equal(outPort('llm'), 'text');
  assert.equal(outPort('reference'), 'image');
  assert.deepEqual(inPorts('video'), ['text', 'image']);
  assert.deepEqual(inPorts('text'), []);
});

test('допустимые и недопустимые связи', () => {
  const t = node('t', 'text');
  const img = node('i', 'image', {model: 'seedream-5-pro'});
  const vid = node('v', 'video', {model: 'minimax-h3'});
  const aud = node('a', 'audio');
  const nodes = [t, img, vid, aud];
  assert.ok(checkConnection(t, img, nodes, [], specs).ok);
  assert.ok(checkConnection(img, vid, nodes, [], specs).ok);
  assert.ok(!checkConnection(vid, img, nodes, [], specs).ok);
  assert.ok(!checkConnection(aud, vid, nodes, [], specs).ok);
  assert.ok(!checkConnection(t, t, nodes, [], specs).ok);
  assert.ok(!checkConnection(t, vid, nodes, [], specs, 'in-image').ok);
});

test('повтор, цикл и лимит референсов модели', () => {
  const r1 = node('r1', 'reference');
  const r2 = node('r2', 'reference');
  const r3 = node('r3', 'reference');
  const img = node('i', 'image', {model: 'gpt-image-2'});
  const img2 = node('i2', 'image', {model: 'gpt-image-2'});
  const nodes = [r1, r2, r3, img, img2];
  const edges = [
    {id: 'e1', source: 'r1', target: 'i'},
    {id: 'e2', source: 'r2', target: 'i'},
  ];
  assert.ok(!checkConnection(r1, img, nodes, edges, specs).ok, 'повтор');
  const full = checkConnection(r3, img, nodes, edges, specs);
  assert.ok(!full.ok && full.reason.includes('2'), 'лимит gpt-image-2');
  const loop = [{id: 'e', source: 'i', target: 'i2'}];
  assert.ok(!checkConnection(img2, img, nodes, loop, specs).ok, 'цикл');
});
