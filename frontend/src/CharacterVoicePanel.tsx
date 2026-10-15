import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';

type Voice = {
  provider: string;
  name: string;
  voice_id: string;
  url: string;
  model: string;
  cost_multiplier: number;
};
type Quote = {estimated_usd: number; quote_token: string; source: string; note: string};
const MODELS: Record<string, string[]> = {
  elevenlabs: ['eleven_multilingual_v2', 'eleven_v3'],
  fish: ['s2.1-pro', 's2.1-pro-free'],
};
export default function CharacterVoicePanel({
  productionId,
  nodeId,
  projectId,
  onGenerated,
}: {
  productionId: string;
  nodeId: string;
  projectId: string;
  onGenerated: () => void;
}) {
  const [voice, setVoice] = useState<Voice | null>(null),
    [dirty, setDirty] = useState(false),
    [text, setText] = useState(''),
    [quote, setQuote] = useState<Quote | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [notice, setNotice] = useState(''),
    [requestId, setRequestId] = useState('');
  const base = `/api/productions/${productionId}/nodes/${nodeId}/voice`;
  const request = async (path: string, method: string, body?: unknown) =>
    responseJson(
      await apiFetch(path, {
        method,
        headers: {'Content-Type': 'application/json'},
        body: body === undefined ? undefined : JSON.stringify(body),
      })
    );
  const perform = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    let active = true;
    setVoice(null);
    setQuote(null);
    setDirty(false);
    setError('');
    setText('');
    void request(base, 'GET')
      .then(v => {
        if (active) setVoice(v);
      })
      .catch(e => {
        if (active) setError(String(e));
      });
    return () => {
      active = false;
    };
  }, [base]);
  const change = (value: Partial<Voice>) => {
    setVoice(v => (v ? {...v, ...value} : v));
    setDirty(true);
    setQuote(null);
  };
  return (
    <section className="connection-card">
      <h3>Голос персонажа и реплики</h3>
      <a href={base.replace('/voice', '/reference-card')} target="_blank" rel="noreferrer">
        Скачать референс-карту персонажа
      </a>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {voice && (
        <>
          <div className="param-grid">
            <label>
              Сервис голоса
              <select
                value={voice.provider}
                disabled={busy}
                onChange={e =>
                  change({
                    provider: e.target.value,
                    model: MODELS[e.target.value][0],
                    voice_id: '',
                    url: '',
                    name: '',
                  })
                }
              >
                <option value="elevenlabs">ElevenLabs</option>
                <option value="fish">Fish Audio</option>
              </select>
            </label>
            <label>
              Название голоса
              <input value={voice.name} disabled={busy} onChange={e => change({name: e.target.value})} />
            </label>
            <label>
              Voice ID
              <input
                value={voice.voice_id}
                disabled={busy}
                onChange={e => change({voice_id: e.target.value})}
              />
            </label>
            <label>
              Модель озвучки
              <select value={voice.model} disabled={busy} onChange={e => change({model: e.target.value})}>
                {MODELS[voice.provider].map(m => (
                  <option key={m}>{m}</option>
                ))}
              </select>
            </label>
          </div>
          <label>
            Ссылка на голос в сервисе
            <input
              type="url"
              value={voice.url}
              disabled={busy}
              onChange={e => change({url: e.target.value})}
              placeholder="https://…"
            />
          </label>
          {voice.url && (
            <a href={voice.url} target="_blank" rel="noreferrer">
              Открыть голос в {voice.provider === 'fish' ? 'Fish Audio' : 'ElevenLabs'} ↗
            </a>
          )}
          <details>
            <summary>Множитель стоимости голоса</summary>
            <p className="muted">Если выбранный голос имеет повышенный тариф, укажи множитель из сервиса.</p>
            <input
              aria-label="Множитель стоимости голоса"
              type="number"
              min={1}
              max={20}
              step={0.1}
              value={voice.cost_multiplier}
              disabled={busy}
              onChange={e => change({cost_multiplier: Number(e.target.value)})}
            />
          </details>
          <button
            disabled={busy || !dirty}
            onClick={() =>
              void perform(async () => {
                setVoice(await request(base, 'PUT', voice));
                setDirty(false);
                setNotice('Карточка голоса сохранена в папку персонажа.');
              })
            }
          >
            Сохранить голос
          </button>
          <p className="muted">
            Аудиопример прикрепляется ниже в раздел «04 Голос». Для генерации используется сохранённый Voice
            ID.
          </p>
          <label>
            Фраза персонажа
            <textarea
              rows={4}
              maxLength={3000}
              value={text}
              disabled={busy}
              onChange={e => {
                setText(e.target.value);
                setQuote(null);
              }}
              placeholder="Напиши реплику для озвучки…"
            />
          </label>
          <button
            disabled={busy || dirty || !voice.voice_id || !voice.name || !text.trim() || !projectId}
            onClick={() =>
              void perform(async () => {
                setQuote(await request(base + '/estimate', 'POST', {project_id: projectId, text}));
                setRequestId(crypto.randomUUID());
              })
            }
          >
            Рассчитать озвучку
          </button>
          {quote && (
            <div className="notice">
              <p>Оценка: ≈ ${quote.estimated_usd.toFixed(6)}. Расход запишется на открытый проект студии.</p>
              <p className="muted">
                {quote.note}{' '}
                <a href={quote.source} target="_blank" rel="noreferrer">
                  Тариф сервиса
                </a>
              </p>
              <button
                className="primary"
                disabled={busy || dirty}
                onClick={() =>
                  void perform(async () => {
                    const result = await request(base + '/generate', 'POST', {
                      project_id: projectId,
                      text,
                      request_id: requestId,
                      quote_token: quote.quote_token,
                      max_cost_usd: quote.estimated_usd,
                      approved: true,
                    });
                    setNotice(
                      result.status === 'completed'
                        ? 'Реплика готова и сохранена в папку голоса.'
                        : 'Статус заявки: ' + result.status
                    );
                    setQuote(null);
                    onGenerated();
                  })
                }
              >
                Подтвердить и сгенерировать реплику
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
