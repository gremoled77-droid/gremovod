import assert from 'node:assert/strict';
import {test} from 'node:test';
import {FRAMES_HINT, modePrompt, seedanceCost, usesSource} from './src/videoMode.ts';

const none = {hasBase: false, back: false};

test('кадр → кадр добавляет подсказку один раз', () => {
  const once = modePrompt('frames', 'Грэм садится в машину', none);
  assert.equal(once, `${FRAMES_HINT}\nГрэм садится в машину`);
  assert.equal(modePrompt('frames', 'start @image1 end @image2', none), 'start @image1 end @image2');
});

test('правка и продление ссылаются на @video1', () => {
  assert.equal(modePrompt('edit', 'сделай ночь', none), 'Edit @video1: сделай ночь');
  assert.equal(modePrompt('extend', 'камера уходит', none), 'Extend @video1 forward: камера уходит');
  assert.equal(
    modePrompt('extend', 'камера уходит', {hasBase: false, back: true}),
    'Extend @video1 backward: камера уходит'
  );
  assert.equal(modePrompt('edit', 'убери шум в @video1', none), 'убери шум в @video1');
});

test('новый ролик с кадром-основой получает тег @image1', () => {
  assert.equal(
    modePrompt('new', 'едет', {hasBase: true, back: false}),
    '@image1 is the first frame of the video.\nедет'
  );
  assert.equal(modePrompt('new', 'едет', none), 'едет');
});

test('цена: выход плюс половина входного видео, как на сервере', () => {
  assert.equal(seedanceCost(0.15, 5, 7.2), 1.29);
  assert.equal(seedanceCost(0.35, 8, 0), 2.8);
});

test('только правка и продление используют исходный ролик', () => {
  assert.deepEqual(['new', 'frames', 'edit', 'extend'].map(usesSource), [false, false, true, true]);
});
