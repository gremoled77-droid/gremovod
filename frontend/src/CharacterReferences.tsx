import {useEffect, useRef, useState, type ReactNode} from 'react';
import {Plus, MoreHorizontal} from 'lucide-react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';

export type CharacterIdentity = {
  species: string;
  face: string;
  hair: string;
  eyes: string;
  costume: string;
  negative: string;
};
type Reference = {id: string; url: string; original_name: string; category: string};
type DescriptionJob = {
  id: string;
  character_id: string;
  operation: string;
  status: string;
  message: string;
  description_result?: {
    identity: CharacterIdentity;
    baseline_identity: CharacterIdentity;
    skipped_fields: string[];
  } | null;
};
type Props = {
  projectId: string;
  characterId: string;
  name: string;
  identity: CharacterIdentity;
  workingImage?: string;
  busy: boolean;
  ensureProject: () => Promise<string>;
  onName: (name: string) => void;
  onIdentity: (identity: CharacterIdentity) => void;
  onRecognized: (result: NonNullable<DescriptionJob['description_result']>, jobId: string) => void;
  children?: ReactNode;
};
const FIELDS: [keyof CharacterIdentity, string][] = [
  ['species', 'Вид / тип'],
  ['face', 'Лицо и особенности'],
  ['hair', 'Волосы / шерсть'],
  ['eyes', 'Глаза'],
  ['costume', 'Костюм'],
  ['negative', 'Что запрещено менять'],
];

