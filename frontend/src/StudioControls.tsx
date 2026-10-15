import type {ReactNode} from 'react';
import './director-studio.css';

export function ChoiceGroup<T extends string>({
  label,
  value,
  options,
  onChange,
  disabled = false,
}: {
  label: string;
  value: T;
  options: readonly (readonly [T, string])[];
  onChange: (value: T) => void;
  disabled?: boolean;
}) {
  return (
    <fieldset className="director-options">
      <legend>{label}</legend>
      <div>
        {options.map(([id, title]) => (
          <button
            type="button"
            key={id}
            disabled={disabled}
            aria-pressed={value === id}
            className={value === id ? 'chosen' : ''}
            onClick={() => onChange(id)}
          >
            {title}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export function PresetTile({
  title,
  subtitle,
  selected,
  onClick,
  children,
  disabled = false,
}: {
  title: string;
  subtitle?: string;
  selected: boolean;
  onClick: () => void;
  children?: ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className={'director-tile' + (selected ? ' chosen' : '')}
      disabled={disabled}
      aria-pressed={selected}
      onClick={onClick}
    >
      {children && <span className="director-thumb">{children}</span>}
      <span className="director-tile-caption">
        <b>{title}</b>
        {subtitle && <small>{subtitle}</small>}
      </span>
      {selected && (
        <span className="director-check" aria-hidden="true">
          ✓
        </span>
      )}
    </button>
  );
}

export function LightPreview({id}: {id: string}) {
  const warm = id === 'warm-cool',
    rim = id === 'rim',
    overcast = id === 'overcast',
    hard = id === 'split' || id === 'hard-sun';
  return (
    <svg viewBox="0 0 240 135" role="img" aria-label="Условный рисунок света">
      <rect width="240" height="135" fill={warm ? '#233444' : '#11181d'} />
      <ellipse cx="120" cy="137" rx="57" ry="46" fill="#3c4b50" />
      <ellipse cx="120" cy="65" rx="28" ry="39" fill={overcast ? '#c1c3ba' : rim ? '#36454d' : '#736f67'} />
      {!overcast && !rim && (
        <path
          d={
            id === 'butterfly'
              ? 'M94 65Q94 26 120 26Q146 26 146 65L131 78L120 68L109 78Z'
              : id === 'rembrandt'
                ? 'M120 26Q93 26 92 65Q94 97 120 104V26M130 65L141 69L131 80Z'
                : hard
                  ? 'M120 26Q93 26 92 65Q94 97 120 104Z'
                  : 'M120 26Q93 26 92 65Q94 97 120 104Q134 92 130 65Q133 38 120 26Z'
          }
          fill={warm ? '#e7b77f' : '#d3c6aa'}
          opacity={hard ? 1 : 0.85}
        />
      )}
      {rim && (
        <path
          d="M123 26Q149 28 148 65Q146 95 133 103M133 111Q159 112 171 135"
          stroke="#e7d8a4"
          strokeWidth="4"
          fill="none"
        />
      )}
      <path d="M105 59h7m17 0h7M112 85q8 4 16 0" stroke="#202b31" strokeWidth="2" fill="none" />
      <path d="M120 61l-3 13h6" stroke="#52616a" fill="none" />
      <circle
        cx={id === 'butterfly' || overcast ? 120 : rim ? 178 : hard ? 192 : 48}
        cy="19"
        r="6"
        fill="#f3dba3"
      />
      <path
        d={
          id === 'butterfly' || overcast
            ? 'M120 27v13'
            : rim
              ? 'M174 26l-25 21'
              : hard
                ? 'M185 24l-35 21'
                : 'M55 24l35 21'
        }
        stroke="#cfc3a0"
        strokeDasharray="3 3"
      />
    </svg>
  );
}
