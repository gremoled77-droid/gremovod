/** Чистые правила способов генерации (без сети и хранилища): способы, роли референсов, тела заданий. */
export type ImageRoute = 'api' | 'chatgpt' | 'codex';

export const ROUTES: {id: ImageRoute; label: string; hint: string}[] = [
  {id: 'api', label: 'API · выбранные модели', hint: 'Платно: сначала оценка цены и подтверждение'},
  {
    id: 'chatgpt',
    label: 'ChatGPT вручную',
    hint: 'Подготовить промпт и вернуть картинку вручную. Лимиты и оплата — в ChatGPT',
  },
  {id: 'codex', label: 'Codex', hint: 'Очередь Codex на компьютере. Лимиты и оплата — во внешнем сервисе'},
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

/** Validate the entire batch before any write; the native worker accepts one active job per project. */
export function validateImageJobs(jobs: ImageJob[], route: ImageRoute): void {
  if (!jobs.length) throw Error('Нечего отправлять');
  if (route === 'codex' && jobs.length > 1)
    throw Error('Codex принимает одно задание за раз. Выбери одну картинку и дождись результата.');
  for (const job of jobs) {
    if (!job.projectId) throw Error('Сначала сохрани проект');
    if (!job.prompt.trim()) throw Error('Напиши промпт');
    if (job.projectId !== jobs[0].projectId) throw Error('Задания должны принадлежать одному проекту');
    const max = route === 'codex' ? 4000 : 20000;
    if (job.prompt.length > max) throw Error(`Сократи промпт до ${max} символов для этого способа`);
    if (job.referenceAssetIds.length > (route === 'codex' ? 8 : 16))
      throw Error('Слишком много референсов для выбранного способа');
  }
}
