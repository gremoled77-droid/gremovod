// Регрессия пересборки n8n-контура v2: креды привязаны, критики независимы, вердикт fail-closed.
//
// Исходники проверяем как текст SDK-кода: локально @n8n/workflow-sdk не установлен,
// поэтому структурные правила читаем из исходника, а поведение вердикта — исполняем
// извлечённым jsCode с подставленным $ и $json.
//
// Запуск: node --test integrations/n8n/tests/
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname, join} from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const workflowsDir = join(here, '..', 'workflows');

const LIVE = 'gremovod-qa-studio-live-v2.ts';
const LOOP = 'gremovod-qa-studio-loop-v2.ts';
const DRIVE = 'gremovod-drive-to-qa-v2.ts';
const DIAG = 'gremovod-studio-diagnostics.ts';

const PROJECT_ID = '5b2e8e41-bc8a-4575-aec7-7ba5c2ef16d6';

function source(name) {
  const path = join(workflowsDir, name);
  assert.ok(existsSync(path), `Нет исходника ${name}`);
  return readFileSync(path, 'utf8');
}

// Извлекает jsCode конкретного Code-узла по его имени.
// Шаблонная строка без обратных кавычек внутри, поэтому границы однозначны.
function extractJsCode(text, nodeName) {
  const at = text.indexOf(`name: '${nodeName}'`);
  assert.notEqual(at, -1, `В исходнике нет узла «${nodeName}»`);
  const match = /jsCode: `([\s\S]*?)`,\n/.exec(text.slice(at));
  assert.ok(match, `У узла «${nodeName}» не найден jsCode`);
  return match[1];
}

// Заглушка n8n-окружения: $('Имя узла') возвращает и .first(), и .item.
// Разным узлам — разные данные, иначе тест проверит не тот путь.
function fakeNodeRefs(byNode) {
  const fallback = {};
  return (name) => {
    const json = Object.prototype.hasOwnProperty.call(byNode, name) ? byNode[name] : fallback;
    return {
      first: () => ({json}),
      item: {json},
    };
  };
}

test('исходники v2 лежат в репозитории', () => {
  for (const name of [LIVE, LOOP, DRIVE, DIAG]) {
    assert.ok(existsSync(join(workflowsDir, name)), `Нет исходника ${name}`);
  }
});

test('студийный кред привязан по имени, а не по id', () => {
  // В репозитории нельзя хранить credential ID: связывание выполняется при развёртывании.
  for (const name of [LIVE, LOOP, DRIVE]) {
    const text = source(name);
    assert.match(text, /newCredential\('Header Auth account'\)/, `${name}: нет ссылки на кред студии`);
    assert.doesNotMatch(text, /DXufsqj3qO0pCfyu/, `${name}: credential ID попал в репозиторий`);
  }
});

test('модельный узел привязан к собственному креду MiniMax', () => {
  for (const name of [LIVE]) {
    const text = source(name);
    assert.match(text, /newCredential\('MiniMax account'\)/, `${name}: нет ссылки на кред MiniMax`);
    assert.doesNotMatch(text, /gYqDTNNumENRCldO/, `${name}: credential ID MiniMax попал в репозиторий`);
  }
});

test('HTTP-узлы студии используют обычный Header Auth, а не Templated Custom Auth', () => {
  for (const name of [LIVE, LOOP, DRIVE]) {
    const text = source(name);
    assert.doesNotMatch(text, /httpTemplatedCustomAuth/, `${name}: templated-кред не находится в списке Credentials`);
    assert.match(text, /genericAuthType: 'httpHeaderAuth'/, `${name}: нет обычного Header Auth`);
  }
});

test('в workflow студии стоит project_id стенда', () => {
  for (const name of [LIVE, LOOP, DRIVE]) {
    assert.ok(source(name).includes(PROJECT_ID), `${name}: project_id стенда не зашит в исходник`);
  }
});

test('LIVE-контур держит двух независимых критика с разными пакетами', () => {
  const text = source(LIVE);
  assert.match(text, /REVIEW-REQ/, 'нет роли REVIEW-REQ');
  assert.match(text, /REVIEW-SYSTEM/, 'нет роли REVIEW-SYSTEM');
  // Два разных пакета: критик ТЗ и критик системы получают разные роли.
  assert.match(text, /packet\/REVIEW-REQ/, 'критик ТЗ не берёт свой пакет');
  assert.match(text, /packet\/REVIEW-SYSTEM/, 'критик системы не берёт свой пакет');
  const agents = text.match(/type: '@n8n\/n8n-nodes-langchain\.agent'/g) || [];
  assert.equal(agents.length, 2, 'ожидались ровно два агента-критика');
  const models = text.match(/lmChatMinimax/g) || [];
  assert.equal(models.length, 2, 'ожидались два языковых узла MiniMax');
});

