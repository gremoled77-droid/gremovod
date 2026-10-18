import ProductionStoryboard from './ProductionStoryboard';
import StoryPlanBoard from './StoryPlanBoard';
import SettingsPanel from './SettingsPanel';
import BudgetPanel from './BudgetPanel';
import StageFooter from './StageFooter';
import ProjectHeader from './ProjectHeader';
import {type FrameSelection} from './FramePanel';
import {type CameraSelection} from './CameraPanel';
import {mergeProject} from './projectMerge';
import {apiFetch} from './api';
import {type CharacterVersion} from './ReplaceCharacterButton';
import {type RefineDraft} from './RefinePanel';
import WorldFromBrief from './WorldFromBrief';
import {passportText} from './worldBible';
import WorldStyle from './WorldStyle';
import CharacterReferences from './CharacterReferences';
import AttachmentMenu, {AttachmentStrip} from './AttachmentMenu';
import CharactersScreen from './CharactersScreen';
import {EMPTY_SCENE, type Scene} from './scene';
import ConnectionsPanel from './ConnectionsPanel';
import AssetLibrary from './AssetLibrary';
import CreateScreen from './CreateScreen';
import VideoScreen from './VideoScreen';
import SoundScreen from './SoundScreen';
import ProductionPanel from './ProductionPanel';
import {MontageSummary} from './MontageSummary';
import EconomicsPanel from './EconomicsPanel';
import {ReleaseSummary} from './ReleaseSummary';
import HomeScreen from './HomeScreen';
import GenerationWatcher from './GenerationWatcher';
import {ActivityProvider} from './ActivityContext';
import StageNav from './StageNav';
import {isHidden, screenOf, type Mode} from './screens';
import WorkspaceTrail, {type WorkspaceLocation} from './WorkspaceTrail';
import {readWorkspaceRoute, workspaceHash} from './workspaceRoute';
import {readLocal, writeLocal, clearLocal} from './localDrafts';
import Dock, {countActive} from './Dock';
import Hotkeys from './Hotkeys';
import {rememberStage} from './lastStage';
import {OPEN_QUEUE_EVENT} from './imageRoutes';
import useActivity from './useActivity';
import IdeaBrief from './IdeaBrief';
import IdeaScreen from './IdeaScreen';
import IdeaRefs from './IdeaRefs';
import {lazy, Suspense, useCallback, useEffect, useRef, useState} from 'react';
import type {Node, Edge} from '@xyflow/react';
import {Plus, Settings} from 'lucide-react';

const GraphPanel = lazy(() => import('./WorkflowPanel'));

