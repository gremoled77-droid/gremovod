import {readFile} from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';
const source = await readFile(new URL('./src/shotContract.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: {module: ts.ModuleKind.ES2020, target: ts.ScriptTarget.ES2020},
}).outputText;
const {
  addFact,
  cloneContract,
  contractPayload,
  emptyContract,
  emptyFact,
  filledFacts,
  issueCounts,
  removeFact,
  seriesIssues,
  shotIssues,
  sortIssues,
  toggleEvent,
  updateFact,
  validateDraft,
} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));

const fact = (patch = {}) => ({...emptyFact(), ...patch});

test('новый контракт заполнен безопасными значениями', () => {
  const contract = emptyContract('shot-1', 'scene-1');
  assert.equal(contract.shot_id, 'shot-1');
  assert.equal(contract.scene_id, 'scene-1');
  assert.equal(contract.status, 'draft');
  assert.equal(contract.duration_sec, 3);
  assert.deepEqual(contract.physical_state.opening, []);
  assert.equal(contract.camera.coordinate_space, 'actor_world');
});

test('строки состояния добавляются, меняются и убираются', () => {
  const rows = [fact({subject_id: 'vaz'})];
  const added = addFact(rows);
  assert.equal(added.length, 2);
  assert.equal(added[1].subject_id, '');
  const changed = updateFact(rows, 0, {predicate: 'door_state'});
  assert.equal(changed[0].predicate, 'door_state');
  assert.equal(changed[0].subject_id, 'vaz');
  assert.equal(removeFact(rows, 0).length, 0);
});

test('пустые строки не уходят на сервер, заполненные остаются', () => {
  const rows = [fact(), fact({subject_id: 'vaz', predicate: 'door_state', value: 'closed'})];
  assert.equal(filledFacts(rows).length, 1);
  const payload = contractPayload(emptyContract('shot-1', 'scene-1'));
  assert.deepEqual(payload.physical_state.opening, []);
  assert.deepEqual(payload.source_event_ids, []);
});

test('пробелы убираются, а пустые необязательные поля становятся null', () => {
  const contract = emptyContract('shot-1', 'scene-1');
  contract.physical_state.transitions = [
    fact({subject_id: ' vaz ', predicate: 'door_state', from_value: '', to_value: ' open '}),
  ];
  const payload = contractPayload(contract);
  const transition = payload.physical_state.transitions[0];
  assert.equal(transition.subject_id, 'vaz');
  assert.equal(transition.from_value, null);
  assert.equal(transition.to_value, 'open');
});

test('форма проверяется до отправки', () => {
  const contract = emptyContract('shot-1', 'scene-1');
  assert.deepEqual(validateDraft(contract), []);
  contract.duration_sec = 0;
  assert.ok(validateDraft(contract).some(problem => problem.includes('длительность')));
  contract.duration_sec = 2;
  contract.physical_state.opening = [fact({subject_id: 'vaz'})];
  assert.ok(validateDraft(contract).some(problem => problem.includes('предмет и предикат')));
  contract.physical_state.opening = [];
  contract.physical_state.transitions = [fact({subject_id: 'vaz', predicate: 'door_state'})];
  assert.ok(validateDraft(contract).some(problem => problem.includes('было')));
});

test('замечания сортируются: сначала ошибки, затем по коду и пути', () => {
  const issues = [
    {shot_id: 'a', code: 'continuity_chain_break', severity: 'warning', path: 'shots[1]', message: 'w'},
    {shot_id: 'a', code: 'continuity_locked_change', severity: 'error', path: 'shots[1]', message: 'e2'},
    {shot_id: 'b', code: 'asset_unknown', severity: 'error', path: 'shots[0]', message: 'e1'},
  ];
  const sorted = sortIssues(issues);
  assert.deepEqual(
    sorted.map(issue => issue.code),
    ['asset_unknown', 'continuity_locked_change', 'continuity_chain_break']
  );
  assert.deepEqual(issueCounts(issues), {error: 2, warning: 1, info: 0});
});

test('замечания делятся на кадр и серию', () => {
  const issues = [
    {shot_id: 'a', code: 'one', severity: 'error', path: '', message: ''},
    {shot_id: null, code: 'two', severity: 'warning', path: '', message: ''},
  ];
  assert.equal(shotIssues(issues, 'a').length, 1);
  assert.equal(seriesIssues(issues, 'a').length, 1);
  assert.equal(seriesIssues(issues, 'b').length, 2);
});

test('событие привязывается и отвязывается без дублей', () => {
  assert.deepEqual(toggleEvent([], 'card-1'), ['card-1']);
  assert.deepEqual(toggleEvent(['card-1'], 'card-2'), ['card-1', 'card-2']);
  assert.deepEqual(toggleEvent(['card-1', 'card-2'], 'card-1'), ['card-2']);
});

test('копия контракта не связана с исходным', () => {
  const contract = emptyContract('shot-1', 'scene-1');
  contract.physical_state.opening = [fact({subject_id: 'vaz'})];
  const copy = cloneContract(contract);
  copy.physical_state.opening[0].subject_id = 'bus';
  assert.equal(contract.physical_state.opening[0].subject_id, 'vaz');
});
