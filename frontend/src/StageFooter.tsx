import {STAGES, navMode, type Mode} from './screens';

/** Нижняя полоса этапа: куда вернуться и что делать дальше. Связывает экраны в один конвейер. */
export default function StageFooter({mode, onMode}: {mode: Mode; onMode: (m: Mode) => void}) {
  const index = STAGES.findIndex(s => s.mode === navMode(mode));
  if (index < 0) return null;
  const prev = STAGES[index - 1];
  const next = STAGES[index + 1];
  return (
    <nav className="stage-footer" aria-label="Переход между этапами">
      {prev ? (
        <button className="stage-footer-prev" onClick={() => onMode(prev.mode)}>
          <small>Назад</small>
          <b>← {prev.title}</b>
        </button>
      ) : (
        <span />
      )}
      <span className="stage-footer-step">
        Этап {index + 1} из {STAGES.length} · {STAGES[index].title}
      </span>
      {next ? (
        <button className="primary stage-footer-next" onClick={() => onMode(next.mode)}>
          <small>Дальше · {next.hint}</small>
          <b>{next.title} →</b>
        </button>
      ) : (
        <button className="stage-footer-next" onClick={() => onMode('home')}>
          <small>Кадры, видео и звук готовы</small>
          <b>К обзору проекта</b>
        </button>
      )}
    </nav>
  );
}
