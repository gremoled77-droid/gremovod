import type {WorkspaceLocation} from './WorkspaceTrail';
import SeriesEconomics from './SeriesEconomics';
import ProductionEntityEditor from './ProductionEntityEditor';
import {readLocal, writeLocal} from './localDrafts';
import {useEffect, useRef, useState} from 'react';
import {apiFetch} from './api';
import {responseJson} from './ChatGPTPanel';
import Lightbox, {type LightboxItem} from './Lightbox';
import {withoutMediaItem} from './mediaAsset';
import {analyzeAsset, shotPoints, TensionGraph, useVisualPlans, VisualPlanForm} from './VisualPlanPanel';
import {emptyPlan, planFromAnalysis} from './visualPlan';
import VisualRulesForm from './VisualRulesForm';
import EditListPanel from './EditListPanel';
import './ProductionStoryboard.css';

type Node = {
  id: string;
  kind: string;
  parent_id: string | null;
  title: string;
  number: number;
  notes: string;
};
type Production = {id: string; title: string};
type Media = {id: string; asset_id: string | null; kind: string; filename: string; url: string};
type Selection = {
  character_node_ids: string[];
  location_node_id: string | null;
  selected_image_file_id: string | null;
  selected_video_file_id: string | null;
};
type Frame = Node & {files: Media[]; project_id: string | null; selection: Selection};
type Board = {
  series: Node;
  scenes: (Node & {frames: Frame[]; selection: Selection})[];
  script: string;
  revision: string;
};
type Plan = {
  existing: {id: string; title: string; notes: string}[];
  scenes: {title: string; notes: string}[];
  conflicts: string[];
  body: {
    script: string;
    base_revision: string;
    request_id: string;
    mode: 'append' | 'update';
    scene_node_ids: (string | null)[];
  };
};
const request = async (path: string, body?: unknown) =>
  responseJson(
    await apiFetch(
      path,
      body === undefined
        ? undefined
        : {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}
    )
  );

