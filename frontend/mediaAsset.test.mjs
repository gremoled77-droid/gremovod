import {readFile} from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
const source = await readFile(new URL('./src/mediaAsset.ts', import.meta.url), 'utf8');
const code = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ES2020}}).outputText;
const {mediaPrompt, mediaModel, sourceChat, assetIdFromUrl, copyMediaPrompt, withoutMediaItem} = await import(
  'data:text/javascript;base64,' + Buffer.from(code).toString('base64')
);
test('reads prompts from native, adapter and legacy generation metadata', () => {
  assert.equal(mediaPrompt({request: {payload: {input: {prompt: 'Грэм в такси'}}}}), 'Грэм в такси');
  assert.equal(mediaPrompt({request: {model_id: 'm', prompt: 'Новый кадр'}}), 'Новый кадр');
  assert.equal(mediaPrompt({prompt: 'original', request: {prompt: 'fallback'}}), 'original');
  assert.equal(mediaPrompt({request: null}), '');
  assert.equal(mediaModel({requested_model: 'gpt-image-2.5'}), 'gpt-image-2.5');
  assert.equal(mediaModel({request: {model_id: 'seedream-5-lite'}}), 'seedream-5-lite');
});
test('source chat accepts only known chat destinations and genuine native threads', () => {
  assert.equal(
    sourceChat({provider: 'codex_chat', thread_id: '01a13e25-939c-7b73-9c0a-669abc8aa6a7'}),
    'codex://threads/01a13e25-939c-7b73-9c0a-669abc8aa6a7'
  );
  assert.equal(sourceChat({chat_url: 'https://chatgpt.com/c/example'}), 'https://chatgpt.com/c/example');
  for (const chat_url of [
    'javascript:alert(1)',
    'https://chatgpt.com.evil.test/c/id',
    'https://user:pass@chatgpt.com/',
    'http://chatgpt.com/',
  ])
    assert.equal(sourceChat({chat_url}), null);
  assert.equal(sourceChat({provider: 'external', thread_id: '../../other'}), null);
  assert.equal(assetIdFromUrl('/api/library/my-id/file'), 'my-id');
  assert.equal(assetIdFromUrl('https://evil.test/api/library/my-id/file'), undefined);
});
test('missing or denied clipboard never produces a success', async () => {
  assert.equal(await copyMediaPrompt('prompt'), false);
  assert.equal(
    await copyMediaPrompt('prompt', {
      writeText: async () => {
        throw Error('denied');
      },
    }),
    false
  );
  let copied;
  assert.equal(
    await copyMediaPrompt('prompt', {
      writeText: async value => {
        copied = value;
      },
    }),
    true
  );
  assert.equal(copied, 'prompt');
});
test('removing another image retains the active image and removing the last closes the viewer', () => {
  const items = ['a', 'b', 'c'].map(assetId => ({url: '/api/library/' + assetId + '/file', assetId}));
  const view = withoutMediaItem({items, index: 2}, 'a');
  assert.equal(view.items[view.index].assetId, 'c');
  const next = withoutMediaItem({items, index: 1}, 'b');
  assert.equal(next.items[next.index].assetId, 'c');
  assert.equal(withoutMediaItem({items: [items[0]], index: 0}, 'a'), null);
});
