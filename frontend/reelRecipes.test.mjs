import test from 'node:test';
import assert from 'node:assert/strict';
import {defaultValues, fillPrompt, filterRecipes} from './src/reelRecipes.ts';

const looks = {phone: {label: 'Телефон', text: 'RAW PHONE'}, cartoon: {label: 'Мульт', text: 'CARTOON'}};
const recipe = (over = {}) => ({
  id: 'r1',
  title: 'Ночной гость',
  hook: 'зверь у машины',
  family: 'Страшилка',
  looks: ['phone', 'cartoon'],
  fields: [{key: 'hero', label: 'Герой', default: ' Грэм '}],
  ...over,
});

test('значения по умолчанию включают поля и первый стиль', () => {
  assert.deepEqual(defaultValues(recipe()), {hero: ' Грэм ', look: 'phone'});
  assert.deepEqual(defaultValues(recipe({looks: []})), {hero: ' Грэм '});
});

test('шаблон подставляет поля и текст стиля, неизвестное оставляет как есть', () => {
  const text = fillPrompt('{{look}} / {{hero}} / {{unknown}}', {hero: ' Грэм ', look: 'cartoon'}, looks);
  assert.equal(text, 'CARTOON / Грэм / {{unknown}}');
});

test('стиль без описания не ломает шаблон', () => {
  assert.equal(fillPrompt('{{look}}', {look: 'nope'}, looks), '{{look}}');
});

test('фильтр по семейству и поиску', () => {
  const list = [recipe(), recipe({id: 'r2', title: 'Селфи', hook: 'тюлень', family: 'Тренд'})];
  assert.equal(filterRecipes(list, 'all', '').length, 2);
  assert.deepEqual(
    filterRecipes(list, 'Тренд', '').map(r => r.id),
    ['r2']
  );
  assert.deepEqual(
    filterRecipes(list, 'all', ' ТЮЛЕНЬ ').map(r => r.id),
    ['r2']
  );
  assert.equal(filterRecipes(list, 'Тренд', 'зверь').length, 0);
});
