import test from 'node:test';
import assert from 'node:assert/strict';
import {fromSnapshot, keepDraft, newBeat, validDraft, versionsMatch} from './src/actingSheet.ts';

const server = {
  revision: 3,
  source_revision: 'a'.repeat(64),
  status: 'approved',
  beats: [],
  stale: false,
  scene: {id: 'scene', title: 'Сцена', notes: ''},
  actors: [],
  shots: [],
};

test('a restored stale draft keeps user content until explicit conflict resolution', () => {
  const mine = {...fromSnapshot(server), base_revision: 2, beats: [newBeat('actor')]};
  mine.beats[0].objective = 'Сохранить мой текст';
  assert.equal(versionsMatch(mine, server), false);
  const resolved = keepDraft(mine, server);
  assert.equal(resolved.beats[0].objective, 'Сохранить мой текст');
  assert.equal(resolved.base_revision, 3);
  assert.equal(resolved.status, 'draft');
  assert.equal(mine.base_revision, 2);
  assert.equal(mine.status, 'approved');
});

test('changed scene input invalidates even an unchanged note revision', () => {
  const draft = fromSnapshot(server);
  assert.equal(versionsMatch(draft, server), true);
  assert.equal(versionsMatch(draft, {...server, source_revision: 'b'.repeat(64)}), false);
});

test('corrupt browser drafts are rejected before rendering controls', () => {
  for (const value of [
    null,
    {},
    {beats: []},
    {...fromSnapshot(server), beats: [{}]},
    {...fromSnapshot(server), beats: [null]},
    {...fromSnapshot(server), base_revision: true},
  ]) {
    assert.equal(validDraft(value), false);
  }
  assert.equal(validDraft({...fromSnapshot(server), beats: [newBeat('actor')]}), true);
});
