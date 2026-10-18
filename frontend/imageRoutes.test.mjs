import {readFile} from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const moduleUrl = source => 'data:text/javascript;base64,' + Buffer.from(source).toString('base64');
const compile = async file =>
  ts.transpileModule(await readFile(new URL(file, import.meta.url), 'utf8'), {
    compilerOptions: {module: ts.ModuleKind.ES2020, target: ts.ScriptTarget.ES2020},
  }).outputText;
const deps = {
  './api': moduleUrl('export const apiFetch = (...args) => globalThis.routeTest.fetch(...args);'),
  './chatLink': moduleUrl(
    `export const DEFAULT_CHAT_URL='https://chatgpt.com/'; export const getChatUrl=()=>''; export const copyTextFor=(p,r)=>p+'\\n'+r.join('\\n');`
  ),
  './localDrafts': moduleUrl('export const readLocal=(_,value)=>value; export const writeLocal=()=>true;'),
  './imageJobs': moduleUrl(await compile('./src/imageJobs.ts')),
};
const source = (await compile('./src/imageRoutes.ts')).replace(
  /from ['"]([^'"]+)['"]/g,
  (_, path) => `from '${deps[path]}'`
);
const {sendToChatGPT, sendToCodex, loadExternalJob} = await import(moduleUrl(source));
const {validateImageJobs} = await import(deps['./imageJobs']);
const job = {projectId: 'p1', prompt: 'A full prompt', target: 'gpt-image-2.5', referenceAssetIds: []};

function setup(fetch) {
  globalThis.routeTest = {fetch};
  const events = [];
  globalThis.window = {dispatchEvent: event => events.push(event.type)};
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: {clipboard: {writeText: async () => {}}},
  });
  return events;
}

test('full prompt and ordered references come from the detail endpoint, not activity', async () => {
  const prompt = 'Long prompt '.repeat(90);
  setup(async path => {
    assert.equal(path, '/api/external-jobs/job-1');
    return Response.json({
      id: 'job-1',
      prompt,
      copy_text: prompt + '\nImage 1 — location',
      references: [{index: 1, role: 'location', file_url: '/api/library/a/file'}],
    });
  });
  const details = await loadExternalJob('job-1');
  assert.equal(details.prompt, prompt);
  assert.ok(details.copy_text.length > 1000);
  assert.equal(details.references[0].role, 'location');
});

test('Codex batch is rejected before even the first job is written', async () => {
  let calls = 0;
  setup(async () => {
    calls++;
    return Response.json({});
  });
  await assert.rejects(sendToCodex([job, job]), /одно задание/);
  assert.equal(calls, 0);
});

test('validate all jobs before submission, including native limits and project boundaries', () => {
  assert.throws(() => validateImageJobs([job, {...job, projectId: 'p2'}], 'chatgpt'), /одному проекту/);
  assert.throws(() => validateImageJobs([{...job, prompt: 'x'.repeat(4001)}], 'codex'), /4000/);
  assert.throws(
    () => validateImageJobs([{...job, referenceAssetIds: Array(9).fill('a')}], 'codex'),
    /референсов/
  );
  assert.doesNotThrow(() => validateImageJobs([{...job, prompt: 'x'.repeat(4001)}], 'chatgpt'));
});

test('partial external batch reports saved count and exposes queue without automatic retry', async () => {
  let calls = 0;
  const events = setup(async () =>
    ++calls === 1 ? Response.json({}) : Response.json({detail: 'offline'}, {status: 503})
  );
  await assert.rejects(sendToChatGPT([job, {...job, prompt: 'second'}]), /Сохранено заданий: 1 из 2/);
  assert.equal(calls, 2);
  assert.ok(events.includes('studio:open-queue'));
});

test('manual route preserves full payload and does not navigate away before user opens chat', async () => {
  const prompt = 'Scenario '.repeat(80);
  setup(async (path, init) => {
    assert.equal(path, '/api/external-jobs');
    assert.equal(JSON.parse(init.body).prompt, prompt);
    return Response.json({});
  });
  const note = await sendToChatGPT([{...job, prompt}]);
  assert.match(note, /открой ChatGPT/);
});
