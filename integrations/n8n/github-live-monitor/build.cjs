'use strict';
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const core = fs.readFileSync(path.join(__dirname, 'core.cjs'), 'utf8').split('module.exports =')[0];
const fixtures = fs.readFileSync(path.join(__dirname, 'fixtures.cjs'), 'utf8').split('module.exports =')[0];
const tests = fs.readFileSync(path.join(__dirname, 'tests.cjs'), 'utf8').split('function runTests')[1].split('if (require.main')[0];
const table = { __rl: true, mode: 'name', value: 'GremoVOD_GitHub_Live_Monitor_Events' };
const nodes = [];
const links = [];
const exp = text => `={{ ${text} }}`;
function add(id, type, version, parameters, extra = {}, trigger = false) {
  nodes.push({ id, type: `n8n-nodes-base.${type}`, version, config: { name: id, parameters, ...extra }, output: [{ sample: true }], trigger });
  return id;
}
function code(id, body, extra = {}) { return add(id, 'code', 2, { mode: 'runOnceForAllItems', language: 'javaScript', jsCode: body }, extra); }
function mapping(values) {
  return { mappingMode: 'defineBelow', value: values, schema: Object.keys(values).map(id => ({ id, displayName: id, type: 'string', required: false, defaultMatch: false, display: true, canBeUsedToMatch: true })) };
}
function update(id, values, inputId = exp('$json.row_id')) {
  return add(id, 'dataTable', 1.1, { resource: 'row', operation: 'update', dataTableId: table, matchType: 'allConditions', filters: { conditions: [{ keyName: 'id', condition: 'eq', keyValue: inputId }] }, columns: mapping(values) });
}
add('GitHub Trigger', 'githubTrigger', 1, { owner: { __rl: true, mode: 'name', value: 'gremoled77-droid' }, repository: { __rl: true, mode: 'name', value: 'gremovod' }, events: ['push', 'pull_request', 'pull_request_review', 'pull_request_review_comment', 'issue_comment', 'check_run', 'check_suite', 'status'], options: { insecureSSL: false } }, { credentials: { githubApi: { newCredential: 'GitHub monitor read and hooks' } } }, true);
code('Verify Event', `${core}\nreturn $input.all().map(i => ({json: verify(i.json)}));`, { onError: 'continueErrorOutput' });
add('Current GitHub Snapshot', 'httpRequest', 4.5, { method: 'GET', url: exp('$json.snapshot_url'), authentication: 'predefinedCredentialType', nodeCredentialType: 'githubApi', options: { timeout: 10000 } }, { credentials: { githubApi: { newCredential: 'GitHub monitor read and hooks' } }, retryOnFail: true, maxTries: 2, waitBetweenTries: 1000, onError: 'continueRegularOutput' });
code('Normalize Event', `${core}\nconst input = $('Verify Event').first().json;\nconst event = normalize(input, $input.first().json);\nreturn [{json: event || {kind: ''}}];`, { onError: 'continueErrorOutput' });
add('Event Filter', 'filter', 2.3, { conditions: { options: { caseSensitive: true, typeValidation: 'strict', leftValue: '' }, conditions: [{ leftValue: exp('$json.kind'), rightValue: '', operator: { type: 'string', operation: 'notEmpty' } }], combinator: 'and' } });
code('Prepare Event Journal', `${core}\nreturn $input.all().map(i => ({json: {...journal(i.json), status: $execution.mode === 'production' ? 'PENDING' : 'TEST_ONLY'}}));`);
add('Event Journal', 'dataTable', 1.1, { resource: 'row', operation: 'insert', dataTableId: table, columns: mapping(Object.fromEntries(['event_id', 'delivery_id', 'semantic_key', 'event_json', 'status', 'message_id', 'error_code'].map(k => [k, exp(`$json.${k}`)]))) });
add('Digest Schedule', 'scheduleTrigger', 1.4, { rule: { interval: [{ field: 'seconds', secondsInterval: 30 }] } }, {}, true);
add('Load Event Journal', 'dataTable', 1.1, { resource: 'row', operation: 'get', dataTableId: table, returnAll: true });
code('Deduplicate and Severity Router', `${core}\nreturn plan($input.all().map(i => i.json)).map(json => ({json}));`);
code('Owner Approval Gate', `const OWNER_APPROVED = false;\nconst SIGNATURE_BOUNDARY_CONFIRMED = false;\nconst SERIAL_SENDER_CONFIRMED = false;\nconst CHAT_ID = '';\nif (!OWNER_APPROVED || !SIGNATURE_BOUNDARY_CONFIRMED || !SERIAL_SENDER_CONFIRMED || !/^-?\\d+$/.test(CHAT_ID)) return [];\nreturn $input.all().map(i => ({json: {...i.json, chat_id: CHAT_ID}}));`);
code('Expand Delivery Claim', `return $input.first().json.row_ids.map(row_id => ({json: {row_id}}));`);
update('Mark SENDING', { status: 'SENDING' });
code('Build Single Notification', `const selected = $('Owner Approval Gate').first().json;\nconst ids = $input.all().map(i => Number(i.json.id));\nif (ids.length !== selected.row_ids.length || selected.row_ids.some(id => !ids.includes(id))) throw new Error('INCOMPLETE_CLAIM_NO_SEND');\nreturn [{json: selected}];`);
add('Telegram Notification', 'telegram', 1.2, { resource: 'message', operation: 'sendMessage', chatId: exp('$json.chat_id'), text: exp('$json.text'), additionalFields: { parse_mode: 'HTML', disable_web_page_preview: true, appendAttribution: false } }, { credentials: { telegramApi: { newCredential: 'Telegram owner monitor' } }, retryOnFail: false, onError: 'continueRegularOutput' });
code('Record Delivery Result', `${core}\nconst outcome = telegramOutcome($input.first().json);\nreturn $('Build Single Notification').first().json.row_ids.map(row_id => ({json: {row_id, ...outcome}}));`);
update('Persist Delivery Result', { status: exp('$json.status'), message_id: exp('$json.message_id'), error_code: exp('$json.error_code') });
code('Error Handler', `return [{json: {event_id: 'error:' + $execution.id, delivery_id: '', semantic_key: 'error:' + $execution.id, event_json: '{}', status: 'FAILED', message_id: '', error_code: 'INPUT_REJECTED_SEE_RESTRICTED_EXECUTION'}}];`);
add('Mock Tests', 'manualTrigger', 1, {}, {}, true);
code('Run Mock Contract Tests', `${core}\nconst core = {REPOSITORY, BOT, verify, normalize, journal, plan, telegramOutcome, escapeHtml};\nconst f = (() => {${fixtures}\nreturn {repo, head, old, pr, bot, fixture};})();\nfunction runTests${tests}\nconst results = runTests(core, f);\nif (results.some(r => r.status === 'FAIL')) throw new Error(JSON.stringify(results.filter(r => r.status === 'FAIL')));\nreturn results.map(json => ({json}));`);
function chain(...ids) { for (let i = 1; i < ids.length; i++) links.push([ids[i - 1], ids[i]]); }
chain('GitHub Trigger', 'Verify Event', 'Current GitHub Snapshot', 'Normalize Event', 'Event Filter', 'Prepare Event Journal', 'Event Journal', 'Load Event Journal', 'Deduplicate and Severity Router', 'Owner Approval Gate', 'Expand Delivery Claim', 'Mark SENDING', 'Build Single Notification', 'Telegram Notification', 'Record Delivery Result', 'Persist Delivery Result');
chain('Digest Schedule', 'Load Event Journal');
chain('Mock Tests', 'Run Mock Contract Tests');
chain('Error Handler', 'Event Journal');
function encode(value) {
  if (typeof value === 'string' && value.startsWith('={{ ')) return `expr(${JSON.stringify(value.slice(1))})`;
  if (Array.isArray(value)) return `[${value.map(encode).join(',')}]`;
  if (value && typeof value === 'object') {
    if (value.newCredential) return `newCredential(${JSON.stringify(value.newCredential)})`;
    return `{${Object.entries(value).map(([k, v]) => `${JSON.stringify(k)}:${encode(v)}`).join(',')}}`;
  }
  return JSON.stringify(value);
}
const variables = Object.fromEntries(nodes.map((n, i) => [n.id, `n${i}`]));
const library = require('./core.cjs');
const fixture = require('./fixtures.cjs');
const sampleEvent = library.normalize(fixture.fixture(), fixture.pr);
const sampleRow = {...library.journal(sampleEvent), id: 1};
const samplePlan = library.plan([sampleRow])[0];
const samples = {
  'GitHub Trigger': fixture.fixture(), 'Verify Event': library.verify(fixture.fixture()),
  'Current GitHub Snapshot': fixture.pr, 'Normalize Event': sampleEvent, 'Event Filter': sampleEvent,
  'Prepare Event Journal': sampleRow, 'Event Journal': sampleRow, 'Load Event Journal': sampleRow,
  'Deduplicate and Severity Router': samplePlan, 'Owner Approval Gate': {...samplePlan, chat_id: ''},
  'Expand Delivery Claim': {row_id: 1}, 'Mark SENDING': {...sampleRow, status: 'SENDING'},
  'Build Single Notification': {...samplePlan, chat_id: ''}, 'Telegram Notification': {message_id: 123},
  'Record Delivery Result': {row_id: 1, status: 'SENT', message_id: '123', error_code: ''},
  'Persist Delivery Result': {...sampleRow, status: 'SENT'}, 'Error Handler': {...sampleRow, status: 'FAILED'},
  'Run Mock Contract Tests': {name: 'fixture', status: 'PASS'},
};
for (const n of nodes) n.output = [samples[n.id] || {}];
const declarations = nodes.map(({ id, trigger, ...n }) => `const ${variables[id]} = ${trigger ? 'trigger' : 'node'}(${encode(n)});`).join('\n');
const edges = links.map(([a, b]) => `.add(${variables[a]}).to(${variables[b]})`).join('\n');
const errorEdges = ['Verify Event', 'Normalize Event'].map(a => `.add(${variables[a]}.onError(${variables['Error Handler']}))`).join('\n');
const groups = [
  ['Проверить и записать событие', ['Verify Event', 'Current GitHub Snapshot', 'Normalize Event', 'Event Filter', 'Prepare Event Journal', 'Error Handler', 'Event Journal'], 'Проверить repository, прочитать текущий SHA, скрыть сырой текст и подготовить журнал.'],
  ['Доставка владельцу', ['Load Event Journal', 'Deduplicate and Severity Router', 'Owner Approval Gate', 'Expand Delivery Claim', 'Mark SENDING', 'Build Single Notification', 'Telegram Notification', 'Record Delivery Result', 'Persist Delivery Result'], 'Отправка закрыта до credentials, подтверждения владельца, HMAC и последовательного выполнения. UNKNOWN не повторять.'],
].map(([name, members, description]) => `.group(${JSON.stringify(name)}, [${members.map(m => variables[m]).join(',')}], {description: ${JSON.stringify(description)}})`).join('\n');
const sdk = `${declarations}\nexport default workflow('gremovod-github-live-monitor', 'GremoVOD — GitHub Live Monitor')\n${edges}\n${errorEdges}\n${groups};\n`;
const gate = nodes.find(n => n.id === 'Owner Approval Gate').config.parameters.jsCode;
assert.equal(vm.runInNewContext(`(function(){${gate}})()`, {$input: {all: () => [{json: samplePlan}]}}).length, 0, 'Owner gate must block all fixture sends');
assert.equal(nodes.find(n => n.id === 'Telegram Notification').config.retryOnFail, false, 'Ambiguous sends must not auto retry');
assert(!nodes.some(n => /openai|minimax|langchain/i.test(n.type)), 'Monitoring must never invoke models');
fs.writeFileSync(path.join(__dirname, 'workflow.sdk.ts'), sdk);
const connections = {};
for (const [a, b] of links) { connections[a] ||= { main: [[]] }; connections[a].main[0].push({ node: b, type: 'main', index: 0 }); }
for (const a of ['Verify Event', 'Normalize Event']) connections[a].main[1] = [{ node: 'Error Handler', type: 'main', index: 0 }];
fs.writeFileSync(path.join(__dirname, 'workflow.json'), JSON.stringify({ name: 'GremoVOD — GitHub Live Monitor', active: false, settings: { executionOrder: 'v1' }, nodes: nodes.map(({id, type, version, config}, i) => ({id, type, typeVersion: version, ...Object.fromEntries(Object.entries(config).filter(([k]) => k !== 'credentials')), position: [i * 200, 0]})), connections }, null, 2));
const nullableString = {type: ['string', 'null']};
const properties = Object.fromEntries(['event_id', 'received_at', 'github_delivery_id', 'event_type', 'action', 'repository', 'actor', 'task_id', 'head_sha', 'review_status', 'severity', 'summary', 'source_url'].map(k => [k, {type: 'string'}]));
properties.pr_number = {type: ['integer', 'null'], minimum: 1};
properties.task_id = nullableString; properties.head_sha = {...nullableString, pattern: '^[a-f0-9]{40}$'};
properties.repository = {const: library.REPOSITORY};
properties.received_at.format = 'date-time'; properties.source_url.pattern = '^https://github\\.com/gremoled77-droid/gremovod(?:/|$)';
properties.review_status.enum = ['UNKNOWN', 'STALE', 'FINDINGS', 'APPROVED', 'CHANGES_REQUESTED', 'COMMENTED', 'STARTED', 'COMPLETED'];
properties.severity.enum = ['INFO', 'NORMAL', 'P0', 'P1', 'P2'];
for (const key of Object.keys(properties)) assert(Object.hasOwn(sampleEvent, key), `Sample lacks ${key}`);
fs.writeFileSync(path.join(__dirname, 'event.schema.json'), JSON.stringify({$schema: 'https://json-schema.org/draft/2020-12/schema', title: 'GremoVOD GitHub normalized event', type: 'object', required: Object.keys(properties), properties, additionalProperties: true}, null, 2));
console.log(`Built ${nodes.length} nodes; credentials omitted from workflow.json`);
