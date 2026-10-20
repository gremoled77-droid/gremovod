import test from 'node:test';
import assert from 'node:assert/strict';
import {capUsd, roleRows, changedRows, newRoleRow} from './src/n8nSpend.ts';

test('потолок роли: пусто и мусор — это null, а не ноль', () => {
  assert.equal(capUsd(''), null);
  assert.equal(capUsd('   '), null);
  assert.equal(capUsd('abc'), null);
  assert.equal(capUsd('-1'), null);
  assert.equal(capUsd('1e999'), null);
});

test('потолок роли: число округляется до копеек', () => {
  assert.equal(capUsd('0.05'), 0.05);
  assert.equal(capUsd(' 0.5 '), 0.5);
  assert.equal(capUsd('0'), 0);
  assert.equal(capUsd('0.1234567'), 0.123457);
});

test('строки ролей идут по алфавиту, одна на роль', () => {
  const rows = roleRows([
    {role: 'A3', cap_usd: 0.02, model: 'sonnet'},
    {role: 'A1', cap_usd: 0.05},
  ]);
  assert.deepEqual(rows.map(r => r.role), ['A1', 'A3']);
  assert.equal(rows[0].cap, '0.05');
  assert.equal(rows[0].model, '');
});

test('сохраняются только изменённые потолки, мусор не отправляется', () => {
  const saved = [
    {role: 'A1', cap_usd: 0.05},
    {role: 'A2', cap_usd: 0.15},
  ];
  const rows = [
    {role: 'A1', cap: '0.05', model: '', note: ''},
    {role: 'A2', cap: '0.2', model: '', note: ''},
    {role: 'A3', cap: 'abc', model: '', note: ''},
  ];
  assert.deepEqual(changedRows(rows, saved), [{role: 'A2', cap_usd: 0.2, model: '', note: ''}]);
});

test('новая роль без сохранённого потолка уходит в изменённые', () => {
  const rows = [{role: 'A9', cap: '0.03', model: '', note: ''}];
  assert.deepEqual(changedRows(rows, []), [{role: 'A9', cap_usd: 0.03, model: '', note: ''}]);
});

test('новую роль можно добавить: имя нормализуется, дубль и мусор отбрасываются', () => {
  const rows = [{role: 'A1', cap: '0.05', model: '', note: ''}];
  assert.deepEqual(newRoleRow(rows, ' a2 ', '0.15'), {role: 'A2', cap: '0.15', model: '', note: ''});
  assert.equal(newRoleRow(rows, 'A1', '0.2'), null);
  assert.equal(newRoleRow(rows, '', '0.2'), null);
  assert.equal(newRoleRow(rows, 'роль', '0.2'), null);
});
