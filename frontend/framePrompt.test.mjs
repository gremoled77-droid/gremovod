import test from 'node:test';
import assert from 'node:assert/strict';
import {buildFramePrompt, defaultFrameTitles} from './src/framePrompt.ts';

test('промпт кадра собирает задание, героев, место и мир', () => {
  const p = buildFramePrompt({
    brief: 'Грэм смотрит в окно ночью',
    heroes: [
      {name: 'Грэм', identity: {species: 'таксист', costume: 'красная кепка'}},
      {name: 'Катя', identity: {}},
    ],
    location: 'салон ВАЗ-2106',
    world: {look: 'тёплая 2D анимация', avoid: 'логотипы'},
  });
  assert.match(p, /Кадр: Грэм смотрит в окно ночью\./);
  assert.match(p, /В кадре: Грэм \(таксист, красная кепка\); Катя\./);
  assert.match(p, /Место: салон ВАЗ-2106\./);
  assert.match(p, /Стиль мира: тёплая 2D анимация\./);
  assert.match(p, /Запрещено: логотипы\./);
  assert.doesNotMatch(p, /Палитра/);
});

test('без героев и мира остаётся только задание', () => {
  assert.equal(buildFramePrompt({brief: '  двор  ', heroes: []}), 'Кадр: двор.');
  assert.equal(buildFramePrompt({brief: '', heroes: []}), '');
});

test('названия кадров продолжают нумерацию и не повторяют занятые', () => {
  assert.deepEqual(defaultFrameTitles([], 2), ['Кадр 1', 'Кадр 2']);
  assert.deepEqual(defaultFrameTitles(['Общий', 'Кадр 2'], 3), ['Кадр 3', 'Кадр 4', 'Кадр 5']);
  assert.deepEqual(defaultFrameTitles(['Кадр 3', 'x'], 1), ['Кадр 4']);
});
