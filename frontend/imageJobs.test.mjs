import {readFile} from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
const source = await readFile(new URL('./src/imageJobs.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, {
  compilerOptions: {module: ts.ModuleKind.ES2020, target: ts.ScriptTarget.ES2020},
}).outputText;
const {ROUTES, parseRoute, referenceRoles, externalJobBody, codexJobBody} = await import(
  'data:text/javascript;base64,' + Buffer.from(js).toString('base64')
);

const job = {
  projectId: 'p1',
  prompt: 'Грэм у машины',
  target: 'seedream-5-pro',
  referenceAssetIds: ['a', 'b'],
};

test('three routes, unknown saved value falls back to paid-safe API with review', () => {
  assert.deepEqual(
    ROUTES.map(r => r.id),
    ['api', 'chatgpt', 'codex']
  );
  assert.equal(parseRoute('codex'), 'codex');
  assert.equal(parseRoute('free-api'), 'api');
  assert.equal(parseRoute(null), 'api');
});

test('ChatGPT job keeps reference order and roles', () => {
  assert.deepEqual(referenceRoles(['a', 'b', 'c']), ['главный референс', 'референс', 'референс']);
  const body = externalJobBody(job, 'r1');
  assert.equal(body.service, 'chatgpt');
  assert.equal(body.target, 'seedream-5-pro');
  assert.deepEqual(body.references, [
    {asset_id: 'a', role: 'главный референс'},
    {asset_id: 'b', role: 'референс'},
  ]);
  assert.equal('node_id' in body, false);
  assert.equal(externalJobBody({...job, nodeId: 'n1'}, 'r2').node_id, 'n1');
});

test('Codex always targets a GPT Image model', () => {
  assert.equal(codexJobBody(job, 'r1').target, 'gpt-image-2.5');
  assert.equal(codexJobBody({...job, target: 'gpt-image-2'}, 'r1').target, 'gpt-image-2');
  assert.deepEqual(codexJobBody(job, 'r1').reference_asset_ids, ['a', 'b']);
  assert.equal(codexJobBody(job, 'r1').operation, 'generate');
});
