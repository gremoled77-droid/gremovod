import {useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import {LLM_MAX_TOKENS, LLM_MODELS} from './llmPricing';
import {mergeWorld, parseWorld, WORLD_FIELDS, WORLD_SYSTEM, type World} from './worldBible';

const MODEL = 'gpt-5.6-sol';
const post = (body: unknown) => ({
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(body),
});

/** Кнопка «Составить мир»: LLM пишет «Библию мира» по заданию ролика. Сначала бесплатная оценка цены, запуск только после подтверждения. */
export default function WorldFromBrief({
  projectId,
  brief,
  style,
  ensureProject,
  onApply,
  onDone,
}: {
  projectId: string;
  brief: string;
  style: Partial<World> | undefined;
  ensureProject?: () => Promise<string>;
  onApply: (fields: Partial<World>) => void;
  onDone?: () => void;
}) {
  const [quote, setQuote] = useState<{token: string; usd: number; pid: string} | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const [conflicts, setConflicts] = useState<Partial<World>>({});
  const messages = [
    {role: 'system', content: WORLD_SYSTEM},
    {role: 'user', content: `Задание ролика:\n${brief.trim()}`},
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
      if (!brief.trim()) throw Error('Сначала впиши задание ролика');
      const pid = projectId || (ensureProject ? await ensureProject() : '');
      if (!pid) throw Error('Нет проекта для учёта расходов');
      const q = await responseJson(
        await apiFetch(
          '/api/llm/estimate',
          post({project_id: pid, model: MODEL, messages, max_tokens: LLM_MAX_TOKENS})
        )
      );
      setQuote({token: q.quote_token, usd: q.estimated_usd, pid});
    });
  const generate = () =>
    run(async () => {
      if (!quote) return;
      const answer = await responseJson(
        await apiFetch(
          '/api/llm/chat',
          post({
            provider: 'piapi',
            project_id: quote.pid,
            model: MODEL,
            max_tokens: LLM_MAX_TOKENS,
            messages,
            approved: true,
            quote_token: quote.token,
            max_cost_usd: quote.usd,
            request_id: crypto.randomUUID(),
          })
        )
      );
      setQuote(null);
      const world = parseWorld(String(answer.choices?.[0]?.message?.content || ''));
      const {fill, conflicts: busyFields} = mergeWorld(style, world);
      if (Object.keys(fill).length) onApply(fill);
      setConflicts(busyFields);
      const cost = Number(answer.cost_usd);
      setNote(
        `Мир заполнен: ${Object.keys(fill).length} пустых полей` +
          (Object.keys(busyFields).length ? `, ${Object.keys(busyFields).length} занятых ждут решения` : '') +
          (Number.isFinite(cost) ? ` · списано $${cost.toFixed(4)}` : '')
      );
      if (!Object.keys(busyFields).length) onDone?.();
    });
  const label = (k: string) => WORLD_FIELDS.find(f => f[0] === k)?.[1] || k;
  const keys = Object.keys(conflicts) as (keyof World)[];
  return (
    <div className="world-llm">
      {!quote ? (
        <button disabled={busy || !brief.trim()} onClick={() => void estimate()}>
          {busy ? 'Считаю цену…' : 'Составить мир (GPT)'}
        </button>
      ) : (
        <div className="world-llm-quote" role="group" aria-label="Подтверждение платного вызова">
          <span>
            {LLM_MODELS[MODEL].label} · до ${quote.usd.toFixed(4)}
          </span>
          <button className="primary" disabled={busy} onClick={() => void generate()}>
            {busy ? 'Пишу мир…' : 'Запустить'}
          </button>
          <button disabled={busy} onClick={() => setQuote(null)}>
            Отмена
          </button>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      {note && <p className="muted">{note}</p>}
      {keys.length > 0 && (
        <div className="world-llm-conflicts">
          <b>Эти поля уже заполнены. Заменить новым вариантом?</b>
          {keys.map(k => (
            <div key={k}>
              <small>{label(k)}</small>
              <p>{conflicts[k]}</p>
              <button
                onClick={() => {
                  onApply({[k]: conflicts[k]});
                  setConflicts(c => {
                    const n = {...c};
                    delete n[k];
                    return n;
                  });
                }}
              >
                Заменить
              </button>
            </div>
          ))}
          <button
            onClick={() => {
              setConflicts({});
              onDone?.();
            }}
          >
            Оставить как есть
          </button>
        </div>
      )}
    </div>
  );
}
