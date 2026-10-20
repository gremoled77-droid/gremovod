import {useState} from 'react';
import {Clapperboard} from 'lucide-react';
import {apiFetch, PAID_LLM_ENABLED} from './api';
import {responseJson} from './ChatGPTPanel';
import {newRequestId, paidBody} from './paidProtocol';
import {
  parseScenario,
  producerRequest,
  PRODUCER_DEFAULT_DURATION,
  PRODUCER_MOCK_MODEL,
  PRODUCER_MODELS,
  type ProducerScenario,
} from './producerStage';

const post = (body: unknown) => ({
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(body),
});

/** Этап «Продюсер»: идея → логлайн, драматургические биты, план сцен, допущения.
 *
 * Сначала работает локальный MOCK: сети нет, ключ не нужен, расходов нет.
 * Платные модели выбираются в том же списке, но включаются только вместе с
 * общим флагом платного LLM; запуск идёт через оценку и подтверждение.
 */
export default function ProducerStage({
  projectId,
  brief,
  style,
  characters,
  scenario,
  onScenario,
  ensureProject,
}: {
  projectId: string;
  brief: string;
  style: Record<string, string>;
  characters: {id: string; name: string; working_asset_id?: string}[];
  scenario?: ProducerScenario;
  onScenario: (value: ProducerScenario) => void;
  ensureProject: () => Promise<string>;
}) {
  const [model, setModel] = useState(PRODUCER_MOCK_MODEL);
  const [duration, setDuration] = useState(PRODUCER_DEFAULT_DURATION);
  const [constraints, setConstraints] = useState('');
  const [skipped, setSkipped] = useState<string[]>([]);
  const [quote, setQuote] = useState<{usd: number; token: string; pid: string} | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [note, setNote] = useState('');
  const selected = characters.filter(item => !skipped.includes(item.id));
  const paid = !!PRODUCER_MODELS[model] && !PRODUCER_MODELS[model].mock;

  const request = (pid: string) =>
    producerRequest(
      {brief, style, characters},
      {
        projectId: pid,
        characterIds: selected.map(item => item.id),
        durationSeconds: duration,
        constraints,
        model,
      }
    );

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
      if (!brief.trim()) throw Error('Сначала напиши задание ролика');
      const pid = projectId || (await ensureProject());
      if (!pid) throw Error('Нет проекта для учёта расходов');
      const q = await responseJson(await apiFetch('/api/producer/estimate', post(request(pid))));
      setQuote({usd: Number(q.estimated_usd) || 0, token: q.quote_token, pid});
    });

  const generate = () =>
    run(async () => {
      if (!quote) return;
      const answer = await responseJson(
        await apiFetch(
          '/api/producer/run',
          post({
            ...request(quote.pid),
            ...paidBody(quote, newRequestId()),
          })
        )
      );
      setQuote(null);
      const parsed = parseScenario(answer, new Date().toISOString());
      onScenario(parsed);
      const cost = Number(answer.cost_usd) || 0;
      setNote(
        `Структура готова: ${parsed.beats.length} битов, ${parsed.scenes.length} сцен` +
          (cost > 0 ? ` · списано $${cost.toFixed(4)}` : ' · без затрат')
      );
    });

  return (
    <section className="panel producer" aria-label="Сценарная структура">
      <div className="idea-head">
        <span className="idea-n">П</span>
        <div>
          <h2>Сценарная структура</h2>
          <small>
            Логлайн, драматургические биты и план сцен по твоему заданию. В модель уходят только выбранные
            персонажи и поля библии мира.
          </small>
        </div>
      </div>

      <div className="producer-controls">
        <label>
          Модель
          <select value={model} onChange={e => setModel(e.target.value)} aria-label="Модель этапа">
            {Object.entries(PRODUCER_MODELS).map(([id, m]) => (
              <option key={id} value={id} disabled={!m.mock && !PAID_LLM_ENABLED}>
                {m.label}
                {!m.mock && !PAID_LLM_ENABLED ? ' — платный LLM выключен' : ''}
              </option>
            ))}
          </select>
        </label>
        <label>
          Длительность, сек
          <input
            type="number"
            min={5}
            max={3600}
            value={duration}
            onChange={e => setDuration(Number(e.target.value))}
            aria-label="Длительность ролика в секундах"
          />
        </label>
        <label className="producer-constraints">
          Ограничения
          <textarea
            rows={2}
            value={constraints}
            onChange={e => setConstraints(e.target.value)}
            placeholder="По одной в строке. Например: без говорящих животных"
            aria-label="Ограничения ролика"
          />
        </label>
      </div>

      {characters.length > 0 && (
        <div className="producer-cast" aria-label="Персонажи в структуре">
          <small className="muted">Персонажи в структуре:</small>
          {characters.map(item => (
            <label key={item.id}>
              <input
                type="checkbox"
                checked={!skipped.includes(item.id)}
                onChange={e =>
                  setSkipped(list =>
                    e.target.checked ? list.filter(id => id !== item.id) : [...list, item.id]
                  )
                }
              />
              {item.name}
            </label>
          ))}
        </div>
      )}

      <div className="producer-actions">
        {!quote ? (
          <button disabled={busy || !brief.trim()} onClick={() => void estimate()}>
            {busy ? 'Считаю цену…' : 'Собрать структуру'}
          </button>
        ) : (
          <div className="producer-quote" role="group" aria-label="Подтверждение запуска">
            <span>
              {PRODUCER_MODELS[model]?.label} · {paid ? `до $${quote.usd.toFixed(4)}` : 'без затрат'}
            </span>
            <button className="primary" disabled={busy} onClick={() => void generate()}>
              {busy ? 'Собираю…' : 'Запустить'}
            </button>
            <button disabled={busy} onClick={() => setQuote(null)}>
              Отмена
            </button>
          </div>
        )}
      </div>

      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {note && <p className="muted">{note}</p>}

      {scenario && (
        <div className="producer-result">
          <b>{scenario.logline}</b>
          <div className="producer-beats">
            {scenario.beats.map(beat => (
              <div key={beat.id}>
                <small>{beat.stage}</small>
                <span>{beat.summary}</span>
              </div>
            ))}
          </div>
          <ol className="producer-scenes">
            {scenario.scenes.map(scene => (
              <li key={scene.number}>
                <b>
                  {scene.number}. {scene.title}
                </b>
                <span className="muted"> · {scene.duration_seconds} с</span>
                <p>{scene.summary}</p>
              </li>
            ))}
          </ol>
          {scenario.assumptions.length > 0 && (
            <details className="producer-assumptions">
              <summary>Допущения ({scenario.assumptions.length})</summary>
              <ul>
                {scenario.assumptions.map(item => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </details>
          )}
          <small className="muted producer-meta">
            <Clapperboard size={12} /> {scenario.model.label} · промпт {scenario.prompt_version.revision} ·
            правила {scenario.prompt_version.rules_version} · {scenario.saved_at.slice(0, 16).replace('T', ' ')}
          </small>
        </div>
      )}
    </section>
  );
}
