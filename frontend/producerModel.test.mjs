import {readFile} from 'node:fs/promises';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const source = await readFile(new URL('./src/producerModel.ts', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: {module: ts.ModuleKind.ES2020, target: ts.ScriptTarget.ES2020},
}).outputText;
const {
  parseCatalog,
  defaultsFor,
  modelsForProvider,
  choiceForProvider,
  isRunnable,
  availabilityNote,
  providerLabel,
  estimateBody,
  runBody,
  makeRequestId,
  formatUsd,
  DEFAULT_CHOICE,
} = await import('data:text/javascript;base64,' + Buffer.from(compiled).toString('base64'));

const CATALOG = {
  providers: [
    {
      id: 'mock',
      name: 'Локальный MOCK',
      available: true,
      status: 'available',
      message: 'Ключ не нужен',
      models: ['mock-producer'],
    },
    {
      id: 'piapi',
      name: 'PiAPI',
      available: false,
      status: 'not_configured',
      message: 'Ключ не настроен: PIAPI_API_KEY.txt',
      models: ['gpt-5.6-luna'],
    },
  ],
  models: [
    {
      id: 'mock-producer',
      label: 'Локальный MOCK',
      provider: 'mock',
      price_in: 0,
      price_out: 0,
      scopes: ['idea'],
    },
    {
      id: 'gpt-5.6-luna',
      label: 'GPT-5.6 Luna',
      provider: 'piapi',
      price_in: 0.02,
      price_out: 0.12,
      scopes: ['workflow', 'idea'],
    },
  ],
  default: {provider: 'mock', model: 'mock-producer'},
};

const catalog = parseCatalog(CATALOG);

test('каталог разбирается, а битый ответ — понятная ошибка', () => {
  assert.equal(catalog.providers.length, 2);
  assert.equal(catalog.models.length, 2);
  assert.throws(() => parseCatalog(null), /не разобран/);
  assert.throws(() => parseCatalog({providers: [], models: []}), /не прислал провайдеров или модели/);
  assert.throws(() => parseCatalog({models: []}), /не прислал провайдеров или модели/);
  assert.throws(
    () => parseCatalog({providers: [{}], models: [{id: 'x', label: 'y', provider: 'z'}]}),
    /providers\[\]\.id/
  );
});

test('по умолчанию — локальный MOCK: платный провайдер не выбирается сам', () => {
  assert.deepEqual(defaultsFor(catalog), {provider: 'mock', model: 'mock-producer'});
  assert.deepEqual(DEFAULT_CHOICE, {provider: 'mock', model: 'mock-producer'});
});

test('модели берутся у своего провайдера', () => {
  assert.deepEqual(
    modelsForProvider(catalog, 'mock').map(model => model.id),
    ['mock-producer']
  );
  assert.deepEqual(
    modelsForProvider(catalog, 'piapi').map(model => model.id),
    ['gpt-5.6-luna']
  );
  assert.deepEqual(modelsForProvider(catalog, 'нет-такого'), []);
});

test('смена провайдера оставляет модель, только если её обслуживает новый провайдер', () => {
  const switched = choiceForProvider(catalog, 'piapi', 'mock-producer');
  assert.equal(switched.provider, 'piapi');
  assert.equal(switched.model, 'gpt-5.6-luna');
  const kept = choiceForProvider(catalog, 'piapi', 'gpt-5.6-luna');
  assert.equal(kept.model, 'gpt-5.6-luna');
});

test('провайдер без ключа недоступен: обещать платный запуск нельзя', () => {
  const choice = {provider: 'piapi', model: 'gpt-5.6-luna'};
  assert.equal(isRunnable(catalog, choice), false);
  const note = availabilityNote(catalog, choice);
  assert.match(note, /недоступен/);
  assert.match(note, /Ключ не настроен/);
  assert.match(providerLabel(catalog, 'piapi'), /недоступен/);
  assert.equal(isRunnable(catalog, {provider: 'mock', model: 'mock-producer'}), true);
});

test('тело оценки несёт выбранного провайдера и модель', () => {
  const body = estimateBody({projectId: 'p1', idea: 'Идея'}, {provider: 'mock', model: 'mock-producer'});
  assert.equal(body.project_id, 'p1');
  assert.equal(body.idea, 'Идея');
  assert.equal(body.provider, 'mock');
  assert.equal(body.model, 'mock-producer');
  assert.equal(body.duration_seconds, 60);
  assert.deepEqual(body.character_ids, []);
});

test('платный запуск возможен только с подписью оценки', () => {
  const quote = {mode: 'paid', estimated_usd: 0.0031, quote_token: 'token'};
  const body = runBody({projectId: 'p1', idea: 'Идея'}, {provider: 'piapi', model: 'gpt-5.6-luna'}, quote, 'req-12345678');
  assert.equal(body.approved, true);
  assert.equal(body.quote_token, 'token');
  assert.equal(body.max_cost_usd, 0.0031);
  assert.equal(body.request_id, 'req-12345678');
});

test('идентификатор запроса короче 8 символов не годится: платный повтор не защищён', () => {
  const id = makeRequestId();
  assert.ok(id.length >= 8);
  assert.match(id, /^[A-Za-z0-9_-]+$/);
});

test('цена печатается как есть, без округления до нуля', () => {
  assert.equal(formatUsd(0.0031), '$0.0031');
  assert.equal(formatUsd(0), '$0.0000');
});
