// Регрессия агрегатора QA Orchestrator: fail-closed при ошибках входа и запрет самостоятельной приёмки.
//
// Агрегатор — Code-узел n8n. Проверяем его как чистую функцию: подставляем $input.all() и читаем json.
// Запуск: node --test integrations/n8n/tests/
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, join} from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const workflow = JSON.parse(readFileSync(join(here, '..', 'workflows', 'qa-orchestrator.safe-draft.snapshot.json'), 'utf8'));
const node = workflow.nodes.find(n => n.name === 'Сбор вердиктов');
assert.ok(node, 'В снапшоте нет узла «Сбор вердиктов»');
const run = new Function('$input', node.parameters.jsCode);

const TEXT = ['text_quote', 'transcript_quote'];
const IMAGE = ['image_observation'];

function verdict(role, extra = {}) {
  const base = {
    role,
    model: 'mock-model',
    verdict: 'PASS',
    task_id: 'task-1',
    project_id: 'project-1',
    artifact_id: 'artifact-1',
    artifact_revision: 'rev-3',
    review_round: 1,
    review_phase: 'TEXT_PRECHECK',
    artifact_scope: 'TEXT',
    requested_scopes: ['TEXT'],
    checked_scopes: ['TEXT'],
    scope_results: {TEXT: 'PASS'},
    evidence: [{scope: 'TEXT', evidence_type: 'text_quote', source_text_revision: 'canon-7', quote: 'жёлтая машина'}],
    biggest_gap: null,
    missing_inputs: [],
    ...extra,
  };
  return base;
}

function receipt(extra = {}) {
  return {verified: true, review_id: 'review-1', artifact_revision: 'rev-3', ...extra};
}

function aggregate(items) {
  const out = run({all: () => items.map(json => ({json}))});
  return out[0].json;
}

const THREE = ['REVIEW-REQ', 'REVIEW-SYSTEM', 'REVIEW-CRAFT'];

test('ошибки входа несовместимы с флагом успеха', () => {
  // Точный сценарий из ревью: пакет помечен как проверенный, но содержит input_errors.
  const items = THREE.map(role => verdict(role, {evidence_verified_by_backend: true, input_errors: ['канон не утверждён']}));
  const out = aggregate(items);
  assert.equal(out.status, 'BLOCKED_INVALID_INPUT');
  assert.equal(out.text_precheck_passed, false);
  assert.equal(out.all_passed, false);
  assert.deepEqual(out.input_errors, ['канон не утверждён']);
});

test('ошибки входа в одном пакете несовместимы с флагом успеха', () => {
  const items = THREE.map((role, i) => verdict(role, {evidence_verified_by_backend: true, ...(i === 1 ? {input_errors: ['пустой текст']} : {})}));
  const out = aggregate(items);
  assert.equal(out.status, 'BLOCKED_INVALID_INPUT');
  assert.equal(out.text_precheck_passed, false);
  assert.equal(out.all_passed, false);
});

test('модель не может сама подтвердить свои доказательства', () => {
  const items = THREE.map(role => verdict(role, {evidence_verified_by_backend: true}));
  const out = aggregate(items);
  assert.equal(out.text_precheck_passed, false);
  assert.equal(out.all_passed, false);
  assert.notEqual(out.status, 'TEXT_PRECHECK_PASSED_AWAITING_OWNER');
});

test('серверная квитанция не отменяет блокировку по ошибкам входа', () => {
  const items = THREE.map(role => verdict(role, {server_receipt: receipt(), input_errors: ['канон не утверждён']}));
  const out = aggregate(items);
  assert.equal(out.status, 'BLOCKED_INVALID_INPUT');
  assert.equal(out.text_precheck_passed, false);
  assert.equal(out.all_passed, false);
});

test('серверная квитанция позволяет принять текстовую проверку', () => {
  const items = THREE.map(role => verdict(role, {server_receipt: receipt()}));
  const out = aggregate(items);
  assert.equal(out.status, 'TEXT_PRECHECK_PASSED_AWAITING_OWNER');
  assert.equal(out.text_precheck_passed, true);
  assert.equal(out.all_passed, false, 'TEXT_PRECHECK не даёт финальное принятие');
  assert.equal(out.final_release_approved, false);
  assert.equal(out.owner_approval_required, true);
});

test('квитанция другой ревизии не принимается', () => {
  const items = THREE.map(role => verdict(role, {server_receipt: receipt({artifact_revision: 'rev-2'})}));
  const out = aggregate(items);
  assert.equal(out.text_precheck_passed, false);
  assert.notEqual(out.status, 'TEXT_PRECHECK_PASSED_AWAITING_OWNER');
});

test('неполный набор ролей даёт BLOCKED_INVALID_REVIEW_SET', () => {
  const out = aggregate([verdict('REVIEW-REQ'), verdict('REVIEW-SYSTEM')]);
  assert.equal(out.status, 'BLOCKED_INVALID_REVIEW_SET');
  assert.equal(out.text_precheck_passed, false);
  assert.deepEqual(out.missing_or_duplicate_roles, ['REVIEW-CRAFT']);
});

