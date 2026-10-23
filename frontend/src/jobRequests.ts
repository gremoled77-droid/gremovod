import {readLocal, writeLocal} from './localDrafts';
import type {GenerationRequest} from './GenerationReview';

const KEY = 'studio:job-requests';
const LIMIT = 150;

/** Запоминает исходные параметры запуска в браузере: по ним «Обновить» в очереди открывает новую оценку цены. */
export function rememberRequest(jobId: string, request: GenerationRequest) {
  const all = readLocal<Record<string, GenerationRequest>>(KEY, {});
  all[jobId] = request;
  const ids = Object.keys(all);
  for (const old of ids.slice(0, Math.max(0, ids.length - LIMIT))) delete all[old];
  writeLocal(KEY, all);
}

export const recallRequest = (jobId: string): GenerationRequest | null =>
  readLocal<Record<string, GenerationRequest>>(KEY, {})[jobId] || null;
