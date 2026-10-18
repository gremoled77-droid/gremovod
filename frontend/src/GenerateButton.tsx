import {useEffect, useRef, useState} from 'react';
import {price} from './PriceTable';
import {
  openQueue,
  readRoute,
  ROUTES,
  saveRoute,
  sendToChatGPT,
  sendToCodex,
  type ImageJob,
  type ImageRoute,
} from './imageRoutes';

type Job = ImageJob | ImageJob[];

export const usd = (value: number) => '$' + (value < 0.1 ? value.toFixed(3) : value.toFixed(2));

/** Оценка API-запуска: сумма цен моделей по сухому прогону на сервере (без сети к провайдеру). */
export function useEstimate(runs: {model: string; options: Record<string, string | number>}[]) {
  const [total, setTotal] = useState<number | null>(null);
  const signature = JSON.stringify(runs);
  useEffect(() => {
    let live = true;
    if (!runs.length) {
      setTotal(null);
      return;
    }
    void Promise.all(runs.map(r => price(r.model, r.options))).then(list => {
      if (live) setTotal(list.some(p => p === null) ? null : list.reduce<number>((a, p) => a + (p || 0), 0));
    });
    return () => {
      live = false;
    };
  }, [signature]);
  return total;
}

/**
 * Одна кнопка генерации картинок для всех экранов. Основное нажатие запускает выбранный способ,
 * стрелка ▾ меняет способ: API (оценка цены и подтверждение), ChatGPT вручную, Codex. Выбор
 * запоминается для проекта.
 */
export default function GenerateButton({
  projectId,
  busy = false,
  disabled = false,
  estimate = null,
  count = 1,
  onApi,
  job,
  onNotice,
  onError,
}: {
  projectId: string;
  busy?: boolean;
  disabled?: boolean;
  /** Цена API-запуска; null — пока неизвестна. */
  estimate?: number | null;
  /** Сколько картинок уйдёт в API (для подписи). */
  count?: number;
  /** API: экран собирает заявку и открывает окно цены и подтверждения. */
  onApi: () => void | Promise<void>;
  /** ChatGPT и Codex: промпт и референсы (одно или пакет заданий); строка — что мешает отправке. */
  job: () => Job | string | Promise<Job | string>;
  onNotice: (text: string) => void;
  onError: (text: string) => void;
}) {
  const [route, setRoute] = useState<ImageRoute>(() => readRoute(projectId));
  const [open, setOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => setRoute(readRoute(projectId)), [projectId]);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !box.current?.contains(e.target as Node))
        setOpen(false);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', close);
    };
  }, [open]);

  const choose = (next: ImageRoute) => {
    setRoute(next);
    saveRoute(projectId, next);
    setOpen(false);
  };

  const run = async () => {
    onError('');
    if (route === 'api') return void onApi();
    setSending(true);
    try {
      const prepared = await job();
      if (typeof prepared === 'string') return onError(prepared);
      const jobs = Array.isArray(prepared) ? prepared : [prepared];
      if (!jobs.length) return onError('Нечего отправлять');
      onNotice(route === 'chatgpt' ? await sendToChatGPT(jobs) : await sendToCodex(jobs));
      openQueue();
    } catch (e) {
      onError(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  };

  const working = busy || sending;
  const label = working
    ? 'Готовлю…'
    : route === 'api'
      ? `Сгенерировать${count > 1 ? ` (${count})` : ''}${estimate !== null ? ' · ' + usd(estimate) : ''}`
      : route === 'chatgpt'
        ? 'Сгенерировать в ChatGPT · $0'
        : 'Отправить в Codex · $0';
  const current = ROUTES.find(r => r.id === route)!;
  return (
    <div className="gen-split" ref={box}>
      <button
        className="primary gen-main"
        disabled={disabled || working}
        title={current.hint}
        onClick={() => void run()}
      >
        {label}
      </button>
      <button
        className="primary gen-more"
        aria-label={'Способ генерации: ' + current.label}
        aria-haspopup="menu"
        aria-expanded={open}
        disabled={working}
        onClick={() => setOpen(v => !v)}
      >
        ▾
      </button>
      {open && (
        <div className="gen-menu" role="menu" aria-label="Способ генерации">
          {ROUTES.map(r => (
            <button
              key={r.id}
              role="menuitemradio"
              aria-checked={r.id === route}
              className={r.id === route ? 'on' : ''}
              onClick={() => choose(r.id)}
            >
              <b>{r.label}</b>
              <small>{r.hint}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
