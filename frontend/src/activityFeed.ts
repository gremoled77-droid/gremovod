/** Read-only activity polling. Refresh cancels the outstanding GET, never submits work. */
export function startActivityFeed<T>(
  projectId: string,
  fetcher: (url: string, init: {signal: AbortSignal}) => Promise<Response>,
  onItems: (items: T[]) => void,
  onError: (error: string) => void
) {
  let active = true,
    version = '',
    generation = 0,
    current: AbortController | null = null;
  let retry: ReturnType<typeof setTimeout> | null = null,
    wake: (() => void) | null = null;
  const loop = async () => {
    while (active) {
      const epoch = generation,
        controller = new AbortController();
      current = controller;
      try {
        const response = await fetcher(
          `/api/activity?project_id=${encodeURIComponent(projectId)}&since=${encodeURIComponent(version)}&wait=${version ? 20 : 0}`,
          {signal: controller.signal}
        );
        if (!response.ok) throw Error('Лента заданий недоступна');
        const data = await response.json();
        if (!active || epoch !== generation || controller.signal.aborted) continue;
        if (typeof data.version !== 'string' || !Array.isArray(data.items))
          throw Error('Некорректный ответ ленты заданий');
        version = data.version;
        if (data.changed) onItems(data.items);
        onError('');
      } catch (e) {
        if (!active) return;
        if (epoch !== generation) continue;
        onError(e instanceof Error ? e.message : String(e));
        await new Promise<void>(resolve => {
          wake = resolve;
          retry = setTimeout(resolve, 4000);
        });
        retry = null;
        wake = null;
      }
    }
  };
  void loop();
  const interrupt = () => {
    current?.abort();
    if (retry) clearTimeout(retry);
    wake?.();
    retry = null;
    wake = null;
  };
  return {
    refresh() {
      if (active) {
        generation++;
        version = '';
        interrupt();
      }
    },
    stop() {
      active = false;
      interrupt();
    },
  };
}
