import test from 'node:test';
import assert from 'node:assert/strict';
import {buildSteps, canConnect, hasCycle} from './src/workflowPlan.ts';

const n = (id, x, data) => ({id, position: {x, y: 0}, data});
const e = (source, target) => ({id: source + target, source, target});

test('промпт и референсы собираются слева направо, зависимый шаг ждёт', () => {
  const nodes = [
    n('t', 0, {kind: 'text', text: 'Грэм у такси'}),
    n('r', 10, {kind: 'reference', asset_id: 'a1'}),
    n('i1', 100, {kind: 'image', model: 'seedream-5-lite', title: 'Кадр'}),
    n('i2', 200, {kind: 'image', model: 'gpt-image-2.5', title: 'Правка'}),
  ];
  const edges = [e('t', 'i1'), e('r', 'i1'), e('i1', 'i2'), e('t', 'i2')];
  const {steps, problems} = buildSteps(nodes, edges, {});
  assert.deepEqual(problems, []);
  assert.equal(steps[0].prompt, 'Грэм у такси');
  assert.deepEqual(steps[0].refAssetIds, ['a1']);
  assert.deepEqual(steps[1].waitFor, ['i1']);
  const ready = buildSteps(nodes, edges, {i1: 'res1'}).steps[1];
  assert.deepEqual(ready.refAssetIds, ['res1']);
  assert.deepEqual(ready.waitFor, []);
});

test('цикл и недопустимые соединения отклоняются', () => {
  const a = n('a', 0, {kind: 'image', model: 'x'});
  const b = n('b', 1, {kind: 'image', model: 'x'});
  assert.equal(hasCycle([a, b], [e('a', 'b'), e('b', 'a')]), true);
  assert.equal(buildSteps([a, b], [e('a', 'b'), e('b', 'a')], {}).steps.length, 0);
  assert.equal(canConnect(n('t', 0, {kind: 'text'}), a), true);
  assert.equal(canConnect(a, n('t', 0, {kind: 'text'})), false);
});

test('без текста и модели — понятные проблемы', () => {
  const {problems} = buildSteps([n('i', 0, {kind: 'image', title: 'Кадр'})], [], {});
  assert.equal(problems.length, 2);
});

test('LLM-узел: порядок, вход и промпт изображения из ответа LLM', async () => {
  const {buildLlmSteps, llmInput, PENDING_LLM_TEXT} = await import('./src/workflowPlan.ts');
  const nodes = [
    n('t', 0, {kind: 'text', text: 'Грэм у такси'}),
    n('l1', 100, {kind: 'llm', model: 'gpt-5.6-luna', title: 'LLM'}),
    n('l2', 200, {kind: 'llm', model: 'gpt-5.6-terra', title: 'LLM 2'}),
    n('i', 300, {kind: 'image', model: 'seedream-5-lite', title: 'Кадр'}),
  ];
  const edges = [e('t', 'l1'), e('l1', 'l2'), e('l2', 'i')];
  const plan = buildLlmSteps(nodes, edges);
  assert.deepEqual(plan.problems, []);
  assert.deepEqual(
    plan.steps.map(s => s.nodeId),
    ['l1', 'l2']
  );
  assert.equal(llmInput(plan.steps[0], nodes, {}), 'Грэм у такси');
  assert.equal(llmInput(plan.steps[1], nodes, {l1: 'Подробный промпт'}), 'Подробный промпт');
  // без ответа и без запуска в этом прогоне — понятная проблема; с запуском — заглушка
  assert.equal(buildSteps(nodes, edges, {}).problems.length, 1);
  assert.equal(buildSteps(nodes, edges, {}, {pendingLlm: ['l2']}).steps[0].prompt, PENDING_LLM_TEXT);
  assert.equal(buildSteps(nodes, edges, {}, {llm: {l2: 'Готово'}}).steps[0].prompt, 'Готово');
});

test('LLM принимает только текст и другие LLM', async () => {
  const llm = n('l', 0, {kind: 'llm', model: 'x'});
  assert.equal(canConnect(n('t', 0, {kind: 'text'}), llm), true);
  assert.equal(canConnect(n('r', 0, {kind: 'reference'}), llm), false);
  assert.equal(canConnect(llm, n('i', 1, {kind: 'image'})), true);
});

test('цены узлов: оцениваются узлы с моделью и текстом, LLM — по тарифу', async () => {
  const {priceRequests, llmPrices} = await import('./src/workflowPriceModel.ts');
  const nodes = [
    n('t', 0, {kind: 'text', text: 'Грэм у такси'}),
    n('l', 100, {kind: 'llm', model: 'gpt-5.6-luna', title: 'LLM'}),
    n('i', 200, {kind: 'image', model: 'seedream-5-lite', title: 'Кадр'}),
    n('i2', 300, {kind: 'image', title: 'Без модели'}),
  ];
  const edges = [e('t', 'l'), e('l', 'i'), e('l', 'i2')];
  const requests = priceRequests(nodes, edges, {});
  assert.deepEqual(
    requests.map(r => r.nodeId),
    ['i']
  );
  assert.ok(requests[0].prompt.length > 0);
  const llm = llmPrices(nodes, edges);
  assert.ok(llm.l > 0 && llm.l < 0.01);
});

test('«Текст» с блоком GPT: уходит в GPT только по кнопке, на выход идёт ответ', async () => {
  const {buildLlmSteps, llmInput} = await import('./src/workflowPlan.ts');
  const t = n('t', 0, {kind: 'text', text: 'Грэм у такси', model: 'gpt-5.6-luna', title: 'Текст'});
  const i = n('i', 100, {kind: 'image', model: 'seedream-5-lite', title: 'Кадр'});
  const nodes = [t, i];
  const edges = [e('t', 'i')];
  // «Запустить всё» не отправляет текстовые узлы в GPT
  assert.equal(buildLlmSteps(nodes, edges).steps.length, 0);
  // кнопка узла: шаг с собственным текстом на входе
  const plan = buildLlmSteps(nodes, edges, ['t']);
  assert.deepEqual(plan.problems, []);
  assert.equal(plan.steps.length, 1);
  assert.equal(llmInput(plan.steps[0], nodes, {t: 'старый ответ'}), 'Грэм у такси');
  // до ответа в промпт идёт сам текст, после ответа — ответ GPT
  assert.equal(buildSteps(nodes, edges, {}).steps[0].prompt, 'Грэм у такси');
  const withOut = [{...t, data: {...t.data, output: 'Подробный промпт'}}, i];
  assert.equal(buildSteps(withOut, edges, {}).steps[0].prompt, 'Подробный промпт');
  // без модели и текста — понятные проблемы
  const bad = n('b', 0, {kind: 'text', text: '', title: 'Пусто'});
  assert.equal(buildLlmSteps([bad], [], ['b']).problems.length, 2);
});
