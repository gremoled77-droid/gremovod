import {useEffect, useState, type ReactNode} from 'react';

export type Mode =
  | 'studio'
  | 'graph'
  | 'agents'
  | 'styles'
  | 'connections'
  | 'scene'
  | 'economics'
  | 'refine'
  | 'files'
  | 'settings'
  | 'storyboard'
  | 'create'
  | 'home'
  | 'video'
  | 'audio';

type Item = {key: string; mode: Mode; label: string; hint?: string; icon: ReactNode};

const STAGES: Item[] = [
  {key: 'idea', mode: 'studio', label: 'Идея', hint: 'задание ролика', icon: '1'},
  {key: 'world', mode: 'styles', label: 'Мир', hint: 'стиль и герои', icon: '2'},
  {key: 'board', mode: 'storyboard', label: 'Раскадровка', hint: 'кадры эпизода', icon: '3'},
  {key: 'frames', mode: 'create', label: 'Кадры', hint: 'картинки', icon: '4'},
  {key: 'video', mode: 'video', label: 'Видео', hint: 'оживление кадров', icon: '5'},
  {key: 'sound', mode: 'audio', label: 'Звук', hint: 'голос и обработка', icon: '6'},
  {key: 'edit', mode: 'files', label: 'Монтаж', hint: 'выгрузка в CapCut', icon: '7'},
  {key: 'release', mode: 'economics', label: 'Выпуск', hint: 'бюджет серии', icon: '8'},
];
const TOOLS: Item[] = [
  {key: 'graph', mode: 'graph', label: 'Узлы', icon: '⌁'},
  {key: 'scene', mode: 'scene', label: 'Сцена', icon: '▣'},
  {key: 'refine', mode: 'refine', label: 'Допилить', icon: '✎'},
  {key: 'agents', mode: 'agents', label: 'Агенты', icon: '☁'},
  {key: 'connections', mode: 'connections', label: 'Подключения', icon: '⚷'},
];

export default function StageNav({
  mode,
  onMode,
  onDemo,
}: {
  mode: Mode;
  onMode: (m: Mode) => void;
  onDemo: () => void;
}) {
  const [hidden, setHidden] = useState(false);
  // На телефоне нижняя панель уезжает вниз при прокрутке вниз и возвращается при прокрутке вверх.
  useEffect(() => {
    let last = window.scrollY;
    const onScroll = () => {
      const y = window.scrollY,
        delta = y - last;
      if (Math.abs(delta) < 8) return;
      last = y;
      const bottom = window.innerHeight + y >= document.documentElement.scrollHeight - 4;
      setHidden(delta > 0 && y > 80 && !bottom);
    };
    window.addEventListener('scroll', onScroll, {passive: true});
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  const activeStage = STAGES.find(s => s.mode === mode)?.key;
  const render = (item: Item, active: boolean) => (
    <button
      key={item.key}
      className={'nav-item' + (active ? ' nav-active' : '')}
      aria-current={active ? 'page' : undefined}
      onClick={() => onMode(item.mode)}
    >
      <span className="nav-icon" aria-hidden="true">
        {item.icon}
      </span>
      <span className="nav-text">
        <b>{item.label}</b>
        {item.hint && <small>{item.hint}</small>}
      </span>
    </button>
  );
  return (
    <nav
      className={'stage-nav' + (hidden ? ' nav-hidden' : '')}
      aria-label="Этапы ролика"
      onFocus={() => setHidden(false)}
    >
      <div className="nav-brand">
        <span className="nav-logo">◆</span>
        <div>
          <b>GremoVOD</b>
          <small>Studio</small>
        </div>
      </div>
      <button
        className={'nav-item' + (mode === 'home' ? ' nav-active' : '')}
        aria-current={mode === 'home' ? 'page' : undefined}
        onClick={() => onMode('home')}
      >
        <span className="nav-icon" aria-hidden="true">
          ⌂
        </span>
        <span className="nav-text">
          <b>Старт</b>
          <small>обзор проекта</small>
        </span>
      </button>
      <div className="nav-group-title">Эпизод</div>
      {STAGES.map(s => render(s, s.key === activeStage))}
      <div className="nav-group-title">Инструменты</div>
      {TOOLS.map(t => render(t, t.mode === mode))}
      <button className="nav-item nav-demo" onClick={onDemo}>
        <span className="nav-icon" aria-hidden="true">
          ▷
        </span>
        <span className="nav-text">
          <b>Раскадровка · демо</b>
        </span>
      </button>
    </nav>
  );
}
