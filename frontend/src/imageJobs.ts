/** Чистые правила способов генерации (без сети и хранилища): способы, роли референсов, тела заданий. */
export type ImageRoute = 'api' | 'chatgpt' | 'codex';

export const ROUTES: {id: ImageRoute; label: string; hint: string}[] = [
  {id: 'api', label: 'API · PiAPI', hint: 'Платно: сначала оценка цены и подтверждение'},
  {
    id: 'chatgpt',
    label: 'ChatGPT вручную',
    hint: '$0: копирую промпт и открываю чат, картинку вернёшь вставкой',
  },
  {id: 'codex', label: 'Codex', hint: '$0: задание уходит в очередь ветки Codex на компьютере'},
];

/** Что нужно ChatGPT и Codex: промпт, модель-цель и референсы из библиотеки по порядку. */
export type ImageJob = {
  projectId: string;
  prompt: string;
  /** Модель, под которую написан промпт (для ChatGPT/Codex — подпись задания). */
  target: string;
  referenceAssetIds: string[];
  nodeId?: string;
};

export const referenceRoles = (ids: string[]) =>
  ids.map((_, i) => (i === 0 ? 'главный референс' : 'референс'));

/** Тело POST /api/external-jobs: ручная генерация в ChatGPT. */
export function externalJobBody(job: ImageJob, id: string) {
  const roles = referenceRoles(job.referenceAssetIds);
  return {
    project_id: job.projectId,
    request_id: id,
    target: job.target,
    prompt: job.prompt,
    service: 'chatgpt',
    references: job.referenceAssetIds.map((asset_id, i) => ({asset_id, role: roles[i]})),
    ...(job.nodeId ? {node_id: job.nodeId} : {}),
  };
}

/** Тело POST /api/chatgpt/jobs: генерация веткой Codex (ей нужна модель GPT Image). */
export function codexJobBody(job: ImageJob, id: string) {
  return {
    project_id: job.projectId,
    target: job.target.startsWith('gpt-image-') ? job.target : 'gpt-image-2.5',
    operation: 'generate',
    request_id: id,
    brief: job.prompt,
    reference_asset_ids: job.referenceAssetIds,
  };
}

/** Сохранённое значение способа; неизвестное — API. */
export const parseRoute = (value: unknown): ImageRoute =>
  ROUTES.some(r => r.id === value) ? (value as ImageRoute) : 'api';
