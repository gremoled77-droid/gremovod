import test from 'node:test';
import assert from 'node:assert/strict';
import {
  changeOf,
  outlineBody,
  outlineSystem,
  outlineUser,
  parseOutline,
  shotNotes,
} from './src/outlinePlan.ts';

const reply = `Вот план:
\`\`\`json
{"scenes":[{"title":" Двор ","shots":[
 {"change":"Грэм замечает пассажира","visible":"двор, фонарь","audio":"гул мотора","camera":"медленный наезд"},
 {"change":"  ","visible":"пусто"},
 {"change":"Пассажир садится","visible":"","audio":"","camera":""}]}]}
\`\`\``;

test('план достаётся из обёртки, кадры без «change» отбрасываются', () => {
  const plan = parseOutline(reply);
  assert.equal(plan.scenes[0].title, 'Двор');
  assert.deepEqual(
    plan.scenes[0].shots.map(s => s.change),
    ['Грэм замечает пассажира', 'Пассажир садится']
  );
});

test('плохие ответы дают понятные ошибки', () => {
  assert.throws(() => parseOutline('нет json'), /не похож на JSON/);
  assert.throws(() => parseOutline('{"scenes":'), /JSON|не похож/);
  assert.throws(() => parseOutline('{"scenes":[]}'), /нет сцен/);
  assert.throws(() => parseOutline('{"scenes":[{"title":"А","shots":[{"change":""}]}]}'), /нет кадров/);
});

test('заметка кадра и строка «Изменение» читаются обратно', () => {
  const notes = shotNotes({change: 'Грэм оборачивается', visible: 'салон', audio: '', camera: ' push in '});
  assert.equal(notes, 'Изменение: Грэм оборачивается\nВидно: салон\nКамера: push in');
  assert.equal(changeOf(notes), 'Грэм оборачивается');
  assert.equal(changeOf('просто текст'), '');
  assert.equal(changeOf(undefined), '');
});

test('тело запроса: кадры нумеруются в каждой сцене заново', () => {
  const body = outlineBody(parseOutline(reply));
  assert.equal(body[0].title, 'Двор');
  assert.deepEqual(
    body[0].frames.map(f => f.title),
    ['Кадр 1', 'Кадр 2']
  );
  assert.match(body[0].frames[0].notes, /^Изменение: Грэм замечает пассажира/);
});

test('системный промпт называет число кадров и сцен', () => {
  assert.match(outlineSystem(7, 1), /1 сцену, в каждой по 7 кадров/);
  assert.match(outlineSystem(5, 3), /3 сцен, в каждой по 5 кадров/);
});

test('запрос к GPT: задание, паспорт и герои, пустое пропускается', () => {
  const user = outlineUser({
    brief: ' Грэм везёт пассажира ',
    passport: 'Стиль: 2D',
    heroes: ['Грэм', 'Катя'],
  });
  assert.equal(
    user,
    'Задание ролика:\nГрэм везёт пассажира\n\nПаспорт мира:\nСтиль: 2D\n\nГерои проекта: Грэм, Катя'
  );
  assert.equal(outlineUser({brief: 'x', passport: ' ', heroes: []}), 'Задание ролика:\nx');
});
