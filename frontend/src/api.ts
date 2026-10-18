export const PAID_LLM_ENABLED = false;
// One local session per server launch. A 401 refreshes it for the NEXT action only.
let session: Promise<string> | null = null;
function sessionToken() {
  if (!session)
    session = window
      .fetch('/api/session', {cache: 'no-store', credentials: 'same-origin'})
      .then(async r => {
        if (!r.ok) throw Error('Не удалось открыть локальную сессию');
        return (await r.json()).token as string;
      })
      .catch(e => {
        session = null;
        throw e;
      });
  return session;
}
export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const parentAbort = () => controller.abort();
  if (init?.signal?.aborted) controller.abort();
  init?.signal?.addEventListener('abort', parentAbort, {once: true});
  const timer = window.setTimeout(
    () => controller.abort(),
    String(input).endsWith('/health') ? 10000 : 180000
  );
  try {
    const headers = new Headers(init?.headers);
    headers.set('X-Studio-Session', await sessionToken());
    const response = await window.fetch(input, {
      ...init,
      headers,
      credentials: 'same-origin',
      signal: controller.signal,
    });
    if (response.status === 401) session = null;
    return response;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error(
        'API не ответил вовремя. Проверь состояние сервера; платную задачу повторно не отправляй без проверки очереди.'
      );
    }
    throw new Error('Не удалось подключиться к API. Проверь запуск backend на 127.0.0.1:8000.');
  } finally {
    window.clearTimeout(timer);
    init?.signal?.removeEventListener('abort', parentAbort);
  }
}

/** JSON ответа сервера; при ошибке — исключение с текстом detail. */
export async function responseJson(r: Response) {
  const d = await r.json();
  if (!r.ok) throw Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail));
  return d;
}
