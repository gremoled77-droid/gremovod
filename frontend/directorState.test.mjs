import {existsSync} from 'node:fs';
import {dirname, join} from 'node:path';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {build} from 'esbuild';

const bundled = await build({
  stdin: {
    contents:
      "export {frameBasis,frameOutdated} from './src/FramePanel'; export {carCompatible} from './src/CarStage'; export {cameraBasis,cameraOutdated} from './src/CameraPanel';",
    resolveDir: import.meta.dirname,
  },
  bundle: true,
  write: false,
  format: 'esm',
  platform: 'node',
  loader: {'.css': 'empty'},
});
const {frameBasis, frameOutdated, carCompatible, cameraBasis, cameraOutdated} = await import(
  'data:text/javascript;base64,' + Buffer.from(bundled.outputFiles[0].text).toString('base64')
);
const cwd = new URL('..', import.meta.url).pathname.replace(/^\/(\w:)/, '$1');
// В git worktree своего .venv нет: ищем его вверх по каталогам (корень проекта лежит выше .claude/worktrees).
function findVenvPython() {
  for (let dir = cwd; ;) {
    for (const rel of ['.venv/Scripts/python.exe', '.venv/bin/python']) {
      const candidate = join(dir, rel);
      if (existsSync(candidate)) return candidate;
    }
    const parent = dirname(dir);
    if (parent === dir) return null;
    dir = parent;
  }
}
const python = process.env.STUDIO_PYTHON || findVenvPython() || 'python3';
const legacy = {
  frame_id: 'profile',
  lighting_id: 'rim',
  direction: 'preset',
  softness: 'preset',
  temperature: 'preset',
  note: '',
};
const car = {
  shot_id: 'car-rear-guest',
  steering: 'left',
  guest_seat: 'rear-right',
  vehicle_state: 'moving',
  light_id: 'night',
};

test('browser and server sign old and new compositions identically', () => {
  const values = [
    {},
    legacy,
    {...legacy, shot_size: 'close-up'},
    {car, shot_size: 'medium-close'},
    {car: {shot_id: 'car-rear-guest'}},
    {setup: {lens: 'clean', capture: 'modern', genre: 'comedy'}},
    {setup: {lens: '', palette: 'warm'}},
  ];
  for (const value of values) {
    const server = execFileSync(
      python,
      [
        '-X',
        'utf8',
        '-c',
        'import sys,json;from backend.frame_composition import basis;print(basis(json.loads(sys.argv[1])))',
        JSON.stringify(value),
      ],
      {cwd, encoding: 'utf8'}
    ).trim();
    assert.equal(frameBasis(value), server);
  }
});

test('changing size, seat, light or car station invalidates a prepared prompt', () => {
  const value = {...legacy, frame_id: '', lighting_id: '', shot_size: 'medium-close', car};
  const basis = frameBasis(value);
  assert.equal(frameOutdated(value, basis, 'Reviewed prompt'), false);
  const changes = [
    {...value, shot_size: 'close-up'},
    ...['guest_seat', 'light_id', 'shot_id', 'steering', 'vehicle_state'].map((key, i) => ({
      ...value,
      car: {...car, [key]: ['rear-left', 'day', 'car-driver-reverse', 'right', 'parked'][i]},
    })),
  ];
  for (const changed of changes) assert.equal(frameOutdated(changed, basis, 'Reviewed prompt'), true);
});

test('incompatible passenger row and middle seat are excluded from the picker', () => {
  assert.equal(carCompatible({id: 'car-front-two', guest_row: 'front'}, car), false);
  assert.equal(carCompatible({id: 'car-rear-guest', guest_row: 'rear'}, car), true);
  assert.equal(
    carCompatible({id: 'car-guest-window', guest_row: 'any'}, {...car, guest_seat: 'rear-center'}),
    false
  );
});

test('video prompt bases have matching browser/server signatures without a movement', () => {
  for (const value of [
    {},
    {setup: {lens: 'clean', capture: 'modern'}},
    {preset_id: 'static', setup: {render_style: 'animation-3d', focus: 'both'}},
  ]) {
    const server = execFileSync(
      python,
      [
        '-X',
        'utf8',
        '-c',
        'import sys,json;from backend.camera_movements import basis;print(basis(json.loads(sys.argv[1])))',
        JSON.stringify(value),
      ],
      {cwd, encoding: 'utf8'}
    ).trim();
    assert.equal(cameraBasis(value), server);
  }
  assert.equal(
    cameraOutdated({setup: {lens: 'clean'}}, cameraBasis({setup: {lens: 'warm-vintage'}}), 'Prepared prompt'),
    true
  );
});
