import test from 'node:test';
import assert from 'node:assert/strict';
import {
  parseScenario,
  producerRequest,
  producerWorld,
  withScenario,
  PRODUCER_MODELS,
  PRODUCER_MOCK_MODEL,
} from './src/producerStage.ts';

const state = {
  brief: '  Грэм берёт ночной заказ.  ',
  style: {look: '  тёплая  2D ', palette: 'охра', camera: '', rules: 'Грэм по канону', avoid: 'логотипы'},
  characters: [
    {id: 'grem', name: 'Грэм', working_asset_id: 'asset-1'},
    {id: 'passenger', name: 'Пассажир'},
  ],
};

test('запрос этапа берёт только выбранных персонажей и их рабочие референсы', () => {
  const body = producerRequest(state, {
    projectId: 'p1',
    characterIds: ['grem'],
    durationSeconds: 45,
    constraints: 'Без говорящих животных\n\n  без логотипов  ',
    model: PRODUCER_MOCK_MODEL,
  });
  assert.equal(body.project_id, 'p1');
  assert.equal(body.idea, 'Грэм берёт ночной заказ.');
  assert.deepEqual(body.character_ids, ['grem']);
  assert.deepEqual(body.reference_ids, ['asset-1']);
  assert.deepEqual(body.constraints, ['Без говорящих животных', 'без логотипов']);
  assert.equal(body.duration_seconds, 45);
  assert.equal(body.language, 'ru');
  assert.equal(body.provider, 'mock');
});

test('платная модель не прибивает провайдера: его выбирает бэкенд', () => {
  const body = producerRequest(state, {
    projectId: 'p1',
    characterIds: [],
    durationSeconds: 60,
    constraints: '',
    model: 'gpt-5.6-luna',
  });
  assert.equal(body.provider, '');
  assert.equal(body.model, 'gpt-5.6-luna');
});

test('длительность вне границ заменяется на безопасную', () => {
  const options = {projectId: 'p1', characterIds: [], constraints: '', model: PRODUCER_MOCK_MODEL};
  assert.equal(producerRequest(state, {...options, durationSeconds: 0}).duration_seconds, 60);
  assert.equal(producerRequest(state, {...options, durationSeconds: 99999}).duration_seconds, 60);
  assert.equal(producerRequest(state, {...options, durationSeconds: 30}).duration_seconds, 30);
});

test('в паспорт мира попадают только заполненные поля', () => {
  const world = producerWorld(state.style);
  assert.deepEqual(world, {look: 'тёплая 2D', palette: 'охра', rules: 'Грэм по канону', avoid: 'логотипы'});
  assert.deepEqual(producerWorld(undefined), {});
});

test('полный паспорт мира из 11 полей помещается в пакет', () => {
  const full = {
    look: 'стилизованная анимация',
    environment: 'Минск, дворики',
    time: 'ночь',
    tech: 'современный',
    textures: 'кедр, бетон',
    palette: 'охра и синь',
    lighting: 'фонари',
    camera: '35 мм',
    mood: 'тревожно',
    rules: 'канон не менять',
    avoid: 'логотипы',
  };
  const world = producerWorld(full);
  assert.equal(Object.keys(world).length, 11);
  const body = producerRequest({...state, style: full}, {
    projectId: 'p1',
    characterIds: [],
    durationSeconds: 60,
    constraints: '',
    model: PRODUCER_MOCK_MODEL,
  });
  assert.equal(Object.keys(body.world).length, 11);
});

test('разбор ответа: без логлайна, битов или сцен — понятная ошибка', () => {
  const good = {
    logline: 'Грэм берётся за заказ.',
    beats: [{id: 'b1', stage: 'setup', summary: 'заказ принят'}],
    scenes: [{number: 1, title: 'Сцена 1', duration_seconds: 10, summary: 'машина', character_ids: [], beat_id: 'b1'}],
    assumptions: [],
    prompt_version: {stage: 'producer.structure', revision: 'abc', rules_version: '1', background_version: '2'},
    model: {id: 'mock-producer', label: 'MOCK', provider: 'mock', price_in: 0, price_out: 0, paid: false},
    cost_usd: 0,
    estimated_usd: 0,
    external_calls: 0,
  };
  assert.equal(parseScenario(good, '2026-10-20T10:00:00Z').saved_at, '2026-10-20T10:00:00Z');
  assert.equal(parseScenario(good, 'x').logline, 'Грэм берётся за заказ.');
  assert.throws(() => parseScenario({...good, logline: '  '}, 'x'), /без логлайна/);
  assert.throws(() => parseScenario({...good, beats: []}, 'x'), /битов/);
  assert.throws(() => parseScenario({...good, scenes: []}, 'x'), /плана сцен/);
  assert.throws(() => parseScenario(null, 'x'), /логлайна/);
});

test('модели этапа: локальный MOCK и модели реестра', () => {
  assert.equal(PRODUCER_MODELS[PRODUCER_MOCK_MODEL].mock, true);
  assert.equal(PRODUCER_MODELS['gpt-5.6-luna'].mock, false);
  assert.ok(PRODUCER_MODELS['gpt-6-astra']);
});

test('структура кладётся в состояние проекта и не портит исходное', () => {
  const scenario = parseScenario(
    {
      logline: 'Грэм берётся за заказ.',
      beats: [{id: 'b1', stage: 'setup', summary: 'заказ принят'}],
      scenes: [{number: 1, title: 'Сцена 1', duration_seconds: 10, summary: 'машина', character_ids: [], beat_id: 'b1'}],
      assumptions: [],
      prompt_version: {stage: 'producer.structure', revision: 'abc', rules_version: '1', background_version: '2'},
      model: {id: 'mock-producer', label: 'MOCK', provider: 'mock', price_in: 0, price_out: 0, paid: false},
      cost_usd: 0,
      estimated_usd: 0,
      external_calls: 0,
    },
    '2026-10-20T10:00:00Z'
  );
  const studio = {brief: 'идея', style: {}, characters: []};
  const next = withScenario(studio, scenario);
  assert.equal(next.scenario, scenario);
  assert.equal(studio.scenario, undefined);
  assert.equal(next.brief, 'идея');
});
