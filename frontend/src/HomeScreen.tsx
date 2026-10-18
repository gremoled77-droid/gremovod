import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {useSharedActivity} from './ActivityContext';
import {screenOf, type Mode} from './screens';
import {lastStage} from './lastStage';
import Lightbox from './Lightbox';
import {loadCreateDraft, saveCreateDraft} from './createDraft';
import {onLibraryChanged, trashAsset as trashToBin} from './studioEvents';

type Budget = {
  project_limit_usd: number;
  daily_limit_usd: number;
  project_reserved_usd: number;
  daily_reserved_usd: number;
};
type Project = {id: string; title: string};
type Media = {
  id: string;
  url: string;
  thumbnail_url: string | null;
  filename?: string;
  metadata?: {kind?: string; original_name?: string; width?: number; height?: number; favorite?: boolean};
};
type Cost = {actual_usd?: number | null; estimated_usd?: number | null};
type Reel = 'video' | 'image';
const REELS: {id: Reel; label: string}[] = [
  {id: 'video', label: 'Видео'},
  {id: 'image', label: 'Кадры'},
];

const STEPS: {mode: Mode; n: string; title: string; text: string}[] = [
  {mode: 'studio', n: '1', title: 'Идея', text: 'Задание ролика, шутка, сюжет'},
  {mode: 'styles', n: '2', title: 'Мир', text: 'Стиль, герои, локации'},
  {mode: 'storyboard', n: '3', title: 'Раскадровка', text: 'Сцены и кадры эпизода'},
  {mode: 'create', n: '4', title: 'Кадры', text: 'Картинки от нескольких моделей'},
  {mode: 'video', n: '5', title: 'Видео', text: 'Оживить кадры'},
  {mode: 'audio', n: '6', title: 'Звук', text: 'Голоса и звук кадров'},
  {mode: 'files', n: '7', title: 'Монтаж', text: 'Выгрузка в CapCut'},
  {mode: 'economics', n: '8', title: 'Выпуск', text: 'Бюджет и итоги серии'},
];

const money = (v: number | undefined) => '$' + (v ?? 0).toFixed(2);
const STATUS: Record<string, string> = {
  completed: 'готово',
  succeeded: 'готово',
  failed: 'ошибка',
  waiting_external: 'ждёт ChatGPT',
  queued: 'в очереди',
  running: 'в работе',
  processing: 'в работе',
};

