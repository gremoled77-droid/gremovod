import {useEffect, useState, type ReactNode} from 'react';

export type Mode =
  | 'studio'
  | 'graph'
  | 'agents'
  | 'styles'
  | 'characters'
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
  | 'audio'
  | 'reels'
  | 'archive';

/** Пять категорий этапов (цвет = категория, как у GSAP): придумать, кадры, видео, звук, выпуск. */
export type Hue = 'lilac' | 'pink' | 'orange' | 'blue' | 'green';
type Item = {key: string; mode: Mode; label: string; hint?: string; icon: ReactNode; hue?: Hue};

export const STAGES: Item[] = [
  {key: 'idea', mode: 'studio', label: 'Идея', hint: 'задание ролика', icon: '1', hue: 'lilac'},
  {key: 'world', mode: 'styles', label: 'Мир', hint: 'стиль и герои', icon: '2', hue: 'lilac'},
  {key: 'chars', mode: 'characters', label: 'Персонажи', hint: 'герои и образы', icon: '3', hue: 'lilac'},
  {key: 'board', mode: 'storyboard', label: 'Раскадровка', hint: 'кадры эпизода', icon: '4', hue: 'lilac'},
  {key: 'frames', mode: 'create', label: 'Кадры', hint: 'картинки', icon: '5', hue: 'pink'},
  {key: 'video', mode: 'video', label: 'Видео', hint: 'оживление кадров', icon: '6', hue: 'orange'},
  {key: 'sound', mode: 'audio', label: 'Звук', hint: 'голос и обработка', icon: '7', hue: 'blue'},
  {key: 'edit', mode: 'files', label: 'Монтаж', hint: 'выгрузка в CapCut', icon: '8', hue: 'green'},
  {key: 'release', mode: 'economics', label: 'Выпуск', hint: 'бюджет серии', icon: '9', hue: 'green'},
];
/** Нижние вкладки на телефоне (макет Mobile): пять частых действий и «Ещё». */
const TABS: {mode: Mode; label: string; icon: string}[] = [
  {mode: 'create', label: 'Создать', icon: '✦'},
  {mode: 'storyboard', label: 'Сцены', icon: '▦'},
  {mode: 'characters', label: 'Герои', icon: '☺'},
  {mode: 'archive', label: 'Архив', icon: '▤'},
  {mode: 'economics', label: 'Бюджет', icon: '$'},
];
const TOOLS: Item[] = [
  {key: 'reels', mode: 'reels', label: 'Рилсы', hint: 'рецепты сценариев', icon: '▶'},
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
  const [more, setMore] = useState(false);
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
      data-hue={item.hue}
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
  const go = (m: Mode) => {
    setMore(false);
    onMode(m);
  };
  return (
    <>
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
      <nav className={'mobile-tabs' + (hidden ? ' nav-hidden' : '')} aria-label="Быстрые разделы">
        {TABS.map(t => (
          <button
            key={t.mode}
            className={'mobile-tab' + (mode === t.mode ? ' on' : '')}
            aria-current={mode === t.mode ? 'page' : undefined}
            onClick={() => go(t.mode)}
          >
            <span aria-hidden="true">{t.icon}</span>
            {t.label}
          </button>
        ))}
        <button
          className={'mobile-tab' + (more ? ' on' : '')}
          aria-expanded={more}
          onClick={() => setMore(v => !v)}
        >
          <span aria-hidden="true">⋯</span>
          Ещё
        </button>
      </nav>
      {more && (
        <div className="mobile-sheet-backdrop" onClick={() => setMore(false)}>
          <div
            className="mobile-sheet"
            role="dialog"
            aria-label="Все разделы"
            onClick={e => e.stopPropagation()}
          >
            <b>Этапы ролика</b>
            <div className="mobile-sheet-grid">
              <button className={mode === 'home' ? 'on' : ''} onClick={() => go('home')}>
                ⌂ Старт
              </button>
              {STAGES.map(s => (
                <button key={s.key} className={mode === s.mode ? 'on' : ''} onClick={() => go(s.mode)}>
                  {s.icon}. {s.label}
                </button>
              ))}
            </div>
            <b>Инструменты</b>
            <div className="mobile-sheet-grid">
              {TOOLS.map(t => (
                <button key={t.key} className={mode === t.mode ? 'on' : ''} onClick={() => go(t.mode)}>
                  {t.icon} {t.label}
                </button>
              ))}
              <button className={mode === 'settings' ? 'on' : ''} onClick={() => go('settings')}>
                ⚙ Настройки
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
