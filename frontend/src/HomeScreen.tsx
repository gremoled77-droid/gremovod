import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {useSharedActivity} from './ActivityContext';
import type {Mode} from './StageNav';
import Lightbox from './Lightbox';

type Budget = {
  project_limit_usd: number;
  daily_limit_usd: number;
  project_reserved_usd: number;
  daily_reserved_usd: number;
};
type Project = {id: string; title: string};

const STEPS: {mode: Mode; n: string; title: string; text: string}[] = [
  {mode: 'studio', n: '1', title: 'Идея', text: 'Задание ролика, шутка, сюжет'},
  {mode: 'styles', n: '2', title: 'Мир', text: 'Стиль, герои, локации'},
  {mode: 'storyboard', n: '3', title: 'Раскадровка', text: 'Сцены и кадры эпизода'},
  {mode: 'create', n: '4', title: 'Кадры', text: 'Картинки от нескольких моделей'},
  {mode: 'video', n: '5', title: 'Видео', text: 'Оживить кадры'},
  {mode: 'audio', n: '6', title: 'Звук', text: 'Голос и музыка'},
  {mode: 'files', n: '7', title: 'Монтаж', text: 'Выгрузка в CapCut по порядку кадров'},
  {mode: 'economics', n: '8', title: 'Выпуск', text: 'Бюджет серии и итоги'},
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
  const [images, setImages] = useState<{id: string; url: string; thumbnail_url: string | null}[]>([]);

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
      .then(list => setImages(list.filter((a: any) => (a.metadata?.kind || 'image') === 'image').slice(0, 8)))
      .catch(() => undefined);
  }, [projectId, items]);

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
                <small>ЭТАПОВ</small>8
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
            {projects.length > 1 && (
              <select value={projectId} onChange={e => onOpenProject(e.target.value)} aria-label="Проект">
                {projects.map(p => (
                  <option key={p.id} value={p.id}>
                    {p.title}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>
        <button className="home-cta" onClick={() => onMode(next.mode)}>
          <span className="home-cta-k">NEXT TAKE</span>
          <span className="home-cta-t">{next.text}</span>
          <span className="home-cta-a" aria-hidden="true">
            →
          </span>
        </button>
      </header>

      <div className="home-film" aria-label="Последние кадры">
        <div className="home-perf" aria-hidden="true" />
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
          items={images.slice(0, 6).map((a, i) => ({url: a.url, title: 'Кадр ' + (i + 1)}))}
          index={view}
          onIndex={setView}
          onClose={() => setView(-1)}
        />
      )}
    </section>
  );
}
