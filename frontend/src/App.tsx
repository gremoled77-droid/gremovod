import ProductionStoryboard from "./ProductionStoryboard";
const StoryboardDemo = lazy(() => import("./StoryboardDemo"));
const GraphPanel = lazy(() => import("./GraphPanel"));
import CharacterReferences from "./CharacterReferences";
import SettingsPanel from "./SettingsPanel";
import ProjectHeader from "./ProjectHeader";
import FramePanel, {
  FrameSelector,
  frameBasis,
  frameOutdated,
  type FrameCatalogue,
  type FrameSelection,
} from "./FramePanel";
import CameraPanel, {
  CameraSelector,
  EMPTY_CAMERA,
  cameraBasis,
  cameraOutdated,
  type CameraSelection,
  type CameraPreset,
} from "./CameraPanel";
import ProductionPanel from "./ProductionPanel";
import RecoverJob from "./RecoverJob";
import { mergeProject } from "./projectMerge";
import { apiFetch, PAID_LLM_ENABLED } from "./api";
import NativeGallery from "./NativeGallery";
import { type CharacterVersion } from "./ReplaceCharacterButton";
import RefinePanel, { EMPTY_REFINE, type RefineDraft } from "./RefinePanel";
import ChatGPTPanel from "./ChatGPTPanel";
import ScenePanel, { EMPTY_SCENE, type Scene } from "./ScenePanel";
import EconomicsPanel from "./EconomicsPanel";
import PromptComposer, { type PromptRequest } from "./PromptComposer";
import ConnectionsPanel from "./ConnectionsPanel";
import GenerationReview, { type GenerationRequest } from "./GenerationReview";
import AssetLibrary from "./AssetLibrary";
import CreateScreen from "./CreateScreen";
import AgentPanel from "./AgentPanel";
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type { Node, Edge } from "@xyflow/react";
import {
  MessageSquare,
  GitBranch,
  Plus,
  RefreshCw,
  Download,
  ShieldCheck,
  Music,
  Upload,
  Palette,
  Settings,
} from "lucide-react";

