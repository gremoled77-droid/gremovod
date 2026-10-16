import test from 'node:test';
import assert from 'node:assert/strict';
import {mergeWorld, parseWorld} from './src/worldFromBrief.ts';

test('JSON достаётся из обёртки markdown и текста вокруг', () => {
  const w = parseWorld('Вот мир:\n```json\n{"look":" тёплый 2D ","palette":"охра","x":"лишнее"}\n```');
  assert.deepEqual(w, {look: 'тёплый 2D', palette: 'охра'});
});

test('мусор и пустой ответ дают понятную ошибку', () => {
  assert.throws(() => parseWorld('нет json'), /не похож на JSON/);
  assert.throws(() => parseWorld('{"look":'), /JSON|не похож/);
  assert.throws(() => parseWorld('{"x":"1","look":"  "}'), /нет полей/);
});

test('слияние: пустые заполняются, занятые отличающиеся уходят в вопрос, одинаковые молчат', () => {
  const {fill, conflicts} = mergeWorld(
    {look: 'старый', palette: '', camera: 'то же'},
    {
      look: 'новый',
      palette: 'охра',
      camera: 'то же',
      avoid: 'логотипы',
    }
  );
  assert.deepEqual(fill, {palette: 'охра', avoid: 'логотипы'});
  assert.deepEqual(conflicts, {look: 'новый'});
});
