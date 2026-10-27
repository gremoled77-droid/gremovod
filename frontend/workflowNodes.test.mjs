import test from 'node:test';
import assert from 'node:assert/strict';
import {VIDEO_MODELS, buildLlmSteps, buildSteps, canConnect, llmInput} from './src/workflowPlan.ts';

const n = (id, x, data) => ({id, position: {x, y: 0}, data});
const e = (source, target) => ({id: source + target, source, target});

test('узел «Видео»: промпт, первый кадр из референса, параметры по умолчанию', () => {
  assert.ok(VIDEO_MODELS['minimax-h3']);
  const nodes = [
    n('t', 0, {kind: 'text', text: 'Грэм поворачивается к гостю'}),
    n('r', 10, {kind: 'reference', asset_id: 'grem'}),
    n('a', 20, {kind: 'audio', asset_id: 'voice'}),
    n('v', 300, {kind: 'video', model: 'minimax-h3', title: 'Ролик', options: {duration: 8}}),
  ];
  const edges = [e('t', 'v'), e('r', 'v'), e('a', 'v')];
  assert.equal(canConnect(nodes[2], nodes[3]), false);
  const {steps, problems} = buildSteps(nodes, edges, {});
  assert.deepEqual(problems, []);
  assert.equal(steps.length, 1);
  assert.deepEqual(steps[0].refAssetIds, ['grem']);
  assert.deepEqual(steps[0].options, {resolution: '480p', duration: 8, aspect_ratio: '16:9'});
});

test('видео: больше референсов, чем принимает H3, и неизвестная модель — проблемы', () => {
  const nodes = [
    n('t', 0, {kind: 'text', text: 'x'}),
    n('r1', 10, {kind: 'reference', asset_id: 'a'}),
    n('r2', 11, {kind: 'reference', asset_id: 'b'}),
    n('v', 300, {kind: 'video', model: 'minimax-h3', title: 'Ролик'}),
    n('w', 400, {kind: 'video', model: 'unknown', title: 'Другой'}),
  ];
  const edges = [e('t', 'v'), e('r1', 'v'), e('r2', 'v'), e('t', 'w')];
  const {problems} = buildSteps(nodes, edges, {});
  assert.ok(problems.some(p => p.includes('не больше 1')));
  assert.ok(problems.some(p => p.includes('не поддерживается')));
});

test('файл с текстом подаётся в LLM, PDF без текста — проблема; звук и файл не идут в картинку', () => {
  const nodes = [
    n('f', 0, {kind: 'file', name: 'идея.md', excerpt: 'Ночной Минск, дождь'}),
    n('p', 1, {kind: 'file', name: 'brief.pdf', title: 'PDF'}),
    n('l', 100, {kind: 'llm', model: 'gpt-5.6-luna', title: 'LLM'}),
    n('l2', 200, {kind: 'llm', model: 'gpt-5.6-luna', title: 'LLM 2'}),
    n('i', 400, {kind: 'image', model: 'seedream-5-lite', title: 'Кадр'}),
    n('au', 5, {kind: 'audio', asset_id: 'x'}),
  ];
  const plan = buildLlmSteps(nodes, [e('f', 'l')]);
  assert.equal(llmInput(plan.steps[0], nodes, {}), '[Файл: идея.md]\nНочной Минск, дождь');
  const pdfOnly = buildLlmSteps(nodes, [e('p', 'l2')]);
  assert.ok(pdfOnly.problems.some(p => p.includes('PDF не читается')));
  assert.equal(canConnect(nodes[0], nodes[4]), false);
  assert.equal(canConnect(nodes[5], nodes[4]), false);
  assert.equal(canConnect(nodes[0], nodes[2]), true);
  assert.equal(canConnect(nodes[2], nodes[3]), true);
});