export default function CharacterReferences({
  projectId,
  characterId,
  name,
  identity,
  workingImage,
  busy,
  ensureProject,
  onName,
  onIdentity,
  onRecognized,
  children,
}: Props) {
  const [references, setReferences] = useState<Reference[]>([]),
    [expanded, setExpanded] = useState(false),
    [uploading, setUploading] = useState(false),
    [error, setError] = useState('');
  const [job, setJob] = useState<DescriptionJob | null>(null),
    [worker, setWorker] = useState<{worker_online: boolean; chat_url: string} | null>(null);
  const input = useRef<HTMLInputElement>(null),
    applied = useRef(new Set<string>()),
    pending = useRef<string | null>(null),
    recognized = useRef(onRecognized);
  recognized.current = onRecognized;
  useEffect(() => {
    let active = true;
    const refresh = async () => {
      if (!projectId) return;
      try {
        const [refs, jobs, status] = await Promise.all([
          apiFetch(`/api/characters/${projectId}/${characterId}/assets`).then(responseJson),
          apiFetch('/api/chatgpt/jobs?project_id=' + encodeURIComponent(projectId)).then(responseJson),
          apiFetch('/api/chatgpt/status').then(responseJson),
        ]);
        if (!active) return;
        setReferences(
          refs.filter((r: Reference) => ['real_references', 'approved_generations'].includes(r.category))
        );
        setWorker(status);
        const latest = (jobs as DescriptionJob[]).find(
          j => j.operation === 'describe_character' && j.character_id === characterId
        );
        if (latest) {
          setJob(latest);
          if (latest.status === 'completed' && latest.description_result && !applied.current.has(latest.id)) {
            applied.current.add(latest.id);
            recognized.current(latest.description_result, latest.id);
          }
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : String(e));
      }
    };
    void refresh();
    const timer = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, 4000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [projectId, characterId]);
  const analyze = async (id: string) => {
    pending.current ||= crypto.randomUUID();
    const result = await responseJson(
      await apiFetch('/api/chatgpt/jobs', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          project_id: id,
          character_id: characterId,
          operation: 'describe_character',
          request_id: pending.current,
        }),
      })
    );
    pending.current = null;
    setJob(result);
  };
  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    const chosen = Array.from(files);
    setUploading(true);
    setError('');
    try {
      if (!name.trim()) throw Error('Сначала введи имя персонажа');
      if (
        chosen.some(
          f => !['image/png', 'image/jpeg', 'image/webp'].includes(f.type) || f.size > 20 * 1024 * 1024
        )
      )
        throw Error('Выбери PNG, JPEG или WebP размером до 20 МБ');
      const id = await ensureProject();
      for (const file of chosen) {
        const data = new FormData();
        data.append('file', file);
        data.append('category', 'real_references');
        const added = await responseJson(
          await apiFetch(`/api/characters/${id}/${characterId}/assets`, {method: 'POST', body: data})
        );
        setReferences(current => [
          {...added, original_name: file.name},
          ...current.filter(r => r.id !== added.id),
        ]);
      }
      await analyze(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
      if (input.current) input.current.value = '';
    }
  };
  const retry = async () => {
    setUploading(true);
    setError('');
    try {
      await analyze(await ensureProject());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  };
  const running = !!job && ['queued', 'preparing'].includes(job.status);
  return (
    <div className="character-references">
      <div className="character-name-actions">
        <label>
          Имя
          <input placeholder="Имя персонажа" value={name} onChange={e => onName(e.target.value)} />
        </label>
        <button
          type="button"
          disabled={busy || uploading || job?.status === 'preparing' || !name.trim()}
          title="Добавить фото-референсы"
          aria-label="Добавить фото-референсы"
          onClick={() => input.current?.click()}
        >
          <Plus size={20} />
        </button>
        <button
          type="button"
          className={expanded ? 'active' : ''}
          title="Полное описание персонажа"
          aria-label="Полное описание персонажа"
          aria-expanded={expanded}
          aria-controls="character-description"
          onClick={() => setExpanded(value => !value)}
        >
          <MoreHorizontal size={21} />
        </button>
      </div>
      <input
        ref={input}
        hidden
        type="file"
        multiple
        accept="image/png,image/jpeg,image/webp"
        aria-label="Фото-референсы персонажа"
        onChange={e => void upload(e.target.files)}
      />
      <div className="character-reference-thumbnails">
        {workingImage && (
          <a href={workingImage} target="_blank" rel="noreferrer" title="Основной образ">
            <img src={workingImage} alt="Основной образ персонажа" loading="lazy" />
            <small>Основной образ</small>
          </a>
        )}
        {references.map(reference => (
          <a
            key={reference.id}
            href={reference.url}
            target="_blank"
            rel="noreferrer"
            title={reference.original_name}
          >
            <img src={reference.url} alt={reference.original_name || 'Фото-референс'} loading="lazy" />
            <small>{reference.original_name}</small>
          </a>
        ))}
      </div>
      {!workingImage && !references.length && (
        <p className="muted">Добавь фото через «+» — описание заполнится по референсам.</p>
      )}
      {uploading && <p role="status">Сохраняем референсы…</p>}
      {job && (
        <p className="muted" role="status">
          {(
            {
              queued: 'Описание: ожидает GPT-чат',
              preparing: 'Распознаём внешность по фото…',
              completed: 'Описание заполнено по референсам',
              failed: 'Не удалось распознать описание',
              cancelled: 'Распознавание отменено',
            } as Record<string, string>
          )[job.status] || job.message}
        </p>
      )}
      {running && !worker?.worker_online && (
        <p className="muted">
          Обработчик чата неактивен.
          {worker?.chat_url && (
            <>
              {' '}
              <a href={worker.chat_url}>Открыть GPT-чат</a> и написать «Продолжай очередь студии».
            </>
          )}
        </p>
      )}
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {(references.length > 0 || workingImage) && !running && (
        <button className="secondary" disabled={busy || uploading} onClick={() => void retry()}>
          Распознать описание по фото
        </button>
      )}
      {expanded && (
        <div id="character-description" className="character-full-description">
          <h4>Полное описание</h4>
          {FIELDS.map(([key, label]) => (
            <label key={key}>
              {label}
              <textarea
                rows={3}
                value={identity[key] || ''}
                onChange={e => onIdentity({...identity, [key]: e.target.value})}
              />
            </label>
          ))}
          {children}
        </div>
      )}
    </div>
  );
}
