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
  const roleTitle: Record<string, string> = {
    director: '🎬 Режиссёр',
    continuity: '🛡 Консистентность',
    prompt: '✦ Промпты',
  };
  const stepHead = (n: number, title: string, hint: string) => (
    <div className="rf-head">
      <span className="rf-step">{n}</span>
      <div>
        <h3>{title}</h3>
        <small>{hint}</small>
      </div>
    </div>
  );
  return (
    <section className="sc">
      <div className="ag-state" role="status">
        <b>Платные API-агенты выключены</b>
        <span>
          Пока для них нет оценки стоимости и лимита. Основной чат Codex доступен в студии, а форма ниже
          показывает, как будет работать команда.
        </span>
      </div>
      <p className="muted sc-lede">
        Три специалиста последовательно подготовят план, проверят консистентность и составят промпты под
        выбранные модели. Генерация картинок и видео автоматически не запускается.
      </p>
      <article className="sc-step">
        {stepHead(1, 'Провайдер и модель', 'Ключ берётся из серверных подключений')}
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
      </article>
      <article className="sc-step">
        {stepHead(2, 'Мир проекта', 'Канон берётся из проекта; здесь можно добавить замечания')}
        <textarea
          rows={3}
          value={styleNotes}
          onChange={e => setStyleNotes(e.target.value)}
          placeholder="Дополнительные замечания к стилю проекта"
        />
      </article>
      <article className="sc-step">
        {stepHead(3, 'Для каких моделей нужны промпты', 'Отметь одну или несколько')}
        <div className="ag-targets">
          {options.map(m => (
            <label key={m} className={'ag-target' + (targets.includes(m) ? ' on' : '')}>
              <input
                type="checkbox"
                checked={targets.includes(m)}
                onChange={e => setTargets(t => (e.target.checked ? [...t, m] : t.filter(x => x !== m)))}
              />
              {m}
            </label>
          ))}
        </div>
      </article>
      <article className="sc-step">
        {stepHead(4, 'Запуск', 'Задание берётся из «Идеи». Один запуск — 3 вызова LLM')}
        <div className="rf-actions">
          <button
            className="primary"
            disabled={!PAID_LLM_ENABLED || busy || !brief.trim() || targets.length === 0}
            onClick={run}
          >
            {busy ? 'Агенты работают…' : '▶ Создать план и промпты'}
          </button>
        </div>
        {!brief.trim() && <small className="muted">Сначала напиши задание ролика на экране «Идея».</small>}
        {error && (
          <div className="alert">
            {error.includes('1010')
              ? 'PiAPI заблокировал клиент (Cloudflare 1010). Можно выбрать OpenAI напрямую. '
              : ''}
            {error}
          </div>
        )}
      </article>
      {result && (
        <article className="sc-step">
          <small className="muted">
            Запуск {result.id.slice(0, 8)} · {result.status} · платные генерации не запускались
          </small>
          {Object.entries(result.output).map(([role, r]) => (
            <details key={role} className="ag-result" open>
              <summary>
                <b>{roleTitle[role] || role}</b>
              </summary>
              <pre>{r.content}</pre>
              {role === 'prompt' && (
                <button className="secondary" onClick={() => onApply(r.content)}>
                  Перенести в режиссёрское задание
                </button>
              )}
            </details>
          ))}
        </article>
      )}
    </section>
  );
}
