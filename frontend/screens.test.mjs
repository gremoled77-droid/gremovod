import {readFile} from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
async function module(file) {
  const source = await readFile(new URL(file, import.meta.url), 'utf8');
  const js = ts.transpileModule(source, {
    compilerOptions: {module: ts.ModuleKind.ES2020, target: ts.ScriptTarget.ES2020},
  }).outputText;
  return import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));
}
const {SCREENS, STAGES, TOOLS, isHidden, navMode} = await module('./src/screens.ts');
const {MODES} = await module('./src/workspaceRoute.ts');
test('beta menu: stages in order, hidden screens are out of menu and links', () => {
  assert.deepEqual(
    STAGES.map(s => s.title),
    ['Идея', 'Мир', 'Раскадровка', 'Кадры', 'Видео']
  );
  assert.deepEqual(
    TOOLS.map(s => s.title),
    ['Узлы', 'Библиотека']
  );
  for (const mode of ['audio', 'reels', 'files', 'economics', 'scene', 'refine', 'agents']) {
    assert.ok(isHidden(mode));
    assert.ok(!MODES.includes(mode));
  }
  assert.deepEqual(
    [...MODES].sort(),
    SCREENS.filter(s => s.group !== 'hidden')
      .map(s => s.mode)
      .sort()
  );
});
test('characters live inside the world screen', () => {
  assert.equal(navMode('characters'), 'styles');
  assert.equal(SCREENS.find(s => s.mode === 'characters').main, SCREENS.find(s => s.mode === 'styles').main);
});
