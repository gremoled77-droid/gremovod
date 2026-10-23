import test from 'node:test';
import assert from 'node:assert/strict';
import {buildCharacterPrompt, worldFilled} from './src/characterPrompt.ts';

test('промпт собирает описание героя и мир, пустые поля пропускает', () => {
  const p = buildCharacterPrompt(
    'Грэм',
    {species: 'человек, таксист', face: '', costume: 'кожаная куртка', negative: 'очки'},
    {look: 'тёплая 2D анимация', palette: 'охра и синий', avoid: 'логотипы'}
  );
  assert.match(p, /«Грэм»/);
  assert.match(p, /Вид: человек, таксист\./);
  assert.match(p, /Одежда: кожаная куртка\./);
  assert.match(p, /Стиль мира: тёплая 2D анимация\./);
  assert.match(p, /Запрещено: очки; логотипы\./);
  assert.doesNotMatch(p, /Лицо:/);
  assert.doesNotMatch(p, /Освещение:/);
});

test('без имени и мира промпт всё равно годится, пробелы схлопываются', () => {
  const p = buildCharacterPrompt('  ', {face: '  круглое   лицо '});
  assert.match(p, /«Герой»/);
  assert.match(p, /Лицо: круглое лицо\./);
  assert.doesNotMatch(p, /Запрещено/);
});

test('мир считается заполненным по полю стиля', () => {
  assert.equal(worldFilled({look: ' '}), false);
  assert.equal(worldFilled(undefined), false);
  assert.equal(worldFilled({look: 'x'}), true);
});
