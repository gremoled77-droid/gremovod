import {readFile} from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
const source = await readFile(new URL('./src/visualPlan.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: {module: ts.ModuleKind.ES2020, target: ts.ScriptTarget.ES2020},
}).outputText;
const {tensionWarnings, sectorJumps, emptyPlan, planFromAnalysis, describeAnalysis} = await import(
  'data:text/javascript;base64,' + Buffer.from(compiled).toString('base64')
);
const shot = (label, story, visual, extra = {}) => ({
  id: label,
  label,
  space: '',
  line: '',
  sector_start: null,
  sector_end: null,
  story,
  visual,
  ...extra,
});
test('does not warn when data is missing or short', () => {
  assert.deepEqual(tensionWarnings([]), []);
  assert.deepEqual(tensionWarnings([shot('1.1', null, null), shot('1.2', 5, null)]), []);
  assert.equal(emptyPlan().story, null);
});
test('flat visual line and weak climax are reported', () => {
  const flat = [1, 3, 8, 4].map((s, i) => shot('1.' + i, s, 5));
  assert.ok(tensionWarnings(flat).some(w => w.includes('плоский')));
  const weak = [shot('1.1', 1, 9), shot('1.2', 4, 5), shot('1.3', 9, 3), shot('1.4', 2, 1)];
  assert.ok(tensionWarnings(weak).some(w => w.includes('кульминации')));
});
test('healthy parallel curve gives no warnings', () => {
  const ok = [
    [1, 1],
    [3, 3],
    [6, 6],
    [9, 10],
    [2, 2],
  ].map(([s, v], i) => shot('1.' + i, s, v));
  assert.deepEqual(tensionWarnings(ok), []);
});
test('repeating space and line three times is reported', () => {
  const same = [1, 2, 3].map(i => shot('1.' + i, null, null, {space: 'flat', line: 'horizontal'}));
  assert.equal(tensionWarnings(same).length, 1);
});
test('sector jumps only compare filled neighbours', () => {
  const list = [
    shot('1', null, null, {sector_end: 3}),
    shot('2', null, null, {sector_start: 3, sector_end: 7}),
    shot('3', null, null, {sector_start: 1}),
    shot('4', null, null),
  ];
  assert.deepEqual(sectorJumps(list), [{from: '2', to: '3', a: 7, b: 1}]);
});

test('analysis fills only empty plan fields', () => {
  const analysis = {
    tone: {range: 0.8, mean: 0.4, dark_share: 0.5, light_share: 0.1, hint: 'conceal'},
    color: {saturation: 0.3, warm: 0.2, cool: 0.1, dominant_hue: 'оранжевый'},
    lines: {dominant: 'diagonal'},
    attention: {brightest_sector: 3, contrast_sector: 5, sector: 3},
    focus: {blur_share: 0.6, hint: 'мягкий фон'},
    visual_intensity: 7,
  };
  const filled = planFromAnalysis({...emptyPlan(), line: 'horizontal', visual: 2}, analysis);
  assert.equal(filled.line, 'horizontal');
  assert.equal(filled.visual, 2);
  assert.equal(filled.tone, 'conceal');
  assert.equal(filled.sector_start, 3);
  assert.equal(filled.sector_end, 3);
  assert.ok(describeAnalysis(analysis).some(t => t.includes('мягкий фон')));
});
