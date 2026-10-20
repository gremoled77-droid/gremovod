import {apiFetch, PAID_LLM_ENABLED} from './api';
import {useEffect, useState} from 'react';
import ProducerPanel, {errorText} from './ProducerPanel';
import {
  ProducerCatalog,
  ProducerChoice,
  choiceForProvider,
  defaultsFor,
  modelLabel,
  modelsForProvider,
  parseCatalog,
  providerLabel,
} from './producerModel';

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
  choice: ProducerChoice;
  onChoice: (choice: ProducerChoice) => void;
};
const options = ['seedream-5-pro', 'seedream-5-lite', 'nano-banana-2.1', 'seedance-2.5'];
export default function AgentPanel({
  projectId,
  brief,
  character,
  style,
  onApply,
  choice,
  onChoice,
}: Props) {
  const [catalog, setCatalog] = useState<ProducerCatalog | null>(null);
  const [catalogError, setCatalogError] = useState('');
  const [styleNotes, setStyleNotes] = useState('');
  const [targets, setTargets] = useState<string[]>(['seedream-5-pro', 'seedance-2.5']);
  const [result, setResult] = useState<AgentResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    apiFetch('/api/producer/options')
      .then(async response => {
        const data = await response.json();
        if (!response.ok) throw Error(errorText(data));
        return parseCatalog(data);
      })
      .then(value => {
        if (alive) setCatalog(value);
      })
      .catch(e => {
        if (alive) setCatalogError(String(e.message || e));
      });
    return () => {
      alive = false;
    };
  }, []);

  // Сохранённый выбор сверяется с каталогом: провайдера или модели могло не быть.
  useEffect(() => {
    if (!catalog) return;
    const models = modelsForProvider(catalog, choice.provider);
    if (!models.length) {
      const fallback = defaultsFor(catalog);
      if (fallback.provider !== choice.provider || fallback.model !== choice.model) onChoice(fallback);
      return;
    }
    if (!models.some(m => m.id === choice.model)) {
      const next = choiceForProvider(catalog, choice.provider, choice.model);
      if (next.model !== choice.model) onChoice(next);
    }
  }, [catalog]);

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
          provider: choice.provider,
          model: choice.model,
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
  const models = catalog ? modelsForProvider(catalog, choice.provider) : [];
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
      {catalogError && (
        <div className="alert" role="alert">
          Каталог моделей недоступен: {catalogError}
        </div>
      )}
      <article className="sc-step">
        {stepHead(1, 'Провайдер и модель', 'Выбор из проверенного каталога; ключ берётся из серверных подключений')}
        <div className="param-grid">
          <label>
            Провайдер
            <select
              value={choice.provider}
              disabled={!catalog}
              onChange={e => {
                if (!catalog) return;
                onChoice(choiceForProvider(catalog, e.target.value, choice.model));
              }}
            >
              {(catalog?.providers ?? []).map(p => (
                <option key={p.id} value={p.id}>
                  {providerLabel(catalog!, p.id)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Модель
            <select
              value={choice.model}
              disabled={!catalog || !models.length}
              onChange={e => onChoice({...choice, model: e.target.value})}
            >
              {models.length === 0 && <option value="">— моделей у провайдера нет —</option>}
              {models.map(m => (
                <option key={m.id} value={m.id}>
                  {modelLabel(m)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </article>
      {catalog && (
        <ProducerPanel
          projectId={projectId}
          idea={brief}
          characterIds={character?.id ? [character.id] : []}
          catalog={catalog}
          choice={choice}
          onChoice={onChoice}
        />
      )}
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
        {choice.provider === 'mock' && (
          <small className="muted">
            MOCK-режим локальный и бесплатный, но платных агентов A6–A8 он не обслуживает.
          </small>
        )}
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