type ModelSpec = {
  kind: string;
  model: string;
  task_type: string;
  docs: string;
  max_refs: number;
  [key: string]: unknown;
};
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
  profiles: Record<string, { prompt_notes: string; reference_urls: string }>;
};
type Job = {
  delivery?: { state: string; saved: number; total: number; error: string };
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
    look: "Кинематографичная стилизованная анимация с единым дизайном персонажей и окружения",
    palette: "Баклажановый, янтарные ночные огни, глубокие синие тени",
    lighting: "Ночной Минск; теплые фонари, прохладный ambient",
    camera: "Согласованные пропорции и ракурсы",
    environment: "Минск, дворики, панельки, гаражи, улицы",
    rules: "Грэм и автомобиль соответствуют утвержденным референсам",
    avoid: "Случайные изменения внешности, формы машины, цвета и стилистики",
  },
  brief:
    "Кинематографичный кадр ночного Минска. Герой стоит спиной у окна и поёт. Камера медленно поднимается.",
  prompts: {},
  parameters: {},
  selectedCharacter: "",
  referenceUrls: "",
  videoReference: "",
  characters: [],
  nodes: [
    {
      id: "brief",
      type: "studio",
      position: { x: 30, y: 100 },
      data: { title: "① Идея и GPT", description: "Режиссёрское задание" },
    },
    {
      id: "image",
      type: "studio",
      position: { x: 330, y: 100 },
      data: { title: "② Image Lab", description: "Референсы и кадры" },
    },
    {
      id: "video",
      type: "studio",
      position: { x: 630, y: 100 },
      data: { title: "③ Video Lab", description: "Анимация выбранного кадра" },
    },
  ],
  edges: [
    { id: "e1", source: "brief", target: "image", animated: true },
    { id: "e2", source: "image", target: "video", animated: true },
  ],
};
const json = async (r: Response) => {
  const d = await r.json().catch(() => ({ detail: "Не-JSON ответ" }));
  if (!r.ok) {
    const info = d.detail || d;
    throw Error(typeof info === "string" ? info : JSON.stringify(info));
  }
  return d;
};
const url = "/api";
function App() {
  const [productionTarget, setProductionTarget] = useState<{
    productionId: string;
    nodeId: string;
  } | null>(null);
  const [storyboardDemoOpen, setStoryboardDemoOpen] = useState(false);
  const [demoVisited, setDemoVisited] = useState(false);
  const [mode, setMode] = useState<
    | "studio"
    | "graph"
    | "agents"
    | "styles"
    | "connections"
    | "scene"
    | "economics"
    | "refine"
    | "files"
    | "settings"
    | "storyboard"
    | "create"
  >("studio");
  const [audioFile, setAudioFile] = useState("");
  const [audioDuration, setAudioDuration] = useState(0);
  const [audioSegments, setAudioSegments] = useState<
    { start: number; end: number; duration: number }[]
  >([]);
  const [audioStart, setAudioStart] = useState(0);
  const [audioEnd, setAudioEnd] = useState(10);
  const [denoise, setDenoise] = useState(true);
  const [audioConsent, setAudioConsent] = useState(false);
  const [audioResult, setAudioResult] = useState("");
  const [provider, setProvider] = useState<"openai" | "piapi">("piapi");
  const [diagnostics, setDiagnostics] = useState<any>(null);
  const [assetList, setAssetList] = useState<any[]>([]);
  const [assetCategory, setAssetCategory] = useState("real_references");
  const [assetNote, setAssetNote] = useState("");
  const [projectId, setProjectId] = useState("");
  const [projectName, setProjectName] = useState("Новый клип");
  const [projects, setProjects] = useState<{ id: string; title: string }[]>([]);
  const [titleEditing, setTitleEditing] = useState(true);
  const [startup, setStartup] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [startupAttempt, setStartupAttempt] = useState(0);
  type ProjectChange = { type: "new" } | { type: "load"; id: string };
  const [pendingProjectChange, setPendingProjectChange] =
    useState<ProjectChange | null>(null);
  const [catalogue, setCatalogue] = useState<"frame" | "camera" | null>(null);
  const [frameCatalogue, setFrameCatalogue] = useState<FrameCatalogue>({
      frames: [],
      lights: [],
    }),
    [frameError, setFrameError] = useState("");
  useEffect(() => {
    let active = true;
    void apiFetch("/api/frame-presets")
      .then(json)
      .then((d) => {
        if (active) setFrameCatalogue(d);
      })
      .catch((e) => {
        if (active) setFrameError(String(e));
      });
    return () => {
      active = false;
    };
  }, []);
  const [cameraPresets, setCameraPresets] = useState<CameraPreset[]>([]),
    [cameraError, setCameraError] = useState("");
  useEffect(() => {
    let active = true;
    void apiFetch("/api/camera-presets")
      .then(json)
      .then((d) => {
        if (active) setCameraPresets(d.presets);
      })
      .catch((e) => {
        if (active) setCameraError(String(e));
      });
    return () => {
      active = false;
    };
  }, []);
  const [state, setState] = useState<Studio>(INITIAL);
  const [specs, setSpecs] = useState<Record<string, ModelSpec>>({});
  const [imageModel, setImageModel] = useState("seedream-5-lite");
  const [videoModel, setVideoModel] = useState("seedance-2.5");
  const [llm, setLlm] = useState("gpt-5.6-luna");
  const [chatText, setChatText] = useState("");
  const [messages, setMessages] = useState<{ role: string; content: string }[]>(
    [],
  );
  const [jobs, setJobs] = useState<Job[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selectedJob, setSelectedJob] = useState("");
  const [profileModel, setProfileModel] = useState("seedream-5-lite");
  useEffect(() => {
    setAssetList([]);
  }, [projectId, state.selectedCharacter]);
  const change = (patch: Partial<Studio>) =>
    setState((s) => ({ ...s, ...patch }));
  const character = state.characters.find(
    (c) => c.id === state.selectedCharacter,
  );
  const [apiHealth, setApiHealth] = useState<"checking" | "online" | "offline">(
    "checking",
  );
  const checkHealth = useCallback(async () => {
    setApiHealth("checking");
    try {
      const d = await json(await apiFetch(url + "/health"));
      if (d.ok !== true) throw Error("Некорректный ответ /api/health");
      setApiHealth("online");
    } catch (e) {
      setApiHealth("offline");
      setError(
        "Нет связи с API: " + (e instanceof Error ? e.message : String(e)),
      );
    }
  }, []);
  useEffect(() => {
    void checkHealth();
  }, [checkHealth]);
  const refresh = useCallback(async () => {
    try {
      setProjects(await json(await apiFetch(url + "/projects")));
      setJobs(
        projectId
          ? await json(
              await apiFetch(
                url + "/jobs?project_id=" + encodeURIComponent(projectId),
              ),
            )
          : [],
      );
    } catch (e) {
      setError(
        "Не удалось обновить проекты и очередь: " +
          (e instanceof Error ? e.message : String(e)),
      );
    }
  }, [projectId]);
  useEffect(() => {
    apiFetch(url + "/model-specs")
      .then(json)
      .then(setSpecs)
      .catch(() => setError("Backend недоступен. Запусти START_WINDOWS.bat."));
    refresh();
  }, [refresh]);
  const headers = { "Content-Type": "application/json" };
  const baseProject = useRef<{
    id: string;
    revision: number;
    title: string;
    state: Studio;
  } | null>(null);
  const loadingEpoch = useRef(0),
    saving = useRef(false);
  const [conflict, setConflict] = useState("");
  const persistProject = async () => {
    if (saving.current)
      throw Error("Сохранение уже выполняется. Дождись завершения.");
    const epoch = loadingEpoch.current,
      initial = { title: projectName.trim(), state };
    if (!initial.title) throw Error("Укажи название проекта");
    let local = initial,
      base = baseProject.current;
    if (projectId && base?.id !== projectId)
      throw Error("Перезагрузи проект перед сохранением.");
    saving.current = true;
    try {
      for (let attempt = 0; attempt < 3; attempt++) {
        const response = await apiFetch("/api/projects", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            id: projectId || undefined,
            ...local,
            base_revision: projectId ? base?.revision : undefined,
          }),
        });
        if (response.status === 409 && projectId && base) {
          const remote = await json(
            await apiFetch("/api/projects/" + projectId),
          );
          const merged = mergeProject(
            { title: base.title, state: base.state },
            local,
            {
              title: remote.title,
              state: { ...INITIAL, ...remote.state } as Studio,
            },
          );
          if (merged.conflicts.length) {
            setConflict(
              "Конфликт сохранения: " +
                merged.conflicts.join(", ") +
                ". Локальные правки остались в форме. Скачай их перед загрузкой серверной версии.",
            );
            throw Error(
              "Сохранение остановлено: проект изменён в другом окне или обработчиком.",
            );
          }
          local = merged.value;
          base = { ...remote, state: { ...INITIAL, ...remote.state } };
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
        setState(
          (current) => mergeProject(initial.state, current, local.state).value,
        );
        setProjectName((current) =>
          current.trim() === initial.title ? local.title : current,
        );
        setTitleEditing(false);
        setConflict("");
        return result.id as string;
      }
      throw Error(
        "Проект продолжает изменяться. Правки сохранены в форме; повтори сохранение позже.",
      );
    } finally {
      saving.current = false;
    }
  };
  const projectDirty =
    !projectId ||
    !baseProject.current ||
    projectName !== baseProject.current.title ||
    JSON.stringify(state) !== JSON.stringify(baseProject.current.state);
  const downloadDraft = () => {
    const blob = new Blob(
      [JSON.stringify({ id: projectId, title: projectName, state }, null, 2)],
      {
        type: "application/json",
      },
    );
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "studio-local-draft.json";
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const [promptRequest, setPromptRequest] = useState<PromptRequest | null>(
    null,
  );
  const [generationRequest, setGenerationRequest] =
    useState<GenerationRequest | null>(null);
  const [libraryRevision, setLibraryRevision] = useState(0);
  const deliverySignature = useRef("");
  useEffect(() => {
    let active = true;
    deliverySignature.current = "";
    const update = async () => {
      if (!projectId || document.hidden) return;
      try {
        const items: Job[] = await json(
          await apiFetch(
            "/api/jobs?project_id=" + encodeURIComponent(projectId),
          ),
        );
        if (!active) return;
        setJobs(items);
        const signature = JSON.stringify(
          items.map((j) => [j.id, j.delivery?.saved]),
        );
        if (signature !== deliverySignature.current) {
          deliverySignature.current = signature;
          setLibraryRevision((x) => x + 1);
        }
      } catch (e) {
        if (active) setError(String(e));
      }
    };
    void update();
    const timer = window.setInterval(() => void update(), 10000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [projectId]);

  const replacementControls = {
    character,
    onReplaced: (updated: CharacterVersion, source: string) => {
      setState((s) => ({
        ...s,
        characters: s.characters.map((c) =>
          c.id === updated.id
            ? {
                ...c,
                working_asset_id: updated.working_asset_id,
                version_history: updated.version_history,
              }
            : c,
        ),
        refinement: {
          source_asset_id: source,
          reference_asset_id: "",
          instruction: "",
        },
      }));
      setAssetList([]);
      setLibraryRevision((x) => x + 1);
      setNotice(
        "Рабочий образ персонажа заменён. Предыдущая версия перенесена в архив образов.",
      );
    },
  };
  const work = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e: any) {
      const msg = e.message || String(e);
      setError(
        msg.includes("1010")
          ? "Cloudflare 1010: PiAPI отклонил клиент. Не повторяй запрос — передай Ray ID поддержке. " +
              msg
          : msg,
      );
    } finally {
      setBusy("");
    }
  };
  const ensureProject = persistProject;
  const refineAsset = (source_asset_id: string) => {
    setState((s) => ({
      ...s,
      refinement: {
        ...(s.refinement || EMPTY_REFINE),
        source_asset_id,
        reference_asset_id: "",
      },
    }));
    setMode("refine");
    setNotice("Оригинал выбран для точечной правки в GPT Image.");
  };
  const addToScene = (asset_id: string) => {
    setState((s) => {
      const scene = s.scene || EMPTY_SCENE;
      return {
        ...s,
        scene: {
          ...scene,
          assets: scene.assets.some((a) => a.asset_id === asset_id)
            ? scene.assets
            : [
                ...scene.assets,
                {
                  asset_id,
                  role: scene.assets.length ? "location" : "character",
                  note: "",
                },
              ],
        },
      };
    });
    setMode("scene");
    setNotice("Исходник добавлен в сцену. Уточни его роль и постановку.");
  };
  const sceneGenerate = (target: string, prompt: string) =>
    work("scene-review", async () => {
      const id = await ensureProject();
      const context = await json(
        await apiFetch("/api/compose/preview", {
          method: "POST",
          headers,
          body: JSON.stringify({ project_id: id, target, use_scene: true }),
        }),
      );
      const refs = context.context.references.map(
        (r: { url: string }) => r.url,
      );
      if (refs.some((r: string) => !r.startsWith("https://")))
        throw Error(
          "Для передачи локальных исходников видеопровайдеру нужен публичный HTTPS URL. Загрузка исходников к провайдеру пока не подключена. Промпт и сцена сохранены.",
        );
      setGenerationRequest({
        project_id: id,
        model_id: target,
        prompt,
        options: state.parameters[target] || {},
        reference_urls: refs,
      });
    });
  const save = () =>
    work("save", async () => {
      await persistProject();
      setNotice("Проект сохранён");
      void refresh();
    });
  const openProject = useCallback(
    async (id: string, isActive: () => boolean = () => true) => {
      const epoch = ++loadingEpoch.current;
      const p = await json(
        await apiFetch(url + "/projects/" + encodeURIComponent(id)),
      );
      if (!isActive() || epoch !== loadingEpoch.current) return;
      const loaded = { ...INITIAL, ...p.state };
      baseProject.current = {
        id: p.id,
        revision: p.revision,
        title: p.title,
        state: loaded,
      };
      setProjectId(p.id);
      setProjectName(p.title);
      setTitleEditing(false);
      setState(loaded);
      setMessages([]);
      setChatText("");
      setJobs([]);
      setSelectedJob("");
      setConflict("");
    },
    [],
  );
  useEffect(() => {
    let active = true;
    setStartup("loading");
    void (async () => {
      try {
        const saved = await json(await apiFetch(url + "/projects"));
        if (!active) return;
        setProjects(saved);
        // The API orders projects by their last saved time, newest first.
        if (saved.length) await openProject(saved[0].id, () => active);
        if (active) {
          setStartup("ready");
          setError("");
        }
      } catch (e) {
        if (active) {
          setStartup("error");
          setError(
            "Не удалось открыть последний проект: " +
              (e instanceof Error ? e.message : String(e)),
          );
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [openProject, startupAttempt]);
  const applyProjectChange = async (target: ProjectChange) => {
    if (target.type === "load") await openProject(target.id);
    else {
      loadingEpoch.current++;
      baseProject.current = null;
      setProjectId("");
      setProjectName("Новый клип");
      setTitleEditing(true);
      setState(INITIAL);
      setMessages([]);
      setChatText("");
      setJobs([]);
      setSelectedJob("");
      setConflict("");
    }
    setCatalogue(null);
    setPromptRequest(null);
    setGenerationRequest(null);
    setMode("studio");
    setNotice("");
  };
  const requestProjectChange = async (target: ProjectChange) => {
    if (
      busy ||
      saving.current ||
      startup !== "ready" ||
      (target.type === "load" && target.id === projectId)
    )
      return;
    const hasChanges = projectId
      ? projectDirty
      : projectName !== "Новый клип" ||
        JSON.stringify(state) !== JSON.stringify(INITIAL);
    if (hasChanges) {
      setPendingProjectChange(target);
      return;
    }
    await work("load", () => applyProjectChange(target));
  };
  const load = (id: string) => requestProjectChange({ type: "load", id });
  const finishProjectChange = (saveFirst: boolean) =>
    work("switch-project", async () => {
      if (!pendingProjectChange) return;
      if (saveFirst) {
        await persistProject();
        void refresh();
      }
      await applyProjectChange(pendingProjectChange);
      setPendingProjectChange(null);
    });
  const sendChat = () =>
    work("chat", async () => {
      if (!chatText.trim()) return;
      const next = [...messages, { role: "user", content: chatText }];
      setMessages(next);
      setChatText("");
      const d = await json(
        await apiFetch(url + "/llm/chat", {
          method: "POST",
          headers,
          body: JSON.stringify({
            provider,
            model: llm,
            messages: [
              {
                role: "system",
                content:
                  "Ты режиссёр AI-видеостудии. Помогай создавать точные сцены и промпты; сохраняй внешность персонажей.",
              },
              ...next,
            ],
          }),
        }),
      );
      setMessages([
        ...next,
        {
          role: "assistant",
          content: d.choices?.[0]?.message?.content || "Нет ответа",
        },
      ]);
    });
  const draft = (model: string) =>
    work("draft", async () => {
      const d = await json(
        await apiFetch(url + "/prompt-drafts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target: model,
            brief: state.brief,
            character,
            style: state.style,
            camera: state.camera,
            composition: state.composition,
            motion_brief: state.motionBrief || "",
          }),
        }),
      );
      change({
        prompts: { ...state.prompts, [model]: d.prompt },
        ...(specs[model]?.kind === "video"
          ? {
              cameraPromptBasis: {
                ...state.cameraPromptBasis,
                [model]: cameraBasis(state.camera),
              },
            }
          : {
              compositionPromptBasis: {
                ...state.compositionPromptBasis,
                [model]: frameBasis(state.composition),
              },
            }),
      });
      setNotice(
        "Локальный черновик подготовлен без платного API. Проверь и отредактируй текст.",
      );
    });
  const compose = (model: string) =>
    work("compose-preview", async () => {
      const id = await persistProject();
      void refresh();
      setPromptRequest({ project_id: id, target: model, provider, model: llm });
    });
  const submit = (model: string, kind: string) =>
    work("review", async () => {
      if (!projectId) throw Error("Сначала сохрани проект");
      if (
        kind === "image" &&
        frameOutdated(
          state.composition,
          state.compositionPromptBasis?.[model],
          state.prompts[model] || "",
        )
      )
        throw Error(
          "Ракурс или свет изменены. Подготовь новый фотопромпт или проверь его вручную.",
        );
      if (
        kind === "video" &&
        cameraOutdated(
          state.camera,
          state.cameraPromptBasis?.[model],
          state.prompts[model] || "",
        )
      )
        throw Error(
          "Камера изменена. Пересобери видеопромпт или проверь его вручную.",
        );
      const profileRefs = (character?.profiles[model]?.reference_urls || "")
        .split(/[\n,]/)
        .map((x) => x.trim())
        .filter(Boolean);
      const manualRefs = (
        kind === "video"
          ? [state.videoReference]
          : state.referenceUrls.split(/[\n,]/)
      )
        .map((x) => x.trim())
        .filter(Boolean);
      setGenerationRequest({
        project_id: projectId,
        model_id: model,
        prompt: state.prompts[model] || state.brief,
        options: state.parameters[model] || {},
        reference_urls: [...new Set([...manualRefs, ...profileRefs])],
      });
    });
  const saveImage = (id: string, index: number) =>
    work("save-image", async () => {
      await json(
        await apiFetch(`/api/jobs/${id}/outputs/${index}/save`, {
          method: "POST",
        }),
      );
      setLibraryRevision((v) => v + 1);
      setNotice("Оригинал и параметры сохранены в библиотеке проекта");
    });
  const poll = (id: string) =>
    work("poll", async () => {
      const d = await json(await apiFetch(url + "/jobs/" + id));
      setJobs((a) =>
        a.map((j) =>
          j.id === id
            ? {
                ...j,
                status: d.upstream?.data?.status || j.status,
                response: d.upstream,
              }
            : j,
        ),
      );
      setNotice("Статус обновлён");
    });
  const extract = (j: Job): string[] => {
    const o = j.response?.data?.output || {};
    const vals = [
      o.image_urls,
      o.images,
      o.video_urls,
      o.image_url,
      o.video_url,
      o.url,
      o.image,
      o.video,
    ]
      .flat(3)
      .filter(Boolean);
    return [
      ...new Set<string>(
        vals
          .map((v: any) => (typeof v === "string" ? v : v?.url || ""))
          .filter((v: string) => /^https?:\/\//.test(v)),
      ),
    ];
  };
  const updateChar = (patch: Partial<Character>) => {
    if (!character) return;
    change({
      characters: state.characters.map((c) =>
        c.id === character.id ? { ...c, ...patch } : c,
      ),
    });
  };
  const mkChar = () => {
    const id = crypto.randomUUID();
    const c: Character = {
      id,
      name: "Новый персонаж",
      identity: {
        species: "",
        face: "",
        hair: "",
        eyes: "",
        costume: "",
        negative: "",
      },
      profiles: {},
    };
    change({ characters: [...state.characters, c], selectedCharacter: id });
  };
  const chooseComposition = (composition: FrameSelection) => {
    change({ composition });
    setNotice(
      "Ракурс и свет выбраны. Подготовь фотопромпт с этими настройками.",
    );
  };
  const chooseCamera = (camera: CameraSelection) => {
    change({ camera });
    setNotice("Камера выбрана. Подготовь новый видеопромпт с этим движением.");
  };
  const models = Object.entries(specs);
  const images = models.filter(([, v]) => v.kind === "image");
  const videos = models.filter(([, v]) => v.kind === "video");
  const paramFields = (model: string) => {
    const spec = specs[model];
    if (!spec) return null;
    return (
      <div className="param-grid">
        {["size", "resolution", "aspect_ratio", "output_format"]
          .filter((k) => Array.isArray(spec[k]))
          .map((k) => (
            <label key={k}>
              {k}
              <select
                value={String(state.parameters[model]?.[k] || "")}
                onChange={(e) =>
                  change({
                    parameters: {
                      ...state.parameters,
                      [model]: {
                        ...state.parameters[model],
                        [k]: e.target.value,
                      },
                    },
                  })
                }
              >
                <option value="">По умолчанию</option>
                {(spec[k] as string[]).map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            </label>
          ))}
        {spec.kind === "video" &&
          !spec.prompt_only &&
          spec.duration_mode !== "provider_default" && (
            <label>
              Длительность, сек.
              <input
                type="number"
                min={Number(spec.duration_min)}
                max={Number(spec.duration_max)}
                value={Number(state.parameters[model]?.duration || 5)}
                onChange={(e) =>
                  change({
                    parameters: {
                      ...state.parameters,
                      [model]: {
                        ...state.parameters[model],
                        duration: Number(e.target.value),
                      },
                    },
                  })
                }
              />
            </label>
          )}
      </div>
    );
  };
  const modelPanel = (kind: "image" | "video") => {
    const model = kind === "image" ? imageModel : videoModel;
    const options = kind === "image" ? images : videos;
    return (
      <section className="panel">
        <div className="panel-title">
          <h2>{kind === "image" ? "② Image Lab" : "③ Video Lab"}</h2>
          <a target="_blank" rel="noreferrer" href={specs[model]?.docs}>
            Мануал ↗
          </a>
        </div>
        <div className="model-tabs">
          {options.map(([id]) => (
            <button
              key={id}
              className={model === id ? "active" : ""}
              onClick={() =>
                kind === "image" ? setImageModel(id) : setVideoModel(id)
              }
            >
              {id}
            </button>
          ))}
        </div>
        {kind === "image" && (
          <FrameSelector
            catalogue={frameCatalogue}
            value={state.composition}
            onChange={chooseComposition}
            onCatalogue={() => setCatalogue("frame")}
          />
        )}
        {kind === "video" && (
          <label>
            Действие в кадре
            <textarea
              rows={3}
              value={state.motionBrief || ""}
              onChange={(e) => change({ motionBrief: e.target.value })}
              placeholder="Опиши действия героя и происходящее за выбранную длительность"
            />
          </label>
        )}
        {kind === "video" && (
          <label>
            Выбранный референс из Image Lab
            <input
              value={state.videoReference}
              onChange={(e) => change({ videoReference: e.target.value })}
              placeholder="https://..."
            />
          </label>
        )}
        {kind === "video" && (
          <>
            <CameraSelector
              setupEnabled={!!frameCatalogue.capabilities?.prompt_setup}
              presets={cameraPresets}
              value={state.camera || EMPTY_CAMERA}
              onChange={chooseCamera}
              onCatalogue={() => setCatalogue("camera")}
              disabled={!!busy}
            />
            {cameraError && <p role="alert">{cameraError}</p>}
          </>
        )}
        {kind === "video" && (
          <ChatGPTPanel
            projectId={projectId}
            target={model}
            ensureProject={ensureProject}
            onAsset={() => setLibraryRevision((x) => x + 1)}
            onPrompt={(prompt, target, movement) =>
              setState((s) => ({
                ...s,
                prompts: { ...s.prompts, [target]: prompt },
                cameraPromptBasis: {
                  ...s.cameraPromptBasis,
                  [target]: cameraBasis(movement),
                },
              }))
            }
          />
        )}
        <div className="capabilities">
          <b>Входы модели:</b> <span>✍ Текст ✓</span>
          <span>🖼 Фото {specs[model]?.max_refs ? "✓" : "—"}</span>
          <span>🎥 Видео {kind === "video" ? "пока не подключено" : "—"}</span>
          <span>🔊 Аудио {kind === "video" ? "пока не подключено" : "—"}</span>
        </div>
        {kind === "image" && (
          <label>
            URL референсов (по одному на строку)
            <textarea
              rows={2}
              value={state.referenceUrls}
              onChange={(e) => change({ referenceUrls: e.target.value })}
              placeholder="https://..."
            />
          </label>
        )}
        <div className="twocol">
          <div>
            <label>
              Отдельный промпт — {model}
              <textarea
                rows={7}
                value={state.prompts[model] || ""}
                onChange={(e) =>
                  change({
                    prompts: { ...state.prompts, [model]: e.target.value },
                  })
                }
                placeholder="Можно написать вручную либо сгенерировать через GPT"
              />
            </label>
            {kind === "video" &&
              cameraOutdated(
                state.camera,
                state.cameraPromptBasis?.[model],
                state.prompts[model] || "",
              ) && (
                <div className="notice" role="status">
                  <p>
                    Камера изменена: подготовь новый видеопромпт или проверь
                    текущий вручную.
                  </p>
                  <button
                    onClick={() =>
                      change({
                        cameraPromptBasis: {
                          ...state.cameraPromptBasis,
                          [model]: cameraBasis(state.camera),
                        },
                      })
                    }
                  >
                    Камера учтена в этом промпте
                  </button>
                </div>
              )}
            {kind === "image" &&
              frameOutdated(
                state.composition,
                state.compositionPromptBasis?.[model],
                state.prompts[model] || "",
              ) && (
                <div className="notice" role="status">
                  <p>
                    Ракурс или свет изменены. Подготовь новый фотопромпт либо
                    проверь его вручную.
                  </p>
                  <button
                    onClick={() =>
                      change({
                        compositionPromptBasis: {
                          ...state.compositionPromptBasis,
                          [model]: frameBasis(state.composition),
                        },
                      })
                    }
                  >
                    Ракурс и свет учтены в промпте
                  </button>
                </div>
              )}
            <button
              className="secondary"
              disabled={!!busy}
              onClick={() => draft(model)}
            >
              Локальный черновик
            </button>
            <button
              className="secondary"
              disabled={!!busy}
              onClick={() => compose(model)}
            >
              ✦ Подготовить промпт через API
            </button>
          </div>
          <div>
            <h3>Настройки по API-мануалу</h3>
            {paramFields(model)}
            <div className="muted">
              Референсов: до {specs[model]?.max_refs || "—"}. Непроверенные
              модели отключены до добавления API-схем.
            </div>
            <button
              className="primary"
              disabled={
                !!busy ||
                !specs[model]?.launch_enabled ||
                (kind === "image" &&
                  frameOutdated(
                    state.composition,
                    state.compositionPromptBasis?.[model],
                    state.prompts[model] || "",
                  )) ||
                (kind === "video" &&
                  cameraOutdated(
                    state.camera,
                    state.cameraPromptBasis?.[model],
                    state.prompts[model] || "",
                  ))
              }
              onClick={() => submit(model, kind)}
            >
              ▶ Проверить и запустить{" "}
              {kind === "image" ? "изображение" : "видео"}
            </button>
            {!specs[model]?.launch_enabled && (
              <p className="muted">
                Запуск отключён до проверки схемы и стоимости.
              </p>
            )}
          </div>
        </div>
      </section>
    );
  };
  const uploadAudio = (f: File) =>
    work("upload", async () => {
      const form = new FormData();
      form.append("file", f);
      const result = await json(
        await apiFetch("/api/media/upload", { method: "POST", body: form }),
      );
      setAudioFile(result.url);
      setAudioResult("");
      setAudioSegments([]);
      setNotice("Медиа импортировано локально: " + f.name);
    });
  const analyzeAudio = () =>
    work("analyze", async () => {
      const result = await json(
        await apiFetch("/api/audio/analyze/" + audioFile.split("/").pop()),
      );
      setAudioDuration(result.duration);
      setAudioEnd(Math.min(result.duration, 10));
      setAudioSegments(result.suggested_segments);
      setNotice(
        "Найдены предложения для монтажа по паузам (не оценка качества исполнения)",
      );
    });
  const cutAudio = () =>
    work("cut", async () => {
      const result = await json(
        await apiFetch("/api/audio/cut", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filename: audioFile.split("/").pop(),
            start: audioStart,
            end: audioEnd,
            denoise,
            normalize: true,
            consent_confirmed: audioConsent,
          }),
        }),
      );
      setAudioResult(result.url);
      setNotice("Фрагмент подготовлен: WAV 44.1 kHz, mono, loudnorm");
    });
  const apiStatus =
    apiHealth === "online"
      ? "Backend подключён"
      : apiHealth === "checking"
        ? "Проверка API…"
        : "Backend недоступен";
  return (
    <div className="app">
      <Suspense fallback={<p>Открываем демо…</p>}>
        {demoVisited && (
          <StoryboardDemo
            open={storyboardDemoOpen}
            onClose={() => setStoryboardDemoOpen(false)}
          />
        )}
      </Suspense>
      <header>
        <div className="brand">
          <span className="logo">◆</span>
          <div>
            <b>AI WORKFLOW STUDIO</b>
            <small>Локальная AI-студия</small>
          </div>
        </div>
        <div className="top-actions">
          <button
            onClick={() => setMode("connections")}
            className={mode === "connections" ? "active" : ""}
          >
            Подключения
          </button>
          <span className={"status " + apiHealth} role="status">
            ● {apiStatus}
          </span>
          <button
            onClick={() => {
              void checkHealth();
              void refresh();
            }}
          >
            Проверить API
          </button>
          <button
            onClick={() => setMode("create")}
            className={mode === "create" ? "active" : ""}
          >
            Создать
          </button>
          <button
            onClick={() => setMode("studio")}
            className={mode === "studio" ? "active" : ""}
          >
            ▤ Студия
          </button>
          <button
            onClick={() => setMode("storyboard")}
            className={mode === "storyboard" ? "active" : ""}
          >
            Раскадровка
          </button>
          <button
            onClick={() => {
              setDemoVisited(true);
              setStoryboardDemoOpen(true);
            }}
          >
            Раскадровка · демо
          </button>
          <button
            onClick={() => setMode("files")}
            className={mode === "files" ? "active" : ""}
          >
            Папки проекта
          </button>
          <button
            onClick={() => setMode("scene")}
            className={mode === "scene" ? "active" : ""}
          >
            Сцена
          </button>
          <button
            onClick={() => setMode("refine")}
            className={mode === "refine" ? "active" : ""}
          >
            Допилить
          </button>
          <button
            onClick={() => setMode("economics")}
            className={mode === "economics" ? "active" : ""}
          >
            Экономика
          </button>
          <button
            onClick={() => setMode("agents")}
            className={mode === "agents" ? "active" : ""}
          >
            ☁ Агенты
          </button>
          <button
            onClick={() => setMode("styles")}
            className={mode === "styles" ? "active" : ""}
          >
            <Palette size={15} /> Мир и стиль
          </button>
          <button
            onClick={() => setMode("graph")}
            className={mode === "graph" ? "active" : ""}
          >
            <GitBranch size={15} /> Узлы
          </button>
          <div className="project-global-actions">
            <button
              disabled={startup !== "ready" || !!busy}
              onClick={() => void requestProjectChange({ type: "new" })}
            >
              <Plus size={16} /> Новый проект
            </button>
            <button
              className={
                "settings-button " + (mode === "settings" ? "active" : "")
              }
              aria-label="Настройки"
              title="Настройки"
              onClick={() => setMode("settings")}
            >
              <Settings size={19} />
            </button>
          </div>
        </div>
      </header>
      {startup !== "ready" ? (
        <section className="panel startup-panel" aria-live="polite">
          {startup === "loading" ? (
            <p>Открываем последний сохранённый проект…</p>
          ) : (
            <>
              <p role="alert">{error}</p>
              <button onClick={() => setStartupAttempt((x) => x + 1)}>
                Повторить открытие проекта
              </button>
            </>
          )}
        </section>
      ) : (
        <main className={mode === "storyboard" ? "storyboard-main" : ""}>
          <aside className="sidebar">
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
            <label>
              Открыть проект
              <select
                value={projectId}
                disabled={!!busy}
                onChange={(e) => void load(e.target.value)}
              >
                <option value="" disabled>
                  {projects.length
                    ? "Выбери сохранённый проект"
                    : "Нет сохранённых проектов"}
                </option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.title}
                  </option>
                ))}
              </select>
            </label>
            <hr />
            <hr />
            <h3>
              <ShieldCheck size={16} /> Character Vault
            </h3>
            <button className="secondary" onClick={mkChar}>
              <Plus size={14} /> Новый персонаж
            </button>
            <select
              value={state.selectedCharacter}
              onChange={(e) => change({ selectedCharacter: e.target.value })}
            >
              <option value="">Без персонажа</option>
              {state.characters.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            {character && (
              <div className="char-editor">
                <CharacterReferences
                  key={character.id}
                  projectId={projectId}
                  characterId={character.id}
                  name={character.name}
                  identity={character.identity}
                  workingImage={
                    character.working_asset_id
                      ? "/api/library/" + character.working_asset_id + "/file"
                      : undefined
                  }
                  busy={!!busy}
                  ensureProject={ensureProject}
                  onName={(name) => updateChar({ name })}
                  onIdentity={(identity) => updateChar({ identity })}
                  onRecognized={(result) =>
                    setState((current) => ({
                      ...current,
                      characters: current.characters.map((item) => {
                        if (item.id !== character.id) return item;
                        const identity = { ...item.identity };
                        for (const key of Object.keys(
                          result.identity,
                        ) as (keyof Character["identity"])[]) {
                          if (
                            (identity[key] || "") ===
                            (result.baseline_identity[key] || "")
                          )
                            identity[key] = result.identity[key];
                        }
                        return { ...item, identity };
                      }),
                    }))
                  }
                >
                  <h4>Профиль конкретной модели</h4>
                  <select
                    value={profileModel}
                    onChange={(e) => setProfileModel(e.target.value)}
                  >
                    {models.map(([k]) => (
                      <option key={k} value={k}>
                        {k}
                      </option>
                    ))}
                  </select>
                  <label>
                    Особые инструкции
                    <textarea
                      rows={3}
                      value={
                        character.profiles[profileModel]?.prompt_notes || ""
                      }
                      onChange={(e) =>
                        updateChar({
                          profiles: {
                            ...character.profiles,
                            [profileModel]: {
                              reference_urls:
                                character.profiles[profileModel]
                                  ?.reference_urls || "",
                              prompt_notes: e.target.value,
                            },
                          },
                        })
                      }
                    />
                  </label>
                  <label>
                    Референсы только для этой модели
                    <textarea
                      rows={2}
                      value={
                        character.profiles[profileModel]?.reference_urls || ""
                      }
                      onChange={(e) =>
                        updateChar({
                          profiles: {
                            ...character.profiles,
                            [profileModel]: {
                              prompt_notes:
                                character.profiles[profileModel]
                                  ?.prompt_notes || "",
                              reference_urls: e.target.value,
                            },
                          },
                        })
                      }
                    />
                  </label>
                  <p className="muted">
                    Выбери любую модель выше. Профили и референсы хранятся
                    отдельно и подставляются при запуске.
                  </p>
                  <h4>Папки и файлы персонажа</h4>
                  <p className="muted">
                    Сначала сохрани проект, затем загружай исходники. Категория
                    rejected — негативные примеры, они не подаются как
                    референсы.
                  </p>
                  <select
                    value={assetCategory}
                    onChange={(e) => setAssetCategory(e.target.value)}
                  >
                    {[
                      ["real_references", "Реальные референсы"],
                      ["candidate_generations", "Кандидаты на утверждение"],
                      ["approved_generations", "Утверждённые"],
                      ["archived_generations", "Архив образов"],
                      ["rejected_generations", "Неудачные"],
                      ["model_references", "Для конкретной модели"],
                    ].map(([v, n]) => (
                      <option key={v} value={v}>
                        {n}
                      </option>
                    ))}
                  </select>
                  <input
                    placeholder="Комментарий или ошибка"
                    value={assetNote}
                    onChange={(e) => setAssetNote(e.target.value)}
                  />
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (!f || !projectId || !character) return;
                      work("asset", async () => {
                        const fd = new FormData();
                        fd.append("file", f);
                        fd.append("category", assetCategory);
                        fd.append(
                          "model_id",
                          assetCategory === "model_references"
                            ? profileModel
                            : "",
                        );
                        fd.append("note", assetNote);
                        await json(
                          await apiFetch(
                            `/api/characters/${projectId}/${character.id}/assets`,
                            {
                              method: "POST",
                              body: fd,
                            },
                          ),
                        );
                        setAssetList(
                          await json(
                            await apiFetch(
                              `/api/characters/${projectId}/${character.id}/assets`,
                            ),
                          ),
                        );
                        setNotice("Референс сохранён");
                      });
                    }}
                  />
                  <button
                    className="secondary"
                    onClick={() =>
                      work("assets", async () => {
                        if (!projectId || !character)
                          throw Error(
                            "Сначала сохрани проект и выбери персонажа",
                          );
                        setAssetList(
                          await json(
                            await apiFetch(
                              `/api/characters/${projectId}/${character.id}/assets`,
                            ),
                          ),
                        );
                      })
                    }
                  >
                    Показать файлы персонажа
                  </button>
                  <div className="asset-grid">
                    {assetList.map((a) => (
                      <div key={a.id} className="asset-card">
                        <img src={a.url} alt={a.original_name} />
                        <small>
                          {a.category} · {a.original_name}
                        </small>
                        <small>{a.note}</small>
                        <button
                          onClick={() =>
                            work("remove", async () => {
                              await json(
                                await apiFetch(
                                  "/api/character-assets/" + a.id,
                                  { method: "DELETE" },
                                ),
                              );
                              setAssetList((v) =>
                                v.filter((x) => x.id !== a.id),
                              );
                            })
                          }
                        >
                          Удалить
                        </button>
                      </div>
                    ))}
                  </div>
                </CharacterReferences>
              </div>
            )}
          </aside>
          <div className="content">
            {conflict && (
              <div className="alert" role="alert">
                {conflict}
                <div className="chips">
                  <button onClick={downloadDraft}>
                    Скачать локальный черновик
                  </button>
                  <button onClick={() => load(projectId)}>
                    Загрузить серверную версию
                  </button>
                </div>
              </div>
            )}
            {error && (
              <div className="alert">
                {error}
                <button onClick={() => setError("")}>✕</button>
              </div>
            )}
            {notice && <div className="notice">{notice}</div>}
            {mode === "settings" ? (
              <SettingsPanel
                provider={provider}
                model={llm}
                busy={!!busy}
                diagnostics={diagnostics}
                onProvider={(value) => {
                  setProvider(value);
                  setLlm(value === "openai" ? "gpt-4.1-mini" : "gpt-5.6-luna");
                }}
                onModel={setLlm}
                onConnections={() => setMode("connections")}
                onDiagnose={() =>
                  void work("diagnose", async () =>
                    setDiagnostics(
                      await json(await apiFetch("/api/diagnostics")),
                    ),
                  )
                }
              >
                <>
                  <section className="panel">
                    <div className="panel-title">
                      <h2>① Prompt Director + GPT</h2>
                      <MessageSquare size={20} />
                    </div>
                    <label>
                      Режиссёрское задание
                      <textarea
                        rows={4}
                        value={state.brief}
                        onChange={(e) => change({ brief: e.target.value })}
                      />
                    </label>
                    <div className="chat-history">
                      {messages.length ? (
                        messages.map((m, i) => (
                          <div key={i} className={"bubble " + m.role}>
                            {m.content}
                          </div>
                        ))
                      ) : (
                        <span className="muted">
                          Чат сохраняет контекст в текущей сессии. Создай сцену,
                          затем адаптируй её для выбранных моделей.
                        </span>
                      )}
                    </div>
                    <div className="chat-controls">
                      <input
                        value={chatText}
                        onChange={(e) => setChatText(e.target.value)}
                        onKeyDown={(e) =>
                          e.key === "Enter" && !e.shiftKey && sendChat()
                        }
                        placeholder="Спроси GPT о сцене или промпте…"
                      />
                      <button
                        className="primary"
                        disabled={!PAID_LLM_ENABLED || !!busy}
                        onClick={sendChat}
                      >
                        Отправить
                      </button>
                    </div>
                  </section>
                  {modelPanel("image")}
                </>
              </SettingsPanel>
            ) : mode === "storyboard" ? (
              <ProductionStoryboard
                onInspect={(productionId, nodeId) => {
                  setProductionTarget({ productionId, nodeId });
                  setMode("files");
                }}
                onOpenProject={(id) => {
                  void load(id);
                  setMode("studio");
                }}
              />
            ) : mode === "files" ? (
              <ProductionPanel
                initialLocation={productionTarget}
                projectId={projectId}
                onOpenProject={(id, characterId) => {
                  void load(id).then(() => {
                    if (characterId)
                      setState((s) => ({
                        ...s,
                        selectedCharacter: characterId,
                      }));
                    setMode("studio");
                  });
                }}
              />
            ) : mode === "connections" ? (
              <ConnectionsPanel />
            ) : mode === "agents" ? (
              <AgentPanel
                projectId={projectId}
                brief={state.brief}
                character={character}
                style={state.style}
                onApply={(prompt) => {
                  change({ brief: prompt });
                  setMode("studio");
                }}
              />
            ) : mode === "refine" ? (
              <RefinePanel
                {...replacementControls}
                projectId={projectId}
                draft={state.refinement || EMPTY_REFINE}
                onChange={(refinement) => change({ refinement })}
                ensureProject={ensureProject}
                onAsset={() => setLibraryRevision((x) => x + 1)}
                revision={libraryRevision}
              />
            ) : mode === "scene" ? (
              <ScenePanel
                onFrameCatalogue={() => setCatalogue("frame")}
                onCameraCatalogue={() => setCatalogue("camera")}
                frameCatalogue={frameCatalogue}
                composition={state.composition}
                onComposition={chooseComposition}
                cameraPresets={cameraPresets}
                camera={state.camera}
                onCamera={chooseCamera}
                scene={state.scene || EMPTY_SCENE}
                onChange={(scene) => change({ scene })}
                projectId={projectId}
                revision={libraryRevision}
                models={models.map(([id, v]) => ({
                  id,
                  kind: v.kind,
                  enabled: !!v.launch_enabled,
                }))}
                ensureProject={ensureProject}
                onAsset={() => setLibraryRevision((x) => x + 1)}
                onGenerate={(target, prompt) =>
                  void sceneGenerate(target, prompt)
                }
              />
            ) : mode === "economics" ? (
              <EconomicsPanel
                projectId={projectId}
                revision={libraryRevision}
              />
            ) : mode === "styles" ? (
              <section className="panel">
                <div className="panel-title">
                  <h2>Библия мира / Style Library</h2>
                  <Palette size={22} />
                </div>
                <p className="muted">
                  Единый стиль сохраняется вместе с проектом. Это канон
                  визуального мира, а не случайный пресет. Применяй его при
                  постановке задач агентам и проверке результатов.
                </p>
                {(
                  [
                    ["look", "Визуальный стиль"],
                    ["palette", "Палитра"],
                    ["lighting", "Освещение"],
                    ["camera", "Камера и оптика"],
                    ["environment", "Среда и локации"],
                    ["rules", "Неизменные правила"],
                    ["avoid", "Что запрещено"],
                  ] as [keyof StyleBible, string][]
                ).map(([k, label]) => (
                  <label key={k}>
                    {label}
                    <textarea
                      rows={3}
                      value={state.style?.[k] || ""}
                      onChange={(e) =>
                        change({
                          style: { ...state.style, [k]: e.target.value },
                        })
                      }
                    />
                  </label>
                ))}
                <button className="primary" disabled={!!busy} onClick={save}>
                  Сохранить стиль проекта
                </button>
                <p className="muted">
                  Для «Таксиста Грэма» добавляй утверждённые референсы в
                  Character Vault. Библия мира не заменяет проверку изображений
                  человеком.
                </p>
              </section>
            ) : mode === "create" ? (
              <CreateScreen
                projectId={projectId}
                heroes={state.characters.map((c) => ({
                  id: c.id,
                  name: c.name,
                }))}
              />
            ) : mode === "studio" ? (
              <>
                <section className="panel">
                  <h2>Задание ролика</h2>
                  <label>
                    Режиссёрское задание
                    <textarea
                      rows={4}
                      value={state.brief}
                      onChange={(e) => change({ brief: e.target.value })}
                    />
                  </label>
                  <button onClick={() => setMode("scene")}>
                    Собрать сцену из исходников →
                  </button>
                </section>
                <section className="panel photo-setup" aria-label="Фото">
                  <h2>Фото · постановка и промпт</h2>
                  <FrameSelector
                    catalogue={frameCatalogue}
                    value={state.composition}
                    onChange={chooseComposition}
                    onCatalogue={() => setCatalogue("frame")}
                  />
                  {frameError && <p role="alert">{frameError}</p>}
                  <ChatGPTPanel
                    {...replacementControls}
                    projectId={projectId}
                    ensureProject={ensureProject}
                    onPrompt={(prompt, target, _movement, frame) =>
                      setState((s) => ({
                        ...s,
                        prompts: { ...s.prompts, [target]: prompt },
                        compositionPromptBasis: {
                          ...s.compositionPromptBasis,
                          [target]: frameBasis(frame),
                        },
                      }))
                    }
                    onAsset={() => setLibraryRevision((x) => x + 1)}
                  />
                </section>
                {modelPanel("video")}
                <section className="panel">
                  <div className="panel-title">
                    <h2>④ Audio Lab — референсы голоса</h2>
                    <Music size={19} />
                  </div>
                  <p className="muted">
                    Загрузи собственный или разрешённый медиафайл. Сервис
                    предлагает фрагменты по паузам, затем ты вручную выбираешь
                    лучший дубль. Экспорт WAV подходит для дальнейшей загрузки в
                    разрешённый сервис озвучки.
                  </p>
                  <label className="upload-area">
                    <Upload size={18} /> Импорт MP3 / WAV / MP4 / MOV / WEBM (до
                    100 МБ)
                    <input
                      type="file"
                      accept="audio/*,video/mp4,video/quicktime,video/webm,.mkv"
                      onChange={(e) =>
                        e.target.files?.[0] && uploadAudio(e.target.files[0])
                      }
                    />
                  </label>
                  {audioFile && (
                    <>
                      <audio src={audioFile} controls />
                      <div className="audio-actions">
                        <button
                          className="secondary"
                          disabled={!!busy}
                          onClick={analyzeAudio}
                        >
                          Найти интервалы по паузам
                        </button>
                        <span className="muted">
                          Длительность: {audioDuration.toFixed(1)} сек.
                        </span>
                      </div>
                      {audioSegments.length > 0 && (
                        <div className="chips">
                          {audioSegments.map((s, i) => (
                            <button
                              key={i}
                              className="secondary"
                              onClick={() => {
                                setAudioStart(s.start);
                                setAudioEnd(s.end);
                              }}
                            >
                              {s.start}–{s.end} c
                            </button>
                          ))}
                        </div>
                      )}
                      <div className="param-grid">
                        <label>
                          От (сек)
                          <input
                            type="number"
                            min="0"
                            step="0.1"
                            value={audioStart}
                            onChange={(e) =>
                              setAudioStart(Number(e.target.value))
                            }
                          />
                        </label>
                        <label>
                          До (сек)
                          <input
                            type="number"
                            min="0"
                            step="0.1"
                            value={audioEnd}
                            onChange={(e) =>
                              setAudioEnd(Number(e.target.value))
                            }
                          />
                        </label>
                        <label className="inline-checkbox">
                          <input
                            type="checkbox"
                            checked={denoise}
                            onChange={(e) => setDenoise(e.target.checked)}
                          />{" "}
                          Лёгкая очистка
                        </label>
                      </div>
                      <label className="inline-checkbox">
                        <input
                          type="checkbox"
                          checked={audioConsent}
                          onChange={(e) => setAudioConsent(e.target.checked)}
                        />{" "}
                        Подтверждаю права на использование голоса и разрешение
                        на создание голосового референса
                      </label>
                      <button
                        className="primary"
                        disabled={!!busy || !audioConsent}
                        onClick={cutAudio}
                      >
                        ✂ Вырезать и подготовить WAV
                      </button>
                      {audioResult && (
                        <div className="audio-result">
                          <audio controls src={audioResult} />
                          <a href={audioResult} download>
                            Скачать подготовленный WAV ↓
                          </a>
                          <p className="muted">
                            Передавать в ElevenLabs/Fish Audio следует только
                            при соблюдении их правил и разрешений. Прямая
                            отправка API ещё не подключена.
                          </p>
                        </div>
                      )}
                    </>
                  )}
                </section>
                <section className="panel">
                  <h2>⑤ Очередь и галерея</h2>
                  <NativeGallery
                    {...replacementControls}
                    projectId={projectId}
                    onRefine={refineAsset}
                  />
                  <button className="secondary" onClick={refresh}>
                    <RefreshCw size={14} /> Обновить список
                  </button>
                  <div className="jobs">
                    {jobs.length === 0 ? (
                      <p className="muted">Задач через API пока нет.</p>
                    ) : (
                      jobs.map((j) => (
                        <div className="job" key={j.id}>
                          <div className="jobtop">
                            <b>
                              {j.kind} · {j.provider}
                            </b>
                            <span>{j.status}</span>
                            <button
                              onClick={() => poll(j.id)}
                              disabled={!!busy}
                            >
                              Проверить
                            </button>
                          </div>
                          <small>Task ID: {j.task_id || "—"}</small>
                          {j.delivery && (
                            <div>
                              <p>
                                {j.delivery.state === "saved"
                                  ? `Сохранено в библиотеке: ${j.delivery.saved}/${j.delivery.total}`
                                  : j.delivery.state === "retry"
                                    ? "Скачивание будет повторено автоматически"
                                    : "Требуется проверить скачивание"}
                              </p>
                              {j.delivery.error && (
                                <p role="alert">{j.delivery.error}</p>
                              )}
                              {j.delivery.state !== "saved" && (
                                <button
                                  disabled={!!busy}
                                  onClick={() =>
                                    work("retry-download", async () => {
                                      await json(
                                        await apiFetch(
                                          `/api/jobs/${j.id}/retry-download`,
                                          { method: "POST" },
                                        ),
                                      );
                                      setLibraryRevision((x) => x + 1);
                                      await refresh();
                                    })
                                  }
                                >
                                  Повторить скачивание без генерации
                                </button>
                              )}
                            </div>
                          )}
                          {j.provider === "piapi" &&
                            ["submission_unknown", "submitting"].includes(
                              j.status,
                            ) &&
                            !j.task_id && (
                              <RecoverJob
                                jobId={j.id}
                                onRecovered={() => void refresh()}
                              />
                            )}{" "}
                          {j.kind === "audio" && j.response?.asset_id && (
                            <div>
                              <audio
                                src={
                                  "/api/library/" +
                                  j.response.asset_id +
                                  "/file"
                                }
                                controls
                              />
                              <a
                                href={
                                  "/api/library/" +
                                  j.response.asset_id +
                                  "/file"
                                }
                                download
                              >
                                Скачать реплику
                              </a>
                            </div>
                          )}
                          <div className="results">
                            {extract(j).map((link, i) => (
                              <div key={i} className="result">
                                {j.kind === "video" ? (
                                  <video src={link} controls />
                                ) : (
                                  <img src={link} alt="Результат генерации" />
                                )}
                                <a href={link} target="_blank" rel="noreferrer">
                                  <Download size={13} /> Открыть
                                </a>
                                {j.status === "completed" && (
                                  <button
                                    disabled={!!busy}
                                    onClick={() => saveImage(j.id, i)}
                                  >
                                    Сохранить в библиотеку
                                  </button>
                                )}
                                {j.kind === "image" && (
                                  <button
                                    className="primary"
                                    onClick={() => {
                                      change({ videoReference: link });
                                      setSelectedJob(j.id);
                                      setNotice("Кадр передан в Video Lab");
                                    }}
                                  >
                                    Использовать для видео
                                  </button>
                                )}
                              </div>
                            ))}
                          </div>
                          {selectedJob === j.id && (
                            <small>Выбран для видео ✓</small>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </section>
                <AssetLibrary
                  {...replacementControls}
                  onRefine={refineAsset}
                  onScene={addToScene}
                  projectId={projectId}
                  revision={libraryRevision}
                  onUse={(link, id) => {
                    change({ videoReference: link, videoAssetId: id });
                    setNotice(
                      "Изображение из библиотеки выбрано для Video Lab",
                    );
                  }}
                />
              </>
            ) : (
              <Suspense fallback={<p>Открываем редактор узлов…</p>}>
                <GraphPanel
                  nodes={state.nodes}
                  edges={state.edges}
                  onChange={(update) =>
                    setState((s) => ({ ...s, ...update(s) }))
                  }
                />
              </Suspense>
            )}
            <footer>
              Workflow Studio · ChatGPT · сцены · экономика ролика
            </footer>
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
              <button
                className="primary"
                disabled={!!busy}
                onClick={() => void finishProjectChange(true)}
              >
                Сохранить и продолжить
              </button>
              <button
                disabled={!!busy}
                onClick={() => void finishProjectChange(false)}
              >
                Продолжить без сохранения
              </button>
              <button
                autoFocus
                disabled={!!busy}
                onClick={() => setPendingProjectChange(null)}
              >
                Остаться в проекте
              </button>
            </div>
          </section>
        </div>
      )}
      {catalogue && (
        <div
          className="modal-backdrop"
          onClick={(e) => {
            if (e.target === e.currentTarget) setCatalogue(null);
          }}
        >
          <section
            className="panel catalogue-dialog"
            role="dialog"
            aria-modal="true"
            aria-label={
              catalogue === "frame"
                ? "Каталог композиций фото"
                : "Каталог движений видео"
            }
            onKeyDown={(e) => {
              if (e.key === "Escape") setCatalogue(null);
            }}
          >
            <div className="catalogue-toolbar">
              <b>
                {catalogue === "frame"
                  ? "Фото / сцена · ракурс и свет"
                  : "Видео / сцена · движение камеры"}
              </b>
              <button autoFocus onClick={() => setCatalogue(null)}>
                Закрыть каталог
              </button>
            </div>
            {catalogue === "frame" ? (
              <FramePanel
                catalogue={frameCatalogue}
                value={state.composition}
                onChange={chooseComposition}
                onImage={() => setCatalogue(null)}
                error={frameError}
              />
            ) : (
              <CameraPanel
                setupEnabled={!!frameCatalogue.capabilities?.prompt_setup}
                presets={cameraPresets}
                value={state.camera}
                onChange={chooseCamera}
                onVideo={() => setCatalogue(null)}
                error={cameraError}
              />
            )}
          </section>
        </div>
      )}
      {promptRequest && (
        <PromptComposer
          request={promptRequest}
          onClose={() => setPromptRequest(null)}
          onComposed={(prompt) => {
            setState((s) => ({
              ...s,
              prompts: { ...s.prompts, [promptRequest.target]: prompt },
            }));
            setPromptRequest(null);
            setNotice(
              "Промпт подготовлен через API и сохранён в истории проекта",
            );
          }}
        />
      )}
      {generationRequest && (
        <GenerationReview
          request={generationRequest}
          onClose={() => setGenerationRequest(null)}
          onSubmitted={() => {
            setGenerationRequest(null);
            setNotice(
              "Заявка сохранена в очереди. Проверяй её статус перед повторным запуском.",
            );
            void refresh();
          }}
        />
      )}
    </div>
  );
}
export default App;
