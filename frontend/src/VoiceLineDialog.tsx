import {useRef, useState} from 'react';
import {estimateVoice, frameProject, generateVoice, linkCueAsset, type Quote} from './soundApi';
import type {Cue} from './soundCues';
import type {Voice} from './soundApi';

/** Озвучка реплики голосом героя: оценка цены, подтверждение, файл ложится в звук кадра. */
export default function VoiceLineDialog({
  pid,
  cue,
  hero,
  voices,
  onClose,
  onDone,
}: {
  pid: string;
  cue: Cue;
  hero: string;
  /** Голоса, привязанные к герою реплики; выбор показывается, если их больше одного. */
  voices: Voice[];
  onClose: () => void;
  onDone: () => void;
}) {
  const [quote, setQuote] = useState<Quote | null>(null),
    [project, setProject] = useState(''),
    [voiceId, setVoiceId] = useState(''),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    requestId = useRef(crypto.randomUUID());
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError('');
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
      const projectId = await frameProject(pid, cue.frame_id);
      setProject(projectId);
      setQuote(await estimateVoice(pid, cue.hero_node_id || '', cue.text, projectId, voiceId));
    });
  const generate = () =>
    run(async () => {
      if (!quote) return;
      const done = await generateVoice(
        pid,
        cue.hero_node_id || '',
        cue.text,
        project,
        quote,
        requestId.current,
        voiceId
      );
      await linkCueAsset(pid, cue.id, done.asset_id);
      onDone();
    });
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Озвучить реплику">
      <section className="panel ol">
        <h3>Озвучить реплику</h3>
        <p>
          <b>{hero}:</b> «{cue.text}»
        </p>
        {voices.length > 1 && (
          <label>
            Голос
            <select value={voiceId} disabled={busy || !!quote} onChange={e => setVoiceId(e.target.value)}>
              <option value="">Голос героя по умолчанию</option>
              {voices.map(v => (
                <option key={v.id} value={v.id}>
                  {v.name} · {v.model}
                </option>
              ))}
            </select>
          </label>
        )}
        {!quote ? (
          <button className="primary" disabled={busy} onClick={() => void estimate()}>
            {busy ? 'Считаю цену…' : 'Рассчитать цену'}
          </button>
        ) : (
          <div className="chips" role="group" aria-label="Подтверждение платного вызова">
            <span>Озвучка до ${quote.estimated_usd.toFixed(4)}</span>
            <button className="primary" disabled={busy} onClick={() => void generate()}>
              {busy ? 'Озвучиваю…' : 'Озвучить'}
            </button>
            <button disabled={busy} onClick={() => setQuote(null)}>
              Отмена
            </button>
          </div>
        )}
        {quote && <p className="muted">{quote.note}</p>}
        {error && <p role="alert">{error}</p>}
        <div className="chips">
          <button disabled={busy} onClick={onClose}>
            Закрыть
          </button>
        </div>
      </section>
    </div>
  );
}
