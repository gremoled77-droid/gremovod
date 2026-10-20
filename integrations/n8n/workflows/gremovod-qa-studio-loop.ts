import { workflow, node, trigger, newCredential, expr } from '@n8n/workflow-sdk';

const BASE = 'https://studio.grem.win';
const PROJECT = '5b2e8e41-bc8a-4575-aec7-7ba5c2ef16d6';

const start = trigger({
  type: 'n8n-nodes-base.manualTrigger',
  version: 1,
  config: { name: 'Старт: ручной прогон' },
});

const buildRequest = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Собрать запрос ревью',
    parameters: {
      mode: 'runOnceForAllItems',
      language: 'javaScript',
      jsCode: `const input = $json || {};
const base = '${BASE}';
const projectId = '${PROJECT}';
const stamp = Date.now();
return [{ json: {
  base,
  project_id: projectId,
  body: {
    project_id: projectId,
    task_id: input.task_id || 'task-n8n-1',
    artifact_id: input.artifact_id || 'artifact-1',
    artifact_revision: input.artifact_revision || 'rev-1',
    artifact_text: input.artifact_text || 'Грэм подмигивает в машине цвета жёлтый.',
    canon_text: input.canon_text || 'Машина жёлтая, фары круглые.',
    brief_text: input.brief_text || 'Сцена: подмигнуть.',
    review_phase: input.review_phase || 'TEXT_PRECHECK',
    requested_scopes: input.requested_scopes || ['TEXT'],
    request_id: input.request_id || ('n8n-review-' + stamp),
  },
}}];`,
    },
  },
});

const createReview = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.3,
  config: {
    name: 'Создать ревью',
    parameters: {
      method: 'POST',
      url: expr('{{ $json.base }}/api/qa/reviews'),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ $json.body }}'),
      options: { timeout: 30000 },
    },
    credentials: { httpTemplatedCustomAuth: newCredential('GremoVOD Studio QA Token') },
  },
});

const packetReq = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.3,
  config: {
    name: 'Пакет: критик ТЗ',
    parameters: {
      method: 'GET',
      url: expr("{{ $('Собрать запрос ревью').item.json.base }}/api/qa/reviews/{{ $('Создать ревью').item.json.review.review_id }}/packet/REVIEW-REQ"),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
      options: { timeout: 30000 },
    },
    credentials: { httpTemplatedCustomAuth: newCredential('GremoVOD Studio QA Token') },
  },
});

const verdictReq = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Вердикт: критик ТЗ',
    parameters: {
      mode: 'runOnceForAllItems',
      language: 'javaScript',
      jsCode: `const packet = $json || {};
const role = 'REVIEW-REQ';
const provided = (($('Старт: ручной прогон').item.json || {}).verdicts || {})[role];
const base = {
  role,
  artifact_revision: packet.artifact_revision,
  model: 'n8n-scaffold-no-critic',
  checked_scopes: [],
  scope_results: {},
  evidence: [],
  biggest_gap: null,
};
if (provided) {
  return [{ json: Object.assign({}, base, provided, { role, artifact_revision: packet.artifact_revision }) }];
}
return [{ json: Object.assign({}, base, {
  verdict: 'BLOCKED',
  missing_inputs: ['Независимый критик ТЗ не подключён: нужен вызов A6. Пока вердикт не выносится.'],
}) }];`,
    },
  },
});

const submitReq = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.3,
  config: {
    name: 'Отправить вердикт ТЗ',
    parameters: {
      method: 'POST',
      url: expr("{{ $('Собрать запрос ревью').item.json.base }}/api/qa/reviews/{{ $('Создать ревью').item.json.review.review_id }}/verdicts"),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ $json }}'),
      options: { timeout: 30000 },
    },
    credentials: { httpTemplatedCustomAuth: newCredential('GremoVOD Studio QA Token') },
  },
});

