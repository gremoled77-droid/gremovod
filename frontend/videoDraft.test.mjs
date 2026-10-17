import test from 'node:test';
import assert from 'node:assert/strict';
import {loadVideoDraft, saveVideoDraft, videoDraftKey} from './src/videoDraft.ts';

const memory = () => {
  const data = new Map();
  return {getItem: k => (data.has(k) ? data.get(k) : null), setItem: (k, v) => void data.set(k, String(v))};
};

const draft = {
  prompt: 'rack focus',
  base: 'asset-1',
  refs: ['asset-2'],
  model: 'minimax-h3',
  values: {resolution: '480p', duration: 5},
};

test('черновик «Видео» возвращает модель и промпт, выбранные до загрузки оригинала в облако', () => {
  const storage = memory();
  saveVideoDraft('p1', draft, storage);
  const restored = loadVideoDraft('p1', storage);
  assert.equal(restored.model, 'minimax-h3');
  assert.equal(restored.prompt, 'rack focus');
  assert.deepEqual(restored, draft);
});

test('черновики разных проектов не смешиваются', () => {
  const storage = memory();
  saveVideoDraft('p1', draft, storage);
  assert.deepEqual(loadVideoDraft('p2', storage), {});
  assert.notEqual(videoDraftKey('p1'), videoDraftKey('p2'));
});

test('битый или чужой черновик даёт пустые значения, а не ошибку', () => {
  const storage = memory();
  storage.setItem(videoDraftKey('p1'), '{oops');
  assert.deepEqual(loadVideoDraft('p1', storage), {});
  storage.setItem(videoDraftKey('p1'), '[1,2]');
  assert.deepEqual(loadVideoDraft('p1', storage), {});
  storage.setItem(videoDraftKey('p1'), 'null');
  assert.deepEqual(loadVideoDraft('p1', storage), {});
});

test('недоступное хранилище не ломает экран', () => {
  const broken = {
    getItem: () => {
      throw Error('blocked');
    },
    setItem: () => {
      throw Error('blocked');
    },
  };
  assert.deepEqual(loadVideoDraft('p1', broken), {});
  assert.doesNotThrow(() => saveVideoDraft('p1', draft, broken));
});
