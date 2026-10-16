import test from 'node:test';
import assert from 'node:assert/strict';
import {buildOperatorPrompt, EMPTY_LAYERS, layersEmpty, stripJunk} from './src/operatorPrompt.ts';

const ctx = {
  heroes: [{name: 'Грэм', identity: {species: 'таксист', costume: 'красная кепка'}}],
  world: {look: 'warm 2D animation', palette: 'ochre and blue', avoid: 'logos'},
};

test('пять слоёв собираются в строки по порядку', () => {
  const p = buildOperatorPrompt(
    {
      ...EMPTY_LAYERS,
      subject: 'Graham looks out of the taxi window',
      environment: 'night courtyard',
      depth: ['fg-glass'],
      atmosphere: ['rain'],
      lightKey: ['rim', 'practical'],
      lightTemp: 'warm',
      lightNote: 'motivated by the street lamp',
      shot: 'mcu',
      lens: '85',
      aperture: 'f18',
      camera: 'alexa',
      director: 'Denis Villeneuve',
    },
    ctx
  );
  const lines = p.split('\n');
  assert.deepEqual(
    lines.map(l => l.split(':')[0]),
    ['Scene', 'Environment', 'Light', 'Camera', 'Style', 'Avoid']
  );
  assert.match(lines[0], /Graham looks out of the taxi window\. Subject: Грэм \(таксист, красная кепка\)/);
  assert.match(lines[1], /night courtyard, rain-streaked glass in the foreground, rain and water droplets/);
  assert.match(lines[2], /rim light.*practical lamp.*warm tungsten.*street lamp/);
  assert.match(lines[3], /medium close-up, 85mm lens, f\/1\.8 shallow depth of field, shot on Arri Alexa/);
  assert.match(lines[4], /warm 2D animation\. ochre and blue\. Directed by Denis Villeneuve/);
  assert.equal(lines[5], 'Avoid: logos.');
});

test('пустые слои пропускаются, мусорные слова вычищаются', () => {
  const p = buildOperatorPrompt(
    {...EMPTY_LAYERS, subject: 'A cab, 8K, masterpiece, best quality'},
    {heroes: []}
  );
  assert.equal(p, 'Scene: A cab.');
  assert.equal(stripJunk('ultra detailed portrait, 4K , hyperrealistic'), 'portrait');
  assert.equal(buildOperatorPrompt(EMPTY_LAYERS, {heroes: []}), '');
});

test('неизвестные ключи чипов не ломают сборку', () => {
  const p = buildOperatorPrompt({...EMPTY_LAYERS, shot: 'нет такого', depth: ['x', 'fg-blur']}, {heroes: []});
  assert.equal(p, 'Environment: out-of-focus foreground element.');
});

test('пустота слоёв определяется по всем полям', () => {
  assert.equal(layersEmpty(EMPTY_LAYERS), true);
  assert.equal(layersEmpty({...EMPTY_LAYERS, subject: '  '}), true);
  assert.equal(layersEmpty({...EMPTY_LAYERS, lens: '35'}), false);
});
