import test from 'node:test';
import assert from 'node:assert/strict';
import {buildMotionPrompt, EMPTY_MOTION, overload, withFramePrefix} from './src/motionPrompt.ts';

const ctx = {heroes: [{name: 'Грэм', look: 'таксист, красная кепка'}]};

test('формула: камера, субъект с действием, окружение, свет и страховки по порядку', () => {
  const p = buildMotionPrompt(
    {...EMPTY_MOTION, action: ['breathe', 'glance'], scenery: ['rain'], light: ['passing']},
    ctx
  );
  const parts = p.split('. ');
  assert.match(parts[0], /^Slow push in, very subtle camera movement$/);
  assert.match(parts[1], /^Грэм \(таксист, красная кепка\): subtle breathing, eyes glance to the side$/);
  assert.match(parts[2], /^Raindrops sliding down the glass$/);
  assert.match(parts[3], /^Headlights of a passing car sweeping across$/);
  assert.match(parts[4], /Maintain subject consistency, no morphing, minimal motion/);
});

test('минимальное движение сводит амплитуду к «very subtle», без него берётся выбранная', () => {
  const loose = buildMotionPrompt({...EMPTY_MOTION, minimal: false, amplitude: 'large', noMorph: false}, ctx);
  assert.match(loose, /pronounced camera movement/);
  assert.doesNotMatch(loose, /no morphing|minimal motion/);
  assert.match(buildMotionPrompt({...EMPTY_MOTION, amplitude: 'large'}, ctx), /very subtle camera movement/);
});

test('статичная камера не получает слов про скорость и амплитуду', () => {
  const p = buildMotionPrompt({...EMPTY_MOTION, camera: 'static', action: []}, {heroes: []});
  assert.match(p, /^Locked-off static camera\./);
  assert.doesNotMatch(p, /slow|subtle camera/i);
});

test('мусорные слова в свободном тексте вычищаются', () => {
  const p = buildMotionPrompt({...EMPTY_MOTION, action: [], actionNote: 'he smiles, 8K masterpiece'}, ctx);
  assert.match(p, /he smiles/);
  assert.doesNotMatch(p, /8K|masterpiece/i);
});

test('перегрузка: несколько крупных действий и цепочки дают подсказку', () => {
  assert.equal(overload(EMPTY_MOTION).warn, false);
  const big = overload({...EMPTY_MOTION, actionNote: 'встал, повернулся и вышел'});
  assert.equal(big.warn, true);
  assert.match(big.reasons[0], /несколько крупных действий/);
  const chain = overload({...EMPTY_MOTION, actionNote: 'he stands up and then walks away'});
  assert.equal(chain.warn, true);
  assert.equal(overload({...EMPTY_MOTION, actionNote: 'смотрит в окно'}).warn, false);
  const many = overload({...EMPTY_MOTION, action: ['breathe', 'glance', 'lips', 'blink'], actionNote: ''});
  assert.equal(many.warn, true);
  assert.match(many.reasons[0], /больше трёх/);
});

test('для Seedance первым идёт тег стартового кадра, для остальных промпт не меняется', () => {
  assert.match(
    withFramePrefix('seedance-2.5', 'Slow push in.'),
    /^@image1 is the opening frame.*Slow push in\.$/
  );
  assert.equal(withFramePrefix('minimax-h3', 'Slow push in.'), 'Slow push in.');
});
