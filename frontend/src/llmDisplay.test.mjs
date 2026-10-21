import test from 'node:test';
import assert from 'node:assert/strict';
import {
  actualLine,
  approvalMoney,
  budgetLines,
  cardFrom,
  cardLines,
  executionLine,
  expectedPaymentLine,
  exposureLine,
  limitsFootnote,
  maxApprovedLine,
  modelLabel,
  providerTitle,
  referenceLine,
  referenceNote,
  statusLine,
} from './llmDisplay.ts';

/** Карточка вызова: тарифный ориентир, кто выполнил, статус, фактический платёж. */
const card = (patch = {}) => ({
  reference: {
    provider: 'kie',
    model: 'gpt-6-luna',
    kind: 'exact_model',
    cost_usd: 0.0003,
    status: 'estimated',
    rate_source: 'https://kie.ai/gpt-6-sol-and-luna',
    rate_as_of: '2026-10-20',
    rate_verified: false,
    ...(patch.reference || {}),
  },
  execution: {provider: 'kie', model: 'gpt-6-luna', status: 'paid', ...(patch.execution || {})},
  actual: {cost_usd: null, status: 'estimated', max_cost_usd: 0.0003, ...(patch.actual || {})},
});

test('тарифный ориентир: провайдер, модель-ориентир, дата тарифа и сумма с шестью знаками', () => {
  const line = referenceLine(card());
  assert.equal(line, 'По тарифу Kie.ai — GPT-6 Luna: ≈ $0.000300 (тариф от 2026-10-20)');
  assert.ok(line.includes('$0.000300'));
  assert.ok(!line.includes('$0.00 '));
});

test('ориентир по другой модели помечен прямо', () => {
  const other = card({reference: {kind: 'reference_model', model: 'gpt-5.6-luna', provider: 'piapi'}});
  assert.equal(referenceNote(other), '(другая модель, сравнение по объёму токенов)');
  assert.ok(referenceLine(other).includes('PiAPI'));
  assert.ok(referenceLine(other).includes('GPT-5.6 Luna'));
});

test('неподтверждённый тариф: «Тариф не подтверждён» без числа, нуля нет', () => {
  const none = card({
    reference: {kind: 'unavailable', status: 'unavailable', cost_usd: null, model: null, provider: null},
  });
  assert.equal(referenceLine(none), 'Тариф не подтверждён');
  assert.ok(!referenceLine(none).includes('$0'));
  assert.ok(!referenceLine(none).includes('0.00'));
  assert.equal(referenceNote(none), '');
});

test('кто выполнил: провайдер и читаемое имя модели', () => {
  const line = executionLine(
    card({execution: {provider: 'openrouter', model: 'minimax/minimax-m3.1-flash:free', status: 'free'}})
  );
  assert.equal(line, 'Исполняет: OpenRouter — MiniMax M3.1 Flash Free');
  assert.equal(providerTitle('piapi'), 'PiAPI');
});

test('статус маршрута: бесплатный, платный, неизвестное списание', () => {
  assert.equal(statusLine(card({actual: {status: 'free', cost_usd: 0, max_cost_usd: 0}})), 'Бесплатный API');
  assert.equal(statusLine(card({actual: {status: 'confirmed', cost_usd: 0.0003}})), 'Платный');
  assert.equal(statusLine(card({actual: {status: 'unknown', cost_usd: null}})), 'Неизвестное списание');
});

test('фактический платёж: подтверждённая сумма, бесплатный API, неизвестно — не ноль', () => {
  assert.equal(actualLine(card({actual: {status: 'confirmed', cost_usd: 0.0003}})), 'Реальный платёж: $0.000300');
  assert.equal(actualLine(card({actual: {status: 'free', cost_usd: 0}})), 'Бесплатный API');
  const unknown = actualLine(card({actual: {status: 'unknown', cost_usd: null}}));
  assert.equal(unknown, 'Реальный платёж: неизвестно');
  assert.ok(!unknown.includes('$0'));
});

test('порядок строк карточки зафиксирован: тариф, исполнитель, статус, фактический платёж', () => {
  const lines = cardLines(card({actual: {status: 'confirmed', cost_usd: 0.0003}}));
  assert.equal(lines.length, 4);
  assert.ok(lines[0].startsWith('По тарифу Kie.ai'));
  assert.ok(lines[1].startsWith('Исполняет:'));
  assert.equal(lines[2], 'Платный');
  assert.equal(lines[3], 'Реальный платёж: $0.000300');
});

test('до согласия видны ожидаемый реальный платёж и максимальный одобренный расход', () => {
  assert.equal(expectedPaymentLine(card()), 'Ожидаемый реальный платёж: $0.000300');
  assert.equal(maxApprovedLine(0.5), 'Максимальный одобренный расход: $0.5000');
  assert.equal(maxApprovedLine(null), 'Максимальный одобренный расход: не задан');
});

