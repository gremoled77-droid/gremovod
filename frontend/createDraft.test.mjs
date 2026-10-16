import {readFile} from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
const source = await readFile(new URL('./src/createDraft.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: {module: ts.ModuleKind.ES2020, target: ts.ScriptTarget.ES2020},
}).outputText;
const {emptyCreateDraft, loadCreateDraft, saveCreateDraft} = await import(
  'data:text/javascript;base64,' + Buffer.from(compiled).toString('base64')
);
function store() {
  const data = new Map();
  return {data, getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value)};
}
test('restores editable inputs after remount, without restoring paid actions', () => {
  const storage = store();
  const draft = {...emptyCreateDraft(), prompt: 'Грэм встречает гостя', selected: ['qwen-image-2.1'],
    refs: ['ref-one'], options: {'qwen-image-2.1': {aspect_ratio: '16:9'}},
    motion: 'Медленная улыбка', videoOptions: {duration: 5}, queue: [{approved: true, request_id: 'paid'}]};
  assert.equal(saveCreateDraft('project-one', draft, storage), true);
  const restored = loadCreateDraft('project-one', storage);
  assert.equal(restored.prompt, draft.prompt);
  assert.deepEqual(restored.refs, draft.refs);
  assert.deepEqual(restored.options, draft.options);
  assert.deepEqual(restored.videoOptions, {duration: 5});
  assert.equal('queue' in restored, false);
  assert.equal([...storage.data.values()][0].includes('approved'), false);
});
test('projects have independent drafts and an empty prompt replaces old text', () => {
  const storage = store();
  saveCreateDraft('a', {...emptyCreateDraft(), prompt: 'Первый'}, storage);
  saveCreateDraft('b', {...emptyCreateDraft(), prompt: 'Второй', refs: ['b-only']}, storage);
  saveCreateDraft('a', {...emptyCreateDraft(), prompt: ''}, storage);
  assert.equal(loadCreateDraft('a', storage).prompt, '');
  assert.deepEqual(loadCreateDraft('a', storage).refs, []);
  assert.equal(loadCreateDraft('b', storage).prompt, 'Второй');
  assert.deepEqual(loadCreateDraft('b', storage).refs, ['b-only']);
});
test('corrupt or inaccessible storage does not prevent opening the screen', () => {
  assert.deepEqual(loadCreateDraft('a', {getItem: () => '{broken'}), emptyCreateDraft());
  const blocked = {getItem: () => {throw Error('denied');}, setItem: () => {throw Error('quota');}};
  assert.deepEqual(loadCreateDraft('a', blocked), emptyCreateDraft());
  assert.equal(saveCreateDraft('a', emptyCreateDraft(), blocked), false);
});
