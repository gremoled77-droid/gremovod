import {useEffect, useMemo, useRef, useState} from 'react';
import {createPortal} from 'react-dom';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import GenerationReview, {type GenerationRequest} from './GenerationReview';

type OptionSpec = {default?: string | number; values?: string[]};
type Spec = {kind: string; launch_enabled?: boolean; api_refs?: number; options?: Record<string, OptionSpec>};
const DEFAULT_MODEL = 'seedream-5-pro';

/** Окно «Создать нового» для героя или локации: имя, модель, промпт, референсы, запуск через оценку цены. */
export default function CreateEntityDialog({
  title,
  namePlaceholder,
  aspect,
  projectId,
  ensureProject,
  buildPrompt,
  create,
  onClose,
  onStarted,
}: {
  title: string;
  namePlaceholder: string;
  aspect: string;
  projectId: string;
  ensureProject: () => Promise<string>;
  buildPrompt: (name: string) => string;
  /** Создаёт карточку (героя или локацию); вызывается один раз, когда запуск подтверждён к оценке. */
  create: (name: string) => Promise<void>;
  onClose: () => void;
  onStarted: () => void;
}) {
  const [specs, setSpecs] = useState<Record<string, Spec>>({}),
    [name, setName] = useState(''),
    [model, setModel] = useState(DEFAULT_MODEL),
    [prompt, setPrompt] = useState(''),
    [edited, setEdited] = useState(false),
    [files, setFiles] = useState<File[]>([]),
    [request, setRequest] = useState<GenerationRequest | null>(null),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false),
    input = useRef<HTMLInputElement>(null);
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
  useEffect(() => {
    if (!edited) setPrompt(buildPrompt(name));
  }, [name, edited]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && !request && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });
  const start = async () => {
    setError('');
    if (!name.trim()) return setError('Введи имя');
    if (!prompt.trim()) return setError('Промпт пустой');
    if (files.some(f => !['image/png', 'image/jpeg', 'image/webp'].includes(f.type) || f.size > 7_500_000))
      return setError('Референсы: PNG, JPEG или WebP до 7,5 МБ');
    setBusy(true);
    try {
      const pid = projectId || (await ensureProject());
      const spec = specs[model];
      const urls: string[] = [];
      if ((spec?.api_refs ?? 0) > 0)
        for (const file of files.slice(0, spec.api_refs)) {
          const form = new FormData();
          form.append('project_id', pid);
          form.append('file', file);
          const asset = await responseJson(
            await apiFetch('/api/library/import-image', {method: 'POST', body: form})
          );
          const uploaded = await responseJson(
            await apiFetch(`/api/library/${asset.id}/upload-reference`, {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({approved: true, provider: 'tempfile'}),
            })
          );
          urls.push(uploaded.url);
        }
      const options = Object.fromEntries(
        Object.entries(spec?.options || {})
          .filter(([, s]) => s.default !== undefined)
          .map(([k, s]) => [
            k,
            k === 'aspect_ratio' && s.values?.includes(aspect) ? aspect : (s.default as string | number),
          ])
      );
      await create(name.trim());
      setRequest({project_id: pid, model_id: model, prompt, options, reference_urls: urls});
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  if (request)
    return (
      <GenerationReview
        request={request}
        onClose={() => {
          setRequest(null);
          onClose();
        }}
        onSubmitted={() => {
          setRequest(null);
          onStarted();
        }}
      />
    );
  const refsOk = (specs[model]?.api_refs ?? 0) > 0;
  return createPortal(
    <div className="lb" role="dialog" aria-modal="true" aria-label={title} onClick={onClose}>
      <div className="panel create-dialog" onClick={e => e.stopPropagation()}>
        <h3>{title}</h3>
        <label>
          Имя
          <input
            autoFocus
            value={name}
            placeholder={namePlaceholder}
            onChange={e => setName(e.target.value)}
          />
        </label>
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
          Промпт
          <textarea
            rows={7}
            value={prompt}
            onChange={e => {
              setPrompt(e.target.value);
              setEdited(true);
            }}
          />
        </label>
        <div className="chips">
          <button type="button" disabled={!refsOk} onClick={() => input.current?.click()}>
            Прикрепить референсы{files.length ? ` (${files.length})` : ''}
          </button>
          <input
            ref={input}
            hidden
            type="file"
            multiple
            accept="image/png,image/jpeg,image/webp"
            aria-label="Референсы"
            onChange={e => {
              setFiles(Array.from(e.target.files || []));
              e.target.value = '';
            }}
          />
          {files.map(f => (
            <span key={f.name + f.size} className="muted">
              {f.name}
            </span>
          ))}
        </div>
        {!refsOk && <p className="muted">Эта модель не принимает референсы: выбери другую.</p>}
        {refsOk && files.length > 0 && (
          <p className="muted">Референсы уйдут на временное хранилище для передачи модели.</p>
        )}
        {error && <p role="alert">{error}</p>}
        <div className="chars-actions">
          <button className="primary" disabled={busy} onClick={() => void start()}>
            {busy ? 'Готовлю…' : 'Сгенерировать: оценка и подтверждение'}
          </button>
          <button onClick={onClose}>Отмена</button>
        </div>
      </div>
    </div>,
    document.body
  );
}
