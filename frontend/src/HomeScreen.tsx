import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {useSharedActivity} from './ActivityContext';
import type {Mode} from './StageNav';
import Lightbox from './Lightbox';
import {loadCreateDraft, saveCreateDraft} from './createDraft';

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
type Reel = 'video' | 'image' | 'audio';
const REELS: {id: Reel; label: string}[] = [
  {id: 'video', label: 'Видео'},
  {id: 'image', label: 'Кадры'},
  {id: 'audio', label: 'Звук'},
];

/** Цвет этапа = категория: придумать, кадры, видео, звук, выпуск (по таксономии GSAP, пять цветов) */
type Hue = 'lilac' | 'pink' | 'orange' | 'blue' | 'green';
const STEPS: {mode: Mode; n: string; title: string; text: string; hue: Hue}[] = [
  {mode: 'studio', n: '1', title: 'Идея', text: 'Задание ролика, шутка, сюжет', hue: 'lilac'},
  {mode: 'styles', n: '2', title: 'Мир', text: 'Стиль, герои, локации', hue: 'lilac'},
  {mode: 'storyboard', n: '3', title: 'Раскадровка', text: 'Сцены и кадры эпизода', hue: 'lilac'},
  {mode: 'create', n: '4', title: 'Кадры', text: 'Картинки от нескольких моделей', hue: 'pink'},
  {mode: 'video', n: '5', title: 'Видео', text: 'Оживить кадры', hue: 'orange'},
  {mode: 'audio', n: '6', title: 'Звук', text: 'Голос и музыка', hue: 'blue'},
  {mode: 'files', n: '7', title: 'Монтаж', text: 'Выгрузка в CapCut по порядку кадров', hue: 'green'},
  {mode: 'economics', n: '8', title: 'Выпуск', text: 'Бюджет серии и итоги', hue: 'green'},
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
}: {
  projectId: string;
  projectName: string;
  projects: Project[];
  onMode: (m: Mode) => void;
  onOpenProject: (id: string) => void;
}) {
  const {items} = useSharedActivity();
  const [budget, setBudget] = useState<Budget | null>(null);
  const [view, setView] = useState(-1);
  const [images, setImages] = useState<Media[]>([]);
  const [refIds, setRefIds] = useState<string[]>(() => loadCreateDraft(projectId).refs);
  const [clips, setClips] = useState<Media[]>([]);
  const [sounds, setSounds] = useState<Media[]>([]);
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
  useEffect(() => {
    if (!projectId) return;
    void apiFetch('/api/library?project_id=' + encodeURIComponent(projectId))
      .then(r => (r.ok ? r.json() : []))
      .then((list: Media[]) => {
        const of = (kind: string) => list.filter(a => (a.metadata?.kind || 'image') === kind);
        setImages(of('image').slice(0, 8));
        setClips(of('video').slice(0, 12));
        setSounds(of('audio').slice(0, 12));
      })
      .catch(() => undefined);
  }, [projectId, items]);

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
    if (!window.confirm('Убрать кадр в корзину? Его можно вернуть в течение 30 дней.')) return;
    const r = await apiFetch(`/api/library/${a.id}/trash`, {method: 'POST'});
    if (!r.ok) return window.alert('Не удалось убрать: кадр используется в проекте или недоступен');
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
        ? {mode: 'create' as Mode, text: 'Продолжить: выбрать главный дубль и оживить кадр'}
        : {mode: 'studio' as Mode, text: 'Начать с идеи ролика'};

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
      <header className="home-hero">
        <span className="home-eyebrow">GremoVOD Studio</span>
        <h1>{projectName || 'Новый проект'}</h1>
        <div className="home-meta">
          <span>
            <small>Этапов</small>8
          </span>
          <span>
            <small>Кадров</small>
            {images.length}+
          </span>
          <span>
            <small>В работе</small>
            {active.length + waiting.length}
          </span>
          <span>
            <small>Сегодня</small>
            {money(budget?.daily_reserved_usd)}
          </span>
        </div>
        {projects.length > 1 && (
          <select value={projectId} onChange={e => onOpenProject(e.target.value)} aria-label="Проект">
            {projects.map(p => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        )}
        <div className="home-next">
          <span className="home-eyebrow">Следующий шаг</span>
          <p>{next.text}</p>
          <button className="home-cta" onClick={() => onMode(next.mode)}>
            Продолжить <span aria-hidden="true">→</span>
          </button>
        </div>
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
              <em>{r.id === 'video' ? clips.length : r.id === 'audio' ? sounds.length : images.length}</em>
            </button>
          ))}
        </div>
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
        {reel === 'audio' && (
          <div className="home-sounds">
            {sounds.map((a, i) => (
              <div key={a.id} className="home-sound">
                <span className="home-sound-n">{String(i + 1).padStart(2, '0')}</span>
                <b>{a.metadata?.original_name || 'Дорожка ' + (i + 1)}</b>
                <audio src={a.url} controls preload="none" />
              </div>
            ))}
            {!sounds.length && (
              <div className="home-frames-empty">
                Звука пока нет. Голос и музыка делаются на экране «Звук».
              </div>
            )}
          </div>
        )}
      </div>

      <div className="home-grid">
        <div className="home-col">
          <h2>Конвейер ролика</h2>
          <ol className="home-track">
            {STEPS.map(s => (
              <li key={s.n + s.title} className={s.n === nextN ? 'now' : ''} data-hue={s.hue}>
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
          <h2>Очередь рендера</h2>
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

          <h2>Бюджет</h2>
          <div className="home-card home-gauges">
            <Gauge label="Сегодня" used={budget?.daily_reserved_usd} limit={budget?.daily_limit_usd} />
            <Gauge label="Проект" used={budget?.project_reserved_usd} limit={budget?.project_limit_usd} />
            <button onClick={() => onMode('economics')}>Лимиты</button>
          </div>

          <div className="home-quick">
            <button onClick={() => onMode('create')}>Сгенерировать кадр</button>
            <button onClick={() => onMode('graph')}>Узлы</button>
            <button onClick={() => onMode('connections')}>API</button>
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