test('деньги окна подтверждения: ориентир первым, обе суммы — до согласия', () => {
  const money = approvalMoney(card(), '0.5');
  assert.equal(money.lines.length, 3);
  assert.equal(money.reference, referenceLine(card()));
  assert.equal(money.expectedPayment, 'Ожидаемый реальный платёж: $0.000300');
  assert.equal(money.maxApproved, 'Максимальный одобренный расход: $0.5000');
  assert.deepEqual(money.lines, [money.reference, money.expectedPayment, money.maxApproved]);
  assert.ok(money.lines[0].startsWith('По тарифу Kie.ai'));
});

test('под «Максимальный одобренный расход» лимит владельца, а не оценка узла', () => {
  const estimate = card({actual: {cost_usd: null, status: 'estimated', max_cost_usd: 0.0003}});
  const money = approvalMoney(estimate, '5');
  // ожидаемый реальный платёж — оценка узла...
  assert.equal(money.expectedPayment, 'Ожидаемый реальный платёж: $0.000300');
  // ...а одобренный потолок — тот лимит, который владелец реально одобряет
  assert.equal(money.maxApproved, 'Максимальный одобренный расход: $5.0000');
  assert.ok(!money.maxApproved.includes('$0.000300'));
  assert.deepEqual(money.lines, [money.reference, money.expectedPayment, money.maxApproved]);
  // лимит не выбран — потолок не показывается, нуля не выдумывается
  assert.equal(approvalMoney(estimate, '').maxApproved, 'Максимальный одобренный расход: не задан');
});

test('экспозиция LLM подписана и не путается с фактически потраченным', () => {
  const line = exposureLine('LLM-запросов кадров серии', 0.0003, 3);
  assert.ok(line.startsWith('Экспозиция LLM-запросов кадров серии'));
  assert.ok(line.includes('факт + резервы + неизвестные списания'));
  assert.ok(line.includes('$0.000300'));
  assert.ok(line.includes('3 вызовов'));
  assert.ok(!line.includes('Фактически потрачено'));
});

test('сноска лимитов: работа агента в чате Codex занимает те же лимиты', () => {
  const note = limitsFootnote();
  assert.ok(note.includes('Работа агента в чате Codex'));
  assert.ok(note.includes('занимает те же лимиты'));
  assert.ok(!note.includes('не расходует'));
});

test('сводка бюджета: четыре итога раздельными строками, ориентир — не деньги', () => {
  const lines = budgetLines({
    actual_cost_usd: 0.0003,
    reserved_usd: 0.5,
    unknown_cost_usd: 0,
    reference_cost_usd: 0.0003,
    calls: 3,
  });
  assert.equal(lines.length, 4);
  assert.ok(lines[0].includes('Фактически потрачено'));
  assert.ok(lines[0].includes('$0.000300'));
  assert.ok(lines[1].includes('Зарезервировано'));
  assert.ok(lines[2].includes('Неизвестные списания'));
  assert.ok(lines[3].includes('Эквивалент по Kie/PiAPI'));
  assert.ok(lines[3].includes('не деньги'));
});

test('имя модели читаемое, непрочитанный идентификатор отдаётся как есть', () => {
  assert.equal(modelLabel('gpt-6-luna'), 'GPT-6 Luna');
  assert.equal(modelLabel('claude-haiku-5-5'), 'Claude Haiku 5.5');
  assert.equal(modelLabel('MiniMax-M3.1-Flash'), 'MiniMax M3.1 Flash');
  assert.equal(modelLabel('zzz-unknown-id'), 'Zzz Unknown Id');
  assert.equal(modelLabel('zzz'), 'zzz');
  assert.equal(modelLabel(''), '');
});

test('карточка собирается из ответа сервера, недостающие поля не выдумываются', () => {
  const built = cardFrom({
    reference: {provider: 'kie', model: 'gpt-6-luna', kind: 'exact_model', cost_usd: 0.0003, status: 'confirmed'},
    execution: {provider: 'kie', model: 'gpt-6-luna', status: 'paid'},
    actual: {cost_usd: 0.0003, status: 'confirmed', max_cost_usd: 0.0003},
  });
  assert.equal(built.reference.provider, 'kie');
  assert.equal(built.actual.cost_usd, 0.0003);
  assert.equal(built.reference.rate_as_of, null);
  const empty = cardFrom({});
  assert.equal(empty.reference.kind, 'unavailable');
  assert.equal(empty.reference.cost_usd, null);
  assert.equal(empty.actual.cost_usd, null);
  assert.equal(empty.actual.status, 'unknown');
});