export default function ProductionStoryboard({
  onInspect,
  onOpenProject,
  location,
}: {
  location?: WorkspaceLocation | null;
  onInspect: (productionId: string, nodeId: string) => void;
  onOpenProject: (id: string) => void;
}) {
  const [productions, setProductions] = useState<Production[]>([]),
    [pid, setPid] = useState(
      () =>
        location?.production_id ||
        readLocal<{pid: string; sid: string}>('studio:board-location', {pid: '', sid: ''}).pid
    ),
    [sid, setSid] = useState(
      () =>
        location?.series?.id ||
        readLocal<{pid: string; sid: string}>('studio:board-location', {pid: '', sid: ''}).sid
    );
  const restoredScroll = useRef('');
  useEffect(() => {
    if (location?.production_id && location.series?.id) {
      setPid(location.production_id);
      setSid(location.series.id);
    }
  }, [location?.production_id, location?.series?.id]);
  const [nodes, setNodes] = useState<Node[]>([]),
    [board, setBoard] = useState<Board | null>(null),
    [tick, setTick] = useState(0);
  const [drafts, setDrafts] = useState<Record<string, string>>(() =>
      readLocal('studio:storyboard-drafts', {})
    ),
    [plan, setPlan] = useState<Plan | null>(null),
    [name, setName] = useState('');
  const [editorStack, setEditorStack] = useState<string[]>([]),
    [storageOK, setStorageOK] = useState(true);
  const [view, setView] = useState<{items: LightboxItem[]; index: number} | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [notice, setNotice] = useState(''),
    [showScript, setShowScript] = useState(false),
    [importMode, setImportMode] = useState<'append' | 'update'>('append');
  const visual = useVisualPlans(pid, sid);
  const [estimating, setEstimating] = useState(false);
  const estimateEmpty = async () => {
    if (!board) return;
    setEstimating(true);
    setError('');
    try {
      for (const scene of board.scenes)
        for (const frame of scene.frames) {
          const current = visual.plans[frame.id] || emptyPlan();
          if (current.visual !== null) continue;
          const image =
            frame.files.find(f => f.id === frame.selection.selected_image_file_id) ||
            frame.files.find(f => f.kind === 'image');
          if (!image?.asset_id) continue;
          await visual.save(frame.id, planFromAnalysis(current, await analyzeAsset(image.asset_id)));
        }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setEstimating(false);
    }
  };
  const key = pid + '/' + sid,
    path = `/api/productions/${pid}/series/${sid}/storyboard`;
  const script = drafts[key] ?? board?.script ?? '';
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
    let live = true;
    void request('/api/productions')
      .then((items: Production[]) => {
        if (live) {
          setProductions(items);
          setPid(p =>
            items.some(x => x.id === p)
              ? p
              : items.find(x => x.title.toLowerCase() === 'gremovod')?.id || items[0]?.id || ''
          );
        }
      })
      .catch(e => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
    };
  }, []);
  useEffect(() => {
    let live = true;
    setNodes([]);
    setBoard(null);
    if (pid)
      void request('/api/productions/' + pid)
        .then(t => {
          if (live) {
            setNodes(t.nodes);
            setSid(current =>
              t.nodes.some((n: Node) => n.id === current && n.kind === 'series')
                ? current
                : t.nodes.find((n: Node) => n.kind === 'series')?.id || ''
            );
          }
        })
        .catch(e => {
          if (live) setError(String(e));
        });
    return () => {
      live = false;
    };
  }, [pid, tick]);
  useEffect(() => {
    let live = true;
    setBoard(null);
    if (pid && sid)
      void request(path)
        .then(b => {
          if (live) setBoard(b);
        })
        .catch(e => {
          if (live) setError(String(e));
        });
    return () => {
      live = false;
    };
  }, [pid, sid, tick, path]);
  useEffect(() => {
    if (pid && sid && nodes.some(n => n.id === sid)) writeLocal('studio:board-location', {pid, sid});
  }, [pid, sid, nodes]);
  useEffect(() => {
    if (!board) return;
    const scrollKey = 'studio:board-scroll:' + key;
    if (restoredScroll.current !== key) {
      restoredScroll.current = key;
      try {
        const stored = sessionStorage.getItem(scrollKey);
        if (stored !== null) requestAnimationFrame(() => window.scrollTo(0, Number(stored) || 0));
        else if (location?.frame)
          requestAnimationFrame(() =>
            document.getElementById('board-frame-' + location.frame!.id)?.scrollIntoView({block: 'center'})
          );
      } catch {
        /* Storage may be disabled. */
      }
    }
    const remember = () => {
      try {
        sessionStorage.setItem(scrollKey, String(window.scrollY));
      } catch {
        /* Keep the board usable. */
      }
    };
    window.addEventListener('scroll', remember, {passive: true});
    return () => window.removeEventListener('scroll', remember);
  }, [board, key, location?.frame]);
  const inspect = (id: string) => {
    if (nodes.find(n => n.id === id)?.kind === 'series') {
      onInspect(pid, id);
      return;
    }
    setEditorStack([id]);
  };
  useEffect(() => {
    setStorageOK(writeLocal('studio:storyboard-drafts', drafts));
  }, [drafts]);
  function prepare() {
    void perform(async () => {
      if (!board) return;
      const body = {
        script,
        base_revision: board.revision,
        request_id: crypto.randomUUID(),
        mode: importMode,
        scene_node_ids: [] as (string | null)[],
      };
      const preview = await request(path + '/preview', body);
      setPlan({...preview, body: {...body, scene_node_ids: preview.scenes.map(() => null)}});
    });
  }
  function importPlan() {
    void perform(async () => {
      if (!plan) return;
      const result = await request(path + '/import', plan.body);
      setPlan(null);
      setDrafts(d => {
        const next = {...d};
        delete next[key];
        return next;
      });
      setTick(t => t + 1);
      setNotice(
        result.file_warning ||
          `Сохранено сцен: ${result.node_ids.length}. Текст и папки сохранены; готовые кадры остались на месте.`
      );
      setShowScript(false);
    });
  }
  function createFrame(scene: Node) {
    void perform(async () => {
      const title = name.trim();
      if (!title) return;
      await request(`/api/productions/${pid}/nodes`, {
        kind: 'frame',
        parent_id: scene.id,
        title,
        notes: scene.notes,
      });
      setName('');
      setTick(t => t + 1);
      setNotice('Кадр создан. Открой его в студии для подготовки изображения.');
    });
  }
  function openFrame(frame: Frame) {
    void perform(async () => {
      const bound = await request(`/api/productions/${pid}/nodes/${frame.id}/open-project`, {});
      onOpenProject(bound.project_id);
    });
  }
  return (
    <section className="ps-board">
      <header className="ps-top">
        <div>
          <span className="ps-eyebrow">РАСКАДРОВКА · РАБОЧАЯ ДОСКА</span>
          <h2>{nodes.find(n => n.id === sid)?.title || 'Сценарий и раскадровка'}</h2>
        </div>
        <div className="ps-top-actions">
          {board && (
            <span className="ps-pill">
              Кадров: <b>{board.scenes.reduce((n, sc) => n + sc.frames.length, 0)}</b> · с фото{' '}
              <b>
                {board.scenes.reduce(
                  (n, sc) => n + sc.frames.filter(f => f.files.some(x => x.kind === 'image')).length,
                  0
                )}
              </b>
            </span>
          )}
          <button
            disabled={busy}
            onClick={() => {
              setPlan(null);
              setTick(t => t + 1);
            }}
          >
            Обновить
          </button>
        </div>
      </header>
      {!storageOK && (
        <p role="alert">Черновик не сохранён браузером. Сохрани сценарий до ухода со страницы.</p>
      )}
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      <div className="ps-pick">
        <label>
          Проект раскадровки
          <select
            disabled={busy}
            value={pid}
            onChange={e => {
              setPid(e.target.value);
              setSid('');
              setPlan(null);
              setError('');
            }}
          >
            <option value="">Выбери проект</option>
            {productions.map(p => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </label>
        <label>
          Серия раскадровки
          <select
            disabled={busy || !pid}
            value={sid}
            onChange={e => {
              setSid(e.target.value);
              setPlan(null);
              setError('');
            }}
          >
            <option value="">Выбери серию</option>
            {nodes
              .filter(n => n.kind === 'series')
              .map(n => (
                <option key={n.id} value={n.id}>
                  {n.number}. {n.title}
                </option>
              ))}
          </select>
        </label>
      </div>
      {!productions.length && <p>Создай общий проект в разделе «Папки проекта».</p>}
      {pid && (
        <details>
          <summary>＋ Новая серия</summary>
          <label>
            Название серии
            <input disabled={busy} value={name} onChange={e => setName(e.target.value)} />
          </label>
          <button
            disabled={busy || !name.trim()}
            onClick={() =>
              void perform(async () => {
                const n = await request(`/api/productions/${pid}/nodes`, {
                  kind: 'series',
                  title: name.trim(),
                });
                setSid(n.id);
                setName('');
                setTick(t => t + 1);
              })
            }
          >
            Создать серию
          </button>
        </details>
      )}
      {board && (
        <>
          <SeriesEconomics key={pid + sid} pid={pid} sid={sid} />
          <div className="chips">
            <button onClick={() => setShowScript(s => !s)}>Вставить сценарий</button>
            <button onClick={() => inspect(sid)}>Файлы и описание серии ↗</button>
          </div>
          <VisualRulesForm key={sid} pid={pid} nid={sid} />
          {showScript && (
            <section className="ps-script">
              <label>
                Режим импорта
                <select
                  value={importMode}
                  disabled={busy}
                  onChange={e => {
                    setImportMode(e.target.value as 'append' | 'update');
                    setPlan(null);
                  }}
                >
                  <option value="append">Добавить новые сцены</option>
                  <option value="update">Сопоставить и обновить существующие</option>
                </select>
              </label>
              <label>
                Сценарий с заголовками «Сцена 1 — Название»
                <textarea
                  rows={10}
                  disabled={busy}
                  value={script}
                  onChange={e => {
                    setDrafts(d => ({...d, [key]: e.target.value}));
                    setPlan(null);
                  }}
                  placeholder={
                    'Сцена 1 — Встреча\nДействие и реплики...\n\nСцена 2 — Поездка\nДействие и реплики...'
                  }
                />
              </label>
              <p className="muted">
                В режиме обновления явно выбери соответствие сцен. Неупомянутые сцены, кадры и готовые
                результаты остаются. Папки обновлённых сцен сохраняют прежний путь. Названия должны
                различаться. Перед импортом текст ещё не сохранён.
              </p>
              <button disabled={busy || !script.trim()} onClick={prepare}>
                Предпросмотр сцен
              </button>
              {plan && (
                <div>
                  <h3>Будет добавлено: {plan.scenes.length}</h3>
                  {plan.scenes.map((s, i) => (
                    <article key={i}>
                      <b>
                        {i + 1}. {s.title}
                      </b>
                      {plan.body.mode === 'update' && (
                        <label>
                          Действие со сценой
                          <select
                            disabled={busy}
                            value={plan.body.scene_node_ids[i] || ''}
                            onChange={e => {
                              const id = e.target.value || null;
                              setPlan(p =>
                                p
                                  ? {
                                      ...p,
                                      body: {
                                        ...p.body,
                                        scene_node_ids: p.body.scene_node_ids.map((old, j) =>
                                          i === j ? id : old
                                        ),
                                      },
                                    }
                                  : p
                              );
                            }}
                          >
                            <option value="">Создать новую сцену</option>
                            {plan.existing.map(n => (
                              <option key={n.id} value={n.id}>
                                Обновить: {n.title}
                              </option>
                            ))}
                          </select>
                        </label>
                      )}
                      {plan.body.scene_node_ids[i] && (
                        <details>
                          <summary>Было</summary>
                          <p>{plan.existing.find(n => n.id === plan.body.scene_node_ids[i])?.notes}</p>
                        </details>
                      )}
                      <p>Станет: {s.notes}</p>
                    </article>
                  ))}
                  {!!plan.conflicts.length && (
                    <p role="alert">
                      Уже существуют: {plan.conflicts.join(', ')}. Измени названия или отредактируй
                      существующие сцены.
                    </p>
                  )}
                  <button className="primary" disabled={busy || !!plan.conflicts.length} onClick={importPlan}>
                    Сохранить сценарий и сцены
                  </button>
                  <button disabled={busy} onClick={() => setPlan(null)}>
                    Отмена
                  </button>
                </div>
              )}
            </section>
          )}
          {!board.scenes.length && (
            <p>Сцен ещё нет. Вставь сценарий и проверь разбиение перед сохранением.</p>
          )}
          {board.scenes.some(s => s.frames.length) && <EditListPanel key={sid} pid={pid} sid={sid} />}
          {board.scenes.some(s => s.frames.length) && (
            <TensionGraph
              points={shotPoints(board.scenes, visual.plans)}
              onEstimate={() => void estimateEmpty()}
              estimating={estimating}
            />
          )}
          {board.scenes.map(scene => (
            <article key={scene.id} className="ps-scene">
              <div className="ps-scene-head">
                <button className="ps-heading" onClick={() => inspect(scene.id)}>
                  <small>СЦЕНА {String(scene.number).padStart(2, '0')}</small>
                  <h3>{scene.title} ↗</h3>
                </button>
                {(() => {
                  const done = scene.frames.filter(f => f.files.some(x => x.kind === 'image')).length;
                  const all = scene.frames.length;
                  return (
                    <span className={'ps-prog' + (all && done === all ? ' ok' : '')}>
                      {done} из {all} с фото
                    </span>
                  );
                })()}
              </div>
              <p className="ps-text">{scene.notes || 'Описание пока не добавлено'}</p>
              <div className="ps-cast">
                {scene.selection.character_node_ids.map(id => (
                  <button key={id} onClick={() => inspect(id)}>
                    {nodes.find(n => n.id === id)?.title || 'Персонаж'} ↗
                  </button>
                ))}
                {scene.selection.location_node_id && (
                  <button onClick={() => inspect(scene.selection.location_node_id!)}>
                    {nodes.find(n => n.id === scene.selection.location_node_id)?.title || 'Локация'} ↗
                  </button>
                )}
                <button onClick={() => inspect(scene.id)}>Состав сцены и бэкграунд</button>
              </div>
              <VisualPlanForm
                kind="scene"
                plan={visual.plans[scene.id]}
                onSave={plan => visual.save(scene.id, plan)}
              />
              <div className="ps-frames">
                {scene.frames.map(frame => {
                  const image =
                      frame.files.find(f => f.id === frame.selection.selected_image_file_id) ||
                      frame.files.find(f => f.kind === 'image'),
                    video =
                      frame.files.find(f => f.id === frame.selection.selected_video_file_id) ||
                      frame.files.find(f => f.kind === 'video');
                  return (
                    <article key={frame.id} className={'ps-frame' + (image ? '' : ' none')}>
                      <div className="ps-shot">
                        {image ? (
                          <button
                            className="ps-zoom"
                            title="Открыть крупно"
                            onClick={() => {
                              const list = scene.frames
                                .map(fr => {
                                  const im =
                                    fr.files.find(f => f.id === fr.selection.selected_image_file_id) ||
                                    fr.files.find(f => f.kind === 'image');
                                  return im
                                    ? {
                                        url: im.asset_id ? `/api/library/${im.asset_id}/file` : im.url,
                                        assetId: im.asset_id || undefined,
                                        title: `${scene.number}.${fr.number} · ${fr.title}`,
                                        id: fr.id,
                                      }
                                    : null;
                                })
                                .filter(Boolean) as (LightboxItem & {id: string})[];
                              setView({
                                items: list,
                                index: Math.max(
                                  0,
                                  list.findIndex(x => x.id === frame.id)
                                ),
                              });
                            }}
                          >
                            <img
                              src={image.asset_id ? `/api/library/${image.asset_id}/thumbnail` : image.url}
                              alt={frame.title}
                              loading="lazy"
                            />
                          </button>
                        ) : (
                          <div className="ps-empty">нет изображения</div>
                        )}
                        <span className="ps-tag">
                          {scene.number}.{frame.number}
                        </span>
                        {image && frame.selection.selected_image_file_id && (
                          <span className="ps-main">главный</span>
                        )}
                        {video && (
                          <span className="ps-vid">
                            {frame.selection.selected_video_file_id ? 'видео ✓' : 'видео'}
                          </span>
                        )}
                      </div>
                      <b>{frame.title}</b>
                      <small>
                        {image
                          ? frame.selection.selected_image_file_id
                            ? 'основное фото утверждено'
                            : 'последнее фото · не утверждено'
                          : 'запланирован'}
                      </small>
                      <div className="ps-acts">
                        <button disabled={busy} onClick={() => openFrame(frame)}>
                          В студию
                        </button>
                        <button onClick={() => inspect(frame.id)}>Файлы ↗</button>
                      </div>
                      <VisualPlanForm
                        kind="frame"
                        assetId={image?.asset_id}
                        verticalUrl={`/api/productions/${pid}/nodes/${frame.id}/vertical-prompt`}
                        plan={visual.plans[frame.id]}
                        onSave={plan => visual.save(frame.id, plan)}
                      />
                    </article>
                  );
                })}
              </div>
              <details>
                <summary>＋ Кадр сцены</summary>
                <label>
                  Название нового кадра
                  <input
                    disabled={busy}
                    value={name}
                    onChange={e => setName(e.target.value)}
                    placeholder="Например: реакция гостя"
                  />
                </label>
                <button disabled={busy || !name.trim()} onClick={() => createFrame(scene)}>
                  Создать кадр
                </button>
              </details>
            </article>
          ))}
          <details>
            <summary>Общие персонажи и локации проекта</summary>
            <p className="muted">
              Открой сцену, чтобы закрепить её участников и локацию. Карточки ниже общие для проекта.
            </p>
            <div className="chips">
              {nodes
                .filter(n => ['character', 'location'].includes(n.kind))
                .map(n => (
                  <button key={n.id} onClick={() => inspect(n.id)}>
                    {n.kind === 'character' ? 'Персонаж' : 'Локация'} · {n.title} ↗
                  </button>
                ))}
            </div>
          </details>
        </>
      )}
      {view && (
        <Lightbox
          items={view.items}
          index={view.index}
          onIndex={i => setView(v => (v ? {...v, index: i} : v))}
          onClose={() => setView(null)}
          onAssetChanged={(id, change) => {
            if (change.trashed) {
              setView(current => (current ? withoutMediaItem(current, id) : null));
              setTick(value => value + 1);
            }
          }}
        />
      )}
      {editorStack.length > 0 && (
        <ProductionEntityEditor
          key={pid + '/' + editorStack[editorStack.length - 1]}
          pid={pid}
          nid={editorStack[editorStack.length - 1]}
          onClose={() => {
            setEditorStack(stack => stack.slice(0, -1));
            setTick(t => t + 1);
          }}
          onNavigate={id => setEditorStack(stack => [...stack, id])}
          onSaved={() => setTick(t => t + 1)}
          onOpenProject={onOpenProject}
        />
      )}
    </section>
  );
}