type Character = {
  working_asset_id?: string;
  version_history?: string[];
  id: string;
  name: string;
  identity: {
    species: string;
    face: string;
    hair: string;
    eyes: string;
    costume: string;
    negative: string;
  };
  profiles: Record<string, {prompt_notes: string; reference_urls: string}>;
};
type Job = {
  delivery?: {state: string; saved: number; total: number; error: string};
  id: string;
  kind: string;
  provider: string;
  status: string;
  task_id: string;
  response: any;
};
type StyleBible = {
  look: string;
  palette: string;
  lighting: string;
  camera: string;
  environment: string;
  time: string;
  tech: string;
  textures: string;
  mood: string;
  rules: string;
  avoid: string;
};
type Studio = {
  composition?: FrameSelection;
  compositionPromptBasis?: Record<string, string>;
  cameraPromptBasis?: Record<string, string>;
  camera?: CameraSelection;
  refinement?: RefineDraft;
  scene?: Scene;
  style: StyleBible;
  brief: string;
  ideaResult?: string;
  ideaModel?: string;
  ideaRefs?: string[];
  worldDraft?: Partial<StyleBible>;
  prompts: Record<string, string>;
  parameters: Record<string, Record<string, string | number>>;
  characters: Character[];
  selectedCharacter: string;
  referenceUrls: string;
  videoReference: string;
  motionBrief?: string;
  videoAssetId?: string;
  nodes: Node[];
  edges: Edge[];
};
const INITIAL: Studio = {
  style: {
    look: 'Кинематографичная стилизованная анимация с единым дизайном персонажей и окружения',
    palette: 'Баклажановый, янтарные ночные огни, глубокие синие тени',
    lighting: 'Ночной Минск; теплые фонари, прохладный ambient',
    camera: 'Согласованные пропорции и ракурсы',
    environment: 'Минск, дворики, панельки, гаражи, улицы',
    time: '',
    tech: '',
    textures: '',
    mood: '',
    rules: 'Грэм и автомобиль соответствуют утвержденным референсам',
    avoid: 'Случайные изменения внешности, формы машины, цвета и стилистики',
  },
  brief: '',
  prompts: {},
  parameters: {},
  selectedCharacter: '',
  referenceUrls: '',
  videoReference: '',
  characters: [],
  nodes: [],
  edges: [],
};
/** Старые демо-узлы «① Идея и GPT / ② Image Lab / ③ Video Lab» без вида узла: в открытых проектах убираем. */
const DEMO_NODES = new Set(['brief', 'image', 'video']);
function withoutDemoNodes(state: Studio): Studio {
  const demo = (n: Node) => DEMO_NODES.has(n.id) && n.type === 'studio' && !(n.data as {kind?: string})?.kind;
  if (!state.nodes?.some(demo)) return state;
  const nodes = state.nodes.filter(n => !demo(n));
  const ids = new Set(nodes.map(n => n.id));
  return {...state, nodes, edges: (state.edges || []).filter(e => ids.has(e.source) && ids.has(e.target))};
}
const json = async (r: Response) => {
  const d = await r.json().catch(() => ({detail: 'Не-JSON ответ'}));
  if (!r.ok) {
    const info = d.detail || d;
    throw Error(typeof info === 'string' ? info : JSON.stringify(info));
  }
  return d;
};
const url = '/api';
function App() {
  const [dockOpen, setDockOpen] = useState(false);
  const [worldTab, setWorldTab] = useState<'heroes' | 'locations'>('heroes');
  // Отправка в ChatGPT/Codex открывает «Очередь»: там лоток ожидания картинки.
  useEffect(() => {
    const open = () => setDockOpen(true);
    window.addEventListener(OPEN_QUEUE_EVENT, open);
    return () => window.removeEventListener(OPEN_QUEUE_EVENT, open);
  }, []);
  const [mode, setMode] = useState<Mode>(() => readWorkspaceRoute(window.location.hash)?.mode || 'home');
  // На телефоне «Очередь» закрывает полэкрана: при переходе на другой экран убираем её.
  useEffect(() => {
    if (window.matchMedia('(max-width: 700px)').matches) setDockOpen(false);
  }, [mode]);
  // Экраны, скрытые до беты, не открываются ни по кнопкам, ни по старым ссылкам.
  useEffect(() => {
    if (isHidden(mode)) setMode('home');
  }, [mode]);
  const [workspaceLocation, setWorkspaceLocation] = useState<WorkspaceLocation | null>(null);
  useEffect(() => {
    const header = document.querySelector<HTMLElement>('header.topbar');
    if (!header) return;
    const resize = () =>
      document.documentElement.style.setProperty(
        '--topbar-height',
        header.getBoundingClientRect().height + 'px'
      );
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(header);
    return () => observer.disconnect();
  }, []);
  const [provider, setProvider] = useState<'openai' | 'piapi'>('piapi');
  const [diagnostics, setDiagnostics] = useState<any>(null);
  const [projectId, setProjectId] = useState('');
  const currentProjectId = useRef(projectId);
  currentProjectId.current = projectId;
  const activity = useActivity(projectId);
  const activeCount = countActive(activity.items);
  const [projectName, setProjectName] = useState('Новый клип');
  const [projects, setProjects] = useState<{id: string; title: string}[]>([]);
  const [titleEditing, setTitleEditing] = useState(true);
  const [startup, setStartup] = useState<'loading' | 'ready' | 'error'>('loading');
  const [startupAttempt, setStartupAttempt] = useState(0);
  type ProjectChange =
    {type: 'new'; title?: string} | {type: 'load'; id: string; mode?: Mode; characterId?: string};
  const [pendingProjectChange, setPendingProjectChange] = useState<ProjectChange | null>(null);
  const [state, setState] = useState<Studio>(INITIAL);
  const [llm, setLlm] = useState('gpt-5.6-luna');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const change = (patch: Partial<Studio>) => setState(s => ({...s, ...patch}));
  const character = state.characters.find(c => c.id === state.selectedCharacter);
  const [apiHealth, setApiHealth] = useState<'checking' | 'online' | 'offline'>('checking');
  useEffect(() => {
    if (activity.error) setApiHealth('offline');
    else if (activity.connected) setApiHealth('online');
  }, [activity.error, activity.connected]);
  const checkHealth = useCallback(async () => {
    setApiHealth('checking');
    try {
      const d = await json(await apiFetch(url + '/health'));
      if (d.ok !== true) throw Error('Некорректный ответ /api/health');
      setApiHealth('online');
    } catch (e) {
      setApiHealth('offline');
      setError('Нет связи с API: ' + (e instanceof Error ? e.message : String(e)));
    }
  }, []);
  useEffect(() => {
    void checkHealth();
  }, [checkHealth]);
  const refresh = useCallback(async () => {
    try {
      setProjects(await json(await apiFetch(url + '/projects')));
    } catch (e) {
      if (currentProjectId.current === projectId)
        setError('Не удалось обновить список проектов: ' + (e instanceof Error ? e.message : String(e)));
    }
  }, [projectId]);
  useEffect(() => {
    refresh();
  }, [refresh]);
  const baseProject = useRef<{
    id: string;
    revision: number;
    title: string;
    state: Studio;
  } | null>(null);
  const loadingEpoch = useRef(0),
    saving = useRef(false);
  const [conflict, setConflict] = useState('');
  const [recovery, setRecovery] = useState<{
    projectId: string;
    title: string;
    state: Studio;
    conflicts: string[];
  } | null>(null);
  const [projectDraftSaved, setProjectDraftSaved] = useState(true);
  const persistProject = async () => {
    if (saving.current) throw Error('Сохранение уже выполняется. Дождись завершения.');
    const epoch = loadingEpoch.current,
      initial = {title: projectName.trim(), state};
    if (!initial.title) throw Error('Укажи название проекта');
    let local = initial,
      base = baseProject.current;
    if (projectId && base?.id !== projectId) throw Error('Перезагрузи проект перед сохранением.');
    saving.current = true;
    try {
      for (let attempt = 0; attempt < 3; attempt++) {
        const response = await apiFetch('/api/projects', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            id: projectId || undefined,
            ...local,
            base_revision: projectId ? base?.revision : undefined,
          }),
        });
        if (response.status === 409 && projectId && base) {
          const remote = await json(await apiFetch('/api/projects/' + projectId));
          const merged = mergeProject({title: base.title, state: base.state}, local, {
            title: remote.title,
            state: {...INITIAL, ...remote.state} as Studio,
          });
          if (merged.conflicts.length) {
            setConflict(
              'Конфликт сохранения: ' +
                merged.conflicts.join(', ') +
                '. Локальные правки остались в форме. Скачай их перед загрузкой серверной версии.'
            );
            throw Error('Сохранение остановлено: проект изменён в другом окне или обработчиком.');
          }
          local = merged.value;
          base = {...remote, state: {...INITIAL, ...remote.state}};
          continue;
        }
        const result = await json(response);
        if (epoch !== loadingEpoch.current) return result.id as string;
        baseProject.current = {
          id: result.id,
          revision: result.revision,
          ...local,
        };
        setProjectId(result.id);
        setState(current => mergeProject(initial.state, current, local.state).value);
        setProjectName(current => (current.trim() === initial.title ? local.title : current));
        setTitleEditing(false);
        setConflict('');
        clearLocal('studio:project-draft:' + result.id);
        return result.id as string;
      }
      throw Error('Проект продолжает изменяться. Правки сохранены в форме; повтори сохранение позже.');
    } finally {
      saving.current = false;
    }
  };
  const projectDirty =
    !projectId ||
    !baseProject.current ||
    projectName !== baseProject.current.title ||
    JSON.stringify(state) !== JSON.stringify(baseProject.current.state);
  useEffect(() => {
    if (!projectId || startup !== 'ready' || baseProject.current?.id !== projectId || recovery) return;
    const key = 'studio:project-draft:' + projectId;
    if (projectDirty)
      setProjectDraftSaved(
        writeLocal(key, {
          version: 1,
          base: {title: baseProject.current.title, state: baseProject.current.state},
          local: {title: projectName, state},
        })
      );
    else {
      clearLocal(key);
      setProjectDraftSaved(true);
    }
  }, [projectId, projectName, state, projectDirty, startup, recovery]);
  const downloadDraft = () => {
    const blob = new Blob([JSON.stringify({id: projectId, title: projectName, state}, null, 2)], {
      type: 'application/json',
    });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'studio-local-draft.json';
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const [libraryRevision, setLibraryRevision] = useState(0);
  const deliverySignature = useRef('');
  useEffect(() => {
    let active = true;
    deliverySignature.current = '';
    const update = async () => {
      if (!projectId || document.hidden) return;
      try {
        const items: Job[] = await json(
          await apiFetch('/api/jobs?project_id=' + encodeURIComponent(projectId))
        );
        if (!active) return;
        const signature = JSON.stringify(items.map(j => [j.id, j.delivery?.saved]));
        if (signature !== deliverySignature.current) {
          deliverySignature.current = signature;
          setLibraryRevision(x => x + 1);
        }
      } catch (e) {
        if (active) setError(String(e));
      }
    };
    void update();
    return () => {
      active = false;
    };
  }, [projectId, activity.items]);

  const replacementControls = {
    character,
    onReplaced: (updated: CharacterVersion, source: string) => {
      setState(s => ({
        ...s,
        characters: s.characters.map(c =>
          c.id === updated.id
            ? {
                ...c,
                working_asset_id: updated.working_asset_id,
                version_history: updated.version_history,
              }
            : c
        ),
        refinement: {
          source_asset_id: source,
          reference_asset_id: '',
          instruction: '',
        },
      }));
      setLibraryRevision(x => x + 1);
      setNotice('Рабочий образ персонажа заменён. Предыдущая версия перенесена в архив образов.');
    },
  };
  const work = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setError('');
    setNotice('');
    try {
      await fn();
    } catch (e: any) {
      const msg = e.message || String(e);
      setError(
        msg.includes('1010')
          ? 'Cloudflare 1010: PiAPI отклонил клиент. Не повторяй запрос — передай Ray ID поддержке. ' + msg
          : msg
      );
    } finally {
      setBusy('');
    }
  };
  const ensureProject = persistProject;
  const save = () =>
    work('save', async () => {
      await persistProject();
      setNotice('Проект сохранён');
      void refresh();
    });
  const openProject = useCallback(async (id: string, isActive: () => boolean = () => true) => {
    const epoch = ++loadingEpoch.current;
    const p = await json(await apiFetch(url + '/projects/' + encodeURIComponent(id)));
    if (!isActive() || epoch !== loadingEpoch.current) return;
    setApiHealth('online');
    const loaded = withoutDemoNodes({...INITIAL, ...p.state});
    baseProject.current = {
      id: p.id,
      revision: p.revision,
      title: p.title,
      state: loaded,
    };
    setProjectId(p.id);
    const draft = readLocal<{
      version: number;
      base: {title: string; state: Studio};
      local: {title: string; state: Studio};
    } | null>('studio:project-draft:' + p.id, null);
    let restored = {title: p.title as string, state: loaded as Studio};
    setRecovery(null);
    if (
      draft?.version === 1 &&
      draft.base?.state &&
      draft.local?.state &&
      Array.isArray(draft.local.state.characters) &&
      typeof draft.local.title === 'string'
    ) {
      const merge = mergeProject(
        {...draft.base, state: withoutDemoNodes(draft.base.state)},
        {...draft.local, state: withoutDemoNodes(draft.local.state)},
        restored
      );
      if (merge.conflicts.length) setRecovery({projectId: p.id, ...merge.value, conflicts: merge.conflicts});
      else restored = merge.value;
    }
    setProjectName(restored.title);
    setTitleEditing(false);
    setState(restored.state);
    setConflict('');
  }, []);
  useEffect(() => {
    let active = true;
    setStartup('loading');
    void (async () => {
      try {
        const saved = await json(await apiFetch(url + '/projects'));
        if (!active) return;
        setProjects(saved);
        // The API orders projects by their last saved time, newest first.
        if (saved.length) {
          const route = readWorkspaceRoute(window.location.hash);
          const id =
            route && saved.some((p: {id: string}) => p.id === route.projectId)
              ? route.projectId
              : saved[0].id;
          await openProject(id, () => active);
        }
        if (active) {
          setStartup('ready');
          setError('');
        }
      } catch (e) {
        if (active) {
          setStartup('error');
          setError('Не удалось открыть последний проект: ' + (e instanceof Error ? e.message : String(e)));
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [openProject, startupAttempt]);
  const applyProjectChange = async (target: ProjectChange) => {
    if (target.type === 'load') await openProject(target.id);
    else if (target.title?.trim()) {
      // «＋ Новый проект» со «Старта»: сразу сохраняем с названием и открываем на «Идее».
      const created = await json(
        await apiFetch('/api/projects', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({title: target.title.trim(), state: INITIAL}),
        })
      );
      await openProject(created.id);
      void refresh();
    } else {
      loadingEpoch.current++;
      baseProject.current = null;
      setProjectId('');
      setProjectName('Новый клип');
      setTitleEditing(true);
      setState(INITIAL);
      setConflict('');
    }
    if (target.type === 'new') setRecovery(null);
    if (target.type === 'load' && target.characterId)
      setState(s => ({...s, selectedCharacter: target.characterId!}));
    setMode(target.type === 'load' ? target.mode || 'studio' : 'studio');
    setNotice('');
  };
  const requestProjectChange = async (target: ProjectChange) => {
    if (busy || saving.current || startup !== 'ready') return;
    if (target.type === 'load' && target.id === projectId) {
      if (target.characterId) setState(s => ({...s, selectedCharacter: target.characterId!}));
      setMode(target.mode || 'studio');
      return;
    }
    const hasChanges = projectId
      ? projectDirty
      : projectName !== 'Новый клип' || JSON.stringify(state) !== JSON.stringify(INITIAL);
    if (hasChanges) {
      setPendingProjectChange(target);
      return;
    }
    await work('load', () => applyProjectChange(target));
  };
  const load = (id: string, destination?: Mode, characterId?: string) =>
    requestProjectChange({type: 'load', id, mode: destination, characterId});
  useEffect(() => {
    if (startup === 'ready' && projectId) rememberStage(projectId, mode);
  }, [projectId, mode, startup]);
  useEffect(() => {
    if (startup === 'ready' && projectId) {
      const hash = workspaceHash(projectId, mode);
      if (hash && window.location.hash !== hash) window.history.replaceState(null, '', hash);
    }
  }, [projectId, mode, startup]);
  const finishProjectChange = (saveFirst: boolean) =>
    work('switch-project', async () => {
      if (!pendingProjectChange) return;
      if (saveFirst) {
        await persistProject();
        void refresh();
      }
      if (!saveFirst && projectId) clearLocal('studio:project-draft:' + projectId);
      await applyProjectChange(pendingProjectChange);
      setPendingProjectChange(null);
    });
  const updateChar = (patch: Partial<Character>) => {
    if (!character) return;
    change({
      characters: state.characters.map(c => (c.id === character.id ? {...c, ...patch} : c)),
    });
  };
  const mkChar = () => {
    const id = crypto.randomUUID();
    const c: Character = {
      id,
      name: 'Новый персонаж',
      identity: {
        species: '',
        face: '',
        hair: '',
        eyes: '',
        costume: '',
        negative: '',
      },
      profiles: {},
    };
    change({characters: [...state.characters, c], selectedCharacter: id});
  };
  const apiStatus =
    apiHealth === 'online'
      ? 'Backend подключён'
      : apiHealth === 'checking'
        ? 'Проверка API…'
        : 'Backend недоступен';
  return (
    <ActivityProvider value={activity}>
      <div className="app shell">
        <StageNav mode={mode} onMode={setMode} />
        <header className="topbar">
          <div className="topbar-project">
            <select
              className="topbar-project-picker"
              aria-label="Текущий рабочий проект"
              value={projectId}
              disabled={startup !== 'ready' || !!busy}
              onChange={e => void load(e.target.value, mode)}
            >
              {!projectId && <option value="">Новый проект</option>}
              {projectId && !projects.some(p => p.id === projectId) && (
                <option value={projectId}>{projectName}</option>
              )}
              {projects.map(p => (
                <option key={p.id} value={p.id}>
                  {p.title}
                </option>
              ))}
            </select>
            <span className={'status topbar-status ' + apiHealth} role="status" title={apiStatus}>
              <i aria-hidden="true" />
              {apiStatus}
            </span>
          </div>
          <div className="top-actions">
            {projectId && projectDirty && (
              <button disabled={!!busy} onClick={() => void save()} title="Ctrl + S">
                Сохранить проект
              </button>
            )}
            <button
              className={'dock-toggle' + (dockOpen ? ' active' : '')}
              onClick={() => setDockOpen(v => !v)}
              aria-pressed={dockOpen}
            >
              Очередь{activeCount ? ` · ${activeCount}` : ''}
            </button>
            <button
              className="topbar-ghost"
              onClick={() => {
                void checkHealth();
                void refresh();
              }}
            >
              Проверить API
            </button>
            <div className="project-global-actions">
              <button
                className="topbar-new"
                disabled={startup !== 'ready' || !!busy}
                onClick={() => {
                  // Новый проект создаётся на «Старте»: название и сразу «Идея».
                  setMode('home');
                  window.setTimeout(() => document.getElementById('home-new-title')?.focus(), 50);
                }}
              >
                <Plus size={16} /> Новый проект
              </button>
              <button
                className={'settings-button ' + (mode === 'settings' ? 'active' : '')}
                aria-label="Настройки"
                title="Настройки"
                onClick={() => setMode('settings')}
              >
                <Settings size={19} />
              </button>
            </div>
          </div>
        </header>
        {dockOpen && <Dock projectId={projectId} onClose={() => setDockOpen(false)} />}
        {startup !== 'ready' ? (
          <section className="panel startup-panel" aria-live="polite">
            {startup === 'loading' ? (
              <p>Открываем последний сохранённый проект…</p>
            ) : (
              <>
                <p role="alert">{error}</p>
                <button onClick={() => setStartupAttempt(x => x + 1)}>Повторить открытие проекта</button>
              </>
            )}
          </section>
        ) : (
          <main className={screenOf(mode).main}>
            <div className="content">
              <WorkspaceTrail
                projectId={projectId}
                mode={mode}
                onMode={setMode}
                onLocation={setWorkspaceLocation}
                onOpenProject={id => void load(id, 'home')}
              />
              {!projectDraftSaved && (
                <p className="alert" role="alert">
                  Черновик проекта не сохранён браузером. Сохрани проект перед перезагрузкой.
                </p>
              )}
              {recovery && (
                <section className="alert" role="alert">
                  <p>
                    Сохранённый черновик конфликтует с серверными правками: {recovery.conflicts.join(', ')}.
                    Серверные данные автоматически не заменены.
                  </p>
                  <button
                    onClick={() => {
                      setState(recovery.state);
                      setProjectName(recovery.title);
                      setRecovery(null);
                      setConflict('Восстановлен черновик. Проверь конфликтующие поля перед сохранением.');
                    }}
                  >
                    Восстановить для проверки
                  </button>
                  <button
                    onClick={() => {
                      clearLocal('studio:project-draft:' + projectId);
                      setRecovery(null);
                    }}
                  >
                    Оставить серверную версию
                  </button>
                </section>
              )}
              {conflict && (
                <div className="alert" role="alert">
                  {conflict}
                  <div className="chips">
                    <button onClick={downloadDraft}>Скачать локальный черновик</button>
                    <button onClick={() => load(projectId)}>Загрузить серверную версию</button>
                  </div>
                </div>
              )}
              {error && (
                <div className="alert">
                  {error}
                  <button onClick={() => setError('')}>✕</button>
                </div>
              )}
              {notice && <div className="notice">{notice}</div>}
              {mode === 'settings' ? (
                <SettingsPanel
                  projectHeader={
                    <ProjectHeader
                      id={projectId}
                      name={projectName}
                      editing={titleEditing}
                      dirty={projectDirty}
                      busy={!!busy || saving.current}
                      onName={setProjectName}
                      onEdit={() => setTitleEditing(true)}
                      onCancel={() => {
                        setProjectName(baseProject.current?.title || projectName);
                        setTitleEditing(false);
                      }}
                      onSave={() => void save()}
                    />
                  }
                  onProjectsChanged={() => void refresh()}
                  provider={provider}
                  model={llm}
                  busy={!!busy}
                  diagnostics={diagnostics}
                  onProvider={value => {
                    setProvider(value);
                    setLlm(value === 'openai' ? 'gpt-4.1-mini' : 'gpt-5.6-luna');
                  }}
                  onModel={setLlm}
                  onConnections={() => setMode('connections')}
                  onDiagnose={() =>
                    void work('diagnose', async () =>
                      setDiagnostics(await json(await apiFetch('/api/diagnostics')))
                    )
                  }
                >
                  {projectId && <BudgetPanel projectId={projectId} />}
                </SettingsPanel>
              ) : mode === 'storyboard' ? (
                <>
                  <IdeaRefs projectId={projectId} ids={state.ideaRefs || []} />
                  <ProductionStoryboard
                    location={workspaceLocation}
                    outlineContext={{
                      projectId,
                      brief: state.brief,
                      passport: passportText(state.style),
                      heroes: state.characters.map(c => c.name),
                    }}
                    onOpenProject={id => {
                      void load(id, 'create');
                    }}
                  />
                </>
              ) : mode === 'connections' ? (
                <ConnectionsPanel />
              ) : mode === 'styles' || mode === 'characters' ? (
                <>
                  <nav className="world-tabs" aria-label="Разделы мира">
                    <button className={mode === 'styles' ? 'on' : ''} onClick={() => setMode('styles')}>
                      Стиль мира
                    </button>
                    <button
                      className={mode === 'characters' && worldTab === 'heroes' ? 'on' : ''}
                      onClick={() => {
                        setWorldTab('heroes');
                        setMode('characters');
                      }}
                    >
                      Персонажи{state.characters.length ? ` · ${state.characters.length}` : ''}
                    </button>
                    <button
                      className={mode === 'characters' && worldTab === 'locations' ? 'on' : ''}
                      onClick={() => {
                        setWorldTab('locations');
                        setMode('characters');
                      }}
                    >
                      Локации
                    </button>
                  </nav>
                  {mode === 'styles' ? (
                    <>
                      <IdeaRefs projectId={projectId} ids={state.ideaRefs || []} />
                      <WorldStyle
                        passport={passportText(state.style)}
                        style={state.style}
                        busy={!!busy}
                        attachments={<AttachmentStrip items={(state.scene || EMPTY_SCENE).assets} />}
                        onChange={style => change({style: {...state.style, ...style}})}
                        onSave={() => void save()}
                        onCopy={() =>
                          void navigator.clipboard
                            ?.writeText(passportText(state.style))
                            .then(() => setNotice('Паспорт мира скопирован'))
                        }
                        onNext={() => setMode('characters')}
                      />
                    </>
                  ) : (
                    <>
                      <CharactersScreen
                        projectId={projectId}
                        ensureProject={ensureProject}
                        heroes={state.characters}
                        selectedId={state.selectedCharacter}
                        world={state.style}
                        onSelect={id => change({selectedCharacter: id})}
                        onCreate={mkChar}
                        onToWorld={() => setMode('styles')}
                        onNext={() => setMode('storyboard')}
                        revision={libraryRevision}
                        onLibrary={() => setLibraryRevision(x => x + 1)}
                        card={
                          character && (
                            <section className="panel hero-card" aria-label="Карточка героя">
                              <h3>Карточка героя · {character.name}</h3>
                              <CharacterReferences
                                key={character.id}
                                projectId={projectId}
                                characterId={character.id}
                                name={character.name}
                                identity={character.identity}
                                workingImage={
                                  character.working_asset_id
                                    ? '/api/library/' + character.working_asset_id + '/file'
                                    : undefined
                                }
                                busy={!!busy}
                                ensureProject={ensureProject}
                                onName={name => updateChar({name})}
                                onIdentity={identity => updateChar({identity})}
                                onRecognized={result =>
                                  setState(current => ({
                                    ...current,
                                    characters: current.characters.map(item => {
                                      if (item.id !== character.id) return item;
                                      const identity = {...item.identity};
                                      for (const key of Object.keys(
                                        result.identity
                                      ) as (keyof Character['identity'])[]) {
                                        if ((identity[key] || '') === (result.baseline_identity[key] || ''))
                                          identity[key] = result.identity[key];
                                      }
                                      return {...item, identity};
                                    }),
                                  }))
                                }
                              />
                            </section>
                          )
                        }
                        view={worldTab}
                        results={
                          <AssetLibrary
                            {...replacementControls}
                            projectId={projectId}
                            revision={libraryRevision}
                          />
                        }
                      />
                    </>
                  )}
                </>
              ) : mode === 'home' ? (
                <HomeScreen
                  projectId={projectId}
                  projectName={projectName}
                  projects={projects}
                  onMode={setMode}
                  onOpenProject={(id, stage) => void load(id, stage)}
                  onNewProject={title => void requestProjectChange({type: 'new', title})}
                />
              ) : mode === 'create' ? (
                <CreateScreen
                  projectId={projectId}
                  heroes={state.characters.map(c => ({
                    id: c.id,
                    name: c.name,
                    assetId: c.working_asset_id,
                  }))}
                  world={[
                    state.style?.look,
                    state.style?.palette,
                    state.style?.lighting,
                    state.style?.environment,
                  ]
                    .filter(Boolean)
                    .join('. ')}
                />
              ) : mode === 'video' ? (
                <VideoScreen
                  projectId={projectId}
                  world={[
                    state.style?.look,
                    state.style?.palette,
                    state.style?.lighting,
                    state.style?.environment,
                  ]
                    .filter(Boolean)
                    .join('. ')}
                />
              ) : mode === 'audio' ? (
                <SoundScreen projectId={projectId} />
              ) : mode === 'files' ? (
                <>
                  <MontageSummary projectId={projectId} onMode={setMode} />
                  <ProductionPanel
                    projectId={projectId}
                    onOpenProject={(id, characterId) =>
                      void load(id, characterId ? 'characters' : 'create', characterId)
                    }
                  />
                </>
              ) : mode === 'economics' ? (
                <>
                  <ReleaseSummary projectId={projectId} />
                  <EconomicsPanel projectId={projectId} revision={libraryRevision} />
                </>
              ) : mode === 'archive' ? (
                <AssetLibrary {...replacementControls} projectId={projectId} revision={libraryRevision} />
              ) : mode === 'studio' ? (
                <IdeaScreen
                  briefText={state.brief}
                  worldFilled={Object.values(state.style || {}).filter(v => String(v || '').trim()).length}
                  worldTotal={11}
                  heroes={state.characters.length}
                  onMode={setMode}
                  storyBoard={<StoryPlanBoard location={workspaceLocation} brief={state.brief} />}
                  brief={
                    <IdeaBrief
                      projectId={projectId}
                      brief={state.brief}
                      onBrief={v => change({brief: v})}
                      result={state.ideaResult || ''}
                      onResult={v => change({ideaResult: v})}
                      model={state.ideaModel || 'gpt-5.6-luna'}
                      onModel={v => change({ideaModel: v})}
                      refs={state.ideaRefs || []}
                      onRefs={ids => change({ideaRefs: ids})}
                      world={[state.style.look, state.style.rules].filter(Boolean).join('. ')}
                      onNext={() => setMode('styles')}
                    />
                  }
                  world={
                    <>
                      <AttachmentMenu
                        projectId={projectId}
                        ensureProject={ensureProject}
                        heroes={state.characters}
                        items={(state.scene || EMPTY_SCENE).assets}
                        revision={libraryRevision}
                        onChange={assets =>
                          setState(s => ({...s, scene: {...(s.scene || EMPTY_SCENE), assets}}))
                        }
                        onAsset={() => setLibraryRevision(x => x + 1)}
                      />
                      <WorldFromBrief
                        projectId={projectId}
                        brief={state.brief}
                        style={state.style}
                        conflicts={state.worldDraft || {}}
                        onConflicts={worldDraft => setState(s => ({...s, worldDraft}))}
                        ensureProject={ensureProject}
                        onApply={fields => setState(s => ({...s, style: {...s.style, ...fields}}))}
                        onDone={() => setMode('styles')}
                      />
                    </>
                  }
                />
              ) : (
                <Suspense fallback={<p>Открываем редактор узлов…</p>}>
                  <GraphPanel
                    projectId={projectId}
                    nodes={state.nodes}
                    edges={state.edges}
                    onChange={update => setState(s => ({...s, ...update(s)}))}
                  />
                </Suspense>
              )}
              <StageFooter mode={mode} onMode={setMode} />
              <footer>Workflow Studio · ChatGPT · сцены · экономика ролика</footer>
            </div>
          </main>
        )}
        {pendingProjectChange && (
          <div className="modal-backdrop">
            <section
              className="panel project-switch-dialog"
              role="dialog"
              aria-modal="true"
              aria-labelledby="project-switch-title"
            >
              <h2 id="project-switch-title">Сохранить изменения проекта?</h2>
              <p>В «{projectName}» есть несохранённые изменения.</p>
              {error && <p role="alert">{error}</p>}
              <div className="project-save-actions">
                <button className="primary" disabled={!!busy} onClick={() => void finishProjectChange(true)}>
                  Сохранить и продолжить
                </button>
                <button disabled={!!busy} onClick={() => void finishProjectChange(false)}>
                  Продолжить без сохранения
                </button>
                <button autoFocus disabled={!!busy} onClick={() => setPendingProjectChange(null)}>
                  Остаться в проекте
                </button>
              </div>
            </section>
          </div>
        )}
        {projectId && (
          <GenerationWatcher key={projectId} projectId={projectId} onOpen={() => setMode('create')} />
        )}
        <Hotkeys
          mode={mode}
          onMode={setMode}
          projects={projects}
          onOpenProject={id => void load(id)}
          heroes={state.characters}
          onHero={id => {
            change({selectedCharacter: id});
            setWorldTab('heroes');
            setMode('characters');
          }}
          dockOpen={dockOpen}
          onCloseDock={() => setDockOpen(false)}
          onSave={() => {
            if (projectId && projectDirty && !busy) void save();
          }}
        />
      </div>
    </ActivityProvider>
  );
}
export default App;
