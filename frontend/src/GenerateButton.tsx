import {useEffect, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {price} from './PriceTable';
import {validateImageJobs} from './imageJobs';
import {useSharedActivity} from './ActivityContext';
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
  const signature = JSON.stringify(runs);
  const [quote, setQuote] = useState<{signature: string; total: number | null} | null>(null);
  useEffect(() => {
    let live = true;
    if (!runs.length) {
      setQuote(null);
      return;
    }
    void Promise.all(runs.map(r => price(r.model, r.options))).then(list => {
      if (live)
        setQuote({
          signature,
          total: list.some(p => p === null) ? null : list.reduce<number>((a, p) => a + (p || 0), 0),
        });
    });
    return () => {
      live = false;
    };
  }, [signature]);
  return quote?.signature === signature ? quote.total : null;
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
  const {reset: refreshActivity} = useSharedActivity();
  const [route, setRoute] = useState<ImageRoute>(() => readRoute(projectId));
  const [open, setOpen] = useState(false);
  const [sending, setSending] = useState(false);
  const locked = useRef(false);
  const activeProject = useRef(projectId);
  activeProject.current = projectId;
  const [review, setReview] = useState<{route: ImageRoute; jobs: ImageJob[]; project: string} | null>(null);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    setRoute(readRoute(projectId));
    setReview(null);
    setOpen(false);
  }, [projectId]);
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
    if (locked.current || busy || disabled || !projectId) return;
    locked.current = true;
    const project = projectId;
    onError('');
    setSending(true);
    try {
      if (route === 'api') {
        await onApi();
        return;
      }
      const prepared = await job();
      if (activeProject.current !== project) return;
      if (typeof prepared === 'string') return onError(prepared);
      const jobs = Array.isArray(prepared) ? prepared : [prepared];
      validateImageJobs(jobs, route);
      if (jobs.some(j => j.projectId !== project))
        throw Error('Проект задания изменился. Подготовь его заново.');
      setReview({route, project, jobs: structuredClone(jobs)});
    } catch (e) {
      if (activeProject.current === project) onError(e instanceof Error ? e.message : String(e));
    } finally {
      locked.current = false;
      setSending(false);
    }
  };

  const sendReviewed = async () => {
    if (!review || locked.current || review.project !== projectId) return;
    locked.current = true;
    setSending(true);
    const snapshot = review;
    try {
      const note =
        snapshot.route === 'chatgpt' ? await sendToChatGPT(snapshot.jobs) : await sendToCodex(snapshot.jobs);
      if (activeProject.current === snapshot.project) onNotice(note);
    } catch (e) {
      if (activeProject.current === snapshot.project) onError(e instanceof Error ? e.message : String(e));
    } finally {
      // Even after an uncertain response, inspect the queue instead of blindly submitting the same batch again.
      setReview(null);
      refreshActivity();
      openQueue();
      locked.current = false;
      setSending(false);
    }
  };

  const working = busy || sending;
  const label = working
    ? 'Готовлю…'
    : route === 'api'
      ? `Сгенерировать${count > 1 ? ` (${count})` : ''}${estimate !== null ? ' · ' + usd(estimate) : ''}`
      : route === 'chatgpt'
        ? 'Подготовить для ChatGPT'
        : 'Подготовить для Codex';
  const current = ROUTES.find(r => r.id === route)!;
  return (
    <div className="gen-split" ref={box}>
      <button
        className="primary gen-main"
        disabled={disabled || working || !projectId || !!review}
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
        disabled={working || !!review}
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
      {review &&
        review.project === projectId &&
        createPortal(
          <div className="modal-backdrop">
            <section
              className="panel generation-review"
              role="dialog"
              aria-modal="true"
              aria-label="Проверить внешнее задание"
            >
              <h2>Проверить задание для {review.route === 'chatgpt' ? 'ChatGPT' : 'Codex'}</h2>
              <p>Лимиты и оплата определяются внешним сервисом. Заданий в пакете: {review.jobs.length}.</p>
              {review.route === 'chatgpt' && (
                <p>
                  Текст нужно вставить в чат, референсы приложить вручную. Результат верни файлом или вставкой
                  в очереди.
                </p>
              )}
              {review.route === 'codex' && (
                <p>
                  Задание попадёт в очередь Codex. Для обработки нужен запущенный обработчик на компьютере.
                </p>
              )}
              {review.jobs.map((item, index) => (
                <div key={index}>
                  <b>
                    Задание {index + 1} · промпт для {item.target}
                  </b>
                  <label>
                    Промпт
                    <textarea
                      rows={6}
                      value={item.prompt}
                      disabled={working}
                      onChange={e => {
                        const prompt = e.target.value;
                        setReview(current =>
                          current
                            ? {
                                ...current,
                                jobs: current.jobs.map((j, i) => (i === index ? {...j, prompt} : j)),
                              }
                            : current
                        );
                      }}
                    />
                  </label>
                  <p>Референсов: {item.referenceAssetIds.length}</p>
                  {item.referenceAssetIds.map((id, i) => (
                    <a
                      key={id}
                      href={`/api/library/${encodeURIComponent(id)}/file`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Референс {i + 1}{' '}
                    </a>
                  ))}
                </div>
              ))}
              <div className="chips">
                <button
                  className="primary"
                  disabled={working || review.jobs.some(j => !j.prompt.trim())}
                  onClick={() => void sendReviewed()}
                >
                  {working
                    ? 'Сохраняется…'
                    : review.route === 'chatgpt'
                      ? 'Сохранить в очередь ChatGPT'
                      : 'Отправить в очередь Codex'}
                </button>
                <button disabled={working} onClick={() => setReview(null)}>
                  Назад
                </button>
              </div>
            </section>
          </div>,
          document.body
        )}
    </div>
  );
}
