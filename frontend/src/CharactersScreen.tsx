import {useEffect, useMemo, useState, type ReactNode} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import {buildCharacterPrompt, worldFilled, type Identity, type WorldFields} from './characterPrompt';
import GenerationReview, {type GenerationRequest} from './GenerationReview';

type Hero = {
  id: string;
  name: string;
  identity: Identity;
  working_asset_id?: string;
  version_history?: string[];
};
type OptionSpec = {default?: string | number};
type Spec = {kind: string; launch_enabled?: boolean; options?: Record<string, OptionSpec>};
const DEFAULT_MODEL = 'seedream-5-pro';

/** «Персонажи»: сетка героев проекта, «Создать нового» и «Сгенерировать героя» через оценку цены. Правка карточки — справа, в Character Vault. */
export default function CharactersScreen({
  projectId,
  ensureProject,
  heroes,
  selectedId,
  world,
  onSelect,
  onCreate,
  onToWorld,
  onNext,
  results,
}: {
  projectId: string;
  ensureProject: () => Promise<string>;
  heroes: Hero[];
  selectedId: string;
  world?: WorldFields;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onToWorld: () => void;
  onNext: () => void;
  results: ReactNode;
}) {
  const hero = heroes.find(h => h.id === selectedId);
  const [specs, setSpecs] = useState<Record<string, Spec>>({}),
    [model, setModel] = useState(DEFAULT_MODEL),
    [prompt, setPrompt] = useState(''),
    [edited, setEdited] = useState(false),
    [request, setRequest] = useState<GenerationRequest | null>(null),
    [error, setError] = useState(''),
    [note, setNote] = useState(''),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    void apiFetch('/api/model-specs')
      .then(responseJson)
      .then(s => active && setSpecs(s))
      .catch(e => active && setError(String(e)));
    return () => {
      active = false;
    };
  }, []);
  const models = useMemo(
    () => Object.entries(specs).filter(([, s]) => s.kind === 'image' && s.launch_enabled),
    [specs]
  );
  useEffect(() => {
    if (models.length && !models.some(([id]) => id === model)) setModel(models[0][0]);
  }, [models, model]);
  const auto = useMemo(
    () => (hero ? buildCharacterPrompt(hero.name, hero.identity, world) : ''),
    [hero, world]
  );
  useEffect(() => {
    setEdited(false);
  }, [selectedId]);
  useEffect(() => {
    if (!edited) setPrompt(auto);
  }, [auto, edited]);
  const start = async () => {
    setError('');
    setNote('');
    if (!hero) return setError('Выбери героя или создай нового');
    if (!worldFilled(world)) return setError('Сначала заполни «Мир»: стиль нужен для промпта героя');
    if (!prompt.trim()) return setError('Промпт пустой');
    setBusy(true);
    try {
      const pid = projectId || (await ensureProject());
      const options = Object.fromEntries(
        Object.entries(specs[model]?.options || {})
          .filter(([, s]) => s.default !== undefined)
          .map(([k, s]) => [k, s.default as string | number])
      );
      setRequest({project_id: pid, model_id: model, prompt, options, reference_urls: []});
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="chars">
      <div className="panel">
        <h2>Персонажи</h2>
        <p className="muted">
          Герои проекта. Описание, референсы, голос и версии правятся справа, в Character Vault.
        </p>
        <div className="chars-grid">
          {heroes.map(h => (
            <button
              key={h.id}
              className={'chars-tile' + (h.id === selectedId ? ' on' : '')}
              aria-pressed={h.id === selectedId}
              onClick={() => onSelect(h.id)}
            >
              {h.working_asset_id ? (
                <img src={`/api/library/${h.working_asset_id}/thumbnail`} alt="" loading="lazy" />
              ) : (
                <span className="chars-empty">нет образа</span>
              )}
              <b>{h.name}</b>
              <small>
                {h.version_history?.length ? `версий: ${h.version_history.length + 1}` : 'рабочий образ'}
              </small>
            </button>
          ))}
          <button className="chars-tile chars-new" onClick={onCreate}>
            <span>＋</span>
            <b>Создать нового</b>
          </button>
        </div>
      </div>
      <div className="panel">
        <h3>Сгенерировать героя{hero ? ` · ${hero.name}` : ''}</h3>
        {!worldFilled(world) && (
          <p role="status" className="muted">
            «Мир» пока пуст. <button onClick={onToWorld}>Заполнить мир</button>
          </p>
        )}
        <label>
          Модель
          <select value={model} onChange={e => setModel(e.target.value)}>
            {(models.length ? models.map(([id]) => id) : [DEFAULT_MODEL]).map(id => (
              <option key={id} value={id}>
                {id}
                {id === DEFAULT_MODEL ? ' (по умолчанию)' : ''}
              </option>
            ))}
          </select>
        </label>
        <label>
          Промпт героя
          <textarea
            rows={8}
            value={prompt}
            onChange={e => {
              setPrompt(e.target.value);
              setEdited(true);
            }}
          />
        </label>
        <div className="chars-actions">
          <button className="primary" disabled={busy || !hero} onClick={() => void start()}>
            {busy ? 'Готовлю…' : 'Сгенерировать: оценка и подтверждение'}
          </button>
          <button
            disabled={!edited}
            onClick={() => {
              setEdited(false);
              setPrompt(auto);
            }}
          >
            Собрать промпт заново
          </button>
          <button onClick={onNext}>Дальше: раскадровка →</button>
        </div>
        {error && <p role="alert">{error}</p>}
        {note && <p className="muted">{note}</p>}
        <p className="muted">
          Платный запуск только после оценки цены и подтверждения. Готовые картинки появятся ниже в
          библиотеке: выбери лучшую и нажми «Заменить персонажа».
        </p>
      </div>
      {results}
      {request && (
        <GenerationReview
          request={request}
          onClose={() => setRequest(null)}
          onSubmitted={() => {
            setRequest(null);
            setNote('Задание запущено. Результат появится в библиотеке ниже.');
          }}
        />
      )}
    </section>
  );
}
