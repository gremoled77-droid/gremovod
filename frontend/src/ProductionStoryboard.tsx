import type {WorkspaceLocation} from './WorkspaceTrail';
import SeriesEconomics from './SeriesEconomics';
import ProductionEntityEditor from './ProductionEntityEditor';
import {readLocal, writeLocal} from './localDrafts';
import {useEffect, useRef, useState} from 'react';
import {apiFetch, responseJson} from './api';
import Lightbox, {type LightboxItem} from './Lightbox';
import CinemaInfo from './CinemaInfo';
import {analyzeAsset, shotPoints, TensionGraph, useVisualPlans, VisualPlanForm} from './VisualPlanPanel';
import {emptyPlan, planFromAnalysis} from './visualPlan';
import VisualRulesForm from './VisualRulesForm';
import EditListPanel from './EditListPanel';
import FrameTakes from './FrameTakes';
import SceneCast from './SceneCast';
import AnimateDialog from './AnimateDialog';
import FrameCast from './FrameCast';
import {soundLabel, sceneSound, type Cue, type FrameSound} from './soundCues';
import {frameStatus, photoLabel, sceneVideoCount, videoLabel, type Pending} from './frameStatus';
import UpscaleButton from './UpscaleButton';
import {moveItem} from './boardOrder';
import {patchEntity, putOrder, type EntityPatch} from './boardApi';
import OutlineDialog, {type OutlineContext} from './OutlineDialog';
import {changeOf} from './outlinePlan';
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
  location_angle_file_id?: string | null;
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
  outlineContext,
}: {
  location?: WorkspaceLocation | null;
  outlineContext?: OutlineContext;
  /** Папки серии (экран «Монтаж»); без него серия открывается в редакторе доски. */
  onInspect?: (productionId: string, nodeId: string) => void;
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
    [tick, setTick] = useState(0),
    [sound, setSound] = useState<Record<string, Cue[]>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>(() =>
      readLocal('studio:storyboard-drafts', {})
    ),
    [plan, setPlan] = useState<Plan | null>(null),
    [name, setName] = useState('');
  const [editorStack, setEditorStack] = useState<string[]>([]),
    [storageOK, setStorageOK] = useState(true);
  const [view, setView] = useState<{items: LightboxItem[]; index: number} | null>(null);
  const [newProduction, setNewProduction] = useState('');
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [notice, setNotice] = useState(''),
    [showScript, setShowScript] = useState(false),
    [showOutline, setShowOutline] = useState(false),
    [animate, setAnimate] = useState<{frame: Frame; heroes: {name: string}[]} | null>(null),
    [pending, setPending] = useState<Record<string, Pending>>(() => readLocal('studio:video-pending', {})),
    [onlyNoVideo, setOnlyNoVideo] = useState(false),
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
    let live = true;
    if (pid && sid)
      void apiFetch(`/api/productions/${pid}/series/${sid}/sound`)
        .then(r => (r.ok ? r.json() : []))
        .then((rows: FrameSound[]) => {
          if (live) setSound(Object.fromEntries(rows.map(r => [r.frame_id, r.cues])));
        })
        .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [pid, sid, tick]);
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
    if (onInspect && nodes.find(n => n.id === id)?.kind === 'series') {
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
  /** Сдвиг сцены (parentId = серия) или кадра (parentId = сцена) на одну позицию; папки не переименовываются. */
  function shift(parentId: string, ids: string[], index: number, delta: number) {
    const next = moveItem(ids, index, delta);
    if (!next || !board) return;
    void perform(async () => {
      await putOrder(path, board.revision, parentId, next);
      setTick(t => t + 1);
    });
  }
  /** Состав, локация и главный дубль: сохраняются сразу, остальное в карточке не меняется. */
  function savePatch(nodeId: string, patch: EntityPatch, message: string) {
    void perform(async () => {
      await patchEntity(pid, nodeId, patch);
      setTick(t => t + 1);
      setNotice(message);
    });
  }
  /** Пока идёт генерация видео, доска сама обновляется раз в 20 секунд: готовый клип появится в карточке кадра. */
  useEffect(() => {
    if (!Object.keys(pending).length) return;
    const timer = setInterval(() => setTick(t => t + 1), 20000);
    return () => clearInterval(timer);
  }, [pending]);
  function launched(frame: Frame, videosBefore: number) {
    const next = {...pending, [frame.id]: {since: Date.now(), videosBefore}};
    setPending(next);
    writeLocal('studio:video-pending', next);
    setAnimate(null);
    setNotice('Видео запущено. Готовый клип появится в карточке кадра: доска обновляется сама.');
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
          <CinemaInfo topic="composition" />
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
      <details open={!productions.length}>
        <summary>＋ Новый проект раскадровки</summary>
        <label>
          Название проекта
          <input disabled={busy} value={newProduction} onChange={e => setNewProduction(e.target.value)} />
        </label>
        <button
          disabled={busy || !newProduction.trim()}
          onClick={e => {
            const box = e.currentTarget.closest('details');
            void perform(async () => {
              const created: Production = await request('/api/productions', {
                title: newProduction.trim(),
                source_project_id: outlineContext?.projectId || undefined,
              });
              setProductions(items => [...items, created]);
              setPid(created.id);
              setSid('');
              setPlan(null);
              setNewProduction('');
              setTick(t => t + 1);
              if (box) box.open = false;
            });
          }}
        >
          Создать проект
        </button>
      </details>
      {pid && (
        <details>
          <summary>＋ Новая серия</summary>
          <label>
            Название серии
            <input disabled={busy} value={name} onChange={e => setName(e.target.value)} />
          </label>
          <button
            disabled={busy || !name.trim()}
            onClick={e => {
              const box = e.currentTarget.closest('details');
              void perform(async () => {
                const n = await request(`/api/productions/${pid}/nodes`, {
                  kind: 'series',
                  title: name.trim(),
                });
                setSid(n.id);
                setName('');
                setTick(t => t + 1);
                if (box) box.open = false;
              });
            }}
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
            <label>
              <input type="checkbox" checked={onlyNoVideo} onChange={e => setOnlyNoVideo(e.target.checked)} />{' '}
              только кадры без видео
            </label>
            {outlineContext && (
              <button onClick={() => setShowOutline(true)}>Разбить на сцены и кадры (GPT)</button>
            )}
            <button onClick={() => inspect(sid)}>Файлы и описание серии ↗</button>
          </div>
          <VisualRulesForm key={sid} pid={pid} nid={sid} />
          {animate && (
            <AnimateDialog
              pid={pid}
              frame={animate.frame}
              heroes={animate.heroes}
              onClose={() => setAnimate(null)}
              onLaunched={before => launched(animate.frame, before)}
            />
          )}
          {showOutline && outlineContext && board && (
            <OutlineDialog
              pid={pid}
              sid={sid}
              revision={board.revision}
              context={outlineContext}
              onClose={() => setShowOutline(false)}
              onDone={() => {
                setShowOutline(false);
                setTick(t => t + 1);
                setNotice('Сцены и кадры добавлены в раскадровку');
              }}
            />
          )}
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
          {board.scenes.some(s => s.frames.length) && (
            <EditListPanel key={'edit-' + sid} pid={pid} sid={sid} />
          )}
          {board.scenes.some(s => s.frames.length) && (
            <TensionGraph
              points={shotPoints(board.scenes, visual.plans)}
              onEstimate={() => void estimateEmpty()}
              estimating={estimating}
            />
          )}
          {board.scenes.map((scene, sceneIndex) => (
            <article key={scene.id} className="ps-scene">
              <div className="ps-scene-head">
                <span className="ps-order" role="group" aria-label={`Порядок сцены ${scene.title}`}>
                  <button
                    disabled={busy || sceneIndex === 0}
                    title="Сцену выше"
                    aria-label="Сцену выше"
                    onClick={() =>
                      shift(
                        sid,
                        board.scenes.map(s => s.id),
                        sceneIndex,
                        -1
                      )
                    }
                  >
                    ▲
                  </button>
                  <button
                    disabled={busy || sceneIndex === board.scenes.length - 1}
                    title="Сцену ниже"
                    aria-label="Сцену ниже"
                    onClick={() =>
                      shift(
                        sid,
                        board.scenes.map(s => s.id),
                        sceneIndex,
                        1
                      )
                    }
                  >
                    ▼
                  </button>
                </span>
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
                {(() => {
                  const {done, all} = sceneVideoCount(scene.frames);
                  return (
                    <span className={'ps-prog' + (all && done === all ? ' ok' : '')}>
                      видео {done} из {all}
                    </span>
                  );
                })()}
                {(() => {
                  const {done, all} = sceneSound(scene.frames.map(f => ({cues: sound[f.id] || []})));
                  return (
                    <span className={'ps-prog' + (all && done === all ? ' ok' : '')}>
                      звук {done} из {all}
                    </span>
                  );
                })()}
              </div>
              <p className="ps-text">{scene.notes || 'Описание пока не добавлено'}</p>
              <SceneCast
                catalogue={nodes}
                characterIds={scene.selection.character_node_ids}
                locationId={scene.selection.location_node_id}
                busy={busy}
                onOpen={inspect}
                onChange={patch => savePatch(scene.id, patch, 'Состав сцены сохранён.')}
              />
              <VisualPlanForm
                kind="scene"
                plan={visual.plans[scene.id]}
                onSave={plan => visual.save(scene.id, plan)}
              />
              <div className="ps-frames">
                {scene.frames.map((frame, frameIndex) => {
                  if (onlyNoVideo && frame.selection.selected_video_file_id) return null;
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
                      {changeOf(frame.notes) && <p className="ps-change">{changeOf(frame.notes)}</p>}
                      <small>
                        {image
                          ? frame.selection.selected_image_file_id
                            ? 'основное фото утверждено'
                            : 'последнее фото · не утверждено'
                          : 'запланирован'}
                      </small>
                      {(() => {
                        const st = frameStatus(frame.files, frame.selection, pending[frame.id], Date.now());
                        return (
                          <div className="ps-badges" aria-label="Статус кадра">
                            <span className={'ps-badge ' + st.photo}>{photoLabel(st)}</span>
                            <span className={'ps-badge v-' + st.video}>{videoLabel(st)}</span>
                            <span className={'ps-badge s-' + (sound[frame.id]?.length ? 'on' : 'off')}>
                              {soundLabel(sound[frame.id] || [])}
                            </span>
                          </div>
                        );
                      })()}
                      <FrameCast
                        id={frame.id}
                        pid={pid}
                        catalogue={nodes}
                        own={frame.selection}
                        scene={scene.selection}
                        busy={busy}
                        onChange={(patch, message) => savePatch(frame.id, patch, message)}
                      />
                      {frame.selection.selected_image_file_id && (
                        <UpscaleButton fileId={frame.selection.selected_image_file_id} />
                      )}
                      <FrameTakes
                        files={frame.files}
                        imageId={frame.selection.selected_image_file_id}
                        videoId={frame.selection.selected_video_file_id}
                        busy={busy}
                        onPick={(kind, id) =>
                          savePatch(
                            frame.id,
                            kind === 'image' ? {selected_image_file_id: id} : {selected_video_file_id: id},
                            id
                              ? kind === 'image'
                                ? 'Главное фото выбрано.'
                                : 'Главное видео выбрано.'
                              : 'Выбор снят.'
                          )
                        }
                      />
                      <div className="ps-acts">
                        <button
                          className="primary"
                          disabled={busy || !frame.selection.selected_image_file_id}
                          title={
                            frame.selection.selected_image_file_id
                              ? 'Оживить главное фото кадра'
                              : 'Сначала утверди главное фото'
                          }
                          onClick={() =>
                            setAnimate({
                              frame,
                              heroes: (frame.selection.character_node_ids.length ||
                              frame.selection.location_node_id
                                ? frame.selection.character_node_ids
                                : scene.selection.character_node_ids
                              )
                                .map(id => ({name: nodes.find(n => n.id === id)?.title || ''}))
                                .filter(h => h.name),
                            })
                          }
                        >
                          Оживить
                        </button>
                        <button disabled={busy} onClick={() => openFrame(frame)}>
                          В студию
                        </button>
                        <button onClick={() => inspect(frame.id)}>Файлы ↗</button>
                        <span className="ps-order" role="group" aria-label={`Порядок кадра ${frame.title}`}>
                          <button
                            disabled={busy || frameIndex === 0}
                            title="Кадр раньше"
                            aria-label="Кадр раньше"
                            onClick={() =>
                              shift(
                                scene.id,
                                scene.frames.map(f => f.id),
                                frameIndex,
                                -1
                              )
                            }
                          >
                            ◀
                          </button>
                          <button
                            disabled={busy || frameIndex === scene.frames.length - 1}
                            title="Кадр позже"
                            aria-label="Кадр позже"
                            onClick={() =>
                              shift(
                                scene.id,
                                scene.frames.map(f => f.id),
                                frameIndex,
                                1
                              )
                            }
                          >
                            ▶
                          </button>
                        </span>
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
