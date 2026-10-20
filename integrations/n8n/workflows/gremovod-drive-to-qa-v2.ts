// GremoVOD v2 — Google Drive → приёмка в студии.
//
// Файл из Google Drive (ручной запуск или триггер «новый файл в папке») → текст →
// ревью в студии. Платных вызовов нет: критики приходят из других workflow.
// Пустой или бинарный файл в приёмку не идёт — узел падает с понятной причиной.
//
// Требуется гугл-кред (Google Drive OAuth) — его создаёт владелец в n8n.
// Развёртывание: integrations/n8n/CLOUD_QA_RUNBOOK.md
import { workflow, node, trigger, merge, newCredential, expr } from '@n8n/workflow-sdk';

const BASE = 'https://studio.grem.win';
const PROJECT = '5b2e8e41-bc8a-4575-aec7-7ba5c2ef16d6';
const STUDIO_CRED = { httpHeaderAuth: newCredential('Header Auth account') };
const DRIVE_CRED = { googleDriveOAuth2Api: newCredential('Google Drive — gremshrem') };

const manual = trigger({
  type: 'n8n-nodes-base.manualTrigger',
  version: 1,
  config: { name: 'Старт: вручную (file_id из входа)' },
});

const driveTrigger = trigger({
  type: 'n8n-nodes-base.googleDriveTrigger',
  version: 1,
  config: {
    name: 'Google Drive: новый файл в папке',
    parameters: {
      triggerOn: 'specificFolder',
      authentication: 'oAuth2',
      event: 'fileCreated',
      options: { fileType: 'all' },
    },
    credentials: DRIVE_CRED,
  },
});

const mergeSources = merge({
  mode: 'append',
  config: { name: 'Источник: ручной или Drive' },
});

const download = node({
  type: 'n8n-nodes-base.googleDrive',
  version: 3,
  config: {
    name: 'Drive: скачать файл',
    parameters: {
      resource: 'file',
      operation: 'download',
      authentication: 'oAuth2',
      fileId: { __rl: true, mode: 'id', value: expr('{{ $json.id || $json.file_id }}') },
      options: { binaryPropertyName: 'data' },
    },
    credentials: DRIVE_CRED,
  },
});

const extract = node({
  type: 'n8n-nodes-base.extractFromFile',
  version: 1.1,
  config: {
    name: 'Извлечь текст файла',
    parameters: {
      operation: 'text',
      binaryPropertyName: 'data',
      destinationKey: 'file_text',
    },
  },
});

const buildRequest = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Собрать запрос ревью из файла',
    parameters: {
      mode: 'runOnceForAllItems',
      language: 'javaScript',
      jsCode: `const input = $json || {};
const text = String(input.file_text || '').trim();
const name = input.name || input.file_name || 'drive-file';
if (!text) {
  throw new Error('Из файла не извлечён текст: для проверки нужен .md, .txt, .json или .docx. Пустой или бинарный файл в приёмку не идёт.');
}
const projectId = '${PROJECT}';
return [{ json: {
  base: '${BASE}',
  file_name: name,
  file_text: text,
  body: {
    project_id: projectId,
    task_id: input.task_id || ('drive-' + name),
    artifact_id: input.artifact_id || ('drive-artifact-' + name),
    artifact_revision: input.artifact_revision || 'rev-1',
    artifact_text: text,
    canon_text: input.canon_text || 'Канон не передан: проверяется только соответствие переданному тексту.',
    brief_text: input.brief_text || ('Источник: Google Drive, файл ' + name),
    review_phase: 'TEXT_PRECHECK',
    requested_scopes: ['TEXT'],
    request_id: 'n8n-drive-' + Date.now(),
  },
}}];`,
    },
  },
});

const createReview = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.3,
  config: {
    name: 'Открыть ревью в студии',
    parameters: {
      method: 'POST',
      url: expr('{{ $json.base }}/api/qa/reviews'),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ $json.body }}'),
      options: { timeout: 30000 },
    },
    credentials: STUDIO_CRED,
  },
});

const packet = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.3,
  config: {
    name: 'Пакет: критик ТЗ',
    parameters: {
      method: 'GET',
      url: expr("{{ $('Собрать запрос ревью из файла').item.json.base }}/api/qa/reviews/{{ $('Открыть ревью в студии').item.json.review.review_id }}/packet/REVIEW-REQ"),
      authentication: 'genericCredentialType',
      genericAuthType: 'httpHeaderAuth',
      options: { timeout: 30000 },
    },
    credentials: STUDIO_CRED,
  },
});

const report = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Отчёт: файл принят в студию',
    parameters: {
      mode: 'runOnceForAllItems',
      language: 'javaScript',
      jsCode: `const packet = $json || {};
const src = $('Собрать запрос ревью из файла').first().json || {};
return [{ json: {
  source: 'google-drive',
  file_name: src.file_name || null,
  review_id: packet.review_id || null,
  artifact_revision: packet.artifact_revision || null,
  review_phase: packet.review_phase || 'TEXT_PRECHECK',
  requested_scopes: packet.requested_scopes || ['TEXT'],
  trusted_revisions: packet.trusted_revisions || null,
  next_step: 'Критики A6/A7 должны прислать вердикты; решение по выпуску остаётся за владельцем.',
  published_by_workflow: false,
  artifact_chars: src.file_text ? String(src.file_text).length : 0,
}}];`,
    },
  },
});

export default workflow('gremovod-drive-to-qa-v2', 'GremoVOD v2 — Google Drive → приёмка в студии')
  .add(manual)
  .to(mergeSources)
  .add(driveTrigger)
  .to(mergeSources)
  .to(download)
  .to(extract)
  .to(buildRequest)
  .to(createReview)
  .to(packet)
  .to(report)
  .group('Источник файла', [mergeSources, download, extract], {
    description: 'Файл из Google Drive: ручной запуск или автоматически при появлении файла в папке',
  })
  .group('Открыть ревью', [buildRequest, createReview, packet], {
    description: 'Текст файла превращается в ревью студии; критикам отдаётся пакет REVIEW-REQ',
  })
  .group('Отчёт', [report], {
    description: 'Фиксирует, что файл принят в студию; вердикт и выпуск — за владельцем',
  });
