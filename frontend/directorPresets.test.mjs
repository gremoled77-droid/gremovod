import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DIRECTOR_PRESETS,
  DIRECTOR_TEMPLATE,
  appendDirectorBlock,
  findDirectorPreset,
} from './src/directorPresets.ts';

test('каркас содержит шесть режиссёрских строк', () => {
  const labels = DIRECTOR_TEMPLATE.split('\n').map(l => l.split(':')[0]);
  assert.deepEqual(labels, ['FRAME', 'DOMINANT', 'SYMBOL', 'SHIFT', 'CAMERA', 'LIGHT']);
});

test('заготовки кадра и камеры называют Грэма и ВАЗ-2106 и содержат все строки', () => {
  const frames = DIRECTOR_PRESETS.filter(p => p.group !== 'story');
  assert.ok(frames.length >= 8);
  for (const p of frames) {
    for (const label of ['FRAME:', 'DOMINANT:', 'SYMBOL:', 'SHIFT:', 'CAMERA:', 'LIGHT:'])
      assert.ok(p.text.includes(label), `${p.id} без ${label}`);
    assert.match(p.text, /Grem/, p.id);
  }
  assert.ok(DIRECTOR_PRESETS.some(p => /VAZ-2106/.test(p.text)));
});

test('мотивации камеры: reveal, follow, push in, pull back', () => {
  const camera = DIRECTOR_PRESETS.filter(p => p.group === 'camera').map(p => p.id);
  assert.deepEqual(camera, ['reveal', 'follow', 'push', 'pull']);
});

test('идентификаторы уникальны, поиск работает', () => {
  const ids = DIRECTOR_PRESETS.map(p => p.id);
  assert.equal(new Set(ids).size, ids.length);
  assert.equal(findDirectorPreset('five')?.group, 'story');
  assert.equal(findDirectorPreset('нет'), undefined);
});

test('вставка в конец промпта без дублей', () => {
  const t = DIRECTOR_TEMPLATE;
  assert.equal(appendDirectorBlock('', t), t);
  assert.equal(appendDirectorBlock('Night street.\n', t), 'Night street.\n\n' + t);
  const once = appendDirectorBlock('Night street.', t);
  assert.equal(appendDirectorBlock(once, t), once);
});
