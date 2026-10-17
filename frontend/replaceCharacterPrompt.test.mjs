import test from 'node:test';
import assert from 'node:assert/strict';
import {
  buildReplaceInFramePrompt,
  buildReplaceInVideoPrompt,
  replacementRefs,
} from './src/replaceCharacterPrompt.ts';

test('промпт замены в кадре называет оба референса и сохраняет сцену', () => {
  const p = buildReplaceInFramePrompt();
  assert.match(p, /Image 1 is the original frame/);
  assert.match(p, /Image 2 is the identity reference/);
  assert.match(p, /clothing as in the original frame/);
  assert.match(p, /background and composition/);
});

test('без keepClothing одежда берётся с референса героя', () => {
  const p = buildReplaceInFramePrompt({keepClothing: false});
  assert.match(p, /outfit shown on the character reference/);
  assert.doesNotMatch(p, /clothing as in the original frame/);
});

test('промпт замены в видео подставляет теги и переносит игру и речь', () => {
  const p = buildReplaceInVideoPrompt({video: '@Video1', image: '@Image1'});
  assert.match(p, /@Video1/);
  assert.match(p, /@Image1/);
  assert.doesNotMatch(p, /@VIDEO/);
  assert.match(p, /micro-expressions/);
  assert.match(p, /Speech:/);
});

test('референсы идут в порядке кадр, герой', () => {
  assert.deepEqual(replacementRefs('frame1', 'hero1'), ['frame1', 'hero1']);
});
