import {LIMIT_PRESETS, LIMIT_SLIDER_MAX, limitNeedsConfirm, presetLabel} from './spendLimit';

/** Выбор лимита: быстрые суммы, ползунок по доллару и точное поле. Выше $2 нужна отдельная галочка. */
export default function LimitPicker({
  total,
  limit,
  onLimit,
  highConfirmed,
  onHighConfirmed,
  disabled,
}: {
  total: number;
  limit: string;
  onLimit: (value: string) => void;
  highConfirmed: boolean;
  onHighConfirmed: (value: boolean) => void;
  disabled?: boolean;
}) {
  const n = Number(limit);
  const high = limitNeedsConfirm(limit);
  const set = (value: string) => {
    onLimit(value);
    if (!limitNeedsConfirm(value)) onHighConfirmed(false);
  };
  return (
    <div className="limit-picker">
      <div className="limit-title">Мой лимит на запуск, USD</div>
      <div className="limit-presets" role="group" aria-label="Быстрый выбор лимита">
        {LIMIT_PRESETS.map(v => (
          <button
            key={v}
            type="button"
            className={n === v ? 'active' : ''}
            disabled={disabled || v < total}
            onClick={() => set(String(v))}
          >
            {presetLabel(v)}
          </button>
        ))}
      </div>
      <input
        type="range"
        className="limit-slider"
        min={1}
        max={LIMIT_SLIDER_MAX}
        step={1}
        value={Number.isFinite(n) ? Math.min(LIMIT_SLIDER_MAX, Math.max(1, Math.round(n))) : 1}
        disabled={disabled}
        onChange={e => set(e.target.value)}
        aria-label="Лимит, доллары"
      />
      <label className="limit-exact">
        Точная сумма
        <input
          type="number"
          min={total}
          max="100"
          step="0.001"
          value={limit}
          onChange={e => set(e.target.value)}
          disabled={disabled}
        />
      </label>
      {high && (
        <label className="inline-checkbox limit-high">
          <input
            type="checkbox"
            checked={highConfirmed}
            onChange={e => onHighConfirmed(e.target.checked)}
            disabled={disabled}
          />{' '}
          Подтверждаю генерацию (лимит выше $2: до ${n || 0})
        </label>
      )}
    </div>
  );
}