export default function HomeScreen({
  projectId,
  projectName,
  projects,
  onMode,
  onOpenProject,
  onNewProject,
}: {
  projectId: string;
  projectName: string;
  projects: Project[];
  onMode: (m: Mode) => void;
  /** Открыть другой проект на его последнем этапе. */
  onOpenProject: (id: string, mode: Mode) => void;
  /** Создать проект с названием и открыть его «Идею». */
  onNewProject: (title: string) => void;
}) {
  const [newTitle, setNewTitle] = useState('');
  const {items} = useSharedActivity();
  const [budget, setBudget] = useState<Budget | null>(null);
  const [view, setView] = useState(-1);
  const [images, setImages] = useState<Media[]>([]);
  const [refIds, setRefIds] = useState<string[]>(() => loadCreateDraft(projectId).refs);
  const [clips, setClips] = useState<Media[]>([]);
  const [reel, setReel] = useState<Reel>('image');
  const [playing, setPlaying] = useState('');
  const [costs, setCosts] = useState<Record<string, Cost>>({});

  useEffect(() => {
    if (!projectId) return;
    void apiFetch('/api/budgets/' + encodeURIComponent(projectId))
      .then(r => (r.ok ? r.json() : null))
      .then(setBudget)
      .catch(() => undefined);
  }, [projectId, items]);
  const [libraryTick, setLibraryTick] = useState(0);
  useEffect(() => onLibraryChanged(() => setLibraryTick(t => t + 1)), []);
  useEffect(() => {
    if (!projectId) return;
    void apiFetch('/api/library?project_id=' + encodeURIComponent(projectId))
      .then(r => (r.ok ? r.json() : []))
      .then((list: Media[]) => {
        const of = (kind: string) => list.filter(a => (a.metadata?.kind || 'image') === kind);
        setImages(of('image').slice(0, 8));
        setClips(of('video').slice(0, 12));
      })
      .catch(() => undefined);
  }, [projectId, items, libraryTick]);

  useEffect(() => {
    if (!projectId) return;
    void apiFetch('/api/economics?project_id=' + encodeURIComponent(projectId))
      .then(r => (r.ok ? r.json() : null))
      .then(d => {
        const map: Record<string, Cost> = {};
        for (const a of d?.jobs || []) map[a.id] = a;
        setCosts(map);
      })
      .catch(() => undefined);
  }, [projectId, items]);

  const captionOf = (a: Media) => {
    const job = items.find(i => i.asset_ids.includes(a.id));
    const cost = job ? costs[job.id] : undefined;
    const usd =
      cost?.actual_usd ?? cost?.estimated_usd ?? (job && !job.provider.startsWith('piapi') ? 0 : null);
    const size = a.metadata?.width && a.metadata?.height ? `${a.metadata.width}×${a.metadata.height}` : '';
    const cents = usd === null || usd === undefined ? '' : `${(usd * 100).toFixed(usd * 100 < 10 ? 1 : 0)} ¢`;
    return [job?.model, size, cents].filter(Boolean).join(' · ');
  };
  /** «Редактировать»: кадр уходит в «Кадры» уже прикреплённым референсом для правки через ChatGPT. */
  const editAsset = (a: Media) => {
    const draft = loadCreateDraft(projectId);
    saveCreateDraft(projectId, {
      ...draft,
      refs: [a.id, ...draft.refs.filter(id => id !== a.id)],
      selected: ['gpt-image-2.5'],
      prompt: 'Отредактируй изображение: ',
    });
    setView(-1);
    onMode('create');
  };
  const toggleFavorite = async (a: Media) => {
    const on = !a.metadata?.favorite;
    const r = await apiFetch(`/api/library/${a.id}/favorite`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({favorite: on}),
    });
    if (!r.ok) return window.alert('Не удалось изменить избранное');
    setImages(list => list.map(x => (x.id === a.id ? {...x, metadata: {...x.metadata, favorite: on}} : x)));
  };
  /** «В референсы»: кадр добавляется в черновик «Кадров» (или убирается оттуда). */
  const toggleRef = (a: Media) => {
    const draft = loadCreateDraft(projectId);
    const on = draft.refs.includes(a.id);
    saveCreateDraft(projectId, {
      ...draft,
      refs: on ? draft.refs.filter(id => id !== a.id) : [...draft.refs, a.id],
    });
    setRefIds(ids => (on ? ids.filter(id => id !== a.id) : [...ids, a.id]));
  };
  const trashAsset = async (a: Media) => {
    if (!(await trashToBin(a.id))) return;
    setView(-1);
    setImages(list => list.filter(x => x.id !== a.id));
  };

  const waiting = items.filter(i => i.status === 'waiting_external');
  const active = items.filter(i => ['queued', 'running', 'processing'].includes(i.status));
  const latest = items.slice(0, 6);
  const next = waiting.length
    ? {mode: 'create' as Mode, text: `Вернуть результат из ChatGPT (${waiting.length})`}
    : active.length
      ? {mode: 'create' as Mode, text: `Дождаться заданий: ${active.length} в работе`}
      : images.length
        ? {mode: 'create' as Mode, text: 'Дальше: выбрать главный дубль и оживить кадр'}
        : {mode: 'studio' as Mode, text: 'Начать с идеи ролика'};

  const resume = projectId ? lastStage(projectId) : 'studio';
  const others = projects.filter(p => p.id !== projectId).slice(0, 6);
  const videos = items.filter(i => i.kind === 'video' && i.asset_ids.length).length;
  const stageMeta: Record<string, string> = {
    '4': images.length ? `${images.length}+ картинок` : '',
    '5': videos ? `${videos} клипов` : '',
  };
  const nextN = next.mode === 'create' ? '4' : '1';
  const Gauge = ({label, used, limit}: {label: string; used?: number; limit?: number}) => {
    const p = limit ? Math.min(1, (used ?? 0) / limit) : 0;
    const R = 34;
    const C = 2 * Math.PI * R;
    return (
      <div className="hg">
        <svg viewBox="0 0 84 84" aria-hidden="true">
          <circle cx="42" cy="42" r={R} className="hg-bg" />
          <circle
            cx="42"
            cy="42"
            r={R}
            className="hg-fg"
            strokeDasharray={`${C * p} ${C}`}
            transform="rotate(-90 42 42)"
          />
        </svg>
        <div className="hg-t">
          <b>{money(used)}</b>
          <small>из {money(limit)}</small>
        </div>
        <span>{label}</span>
      </div>
    );
  };

  return (
    <section className="home">
      <div className="home-glow" aria-hidden="true" />
      <header className="home-hero">
        <div className="home-slate">
          <div className="home-slate-bar" aria-hidden="true">
            {Array.from({length: 8}).map((_, i) => (
              <i key={i} />
            ))}
          </div>
          <div className="home-slate-body">
            <span className="home-eyebrow">GREMOVOD STUDIO · AI ANIMATION PIPELINE</span>
            <h1>{projectName || 'Новый проект'}</h1>
            <div className="home-meta">
              <span>
                <small>ЭТАПОВ</small>
                {STEPS.length}
              </span>
              <span>
                <small>КАДРОВ</small>
                {images.length}+
              </span>
              <span>
                <small>В РАБОТЕ</small>
                {active.length + waiting.length}
              </span>
              <span>
                <small>СЕГОДНЯ</small>
                {money(budget?.daily_reserved_usd)}
              </span>
            </div>
            <div className="home-continue">
              <button className="primary home-go" onClick={() => onMode(resume)}>
                {projectId ? `Продолжить: ${screenOf(resume).title}` : 'Начать с идеи'} →
              </button>
              {projectId && (
                <button className="home-hint" onClick={() => onMode(next.mode)}>
                  {next.text}
                </button>
              )}
            </div>
          </div>
        </div>
        <aside className="home-projects" aria-label="Проекты">
          <form
            className="home-new"
            onSubmit={e => {
              e.preventDefault();
              if (newTitle.trim()) onNewProject(newTitle.trim());
            }}
          >
            <input
              id="home-new-title"
              value={newTitle}
              placeholder="Название нового проекта"
              aria-label="Название нового проекта"
              onChange={e => setNewTitle(e.target.value)}
            />
            <button className="primary" disabled={!newTitle.trim()}>
              ＋ Новый проект
            </button>
          </form>
          {others.length > 0 && (
            <>
              <span className="home-eyebrow">ДРУГИЕ ПРОЕКТЫ</span>
              <ul>
                {others.map(p => {
                  const stage = lastStage(p.id);
                  return (
                    <li key={p.id}>
                      <button onClick={() => onOpenProject(p.id, stage)}>
                        <b>{p.title}</b>
                        <small>{screenOf(stage).title} →</small>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </aside>
      </header>

      <div className="home-film" aria-label="Плёнка проекта">
        <div className="home-reels" role="tablist" aria-label="Что показать на плёнке">
          {REELS.map(r => (
            <button
              key={r.id}
              role="tab"
              aria-selected={reel === r.id}
              className={reel === r.id ? 'on' : ''}
              onClick={() => {
                setReel(r.id);
                setPlaying('');
              }}
            >
              {r.label}
              <em>{r.id === 'video' ? clips.length : images.length}</em>
            </button>
          ))}
        </div>
        <div className="home-perf" aria-hidden="true" />
        {reel === 'image' && (
          <div className="home-frames">
            {images.slice(0, 6).map((a, i) => (
              <button key={a.id} onClick={() => setView(i)} aria-label={'Открыть кадр ' + (i + 1)}>
                <img src={a.thumbnail_url || a.url} alt="" />
                <span>{String(i + 1).padStart(2, '0')}</span>
              </button>
            ))}
            {!images.length && (
              <div className="home-frames-empty">Плёнка пуста. Первый кадр рождается на экране «Кадры».</div>
            )}
          </div>
        )}
        {reel === 'video' && (
          <div className="home-frames">
            {clips.map((a, i) => (
              <div key={a.id} className="home-clip">
                <video
                  src={a.url}
                  controls={playing === a.id}
                  autoPlay={playing === a.id}
                  preload="metadata"
                  playsInline
                />
                {playing !== a.id && (
                  <button
                    className="home-play"
                    aria-label={'Играть клип ' + (i + 1)}
                    onClick={() => setPlaying(a.id)}
                  >
                    ▶
                  </button>
                )}
                <span>{String(i + 1).padStart(2, '0')}</span>
              </div>
            ))}
            {!clips.length && (
              <div className="home-frames-empty">Клипов пока нет. Оживи кадр на экране «Видео».</div>
            )}
          </div>
        )}
        <div className="home-perf" aria-hidden="true" />
      </div>

      <div className="home-grid">
        <div className="home-col">
          <h2>
            <i /> Конвейер ролика
          </h2>
          <ol className="home-track">
            {STEPS.map(s => (
              <li key={s.n + s.title} className={s.n === nextN ? 'now' : ''}>
                <button onClick={() => onMode(s.mode)}>
                  <span className="home-n">{s.n}</span>
                  <span className="home-st">
                    <b>{s.title}</b>
                    <small>{s.text}</small>
                    {stageMeta[s.n] && <em>{stageMeta[s.n]}</em>}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </div>

        <aside className="home-col">
          <h2>
            <i /> Очередь рендера
          </h2>
          <div className="home-card">
            {latest.map(i => {
              const live = ['queued', 'running', 'processing'].includes(i.status);
              return (
                <div key={i.id} className={'home-job' + (live ? ' live' : '')}>
                  <span
                    className={'dot ' + (i.status === 'failed' ? 'bad' : waiting.includes(i) ? 'warn' : '')}
                  />
                  <span className="home-job-text">
                    <b>{i.model || i.provider}</b>
                    <small>{i.prompt.slice(0, 48)}</small>
                  </span>
                  <em>{STATUS[i.status] || i.status}</em>
                </div>
              );
            })}
            {!latest.length && <span className="muted">Заданий пока нет</span>}
          </div>

          <h2>
            <i /> Бюджет
          </h2>
          <div className="home-card home-gauges">
            <Gauge label="Сегодня" used={budget?.daily_reserved_usd} limit={budget?.daily_limit_usd} />
            <Gauge label="Проект" used={budget?.project_reserved_usd} limit={budget?.project_limit_usd} />
            <button onClick={() => onMode('settings')}>Лимиты</button>
          </div>
        </aside>
      </div>
      {view >= 0 && (
        <Lightbox
          items={images.slice(0, 6).map((a, i) => ({
            url: a.url,
            title: 'Кадр ' + (i + 1),
            caption: captionOf(a),
            favorite: !!a.metadata?.favorite,
            onFavorite: () => void toggleFavorite(a),
            onEdit: () => editAsset(a),
            onRef: () => toggleRef(a),
            refActive: refIds.includes(a.id),
            downloadName: a.filename,
            onTrash: () => void trashAsset(a),
          }))}
          index={view}
          onIndex={setView}
          onClose={() => setView(-1)}
        />
      )}
    </section>
  );
}