test('дублирующаяся роль даёт BLOCKED_INVALID_REVIEW_SET', () => {
  const out = aggregate([verdict('REVIEW-REQ'), verdict('REVIEW-REQ'), verdict('REVIEW-SYSTEM')]);
  assert.equal(out.status, 'BLOCKED_INVALID_REVIEW_SET');
});

test('подтверждённый FAIL возвращает gap исполнителю', () => {
  const items = THREE.map(role =>
    verdict(role, {
      verdict: 'FAIL',
      scope_results: {TEXT: 'FAIL'},
      server_receipt: receipt(),
      biggest_gap: 'машина красная, а канон требует жёлтую',
    })
  );
  const out = aggregate(items);
  assert.equal(out.status, 'CHANGES_REQUESTED');
  assert.equal(out.text_precheck_passed, false);
  assert.equal(out.next_action, 'return_evidenced_gap_to_original_builder');
});

test('неподтверждённый FAIL не запускает цикл правок', () => {
  const items = THREE.map(role => verdict(role, {verdict: 'FAIL', scope_results: {TEXT: 'FAIL'}}));
  const out = aggregate(items);
  assert.notEqual(out.status, 'CHANGES_REQUESTED');
  assert.equal(out.text_precheck_passed, false);
});

test('BLOCKED от критика остаётся честным блокером', () => {
  const items = THREE.map(role => verdict(role, {verdict: 'BLOCKED', scope_results: {TEXT: 'BLOCKED'}}));
  const out = aggregate(items);
  assert.equal(out.status, 'BLOCKED_TEXT_REVIEW_NOT_CONNECTED');
  assert.equal(out.text_precheck_passed, false);
});

test('TEXT-доказательство не повышает IMAGE до PASS', () => {
  const items = THREE.map(role =>
    verdict(role, {
      artifact_scope: 'IMAGE',
      requested_scopes: ['IMAGE'],
      checked_scopes: ['TEXT'],
      scope_results: {TEXT: 'PASS', IMAGE: 'BLOCKED'},
      evidence: [{scope: 'TEXT', evidence_type: 'text_quote', source_text_revision: 'canon-7', quote: 'машина'}],
      server_receipt: receipt(),
    })
  );
  const out = aggregate(items);
  assert.equal(out.text_precheck_passed, false);
  assert.notEqual(out.status, 'TEXT_PRECHECK_PASSED_AWAITING_OWNER');
});

test('финальная фаза требует всех трёх ролей и не выдаёт релиз', () => {
  const items = THREE.map(role =>
    verdict(role, {
      review_phase: 'FINAL_MEDIA',
      artifact_scope: 'IMAGE',
      requested_scopes: ['IMAGE'],
      checked_scopes: ['IMAGE'],
      scope_results: {IMAGE: 'PASS'},
      evidence: [{scope: 'IMAGE', evidence_type: 'image_observation', source_asset_id: 'asset-9', quote: 'жёлтая'}],
      server_receipt: receipt(),
    })
  );
  const out = aggregate(items);
  assert.equal(out.status, 'AWAITING_OWNER_APPROVAL');
  assert.equal(out.all_passed, true);
  assert.equal(out.text_precheck_passed, false);
  assert.equal(out.final_release_approved, false);
  assert.equal(out.quality_claim, false);
});

test('две роли в финальной фазе недостаточно для прохода', () => {
  const items = [verdict('REVIEW-REQ'), verdict('REVIEW-SYSTEM'), verdict('REVIEW-CRAFT')].slice(0, 2).map(role =>
    verdict(role, {
      review_phase: 'FINAL_MEDIA',
      artifact_scope: 'IMAGE',
      requested_scopes: ['IMAGE'],
      checked_scopes: ['IMAGE'],
      scope_results: {IMAGE: 'PASS'},
      evidence: [{scope: 'IMAGE', evidence_type: 'image_observation', source_asset_id: 'asset-9', quote: 'жёлтая'}],
      server_receipt: receipt(),
    })
  );
  const out = aggregate(items);
  assert.equal(out.all_passed, false);
  assert.notEqual(out.status, 'AWAITING_OWNER_APPROVAL');
});

test('тип доказательства должен соответствовать области', () => {
  const items = THREE.map(role =>
    verdict(role, {
      requested_scopes: ['IMAGE'],
      checked_scopes: ['IMAGE'],
      scope_results: {IMAGE: 'PASS'},
      evidence: [{scope: 'IMAGE', evidence_type: 'text_quote', source_text_revision: 'canon-7', quote: 'машина'}],
      server_receipt: receipt(),
    })
  );
  const out = aggregate(items);
  assert.equal(out.text_precheck_passed, false);
  assert.equal(out.all_passed, false);
});

test('IMAGE в TEXT_PRECHECK не проходит как текст', () => {
  const items = THREE.map(role =>
    verdict(role, {
      requested_scopes: ['IMAGE'],
      checked_scopes: ['IMAGE'],
      scope_results: {IMAGE: 'PASS'},
      evidence: [{scope: 'IMAGE', evidence_type: 'image_observation', source_asset_id: 'asset-9', quote: 'жёлтая'}],
      server_receipt: receipt(),
    })
  );
  const out = aggregate(items);
  assert.equal(out.text_precheck_passed, false);
});
