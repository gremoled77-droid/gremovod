import {useEffect, useState} from 'react';
import {apiFetch} from './api';
import {useSharedActivity} from './ActivityContext';
import type {Mode} from './StageNav';

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
  {mode: 'studio', n: '5', title: 'Видео', text: 'Оживить кадры'},
  {mode: 'studio', n: '6', title: 'Звук', text: 'Голос и музыка'},
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
  const [images, setImages] = useState<{id: string; url: string; thumbnail_url: string | null}[]>([]);

  useEffect(() => {
    if (!projectId) return;
    void apiFetch('/api/budgets/' + encodeURIComponent(projectId))
      .then(r => (r.ok ? r.json() : null))
      .then(setBudget)
      .catch(() => undefined);
  }, [projectId, items.length]);
  useEffect(() => {
    if (!projectId) return;
    void apiFetch('/api/library?project_id=' + encodeURIComponent(projectId))
      .then(r => (r.ok ? r.json() : []))
      .then(list => setImages(list.filter((a: any) => (a.metadata?.kind || 'image') === 'image').slice(0, 8)))
      .catch(() => undefined);
  }, [projectId, items.length]);

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
  const pct = (a: number | undefined, b: number | undefined) =>
    b ? Math.min(100, Math.round(((a ?? 0) / b) * 100)) : 0;

  return (
    <section className="home">
      <div className="home-hero">
        <div>
          <div className="muted">GremoVOD Studio</div>
          <h1>{projectName || 'Новый проект'}</h1>
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
        <button className="primary home-next" onClick={() => onMode(next.mode)}>
          <small>Дальше</small>
          {next.text} →
        </button>
      </div>

      <div className="home-grid">
        <div className="home-col">
          <h2>Путь ролика</h2>
          <div className="home-steps">
            {STEPS.map(s => (
              <button key={s.n + s.title} className="home-step" onClick={() => onMode(s.mode)}>
                <span className="home-n">{s.n}</span>
                <span>
                  <b>{s.title}</b>
                  <small>{s.text}</small>
                </span>
              </button>
            ))}
          </div>

          <h2>Последние картинки</h2>
          <div className="home-thumbs">
            {images.map(a => (
              <button key={a.id} onClick={() => onMode('create')} aria-label="Открыть «Кадры»">
                <img src={a.thumbnail_url || a.url} alt="" />
              </button>
            ))}
            {!images.length && <span className="muted">Пока нет. Начни на экране «Кадры».</span>}
          </div>
        </div>

        <aside className="home-col">
          <h2>Сейчас</h2>
          <div className="home-card">
            {latest.map(i => (
              <div key={i.id} className="home-job">
                <span
                  className={'dot ' + (i.status === 'failed' ? 'bad' : waiting.includes(i) ? 'warn' : '')}
                />
                <span className="home-job-text">
                  <b>{i.model || i.provider}</b>
                  <small>{i.prompt.slice(0, 48)}</small>
                </span>
                <em>{STATUS[i.status] || i.status}</em>
              </div>
            ))}
            {!latest.length && <span className="muted">Заданий пока нет</span>}
          </div>

          <h2>Расход</h2>
          <div className="home-card">
            <div className="home-meter">
              <div>
                <span>Сегодня</span>
                <b>
                  {money(budget?.daily_reserved_usd)} / {money(budget?.daily_limit_usd)}
                </b>
              </div>
              <i>
                <u style={{width: pct(budget?.daily_reserved_usd, budget?.daily_limit_usd) + '%'}} />
              </i>
            </div>
            <div className="home-meter">
              <div>
                <span>Проект</span>
                <b>
                  {money(budget?.project_reserved_usd)} / {money(budget?.project_limit_usd)}
                </b>
              </div>
              <i>
                <u style={{width: pct(budget?.project_reserved_usd, budget?.project_limit_usd) + '%'}} />
              </i>
            </div>
            <button onClick={() => onMode('economics')}>Бюджет и лимиты</button>
          </div>

          <h2>Быстро</h2>
          <div className="home-quick">
            <button onClick={() => onMode('create')}>Сгенерировать кадр</button>
            <button onClick={() => onMode('graph')}>Открыть узлы</button>
            <button onClick={() => onMode('connections')}>Подключения API</button>
          </div>
        </aside>
      </div>
    </section>
  );
}