test('критик не может самовольно пройти: вердикт без строгого JSON даёт BLOCKED', () => {
  const text = source(LIVE);
  const run = new Function('$json', '$', extractJsCode(text, 'Вердикт: критик ТЗ'));
  // Пакет отдаёт ревизию артефакта, агент — ответ модели.
  const refs = (agentOutput) => fakeNodeRefs({
    'Агент: критик ТЗ': {output: agentOutput},
    'Пакет: критик ТЗ': {artifact_revision: 'rev-1'},
  });

  // Мусор вместо JSON от модели.
  const garbage = run({}, refs('всё отлично'));
  assert.equal(garbage[0].json.verdict, 'BLOCKED', 'мусорный ответ не должен давать PASS');
  assert.ok(garbage[0].json.missing_inputs.length > 0, 'не должна быть пустая причина блокировки');

  // Ответ без поля verdict.
  const noVerdict = run({}, refs('{"checked_scopes":[]}'));
  assert.equal(noVerdict[0].json.verdict, 'BLOCKED', 'ответ без вердикта не должен давать PASS');

  // Нераспознанный вердикт.
  const weird = run({}, refs('{"verdict":"OK"}'));
  assert.equal(weird[0].json.verdict, 'BLOCKED', 'вердикт вне перечня не должен проходить');

  // Корректный строгий JSON — вердикт сохраняется.
  const good = run({}, refs('{"verdict":"PASS","checked_scopes":["TEXT"],"scope_results":{"TEXT":"PASS"},"evidence":[],"missing_inputs":[]}'));
  assert.equal(good[0].json.verdict, 'PASS', 'корректный вердикт должен сохраняться');
  assert.deepEqual(good[0].json.checked_scopes, ['TEXT']);
});

test('вердикт сохраняет роль и ревизию артефакта', () => {
  const text = source(LIVE);
  const run = new Function('$json', '$', extractJsCode(text, 'Вердикт: критик ТЗ'));
  const out = run(
    {},
    fakeNodeRefs({
      'Агент: критик ТЗ': {output: '{"verdict":"FAIL","checked_scopes":["TEXT"],"scope_results":{"TEXT":"FAIL"},"evidence":[],"missing_inputs":[]}'},
      'Пакет: критик ТЗ': {artifact_revision: 'rev-7'},
    }),
  );
  assert.equal(out[0].json.role, 'REVIEW-REQ');
  assert.equal(out[0].json.artifact_revision, 'rev-7');
});

test('черновик без критиков остаётся BLOCKED, а не PASS', () => {
  const text = source(LOOP);
  const run = new Function('$json', '$', extractJsCode(text, 'Вердикт: критик ТЗ'));
  const out = run(
    {artifact_revision: 'rev-1'},
    fakeNodeRefs({'Старт: ручной прогон': {}}),
  );
  assert.equal(out[0].json.verdict, 'BLOCKED', 'черновик без критика не может выдать PASS');
  assert.ok(out[0].json.missing_inputs.length > 0, 'нужна причина блокировки');
});

test('отчёт не публикует артефакт сам', () => {
  for (const name of [LIVE, LOOP, DRIVE]) {
    const text = source(name);
    assert.match(text, /published_by_workflow: false/, `${name}: отчёт не фиксирует, что выпуск не автоматический`);
  }
});

test('Drive-контур берёт файл и требует извлечённый текст', () => {
  const text = source(DRIVE);
  assert.match(text, /googleDriveOAuth2Api/, 'нет ссылки на гугл-кред');
  assert.match(text, /operation: 'download'/, 'нет скачивания файла');
  assert.match(text, /operation: 'text'/, 'нет извлечения текста');
  assert.match(text, /не извлечён текст/, 'нет защиты от пустого файла');
  assert.doesNotMatch(text, /DXufsqj3qO0pCfyu/, 'credential ID попал в репозиторий');
});

test('диагностика отличает принятый токен от отклонённого', () => {
  const text = source(DIAG);
  const run = new Function('$json', '$', extractJsCode(text, 'Диагностика'));
  const fake = (statusCode) => fakeNodeRefs({
    'Туннель: /api/health': {statusCode: 200, body: {ok: true}},
    'Токен студии: /api/qa/reviews/<ping>': {statusCode, body: {detail: 'x'}},
  });

  const ok = run({}, fake(404));
  assert.equal(ok[0].json.verdict, 'ТОКЕН ПРИНЯТ');

  const denied = run({}, fake(401));
  assert.equal(denied[0].json.verdict, 'ТОКЕН ОТКЛОНЁН');

  const offline = run({}, fake(undefined));
  assert.equal(offline[0].json.verdict, 'НЕТ СВЯЗИ');
});

test('в исходниках нет токена студии', () => {
  for (const name of [LIVE, LOOP, DRIVE, DIAG]) {
    assert.doesNotMatch(source(name), /idJ7z-V4cWKL3lfHrk2GB2ycbtDi2fbxXC6vnXIcLto/, `${name}: токен студии попал в репозиторий`);
  }
});
