import test from 'node:test';
import assert from 'node:assert/strict';
import {addAttachment, removeAttachment, roleLabel, setAttachmentRole} from './src/attachments.ts';

test('вложение добавляется один раз', () => {
  const one = addAttachment([], 'a', 'character');
  assert.deepEqual(one, [{asset_id: 'a', role: 'character', note: ''}]);
  assert.equal(addAttachment(one, 'a', 'location'), one);
  assert.equal(addAttachment(one, 'b', 'location').length, 2);
});

test('смена роли и удаление не трогают остальные', () => {
  const list = addAttachment(addAttachment([], 'a', 'character'), 'b', 'reference');
  assert.deepEqual(
    setAttachmentRole(list, 'b', 'location').map(x => x.role),
    ['character', 'location']
  );
  assert.deepEqual(
    removeAttachment(list, 'a').map(x => x.asset_id),
    ['b']
  );
  assert.equal(list.length, 2);
});

test('подписи ролей по-русски, неизвестная роль остаётся как есть', () => {
  assert.equal(roleLabel('location'), 'Локация');
  assert.equal(roleLabel('zzz'), 'zzz');
});
