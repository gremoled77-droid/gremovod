import assert from 'node:assert/strict';
import {test} from 'node:test';
import {FRAME_ITEMS, removeFrameItem, selectedFrameItems, toggleFrameItem} from './src/cameraFrameCatalog.ts';

const item = id => FRAME_ITEMS.find(i => i.id === id);

test('фразы ложатся в строки FRAME, CAMERA и LIGHT', () => {
  let p = 'Грэм у машины';
  p = toggleFrameItem(p, item('low'));
  p = toggleFrameItem(p, item('cu'));
  p = toggleFrameItem(p, item('push'));
  p = toggleFrameItem(p, item('neon'));
  assert.equal(
    p,
    'Грэм у машины\nFRAME: low-angle shot looking up; close-up on the face\nCAMERA: slow push in\nLIGHT: neon night light, pink and blue'
  );
  assert.deepEqual(
    selectedFrameItems(p).map(i => i.id),
    ['low', 'cu', 'push', 'neon']
  );
});

test('в группе активна одна фраза, повторный клик снимает её', () => {
  let p = toggleFrameItem('', item('low'));
  p = toggleFrameItem(p, item('high'));
  assert.equal(p, 'FRAME: high-angle shot looking down');
  p = toggleFrameItem(p, item('cu'));
  assert.equal(p, 'FRAME: high-angle shot looking down; close-up on the face');
  p = toggleFrameItem(p, item('high'));
  assert.equal(p, 'FRAME: close-up on the face');
  p = removeFrameItem(p, item('cu'));
  assert.equal(p, '');
});

test('чужой текст в строке и в промпте сохраняется', () => {
  let p = 'Начало\nFRAME: герой слева; wide shot showing the environment\nКонец';
  p = toggleFrameItem(p, item('ms'));
  assert.equal(p, 'Начало\nFRAME: герой слева; medium shot\nКонец');
  p = removeFrameItem(p, item('ms'));
  assert.equal(p, 'Начало\nFRAME: герой слева\nКонец');
});
