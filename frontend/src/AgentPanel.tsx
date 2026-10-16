import {apiFetch, PAID_LLM_ENABLED} from './api';
import {useState} from 'react';

type AgentResult = {
  id: string;
  status: string;
  provider: string;
  model: string;
  target_models: string[];
  output: Record<string, {content: string; usage: any}>;
};
type Props = {
  projectId: string;
  brief: string;
  character: any;
  style: Record<string, string>;
  onApply: (prompt: string) => void;
};
const options = ['seedream-5-pro', 'seedream-5-lite', 'nano-banana-2.1', 'seedance-2.5'];
export default function AgentPanel({projectId, brief, character, style, onApply}: Props) {
  const [provider, setProvider] = useState('openai');
  const [model, setModel] = useState('gpt-4.1-mini');
  const [styleNotes, setStyleNotes] = useState('');
  const [targets, setTargets] = useState<string[]>(['seedream-5-pro', 'seedance-2.5']);
  const [result, setResult] = useState<AgentResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const run = async () => {
    setBusy(true);
    setError('');
    try {
      const response = await apiFetch('/api/agents/run', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          project_id: projectId || null,
          brief,
          provider,
          model,
          character: character || {},
          style: {...style, agent_notes: styleNotes},
          target_models: targets,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw Error(JSON.stringify(data.detail || data));
      setResult(data);
    } catch (e: any) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="panel">
      <p className="notice">
        Платные API-агенты временно отключены до настройки оценки стоимости. Основной чат Codex доступен в
        студии.
      </p>
      <p className="muted">
        Три специалиста последовательно подготовят план, проверят консистентность и составят модельные
        промпты. Генерация изображений и видео автоматически не запускается. Ключ берётся из серверных
        подключений.
      </p>
      <div className="param-grid">
        <label>
          Провайдер
          <select
            value={provider}
            onChange={e => {
              const p = e.target.value;
              setProvider(p);
              setModel(p === 'openai' ? 'gpt-4.1-mini' : 'gpt-5.6-luna');
            }}
          >
            <option value="openai">OpenAI напрямую</option>
            <option value="piapi">PiAPI</option>
          </select>
        </label>
        <label>
          Модель
          <input value={model} onChange={e => setModel(e.target.value)} />
        </label>
      </div>
      <label>
        Дополнение к библии мира (канон берётся из проекта)
        <textarea
          rows={3}
          value={styleNotes}
          onChange={e => setStyleNotes(e.target.value)}
          placeholder="Дополнительные замечания к стилю проекта"
        />
      </label>
      <h3>Модели, для которых нужны промпты</h3>
      <div className="chips">
        {options.map(m => (
          <label key={m} className="inline-checkbox">
            <input
              type="checkbox"
              checked={targets.includes(m)}
              onChange={e => setTargets(t => (e.target.checked ? [...t, m] : t.filter(x => x !== m)))}
            />
            {m}
          </label>
        ))}
      </div>
      <p className="muted">
        Задание берётся из верхнего поля «Режиссёрское задание». Каждый запуск делает 3 платных LLM-вызова. В
        облаке потребуется отдельное развёртывание.
      </p>
      <button
        className="primary"
        disabled={!PAID_LLM_ENABLED || busy || !brief.trim() || targets.length === 0}
        onClick={run}
      >
        {busy ? 'Агенты работают…' : '▶ Создать план и промпты'}
      </button>
      {error && (
        <div className="alert">
          {error.includes('1010')
            ? 'PiAPI заблокировал клиент (Cloudflare 1010). Можно выбрать OpenAI напрямую. '
            : ''}
          {error}
        </div>
      )}
      {result && (
        <div>
          <p className="muted">
            Run ID: {result.id} · {result.status} · оплачиваемые генерации не запускались
          </p>
          {Object.entries(result.output).map(([role, r]) => (
            <details key={role} open>
              <summary>
                <b>
                  {({director: '🎬 Режиссёр', continuity: '🛡 Консистентность', prompt: '✦ Промпты'} as any)[
                    role
                  ] || role}
                </b>
              </summary>
              <pre style={{whiteSpace: 'pre-wrap', fontFamily: 'inherit', lineHeight: 1.6}}>{r.content}</pre>
              {role === 'prompt' && (
                <button className="secondary" onClick={() => onApply(r.content)}>
                  Перенести в режиссёрское задание
                </button>
              )}
            </details>
          ))}
        </div>
      )}
    </section>
  );
}
