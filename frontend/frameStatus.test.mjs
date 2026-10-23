import test from 'node:test';
import assert from 'node:assert/strict';
import {frameStatus, PENDING_MS, photoLabel, sceneVideoCount, videoLabel} from './src/frameStatus.ts';

const sel = (image = null, video = null) => ({selected_image_file_id: image, selected_video_file_id: video});
const img = id => ({id, kind: 'image'});
const vid = id => ({id, kind: 'video'});

test('фото: нет, последнее, утверждено', () => {
  assert.equal(frameStatus([], sel(), undefined, 0).photo, 'none');
  assert.equal(frameStatus([img('a')], sel(), undefined, 0).photo, 'latest');
  assert.equal(frameStatus([img('a')], sel('a'), undefined, 0).photo, 'approved');
  assert.equal(photoLabel(frameStatus([img('a')], sel('a'), undefined, 0)), 'фото ✓');
});

test('видео: нет, дубли без выбора, главное', () => {
  assert.equal(frameStatus([img('a')], sel('a'), undefined, 0).video, 'none');
  const takes = frameStatus([img('a'), vid('v1'), vid('v2')], sel('a'), undefined, 0);
  assert.deepEqual([takes.video, takes.takes], ['takes', 2]);
  assert.equal(videoLabel(takes), 'видео: 2 без выбора');
  const main = frameStatus([vid('v1'), vid('v2')], sel('a', 'v2'), undefined, 0);
  assert.equal(main.video, 'main');
  assert.equal(videoLabel(main), 'видео ✓ (2)');
});

test('генерируется: пока нет нового видео и не вышло 15 минут', () => {
  const pending = {since: 1000, videosBefore: 1};
  const files = [img('a'), vid('v1')];
  assert.equal(frameStatus(files, sel('a'), pending, 2000).video, 'pending');
  assert.equal(frameStatus(files, sel('a'), pending, 1000 + PENDING_MS + 1).video, 'takes');
  assert.equal(frameStatus([...files, vid('v2')], sel('a'), pending, 2000).video, 'takes');
  assert.equal(frameStatus(files, sel('a', 'v1'), pending, 2000).video, 'main');
  assert.equal(videoLabel(frameStatus(files, sel('a'), pending, 2000)), 'видео генерируется…');
});

test('счётчик сцены считает только кадры с главным видео', () => {
  assert.deepEqual(sceneVideoCount([{selection: sel('a', 'v')}, {selection: sel('a')}, {selection: sel()}]), {
    done: 1,
    all: 3,
  });
  assert.deepEqual(sceneVideoCount([]), {done: 0, all: 0});
});
