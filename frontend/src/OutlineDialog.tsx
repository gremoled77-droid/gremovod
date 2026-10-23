import {useRef, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import {moveItem} from './boardOrder';
import {estimateLlm, runLlm, type LlmQuote, type Msg} from './llmAsk';
import {LLM_MODELS} from './llmPricing';
import {outlineBody, outlineSystem, outlineUser, parseOutline, type Outline} from './outlinePlan';

const MODEL = 'gpt-5.6-sol';
export type OutlineContext = {projectId: string; brief: string; passport: string; heroes: string[]};

/** «Разбить на сцены и кадры»: план от GPT (с оценкой цены) или вставленный из чата, предпросмотр с правкой, запись в раскадровку. */
export default function OutlineDialog({
  pid,
  sid,
  revision,
  context,
  onClose,
  onDone,
}: {
  pid: string;
  sid: string;
  revision: string;
  context: OutlineContext;
  onClose: () => void;
  onDone: () => void;
}) {
  const [source, setSource] = useState<'gpt' | 'paste'>('gpt'),
    [shots, setShots] = useState(7),
    [scenes, setScenes] = useState(1),
    [pasted, setPasted] = useState(''),
    [quote, setQuote] = useState<LlmQuote | null>(null),
    [plan, setPlan] = useState<Outline | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [note, setNote] = useState(''),
    requestId = useRef(crypto.randomUUID());
  const messages = (): Msg[] => [
    {role: 'system', content: outlineSystem(shots, scenes)},
    {role: 'user', content: outlineUser(context)},
  ];
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError('');
    setNote('');
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  const estimate = () =>
    run(async () => {
      if (!context.brief.trim()) throw Error('Сначала впиши задание ролика на экране «Идея»');
      setQuote(await estimateLlm(context.projectId, MODEL, messages()));
    });
  const generate = () =>
    run(async () => {
      if (!quote) return;
      const {text, cost} = await runLlm(quote);
      setQuote(null);
      setPlan(parseOutline(text));
      setNote(cost === null ? 'План готов.' : `План готов · списано $${cost.toFixed(4)}`);
    });
  const parsePasted = () => run(async () => setPlan(parseOutline(pasted)));
  const copyPrompt = () =>
    run(async () => {
      const [system, user] = messages();
      await navigator.clipboard.writeText(`${system.content}\n\n${user.content}`);
      setNote('Промпт скопирован. Вставь его в ChatGPT, а ответ принеси сюда.');
    });
  const send = () =>
    run(async () => {
      if (!plan) return;
      await responseJson(
        await apiFetch(`/api/productions/${pid}/series/${sid}/storyboard/outline`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            base_revision: revision,
            request_id: requestId.current,
            scenes: outlineBody(plan),
          }),
        })
      );
      onDone();
    });
  const edit = (si: number, fn: (s: Outline['scenes'][number]) => Outline['scenes'][number]) =>
    setPlan(p => p && {scenes: p.scenes.map((s, i) => (i === si ? fn(s) : s))});
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Разбить на сцены и кадры">
      <section className="panel ol">
        <h3>Разбить на сцены и кадры</h3>
        {!plan && (
          <>
            <div className="chips" role="radiogroup" aria-label="Источник плана">
              <label>
                <input type="radio" checked={source === 'gpt'} onChange={() => setSource('gpt')} /> GPT
                (оценка цены)
              </label>
              <label>
                <input type="radio" checked={source === 'paste'} onChange={() => setSource('paste')} />{' '}
                Вставить ответ из чата
              </label>
            </div>
            <div className="ol-row">
              <label>
                Кадров на сцену
                <select value={shots} onChange={e => setShots(Number(e.target.value))}>
                  {[5, 6, 7, 8, 9].map(n => (
                    <option key={n}>{n}</option>
                  ))}
                </select>
              </label>
              <label>
                Сцен
                <select value={scenes} onChange={e => setScenes(Number(e.target.value))}>
                  {[1, 2, 3].map(n => (
                    <option key={n}>{n}</option>
                  ))}
                </select>
              </label>
            </div>
            {source === 'gpt' ? (
              !quote ? (
                <button className="primary" disabled={busy} onClick={() => void estimate()}>
                  {busy ? 'Считаю цену…' : 'Составить план (GPT)'}
                </button>
              ) : (
                <div className="chips" role="group" aria-label="Подтверждение платного вызова">
                  <span>
                    {LLM_MODELS[MODEL].label} · до ${quote.usd.toFixed(4)}
                  </span>
                  <button className="primary" disabled={busy} onClick={() => void generate()}>
                    {busy ? 'Пишу план…' : 'Запустить'}
                  </button>
                  <button disabled={busy} onClick={() => setQuote(null)}>
                    Отмена
                  </button>
                </div>
              )
            ) : (
              <>
                <button disabled={busy} onClick={() => void copyPrompt()}>
                  Скопировать промпт для ChatGPT
                </button>
                <label>
                  Ответ чата (JSON)
                  <textarea rows={8} value={pasted} onChange={e => setPasted(e.target.value)} />
                </label>
                <button
                  className="primary"
                  disabled={busy || !pasted.trim()}
                  onClick={() => void parsePasted()}
                >
                  Разобрать
                </button>
              </>
            )}
          </>
        )}
        {plan && (
          <div className="ol-plan">
            {plan.scenes.map((scene, si) => (
              <fieldset key={si}>
                <legend>Сцена {si + 1}</legend>
                <input
                  aria-label={`Название сцены ${si + 1}`}
                  value={scene.title}
                  onChange={e => edit(si, s => ({...s, title: e.target.value}))}
                />
                {scene.shots.map((shot, i) => (
                  <div className="ol-shot" key={i}>
                    <b>{i + 1}</b>
                    <div>
                      <input
                        aria-label={`Изменение в кадре ${i + 1}`}
                        value={shot.change}
                        onChange={e =>
                          edit(si, s => ({
                            ...s,
                            shots: s.shots.map((x, j) => (j === i ? {...x, change: e.target.value} : x)),
                          }))
                        }
                      />
                      <small>
                        {[shot.visible, shot.audio, shot.camera].filter(Boolean).join(' · ') || 'без деталей'}
                      </small>
                    </div>
                    <button
                      aria-label="Выше"
                      disabled={i === 0}
                      onClick={() => edit(si, s => ({...s, shots: moveItem(s.shots, i, -1) || s.shots}))}
                    >
                      ↑
                    </button>
                    <button
                      aria-label="Ниже"
                      disabled={i === scene.shots.length - 1}
                      onClick={() => edit(si, s => ({...s, shots: moveItem(s.shots, i, 1) || s.shots}))}
                    >
                      ↓
                    </button>
                    <button
                      aria-label="Убрать кадр"
                      disabled={scene.shots.length < 2}
                      onClick={() => edit(si, s => ({...s, shots: s.shots.filter((_, j) => j !== i)}))}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </fieldset>
            ))}
            <div className="chips">
              <button className="primary" disabled={busy} onClick={() => void send()}>
                {busy ? 'Добавляю…' : 'Добавить в раскадровку'}
              </button>
              <button disabled={busy} onClick={() => setPlan(null)}>
                Назад
              </button>
            </div>
          </div>
        )}
        {error && <p role="alert">{error}</p>}
        {note && <p className="muted">{note}</p>}
        {!plan && (
          <div className="chips">
            <button onClick={onClose}>Закрыть</button>
          </div>
        )}
        {plan && !busy && (
          <button onClick={onClose} className="ol-close">
            Закрыть без добавления
          </button>
        )}
      </section>
    </div>
  );
}
