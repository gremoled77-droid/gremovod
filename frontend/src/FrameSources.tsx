import {useEffect, useRef, useState} from 'react';
import {X} from 'lucide-react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';

type Node = {id: string; kind: string; title: string};
type Entry = {node: Node; assets: string[]};

const fileUrl = (assetId: string) => `/api/library/${assetId}/file`;

/** Персонажи или локации производства: узлы с готовыми картинками из библиотеки. */
function useProductionEntries(projectId: string, kind: 'character' | 'location') {
  const [entries, setEntries] = useState<Entry[] | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const where = await responseJson(
          await apiFetch(`/api/projects/${encodeURIComponent(projectId)}/workspace-location`)
        );
        const production = await responseJson(await apiFetch(`/api/productions/${where.production_id}`));
        const nodes: Node[] = (production.nodes || []).filter((n: Node) => n.kind === kind);
        const out: Entry[] = [];
        for (const node of nodes) {
          const detail = await responseJson(
            await apiFetch(`/api/productions/${where.production_id}/nodes/${node.id}`)
          );
          const images = (detail.files || []).filter(
            (f: {kind?: string; asset_id?: string}) => f.kind === 'image' && f.asset_id
          );
          // Основной образ первым, затем остальные картинки.
          images.sort(
            (a: {relative_path?: string}, b: {relative_path?: string}) =>
              Number(/Основн|Main/i.test(b.relative_path || '')) -
              Number(/Основн|Main/i.test(a.relative_path || ''))
          );
          out.push({
            node,
            assets: [...new Set<string>(images.map((f: {asset_id: string}) => f.asset_id))].slice(0, 8),
          });
        }
        if (live) setEntries(out);
      } catch (e) {
        if (live) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      live = false;
    };
  }, [projectId, kind]);
  return {entries, error};
}

function Modal({title, onClose, children}: {title: string; onClose: () => void; children: React.ReactNode}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        className="panel fs-modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={e => e.stopPropagation()}
      >
        <div className="fs-head">
          <h2>{title}</h2>
          <button type="button" aria-label="Закрыть" onClick={onClose}>
            <X size={16} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}

function EntryList({
  entries,
  error,
  picked,
  onPick,
  empty,
}: {
  entries: Entry[] | null;
  error: string;
  picked: string[];
  onPick: (assetId: string) => void;
  empty: string;
}) {
  if (error) return <p role="alert">{error}</p>;
  if (!entries) return <p className="muted">Загружаю…</p>;
  if (!entries.length) return <p className="muted">{empty}</p>;
  return (
    <div className="fs-list">
      {entries.map(({node, assets}) => (
        <div key={node.id} className="fs-entry">
          <b>{node.title}</b>
          {assets.length ? (
            <div className="fs-thumbs">
              {assets.map(id => (
                <button
                  key={id}
                  type="button"
                  className={picked.includes(id) ? 'on' : ''}
                  aria-pressed={picked.includes(id)}
                  title={picked.includes(id) ? 'Уже в референсах' : 'Добавить в референсы'}
                  onClick={() => onPick(id)}
                >
                  <img src={fileUrl(id)} alt="" loading="lazy" />
                </button>
              ))}
            </div>
          ) : (
            <small className="muted">У этой папки пока нет картинок</small>
          )}
        </div>
      ))}
    </div>
  );
}

/** Окно «＋»: персонаж из библиотеки персонажей или загрузка своего референса. */
export function AddReferenceModal({
  projectId,
  refs,
  onAdd,
  onUploaded,
  onClose,
}: {
  projectId: string;
  refs: string[];
  onAdd: (assetId: string) => void;
  onUploaded: (assetId: string) => void;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<'hero' | 'upload'>('hero');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const {entries, error: loadError} = useProductionEntries(projectId, 'character');

  const upload = async (list: FileList | null) => {
    if (!list?.length) return;
    setBusy(true);
    setError('');
    try {
      for (const f of Array.from(list)) {
        const form = new FormData();
        form.append('project_id', projectId);
        form.append('file', f);
        const asset = await responseJson(
          await apiFetch('/api/library/import-reference', {method: 'POST', body: form})
        );
        onUploaded(asset.id);
      }
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal title="Добавить в кадр" onClose={onClose}>
      <div className="cf-tabs" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'hero'}
          className={tab === 'hero' ? 'on' : ''}
          onClick={() => setTab('hero')}
        >
          Персонаж
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'upload'}
          className={tab === 'upload' ? 'on' : ''}
          onClick={() => setTab('upload')}
        >
          Загрузить референс
        </button>
      </div>
      {tab === 'hero' ? (
        <EntryList
          entries={entries}
          error={loadError}
          picked={refs}
          onPick={onAdd}
          empty="В производстве пока нет персонажей. Добавь героя в Character Vault на экране «Мир»."
        />
      ) : (
        <div className="fs-upload">
          <p className="muted">Картинка сохранится в библиотеку проекта и сразу станет референсом кадра.</p>
          <button type="button" className="primary" disabled={busy} onClick={() => file.current?.click()}>
            {busy ? 'Загружаю…' : 'Выбрать файлы'}
          </button>
          <input
            ref={file}
            type="file"
            accept="image/*"
            multiple
            hidden
            onChange={e => {
              void upload(e.target.files);
              e.target.value = '';
            }}
          />
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      <div className="fs-foot">
        <button type="button" onClick={onClose}>
          Готово
        </button>
      </div>
    </Modal>
  );
}

/** Окно «Локация»: готовые локации или новая «по мотивам мира». */
export function LocationModal({
  projectId,
  refs,
  world,
  onAdd,
  onCreate,
  onClose,
}: {
  projectId: string;
  refs: string[];
  world: string;
  onAdd: (assetId: string) => void;
  onCreate: (brief: string) => void;
  onClose: () => void;
}) {
  const [creating, setCreating] = useState(false);
  const [idea, setIdea] = useState('');
  const {entries, error} = useProductionEntries(projectId, 'location');

  return (
    <Modal title="Локация" onClose={onClose}>
      {!creating ? (
        <>
          <EntryList
            entries={entries}
            error={error}
            picked={refs}
            onPick={onAdd}
            empty="Готовых локаций пока нет. Создай первую кнопкой «＋»."
          />
          <div className="fs-foot">
            <button type="button" onClick={() => setCreating(true)}>
              ＋ Создать другую по мотивам мира
            </button>
            <button type="button" className="primary" onClick={onClose}>
              Готово
            </button>
          </div>
        </>
      ) : (
        <>
          <label>
            Какая локация нужна
            <textarea
              rows={3}
              value={idea}
              autoFocus
              placeholder="Например: дворик с гаражами у панельки, поздний вечер, лужи"
              onChange={e => setIdea(e.target.value)}
            />
          </label>
          <p className="muted">
            {world
              ? 'Стиль и свет возьму из «Мира»: ' + world
              : 'Библия мира пока пустая: заполни её на экране «Мир».'}
          </p>
          <div className="fs-foot">
            <button type="button" onClick={() => setCreating(false)}>
              Назад
            </button>
            <button
              type="button"
              className="primary"
              disabled={!idea.trim()}
              onClick={() => {
                onCreate(
                  `Location only, no characters, empty establishing view: ${idea.trim()}.` +
                    (world ? `\nWorld style: ${world}` : '')
                );
                onClose();
              }}
            >
              Подготовить промпт локации
            </button>
          </div>
        </>
      )}
    </Modal>
  );
}
