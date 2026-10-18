import {useEffect, useState} from 'react';
import {STAGES, TOOLS, navMode, type Mode, type Screen} from './screens';

export type {Mode} from './screens';

/** Нижние вкладки на телефоне: пять частых разделов и «Ещё». */
const TABS: {mode: Mode; label: string; icon: string}[] = [
  {mode: 'create', label: 'Кадры', icon: '✦'},
  {mode: 'storyboard', label: 'Сцены', icon: '▦'},
  {mode: 'styles', label: 'Мир', icon: '☺'},
  {mode: 'video', label: 'Видео', icon: '▶'},
  {mode: 'archive', label: 'Архив', icon: '▤'},
];

export default function StageNav({mode, onMode}: {mode: Mode; onMode: (m: Mode) => void}) {
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
  const current = navMode(mode);
  const render = (item: Screen) => (
    <button
      key={item.mode}
      className={'nav-item' + (item.mode === current ? ' nav-active' : '')}
      aria-current={item.mode === current ? 'page' : undefined}
      onClick={() => onMode(item.mode)}
    >
      <span className="nav-icon" aria-hidden="true">
        {item.icon}
      </span>
      <span className="nav-text">
        <b>{item.title}</b>
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
        {STAGES.map(render)}
        <div className="nav-group-title">Инструменты</div>
        {TOOLS.map(render)}
      </nav>
      <nav className={'mobile-tabs' + (hidden ? ' nav-hidden' : '')} aria-label="Быстрые разделы">
        {TABS.map(t => (
          <button
            key={t.mode}
            className={'mobile-tab' + (current === t.mode ? ' on' : '')}
            aria-current={current === t.mode ? 'page' : undefined}
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
                <button key={s.mode} className={current === s.mode ? 'on' : ''} onClick={() => go(s.mode)}>
                  {s.icon}. {s.title}
                </button>
              ))}
            </div>
            <b>Инструменты</b>
            <div className="mobile-sheet-grid">
              {TOOLS.map(t => (
                <button key={t.mode} className={mode === t.mode ? 'on' : ''} onClick={() => go(t.mode)}>
                  {t.icon} {t.title}
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
