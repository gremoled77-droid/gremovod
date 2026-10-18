/** Способы генерации картинки: API (PiAPI), ChatGPT вручную, Codex. Одна логика для всех экранов. */
import {apiFetch} from './api';
import {copyTextFor, DEFAULT_CHAT_URL, getChatUrl} from './chatLink';
import {readLocal, writeLocal} from './localDrafts';
import {
  codexJobBody,
  externalJobBody,
  parseRoute,
  referenceRoles,
  validateImageJobs,
  type ImageJob,
  type ImageRoute,
} from './imageJobs';

export {ROUTES, type ImageJob, type ImageRoute} from './imageJobs';

const routeKey = (projectId: string) => 'studio:image-route:' + (projectId || 'new');

export function readRoute(projectId: string): ImageRoute {
  return parseRoute(readLocal<string>(routeKey(projectId), 'api'));
}

export function saveRoute(projectId: string, route: ImageRoute) {
  writeLocal(routeKey(projectId), route);
}

export const requestId = () => crypto.randomUUID().replace(/-/g, '');

async function postJson(path: string, body: unknown) {
  const r = await apiFetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const info = data.detail ?? data;
    throw Error(typeof info === 'string' ? info : JSON.stringify(info));
  }
  return data;
}

/** На телефоне уходим в приложение ChatGPT; на компьютере чат открывается во вкладке рядом. */
export function openChatApp() {
  const url = getChatUrl() || DEFAULT_CHAT_URL;
  if (window.matchMedia('(max-width: 700px)').matches) window.location.href = url;
  else window.open(url, '_blank', 'noopener');
}

/** Копирует текст; на телефоне вызывать сразу в обработчике нажатия, до запросов к серверу. */
export function copyText(text: string): Promise<boolean> {
  return navigator.clipboard
    ? navigator.clipboard.writeText(text).then(
        () => true,
        () => false
      )
    : Promise.resolve(false);
}

/** Save before leaving the studio. Opening the external chat is a separate user gesture in the tray. */
export async function sendToChatGPT(jobs: ImageJob[]): Promise<string> {
  validateImageJobs(jobs, 'chatgpt');
  const [job] = jobs;
  const copied = copyText(copyTextFor(job.prompt, referenceRoles(job.referenceAssetIds)));
  let saved = 0;
  try {
    for (const item of jobs) {
      await postJson('/api/external-jobs', externalJobBody(item, requestId()));
      saved++;
    }
  } catch (e) {
    throw Error(
      `Сохранено заданий: ${saved} из ${jobs.length}. Проверь очередь перед повторной отправкой: ответ последнего запроса мог потеряться. ${e instanceof Error ? e.message : String(e)}`
    );
  } finally {
    openQueue();
  }
  const ok = await copied;
  const more = jobs.length > 1 ? ` Остальные промпты (${jobs.length - 1}) — в «Очереди».` : '';
  return ok
    ? `Промпт скопирован. В очереди открой ChatGPT и приложи референсы. Готовую картинку верни туда же: Ctrl+V или файл.${more}`
    : `Задание сохранено. Полный промпт, референсы и кнопка открытия ChatGPT — в очереди справа.${more}`;
}

/** Любое задание очереди Codex (генерация, описание героя, карточка производства). */
export const queueCodexJob = (body: Record<string, unknown>) => postJson('/api/chatgpt/jobs', body);

/** Codex: ставит задания в очередь ветки Codex; сообщает, слушает ли ветка очередь. */
export async function sendToCodex(jobs: ImageJob[]): Promise<string> {
  validateImageJobs(jobs, 'codex');
  for (const job of jobs) await queueCodexJob(codexJobBody(job, requestId()));
  const status = await apiFetch('/api/chatgpt/status')
    .then(r => (r.ok ? r.json() : null))
    .catch(() => null);
  return status?.worker_online
    ? 'Отправлено в Codex. Картинка появится в библиотеке, когда ветка её сгенерирует.'
    : 'Поставлено в очередь Codex, но ветка сейчас не слушает. Открой её на компьютере и напиши «Продолжай очередь студии».';
}

export type ExternalJobDetails = {
  id: string;
  project_id: string;
  prompt: string;
  copy_text: string;
  references: {index: number; asset_id: string; role: string; file_url: string}[];
};

/** Activity contains only a 200-character summary; never use it as the actual prompt. */
export async function loadExternalJob(jobId: string): Promise<ExternalJobDetails> {
  const r = await apiFetch(`/api/external-jobs/${encodeURIComponent(jobId)}`);
  if (!r.ok) throw Error('Не удалось загрузить полное задание. Повтори загрузку.');
  return r.json();
}

/** Готовая картинка из ChatGPT: файл или вставка из буфера. */
export async function attachExternalResult(jobId: string, file: File) {
  const form = new FormData();
  form.append('file', file);
  const r = await apiFetch(`/api/external-jobs/${jobId}/result`, {method: 'POST', body: form});
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw Error(typeof data.detail === 'string' ? data.detail : 'Не удалось сохранить картинку');
  }
}

export async function cancelCodexJob(jobId: string) {
  await postJson(`/api/chatgpt/jobs/${jobId}/cancel`, {});
}

export async function cancelExternalJob(jobId: string) {
  await postJson(`/api/external-jobs/${jobId}/cancel`, {});
}

/** Открыть правую панель «Очередь» (там лоток ожидания ChatGPT/Codex). */
export const OPEN_QUEUE_EVENT = 'studio:open-queue';
export const openQueue = () => window.dispatchEvent(new Event(OPEN_QUEUE_EVENT));
