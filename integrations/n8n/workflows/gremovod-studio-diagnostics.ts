// GremoVOD v2 — диагностика связи со студией.
//
// Без платных вызовов: проверяет туннель (public /api/health) и машинный токен
// (/api/qa/reviews/<ping>). Ответ студии различает три случая:
//   404 — токен принят (ревью с таким id просто не существует);
//   401/403 — токен отклонён;
//   нет ответа — стенд или туннель не подняты.
//
// Развёртывание: integrations/n8n/CLOUD_QA_RUNBOOK.md
import { workflow, node, trigger, expr } from '@n8n/workflow-sdk';

const start = trigger({
  type: 'n8n-nodes-base.manualTrigger',
  version: 1,
  config: { name: 'Старт' },
});

const tunnel = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.3,
  config: {
    name: 'Туннель: /api/health',
    parameters: {
      method: 'GET',
      url: 'https://studio.grem.win/api/health',
      options: { timeout: 20000, response: { response: { neverError: true, fullResponse: true } } },
    },
  },
});

const auth = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.3,
  config: {
    name: 'Токен студии: /api/qa/reviews/<ping>',
    parameters: {
      method: 'GET',
      url: expr("{{ 'https://studio.grem.win/api/qa/reviews/ping-' + Date.now() }}"),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
      options: { timeout: 20000, response: { response: { neverError: true, fullResponse: true } } },
    },
    credentials: { httpHeaderAuth: newCredential('Header Auth account') },
  },
});

const report = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Диагностика',
    parameters: {
      mode: 'runOnceForAllItems',
      language: 'javaScript',
      jsCode: `const t = $('Туннель: /api/health').first().json || {};
const a = $('Токен студии: /api/qa/reviews/<ping>').first().json || {};
const status = a.statusCode;
let verdict = 'НЕИЗВЕСТНО';
let hint = '';
if (status === 404) {
  verdict = 'ТОКЕН ПРИНЯТ';
  hint = 'Студия ответила 404 на несуществующий review — авторизация прошла, туннель и токен исправны.';
} else if (status === 401 || status === 403) {
  verdict = 'ТОКЕН ОТКЛОНЁН';
  hint = 'Студия отклонила токен. Проверь значение в креде и область (project) токена.';
} else if (status === 200) {
  verdict = 'ОТВЕТ ПОЛУЧЕН';
  hint = 'Студия ответила 200 — токен принят.';
} else if (a.error !== undefined || status === undefined) {
  verdict = 'НЕТ СВЯЗИ';
  hint = 'Ответ не получен: ' + String(a.error || a.message || 'неизвестная причина') + '. Проверь, запущен ли стенд и туннель.';
} else {
  verdict = 'КОД ' + status;
  hint = 'Неожиданный код ответа. Проверь логи студии.';
}
return [{ json: {
  tunnel_status: t.statusCode !== undefined ? t.statusCode : 'no-response',
  tunnel_body: t.body || null,
  studio_status: status !== undefined ? status : 'no-response',
  studio_body: a.body || null,
  verdict,
  hint,
  checked_at: new Date().toISOString(),
} }];`,
    },
  },
});

export default workflow('gremovod-studio-diagnostics', 'GremoVOD v2 — диагностика связи со студией')
  .add(start)
  .to(tunnel)
  .to(auth)
  .to(report);
