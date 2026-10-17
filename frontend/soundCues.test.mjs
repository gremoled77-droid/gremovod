import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_LEVEL,
  KINDS,
  kindLabel,
  levelLabel,
  sceneSound,
  soundCount,
  soundLabel,
  voiceIdOk,
} from './src/soundCues.ts';

const cue = status => ({status});

test('рекомендуемые уровни как в плане: голос 0, атмосфера -20, SFX -6, музыка -12', () => {
  assert.deepEqual(DEFAULT_LEVEL, {voice: 0, ambience: -20, sfx: -6, music: -12});
  assert.deepEqual(
    KINDS.map(k => k.id),
    ['voice', 'ambience', 'sfx', 'music']
  );
  assert.equal(kindLabel('sfx'), 'SFX');
  assert.equal(kindLabel('voice'), 'Реплика');
});

test('Voice ID: только безопасные знаки', () => {
  assert.equal(voiceIdOk('Xb7hH8MSUJpSbSDYk0k2'), true);
  assert.equal(voiceIdOk(' abc_-1 '), true);
  assert.equal(voiceIdOk('bad id!'), false);
  assert.equal(voiceIdOk(''), false);
  assert.equal(voiceIdOk('x'.repeat(101)), false);
});

test('счётчики кадра и сцены по заметкам с файлами', () => {
  assert.deepEqual(soundCount([cue('file'), cue('plan'), cue('file')]), {done: 2, all: 3});
  assert.equal(soundLabel([cue('file'), cue('plan')]), 'звук: 1 из 2');
  assert.equal(soundLabel([]), 'звука нет');
  assert.deepEqual(sceneSound([{cues: [cue('file'), cue('plan')]}, {cues: []}, {cues: [cue('file')]}]), {
    framesWith: 2,
    frames: 3,
    done: 2,
    all: 3,
  });
});

test('подпись уровня с настоящим минусом', () => {
  assert.equal(levelLabel(-20), '−20 дБ');
  assert.equal(levelLabel(0), '0 дБ');
  assert.equal(levelLabel(3), '+3 дБ');
  assert.equal(levelLabel(-6.5), '−6.5 дБ');
});
