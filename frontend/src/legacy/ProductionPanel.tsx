import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import ReplaceCharacterButton, {type CharacterVersion} from './ReplaceCharacterButton';
import CharacterVoicePanel from './CharacterVoicePanel';

type Folder = {
  id: string;
  parent_id: string | null;
  kind: string;
  title: string;
  number: number;
  guest: string;
  relative_dir: string;
  notes: string;
  character_id: string | null;
};
type Production = {id: string; title: string; folder: string; source_project_id: string};
type Tree = Production & {
  absolute_path: string;
  nodes: Folder[];
  links: {project_id: string; node_id: string | null}[];
};
type StoredFile = {
  id: string;
  asset_id: string | null;
  filename: string;
  relative_path: string;
  kind: string;
  url: string;
};
type Contents = Folder & {
  absolute_path: string;
  groups: string[];
  files: StoredFile[];
  source_project_id: string;
  character: CharacterVersion | null;
};
type Asset = {id: string; metadata: {kind?: string; original_name?: string; character_status?: string}};
const TITLES: Record<string, string> = {
  character: 'Персонажи',
  location: 'Локации',
  series: 'Серии',
  episode: 'Эпизод / сцена',
  frame: 'Кадр',
};

export default function ProductionPanel({
  projectId,
  onOpenProject,
  initialLocation,
}: {
  projectId: string;
  onOpenProject: (id: string, characterId?: string) => void;
  initialLocation?: {productionId: string; nodeId: string} | null;
}) {
  const [projects, setProjects] = useState<Production[]>([]),
    [pid, setPid] = useState(''),
    [tree, setTree] = useState<Tree | null>(null),
    [selected, setSelected] = useState(''),
    [group, setGroup] = useState('series');
  const [details, setDetails] = useState<Contents | null>(null),
    [assets, setAssets] = useState<Asset[]>([]),
    [category, setCategory] = useState(''),
    [asset, setAsset] = useState('');
  const [title, setTitle] = useState(''),
    [guest, setGuest] = useState(''),
    [newTitle, setNewTitle] = useState('GremoVOD'),
    [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [notice, setNotice] = useState(''),
    [tick, setTick] = useState(0);
  useEffect(() => {
    if (initialLocation) {
      setPid(initialLocation.productionId);
      setSelected(initialLocation.nodeId);
    }
  }, [initialLocation]);
  const request = async (path: string, body?: unknown) =>
    responseJson(
      await apiFetch(
        path,
        body === undefined
          ? undefined
          : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}
      )
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
    void request('/api/productions')
      .then(items => {
        if (active) {
          setProjects(items);
          setPid(current => (items.some((p: Production) => p.id === current) ? current : items[0]?.id || ''));
        }
      })
      .catch(e => {
        if (active) setError(String(e));
      });
    return () => {
      active = false;
    };
  }, [tick]);
  useEffect(() => {
    let active = true;
    setTree(null);
    if (pid)
      void request('/api/productions/' + pid)
        .then(t => {
          if (active) setTree(t);
        })
        .catch(e => {
          if (active) setError(String(e));
        });
    return () => {
      active = false;
    };
  }, [pid, tick]);
  useEffect(() => {
    let active = true;
    setDetails(null);
    if (pid && selected)
      void request(`/api/productions/${pid}/nodes/${selected}`)
        .then(d => {
          if (active) {
            setDetails(d);
            setNotes(d.notes);
            setCategory(d.groups[0] || '');
          }
        })
        .catch(e => {
          if (active) setError(String(e));
        });
    return () => {
      active = false;
    };
  }, [pid, selected, tick]);
  useEffect(() => {
    let active = true;
    setAssets([]);
    if (projectId)
      void request('/api/library?project_id=' + encodeURIComponent(projectId))
        .then(items => {
          if (active) setAssets(items);
        })
        .catch(e => {
          if (active) setError(String(e));
        });
    return () => {
      active = false;
    };
  }, [projectId, tick]);
  const current = tree?.nodes.find(n => n.id === selected);
  const childKind =
    current?.kind === 'series' ? 'episode' : current?.kind === 'episode' ? 'frame' : !current ? group : '';
  const children =
    tree?.nodes.filter(n => (current ? n.parent_id === current.id : !n.parent_id && n.kind === group)) || [];
  const choose = (id: string) => {
    setSelected(id);
    setTitle('');
    setGuest('');
    setNotice('');
    setError('');
  };
  const create = () =>
    perform(async () => {
      const result = await request('/api/productions', {
        title: newTitle,
        source_project_id: projectId || undefined,
      });
      setPid(result.id);
      setSelected('');
      setTick(x => x + 1);
      setNotice('Общий проект создан на диске. Персонажи текущего проекта подключены.');
    });
  const createFolder = () =>
    perform(async () => {
      const result = await request(`/api/productions/${pid}/nodes`, {
        kind: childKind,
        parent_id: selected || null,
        title,
        guest: childKind === 'series' ? guest : '',
      });
      choose(result.id);
      setTick(x => x + 1);
      setNotice('Папка создана на диске.');
    });
  const addAsset = () =>
    perform(async () => {
      await request(`/api/productions/${pid}/nodes/${selected}/assets`, {asset_id: asset, category});
      setAsset('');
      setTick(x => x + 1);
      setNotice('Оригинал и метаданные скопированы в выбранную папку.');
    });
  const upload = (file: File) =>
    perform(async () => {
      const form = new FormData();
      form.append('category', category);
      form.append('file', file);
      await responseJson(
        await apiFetch(`/api/productions/${pid}/nodes/${selected}/upload`, {method: 'POST', body: form})
      );
      setTick(x => x + 1);
      setNotice('Файл сохранён в папке проекта.');
    });
  return (
    <section className="panel production-panel">
      <h2>Папки проекта</h2>
      <p className="muted">
        Общий проект → серия с гостем → эпизод / сцена → кадры. Персонажи и локации общие для всех серий.
        Раскадровка — визуальный план сцены; скринкаст — запись экрана.
      </p>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      <label>
        Общий проект
        <select
          value={pid}
          onChange={e => {
            setPid(e.target.value);
            choose('');
          }}
        >
          <option value="">Выбери общий проект…</option>
          {projects.map(p => (
            <option value={p.id} key={p.id}>
              {p.title}
            </option>
          ))}
        </select>
      </label>
      <details open={!projects.length}>
        <summary>Создать общий проект</summary>
        <label>
          Название общего проекта
          <input value={newTitle} onChange={e => setNewTitle(e.target.value)} />
        </label>
        <p className="muted">
          Персонажи и библия мира будут подключены из открытого проекта студии. Исходные файлы и история
          сохраняются.
        </p>
        <button disabled={busy || !newTitle.trim()} onClick={() => void create()}>
          Создать папку общего проекта
        </button>
      </details>
      {tree && (
        <>
          <p className="folder-path">{tree.absolute_path}</p>
          <div className="chips">
            {(['character', 'location', 'series'] as const).map(k => (
              <button
                className={!selected && group === k ? 'active' : ''}
                key={k}
                onClick={() => {
                  setGroup(k);
                  choose('');
                }}
              >
                {k === 'character' ? '01 · ' : k === 'location' ? '02 · ' : '03 · '}
                {TITLES[k]}
              </button>
            ))}
            <button
              disabled={busy}
              onClick={() =>
                void perform(async () => {
                  await request(`/api/productions/${pid}/sync`, {});
                  setTick(x => x + 1);
                  setNotice('Файлы и промпты связанных кадров синхронизированы. Генерации не запускались.');
                })
              }
            >
              Синхронизировать файлы
            </button>
          </div>
          {current && (
            <div className="chips">
              <button onClick={() => choose(current.parent_id || '')}>← На уровень выше</button>
              <b>
                {TITLES[current.kind]} · {current.title}
                {current.guest ? ' — ' + current.guest : ''}
              </b>
            </div>
          )}
          <div className="folder-list">
            {children.map(n => (
              <button className="folder-entry" key={n.id} onClick={() => choose(n.id)}>
                📁{' '}
                {n.kind === 'series' || n.kind === 'episode' || n.kind === 'frame'
                  ? String(n.number).padStart(3, '0') + ' · '
                  : ''}
                {n.title}
                {n.guest ? ' — ' + n.guest : ''}
                <small>{TITLES[n.kind]}</small>
              </button>
            ))}
          </div>
          {!children.length && childKind && (
            <p className="muted">
              Здесь пока нет папок. Создай{' '}
              {childKind === 'series'
                ? 'серию с названием гостя'
                : childKind === 'episode'
                  ? 'эпизод / сцену'
                  : childKind === 'frame'
                    ? 'кадр'
                    : childKind === 'character'
                      ? 'персонажа'
                      : 'локацию'}
              .
            </p>
          )}
          {childKind && (
            <details>
              <summary>＋ {childKind === 'series' ? 'Серия' : TITLES[childKind]}</summary>
              <label>
                Название новой папки
                <input
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  placeholder={childKind === 'frame' ? 'Например: Грэм встречает гостя' : ''}
                />
              </label>
              {childKind === 'series' && (
                <label>
                  Имя гостя
                  <input value={guest} onChange={e => setGuest(e.target.value)} />
                </label>
              )}
              <p className="muted">
                Номер назначается автоматически. Имя гостя войдёт в название папки серии.
              </p>
              <button disabled={busy || !title.trim()} onClick={() => void createFolder()}>
                Создать папку
              </button>
            </details>
          )}
          {details && (
            <>
              <p className="folder-path">{details.absolute_path}</p>
              {details.kind === 'frame' && (
                <div className="chips">
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() =>
                      void perform(async () => {
                        const result = await request(
                          `/api/productions/${pid}/nodes/${selected}/open-project`,
                          {}
                        );
                        onOpenProject(result.project_id);
                      })
                    }
                  >
                    Открыть кадр в студии
                  </button>
                  {projectId && !tree.links.some(l => l.node_id === selected) && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        void perform(async () => {
                          await request(`/api/productions/${pid}/nodes/${selected}/link-project`, {
                            project_id: projectId,
                          });
                          setTick(x => x + 1);
                          setNotice(
                            'Текущий проект привязан. Готовые результаты будут копироваться в папку кадра.'
                          );
                        })
                      }
                    >
                      Привязать открытый проект студии
                    </button>
                  )}
                </div>
              )}
              {details.kind === 'character' && (
                <>
                  <button
                    onClick={() =>
                      onOpenProject(details.source_project_id, details.character_id || undefined)
                    }
                  >
                    Редактировать общего персонажа в студии
                  </button>
                  <CharacterVoicePanel
                    productionId={pid}
                    nodeId={selected}
                    projectId={projectId}
                    onGenerated={() => setTick(x => x + 1)}
                  />
                </>
              )}
              <label>
                {details.kind === 'series'
                  ? 'Сюжет серии'
                  : details.kind === 'episode'
                    ? 'Сценарий эпизода / сцены'
                    : details.kind === 'frame'
                      ? 'Описание кадра'
                      : 'Описание и заметки'}
                <textarea rows={5} value={notes} onChange={e => setNotes(e.target.value)} />
              </label>
              <button
                disabled={busy}
                onClick={() =>
                  void perform(async () => {
                    await responseJson(
                      await apiFetch(`/api/productions/${pid}/nodes/${selected}/notes`, {
                        method: 'PUT',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({notes}),
                      })
                    );
                    setNotice('Описание сохранено в Markdown-файл на диске.');
                  })
                }
              >
                Сохранить описание
              </button>
              <h3>Файлы и разделы папки</h3>
              <label>
                Куда добавить файл
                <select value={category} onChange={e => setCategory(e.target.value)}>
                  {details.groups.map(g => (
                    <option key={g} value={g}>
                      {g.replace(/_/g, ' ')}
                    </option>
                  ))}
                </select>
              </label>
              <label className="upload-area">
                Прикрепить файл
                <input
                  type="file"
                  disabled={busy}
                  accept=".png,.jpg,.jpeg,.webp,.mp4,.mov,.webm,.mp3,.wav,.m4a,.txt,.md,.json,.pdf,.srt"
                  onChange={e => {
                    const file = e.target.files?.[0];
                    if (file) void upload(file);
                    e.target.value = '';
                  }}
                />
              </label>
              <label>
                Добавить из библиотеки студии
                <select value={asset} onChange={e => setAsset(e.target.value)}>
                  <option value="">Выбери сохранённый результат…</option>
                  {assets.map(a => (
                    <option key={a.id} value={a.id}>
                      {a.metadata.original_name || a.id.slice(0, 8)} · {a.metadata.kind || 'image'}
                      {a.metadata.character_status === 'approved' ? ' · рабочий образ' : ''}
                    </option>
                  ))}
                </select>
              </label>
              <button disabled={busy || !asset} onClick={() => void addAsset()}>
                Скопировать в выбранный раздел
              </button>
              {details.groups.map(g => (
                <div key={g}>
                  <h4>📁 {g.replace(/_/g, ' ')}</h4>
                  <div className="production-files">
                    {details.files
                      .filter(f => f.relative_path.split(/[\\/]/).includes(g))
                      .map(f => (
                        <article className="connection-card" key={f.id}>
                          {f.kind === 'image' ? (
                            <a href={f.url} target="_blank" rel="noreferrer">
                              <img src={f.url} alt={f.filename} loading="lazy" />
                            </a>
                          ) : f.kind === 'video' ? (
                            <video src={f.url} controls preload="metadata" />
                          ) : f.kind === 'audio' ? (
                            <audio src={f.url} controls />
                          ) : null}
                          <b>{f.filename}</b>
                          <div className="chips">
                            <a href={f.url} target="_blank" rel="noreferrer">
                              Открыть файл
                            </a>
                            <a href={f.url} download>
                              Скачать
                            </a>
                          </div>
                          {details.character && f.kind === 'image' && f.asset_id && (
                            <ReplaceCharacterButton
                              projectId={details.source_project_id}
                              assetId={f.asset_id}
                              character={details.character}
                              onReplaced={() => setTick(x => x + 1)}
                            />
                          )}
                        </article>
                      ))}
                  </div>
                  {!details.files.some(f => f.relative_path.split(/[\\/]/).includes(g)) && (
                    <small className="muted">Папка готова для файлов.</small>
                  )}
                </div>
              ))}
            </>
          )}
        </>
      )}
    </section>
  );
}