const packetSys = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.3,
  config: {
    name: 'Пакет: критик системы',
    parameters: {
      method: 'GET',
      url: expr("{{ $('Собрать запрос ревью').item.json.base }}/api/qa/reviews/{{ $('Создать ревью').item.json.review.review_id }}/packet/REVIEW-SYSTEM"),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
      options: { timeout: 30000 },
    },
    credentials: { httpTemplatedCustomAuth: newCredential('GremoVOD Studio QA Token') },
  },
});

const verdictSys = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Вердикт: критик системы',
    parameters: {
      mode: 'runOnceForAllItems',
      language: 'javaScript',
      jsCode: `const packet = $json || {};
const role = 'REVIEW-SYSTEM';
const provided = (($('Старт: ручной прогон').item.json || {}).verdicts || {})[role];
const base = {
  role,
  artifact_revision: packet.artifact_revision,
  model: 'n8n-scaffold-no-critic',
  checked_scopes: [],
  scope_results: {},
  evidence: [],
  biggest_gap: null,
};
if (provided) {
  return [{ json: Object.assign({}, base, provided, { role, artifact_revision: packet.artifact_revision }) }];
}
return [{ json: Object.assign({}, base, {
  verdict: 'BLOCKED',
  missing_inputs: ['Независимый критик системы и канона не подключён: нужен вызов A7. Пока вердикт не выносится.'],
}) }];`,
    },
  },
});

const submitSys = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.3,
  config: {
    name: 'Отправить вердикт системы',
    parameters: {
      method: 'POST',
      url: expr("{{ $('Собрать запрос ревью').item.json.base }}/api/qa/reviews/{{ $('Создать ревью').item.json.review.review_id }}/verdicts"),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ $json }}'),
      options: { timeout: 30000 },
    },
    credentials: { httpTemplatedCustomAuth: newCredential('GremoVOD Studio QA Token') },
  },
});

const finalState = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.3,
  config: {
    name: 'Итог ревью',
    parameters: {
      method: 'GET',
      url: expr("{{ $('Собрать запрос ревью').item.json.base }}/api/qa/reviews/{{ $('Создать ревью').item.json.review.review_id }}"),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpTemplatedCustomAuth',
      options: { timeout: 30000 },
    },
    credentials: { httpTemplatedCustomAuth: newCredential('GremoVOD Studio QA Token') },
  },
});

const report = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Отчёт по приёмке',
    parameters: {
      mode: 'runOnceForAllItems',
      language: 'javaScript',
      jsCode: `const state = $json || {};
const review = state.review || {};
const verdicts = state.verdicts || [];
return [{ json: {
  review_id: review.review_id,
  artifact_revision: review.artifact_revision,
  review_phase: review.review_phase,
  status: state.status,
  next_action: state.next_action,
  owner_decision_required: state.status === 'TEXT_PRECHECK_PASSED_AWAITING_OWNER' || state.status === 'AWAITING_OWNER_APPROVAL',
  published_by_workflow: false,
  verdicts: verdicts.map((v) => ({
    role: v.role,
    overall: v.overall,
    scope_results: v.scope_results,
    notes: v.notes,
    biggest_gap: v.biggest_gap,
  })),
}}];`,
    },
  },
});

export default workflow('gremovod-qa-studio-loop', 'GremoVOD — приёмка через студию')
  .add(start)
  .to(buildRequest)
  .to(createReview)
  .to(packetReq)
  .to(verdictReq)
  .to(submitReq)
  .to(packetSys)
  .to(verdictSys)
  .to(submitSys)
  .to(finalState)
  .to(report)
  .group('Открыть ревью', [buildRequest, createReview], {
    description: 'Собирает версии артефакта и открывает ревью в студии через машинный токен',
  })
  .group('Собрать и записать вердикты', [packetReq, verdictReq, submitReq, packetSys, verdictSys, submitSys], {
    description: 'Раздаёт изолированные пакеты критикам и записывает их вердикты в студию',
  })
  .group('Зафиксировать итог', [finalState, report], {
    description: 'Забирает итог ревью из студии: решение по выпуску остаётся за владельцем',
  });
