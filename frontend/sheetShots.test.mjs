import test from 'node:test';
import assert from 'node:assert/strict';
import {
  batchTotal,
  belongsToSheet,
  HERO_DEFAULT,
  HERO_SHOTS,
  LOCATION_SHOTS,
  locationShotPrompt,
  pickShots,
  readShotLabel,
} from './src/sheetShots.ts';
import {heroShotPrompt} from './src/characterPrompt.ts';

const hero = {species: 'таксист', costume: 'красная кепка'};
const world = {look: 'тёплая 2D', avoid: 'логотипы'};

test('запрос листа героя: описание, мир, ракурс и подпись читается обратно', () => {
  const p = heroShotPrompt('Грэм', hero, world, HERO_SHOTS[1]);
  assert.match(p, /Лист персонажа «Грэм» \(лист героя/);
  assert.match(p, /Одежда: красная кепка\./);
  assert.match(p, /Стиль мира: тёплая 2D\./);
  assert.doesNotMatch(p, /вид спереди, нейтральная поза/);
  assert.equal(readShotLabel(p), 'Профиль');
  assert.equal(belongsToSheet(p, 'hero', 'Грэм'), true);
  assert.equal(belongsToSheet(p, 'hero', 'Катя'), false);
  assert.equal(belongsToSheet(p, 'location', 'Грэм'), false);
});

test('запрос вариации локации: ракурс, мир, принадлежность по имени', () => {
  const p = locationShotPrompt('Двор', 'панельки, гаражи', world, LOCATION_SHOTS[2]);
  assert.match(p, /Вариации локации «Двор»/);
  assert.match(p, /Описание: панельки, гаражи\./);
  assert.equal(readShotLabel(p), 'Обратная точка');
  assert.equal(belongsToSheet(p, 'location', 'Двор'), true);
  assert.equal(belongsToSheet('Обычный промпт', 'location', 'Двор'), false);
  assert.equal(readShotLabel(undefined), '');
});

test('набор по умолчанию: 8 ракурсов, порядок как в каталоге, не больше 12', () => {
  assert.equal(pickShots(HERO_SHOTS, HERO_DEFAULT).length, 8);
  assert.deepEqual(
    pickShots(HERO_SHOTS, ['joy', 'front']).map(s => s.key),
    ['front', 'joy']
  );
  assert.deepEqual(pickShots(HERO_SHOTS, ['нет']), []);
  const many = Array.from({length: 15}, (_, i) => ({key: 'k' + i, label: 'L' + i, prompt: ''}));
  assert.equal(
    pickShots(
      many,
      many.map(s => s.key)
    ).length,
    12
  );
});

test('сумма оценок пакета без накопления погрешности', () => {
  assert.equal(batchTotal(Array.from({length: 8}, () => ({usd: 0.068}))), 0.544);
  assert.equal(batchTotal([]), 0);
});
