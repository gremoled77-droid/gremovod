import {STAGES, type Mode} from './StageNav';

/** Нижняя полоса этапа: куда вернуться и что делать дальше. Связывает экраны в один конвейер. */
export default function StageFooter({mode, onMode}: {mode: Mode; onMode: (m: Mode) => void}) {
  const index = STAGES.findIndex(s => s.mode === mode);
  if (index < 0) return null;
  const prev = STAGES[index - 1];
  const next = STAGES[index + 1];
  return (
    <nav className="stage-footer" aria-label="Переход между этапами">
      {prev ? (
        <button className="stage-footer-prev" onClick={() => onMode(prev.mode)}>
          <small>Назад</small>
          <b>← {prev.label}</b>
        </button>
      ) : (
        <span />
      )}
      <span className="stage-footer-step">
        Этап {index + 1} из {STAGES.length} · {STAGES[index].label}
      </span>
      {next ? (
        <button className="primary stage-footer-next" onClick={() => onMode(next.mode)}>
          <small>Дальше · {next.hint}</small>
          <b>{next.label} →</b>
        </button>
      ) : (
        <button className="stage-footer-next" onClick={() => onMode('home')}>
          <small>Серия готова к выгрузке</small>
          <b>К обзору проекта</b>
        </button>
      )}
    </nav>
  );
}
