import {useState} from 'react';
import LlmApprovalDialog from './LlmApprovalDialog';
import LlmCostCard from './LlmCostCard';
import {cardOf, estimateLlm, runLlm, type LlmQuote, type Msg} from './llmAsk';
import type {LlmCard} from './llmDisplay';
import {initialLimit} from './spendLimit';
import {mergeWorld, parseWorld, WORLD_FIELDS, WORLD_SYSTEM, type World} from './worldBible';
import {smallUsd} from './usdFormat';

const MODEL = 'gpt-5.6-sol';

/** Кнопка «Составить мир»: LLM пишет «Библию мира» по заданию ролика. Сначала бесплатная оценка цены с сервера, запуск — после подтверждения владельца. */
export default function WorldFromBrief({
  projectId,
  brief,
  style,
  ensureProject,
  conflicts,
  onConflicts,
  onApply,
  onDone,
}: {
  projectId: string;
  brief: string;
  style: Partial<World> | undefined;
  ensureProject?: () => Promise<string>;
  conflicts: Partial<World>;
  onConflicts: (fields: Partial<World>) => void;
  onApply: (fields: Partial<World>) => void;
  onDone?: () => void;
}) {
  const [quote, setQuote] = useState<LlmQuote | null>(null);
  const [card, setCard] = useState<LlmCard | null>(null);
  const [approved, setApproved] = useState(false);
  const [limit, setLimit] = useState('');
  const [highOk, setHighOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const messages: Msg[] = [
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
      const q = await estimateLlm(pid, MODEL, messages);
      setQuote(q);
      setCard(null);
      setApproved(false);
      setHighOk(false);
      setLimit(initialLimit(q.actual.max_cost_usd ?? q.usd));
    });
  const generate = () =>
    run(async () => {
      if (!quote) return;
      const answer = await runLlm(quote, Number(limit) || undefined);
      setQuote(null);
      setCard(answer.card);
      const world = parseWorld(answer.text);
      const {fill, conflicts: busyFields} = mergeWorld(style, world);
      if (Object.keys(fill).length) onApply(fill);
      onConflicts(busyFields);
      setNote(
        `Мир заполнен: ${Object.keys(fill).length} пустых полей` +
          (Object.keys(busyFields).length ? `, ${Object.keys(busyFields).length} занятых ждут решения` : '') +
          (answer.cost !== null ? ` · списано ${smallUsd(answer.cost)}` : '')
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
          <span>Оценка с сервера готова — подтвердите запуск</span>
        </div>
      )}
      {card && <LlmCostCard card={card} title="Вызов LLM" />}
      {error && !quote && <p role="alert">{error}</p>}
      {note && <p className="muted">{note}</p>}
      {quote && (
        <LlmApprovalDialog
          card={cardOf(quote)}
          title="Подтверждение платного вызова LLM"
          total={quote.actual.max_cost_usd ?? quote.usd}
          limit={limit}
          onLimit={setLimit}
          highConfirmed={highOk}
          onHighConfirmed={setHighOk}
          approved={approved}
          onApproved={setApproved}
          busy={busy}
          error={error}
          onConfirm={() => void generate()}
          onClose={() => setQuote(null)}
        />
      )}
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
                  const rest = {...conflicts};
                  delete rest[k];
                  onConflicts(rest);
                }}
              >
                Заменить
              </button>
            </div>
          ))}
          <button
            onClick={() => {
              onConflicts({});
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
