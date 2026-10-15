import UploadReferenceButton from './UploadReferenceButton';
import ReplaceCharacterButton, {type ReplacementControls} from './ReplaceCharacterButton';
import {useEffect, useState} from 'react';
import {apiFetch} from './api';
type Asset = {
  id: string;
  url: string;
  provider_reference_url?: string;
  thumbnail_url?: string;
  source_url: string;
  created_at: string;
  metadata: {
    kind?: string;
    duration?: number;
    width: number;
    height: number;
    provider: string;
    request: {payload?: {task_type?: string; input?: {prompt?: string}}};
  };
};
export default function AssetLibrary({
  projectId,
  revision,
  onUse,
  onScene,
  onRefine,
  character,
  onReplaced,
}: {
  projectId: string;
  revision: number;
  onUse: (url: string, id: string) => void;
  onScene: (id: string) => void;
  onRefine: (id: string) => void;
} & ReplacementControls) {
  const [items, setItems] = useState<Asset[]>([]);
  const [error, setError] = useState('');
  const [outcomes, setOutcomes] = useState<Record<string, string>>({});
  useEffect(() => {
    let active = true;
    setOutcomes({});
    if (projectId)
      void apiFetch('/api/economics?project_id=' + encodeURIComponent(projectId))
        .then(r => {
          if (!r.ok) throw Error('Не удалось загрузить оценки');
          return r.json();
        })
        .then(d => {
          if (active)
            setOutcomes(
              Object.fromEntries(d.assets.map((x: {id: string; decision: string}) => [x.id, x.decision]))
            );
        })
        .catch(e => {
          if (active) setError(String(e));
        });
    return () => {
      active = false;
    };
  }, [projectId, revision]);
  const decide = async (id: string, decision: string) => {
    try {
      const r = await apiFetch('/api/economics/assets/' + id, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({decision}),
      });
      if (!r.ok) throw Error('Не удалось сохранить оценку');
      setOutcomes(x => ({...x, [id]: decision}));
    } catch (e) {
      setError(String(e));
    }
  };
  useEffect(() => {
    let active = true;
    setItems([]);
    setError('');
    if (!projectId) return;
    void (async () => {
      try {
        const r = await apiFetch('/api/library?project_id=' + encodeURIComponent(projectId));
        if (!r.ok) throw Error('Не удалось загрузить библиотеку');
        const data = await r.json();
        if (active) setItems(data);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      active = false;
    };
  }, [projectId, revision]);
  return (
    <section className="panel">
      <h2>⑥ Библиотека проекта</h2>
      {!projectId && <p className="muted">Сохрани проект, чтобы хранить результаты в его библиотеке.</p>}
      {projectId && !items.length && !error && (
        <p className="muted">
          Сохраняй готовые изображения из очереди. Оригинал и параметры останутся на компьютере.
        </p>
      )}
      {error && (
        <div className="alert" role="alert">
          {error}
        </div>
      )}
      <div className="library-grid">
        {items.map(a => (
          <article key={a.id} className="connection-card">
            <>
              {a.metadata.kind === 'audio' ? (
                <audio src={a.url} controls />
              ) : a.metadata.kind === 'video' ? (
                <video src={a.url} controls preload="metadata" />
              ) : (
                <a href={a.url} target="_blank" rel="noreferrer">
                  <img loading="lazy" src={a.thumbnail_url || a.url} alt="Сохранённый результат" />
                </a>
              )}
            </>
            <p>
              {a.metadata.request.payload?.task_type || a.metadata.provider} · {a.metadata.width}×
              {a.metadata.height}
            </p>
            <details>
              <summary>Промпт</summary>
              <pre>{a.metadata.request.payload?.input?.prompt || 'Промпт сохранён в метаданных'}</pre>
            </details>
            <div className="chips">
              <a href={a.url} download>
                Скачать оригинал
              </a>
              {!['video', 'audio'].includes(a.metadata.kind || 'image') && (
                <>
                  <button onClick={() => onScene(a.id)}>Отправить в сцену</button>
                  {(a.provider_reference_url || a.source_url) && (
                    <button onClick={() => onUse(a.provider_reference_url || a.source_url, a.id)}>
                      Выбрать для видео
                    </button>
                  )}
                </>
              )}
            </div>
            {!['video', 'audio'].includes(a.metadata.kind || 'image') && (
              <>
                <UploadReferenceButton
                  assetId={a.id}
                  onReady={url => {
                    setItems(items =>
                      items.map(item => (item.id === a.id ? {...item, provider_reference_url: url} : item))
                    );
                    onUse(url, a.id);
                  }}
                />
                <button onClick={() => onRefine(a.id)}>Отправить в GPT Image</button>
                <ReplaceCharacterButton
                  projectId={projectId}
                  assetId={a.id}
                  character={character}
                  onReplaced={onReplaced}
                />
              </>
            )}
            {a.metadata.provider === 'codex_chat' && (
              <a className="button" href="codex://threads/01a13e25-939c-7b73-9c0a-669abc8aa6a7">
                Править в чате ↗
              </a>
            )}
            <label>
              Участие в финальном ролике
              <select value={outcomes[a.id] || 'undecided'} onChange={e => void decide(a.id, e.target.value)}>
                <option value="undecided">Пока не решено</option>
                <option value="used">Использовано в ролике</option>
                <option value="rejected">Отклонено</option>
              </select>
            </label>
          </article>
        ))}
      </div>
      <p className="muted">
        Для видео выбери публичный URL или подготовь локальный оригинал через бесплатное облако. Истёкшую
        временную ссылку нужно загрузить заново. Оригиналы хранятся на компьютере.
      </p>
    </section>
  );
}
