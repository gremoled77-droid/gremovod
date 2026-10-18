import {readFile} from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
const source = await readFile(new URL('./src/hotkeyRules.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, {
  compilerOptions: {module: ts.ModuleKind.ES2020, target: ts.ScriptTarget.ES2020},
}).outputText;
const {comboOf, isTyping, allowedWhileTyping, ALT_DIGIT_MODES, HOTKEY_HELP} = await import(
  'data:text/javascript;base64,' + Buffer.from(js).toString('base64')
);

test('combos use physical keys, so the Russian layout works', () => {
  assert.equal(comboOf({key: 'Enter', ctrlKey: true}), 'mod+enter');
  assert.equal(comboOf({key: 'Enter', metaKey: true}), 'mod+enter');
  assert.equal(comboOf({key: 'л', code: 'KeyK', ctrlKey: true}), 'mod+k');
  assert.equal(comboOf({key: 'я', code: 'KeyZ', ctrlKey: true}), 'mod+z');
  assert.equal(comboOf({key: 'я', code: 'KeyZ', ctrlKey: true, shiftKey: true}), null);
  assert.equal(comboOf({key: '.', code: 'Slash'}), '/');
  assert.equal(comboOf({key: ',', code: 'Slash', shiftKey: true}), '?');
  assert.equal(comboOf({key: 'а', code: 'KeyF'}), 'f');
  assert.equal(comboOf({key: '3', code: 'Digit3', altKey: true}), 'alt+3');
  assert.equal(comboOf({key: 'Escape'}), 'escape');
  assert.equal(comboOf({key: 'Delete'}), 'delete');
  assert.equal(comboOf({key: 'a', code: 'KeyA'}), null);
  // без code (синтетические события) — по символу
  assert.equal(comboOf({key: '/'}), '/');
  assert.equal(comboOf({key: 'а'}), 'f');
  assert.equal(comboOf({key: 'k', ctrlKey: true}), 'mod+k');
  assert.equal(comboOf({key: '4', altKey: true}), 'alt+4');
  assert.equal(comboOf({key: 'ы', code: 'KeyS', ctrlKey: true}), 'mod+s');
  assert.equal(comboOf({key: 'а', code: 'KeyF', ctrlKey: true}), null);
});

test('single keys never fire while typing; Ctrl+Enter, Esc and Ctrl+K do', () => {
  assert.ok(isTyping({tagName: 'TEXTAREA'}));
  assert.ok(isTyping({tagName: 'INPUT', type: 'text'}));
  assert.ok(isTyping({tagName: 'DIV', isContentEditable: true}));
  assert.ok(!isTyping({tagName: 'INPUT', type: 'checkbox'}));
  assert.ok(!isTyping({tagName: 'BUTTON'}));
  assert.ok(!isTyping(null));
  for (const c of ['mod+enter', 'escape', 'mod+k', 'mod+s']) assert.ok(allowedWhileTyping(c));
  for (const c of ['/', '?', 'f', 'delete', 'mod+z', 'alt+1']) assert.ok(!allowedWhileTyping(c));
});

test('Alt+digit map and help cover the beta screens', () => {
  assert.deepEqual(
    [...ALT_DIGIT_MODES],
    ['home', 'studio', 'styles', 'storyboard', 'create', 'video', 'graph', 'archive']
  );
  assert.ok(HOTKEY_HELP.some(h => h.keys === '?'));
});
