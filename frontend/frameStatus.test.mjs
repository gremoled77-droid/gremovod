import test from 'node:test';
import assert from 'node:assert/strict';
import {frameStatus, generatingFrames, photoLabel, sceneVideoCount, videoLabel} from './src/frameStatus.ts';

const sel = (image = null, video = null) => ({selected_image_file_id: image, selected_video_file_id: video});
const img = id => ({id, kind: 'image'});
const vid = id => ({id, kind: 'video'});

test('фото: нет, последнее, утверждено', () => {
  assert.equal(frameStatus([], sel(), false).photo, 'none');
  assert.equal(frameStatus([img('a')], sel(), false).photo, 'latest');
  assert.equal(frameStatus([img('a')], sel('a'), false).photo, 'approved');
  assert.equal(photoLabel(frameStatus([img('a')], sel('a'), false)), 'фото ✓');
});

test('видео: нет, дубли без выбора, главное', () => {
  assert.equal(frameStatus([img('a')], sel('a'), false).video, 'none');
  const takes = frameStatus([img('a'), vid('v1'), vid('v2')], sel('a'), false);
  assert.deepEqual([takes.video, takes.takes], ['takes', 2]);
  assert.equal(videoLabel(takes), 'видео: 2 без выбора');
  const main = frameStatus([vid('v1'), vid('v2')], sel('a', 'v2'), false);
  assert.equal(main.video, 'main');
  assert.equal(videoLabel(main), 'видео ✓ (2)');
});

test('генерируется: флаг из ленты, главное видео важнее', () => {
  const files = [img('a'), vid('v1')];
  assert.equal(frameStatus(files, sel('a'), true).video, 'pending');
  assert.equal(frameStatus(files, sel('a'), false).video, 'takes');
  assert.equal(frameStatus(files, sel('a', 'v1'), true).video, 'main');
  assert.equal(videoLabel(frameStatus(files, sel('a'), true)), 'видео генерируется…');
});

test('кадры с идущим видео из ленты постановки', () => {
  const items = [
    {kind: 'video', status: 'running', node_id: 'f1'},
    {kind: 'video', status: 'saving', node_id: 'f2'},
    {kind: 'video', status: 'done', node_id: 'f3'},
    {kind: 'video', status: 'failed', node_id: 'f4'},
    {kind: 'image', status: 'running', node_id: 'f5'},
    {kind: 'video', status: 'queued', node_id: null},
  ];
  assert.deepEqual([...generatingFrames(items)].sort(), ['f1', 'f2']);
});

test('счётчик сцены считает только кадры с главным видео', () => {
  assert.deepEqual(sceneVideoCount([{selection: sel('a', 'v')}, {selection: sel('a')}, {selection: sel()}]), {
    done: 1,
    all: 3,
  });
  assert.deepEqual(sceneVideoCount([]), {done: 0, all: 0});
});
