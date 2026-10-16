import {useState, type CSSProperties} from 'react';
import PromptStartMenu, {setupBasis, hasSetup, type PromptSetup} from './PromptStartMenu';
import {ChoiceGroup, PresetTile} from './StudioControls';
import CinemaInfo from './CinemaInfo';

export type CameraSelection = {
  preset_id: string;
  speed: 'slow' | 'medium' | 'fast';
  amplitude: 'small' | 'medium' | 'large';
  note: string;
  setup?: PromptSetup;
};
export type CameraPreset = {
  id: string;
  title: string;
  english: string;
  category: string;
  description: string;
  preview: {x: number; y: number; scale: number; background_scale: number; rotation: number};
};
export const EMPTY_CAMERA: CameraSelection = {preset_id: '', speed: 'slow', amplitude: 'small', note: ''};
export function cameraBasis(camera?: CameraSelection | null) {
  return JSON.stringify({
    preset_id: camera?.preset_id || '',
    speed: camera?.speed || 'slow',
    amplitude: camera?.amplitude || 'small',
    note: camera?.note || '',
    ...(hasSetup(camera?.setup) ? {setup: setupBasis(camera?.setup)} : {}),
  });
}
export function cameraOutdated(
  camera: CameraSelection | undefined,
  basis: string | undefined,
  prompt: string
) {
  return (
    !!prompt.trim() &&
    (!!camera?.preset_id || hasSetup(camera?.setup) || basis !== undefined) &&
    basis !== cameraBasis(camera)
  );
}

function Preview({
  preset,
  speed = 'slow',
  amplitude = 'small',
}: {
  preset: CameraPreset;
  speed?: CameraSelection['speed'];
  amplitude?: CameraSelection['amplitude'];
}) {
  const amount = {small: 0.65, medium: 1, large: 1.3}[amplitude],
    p = preset.preview;
  const style = {
    '--camera-x': p.x * amount + '%',
    '--camera-y': p.y * amount + '%',
    '--camera-scale': 1 + (p.scale - 1) * amount,
    '--camera-bg-scale': 1 + (p.background_scale - 1) * amount,
    '--camera-rotation': p.rotation * amount + 'deg',
    '--camera-duration': {slow: '6s', medium: '4s', fast: '2s'}[speed],
  } as CSSProperties;
  return (
    <div
      className={'camera-preview move-' + preset.id}
      style={style}
      role="img"
      aria-label={'Схема: ' + preset.title}
    >
      <svg viewBox="0 0 320 180" aria-hidden="true">
        <g className="camera-background">
          <rect x="-80" y="-60" width="480" height="300" fill="#14233a" />
          <path d="M-80 115H400V240H-80Z" fill="#233b49" />
          <g fill="#304c62">
            <path d="M0 118V33H54V118M64 118V55H111V118M228 118V44H273V118M283 118V21H330V118" />
          </g>
          <g stroke="#63909b" opacity=".45">
            <path d="M-80 123H400M-80 147H400M160 115L50 220M160 115L270 220M160 115L-120 220M160 115L440 220" />
          </g>
          <g fill="#b9ac7a">
            <path d="M15 48H27V58H15ZM34 48H46V58H34ZM79 68H93V78H79ZM242 60H255V70H242ZM297 38H309V48H297Z" />
          </g>
        </g>
        <g className="camera-subject">
          <ellipse cx="160" cy="154" rx="23" ry="5" fill="#081526" opacity=".6" />
          <path d="M151 124L149 153H157L161 132L166 153H174L170 124Z" fill="#d7834d" />
          <path d="M145 101Q160 93 175 101L179 126H141Z" fill="#edb16f" />
          <circle cx="160" cy="86" r="13" fill="#f7d7ad" />
          <path d="M146 84Q148 67 164 72L176 83Z" fill="#bf684e" />
        </g>
        <path
          d="M16 30V16H36M284 16H304V30M304 150V164H284M36 164H16V150"
          fill="none"
          stroke="#b3bfdb"
          strokeWidth="1.5"
        />
        <path d="M154 90H166M160 84V96" stroke="#f7f0d5" opacity=".6" />
      </svg>
      <span>Схематическое превью</span>
    </div>
  );
}

export function CameraSelector({
  presets,
  value,
  onChange,
  onCatalogue,
  disabled = false,
  setupEnabled = true,
}: {
  presets: CameraPreset[];
  value?: CameraSelection;
  onChange: (v: CameraSelection) => void;
  onCatalogue?: () => void;
  disabled?: boolean;
  setupEnabled?: boolean;
}) {
  const camera = value || EMPTY_CAMERA,
    preset = presets.find(p => p.id === camera.preset_id);
  const [search, setSearch] = useState(''),
    [category, setCategory] = useState('Все'),
    [motionOpen, setMotionOpen] = useState(false);
  const matches = presets.filter(
    p =>
      (category === 'Все' || p.category === category) &&
      [p.title, p.english, p.description].join(' ').toLowerCase().includes(search.toLowerCase())
  );
  return (
    <section
      className="camera-selector director-studio director-motion"
      aria-label="Движение камеры перед видеопромптом"
    >
      <div className="panel-title director-topline">
        <div>
          <span className="director-eyebrow">DIRECTOR / VIDEO</span>
          <h3>Стартовое меню видео</h3>
          <CinemaInfo topic="camera" />
        </div>
        {onCatalogue && (
          <button type="button" disabled={disabled} onClick={onCatalogue}>
            Каталог движений ↗
          </button>
        )}
      </div>
      <PromptStartMenu
        value={camera.setup}
        onChange={setup => onChange({...camera, setup})}
        disabled={disabled || !setupEnabled}
        extra={
          <button
            type="button"
            className={'start-parameter' + (preset ? ' configured' : '')}
            disabled={disabled}
            onClick={() => setMotionOpen(true)}
          >
            <span className="start-parameter-icon" aria-hidden="true">
              ▷
            </span>
            <span>
              <small>Движение камеры</small>
              <b>{preset?.title || 'По заданию'}</b>
            </span>
          </button>
        }
      />
      {!setupEnabled && (
        <p className="director-help">Новые параметры обработки станут доступны после перезапуска backend.</p>
      )}
      <div hidden={!motionOpen}>
        <button type="button" className="start-framing-toggle" onClick={() => setMotionOpen(false)}>
          Свернуть движение ↑
        </button>
        <div className="director-layout">
          <aside className="director-monitor">
            <div>
              {preset ? (
                <Preview preset={preset} speed={camera.speed} amplitude={camera.amplitude} />
              ) : (
                <div className="director-empty">
                  ▷<small>Выбери движение камеры</small>
                </div>
              )}
            </div>
            <div>
              <span className="director-mode">
                {preset?.id === 'static' ? 'ФИКСИРОВАННЫЙ КАДР' : 'СХЕМА ДВИЖЕНИЯ'}
              </span>
              <h4>{preset?.title || 'По заданию'}</h4>
              <p>
                {preset?.description || 'Один понятный приём на кадр: выбери его до подготовки видеопромпта.'}
              </p>
              <div className="director-summary">
                {preset && <span>{preset.english}</span>}
                {preset && preset.id !== 'static' && (
                  <span>
                    {{slow: 'Медленно', medium: 'Умеренно', fast: 'Быстро'}[camera.speed]} /{' '}
                    {
                      {small: 'Малая амплитуда', medium: 'Средняя амплитуда', large: 'Большая амплитуда'}[
                        camera.amplitude
                      ]
                    }
                  </span>
                )}
              </div>
              <p className="director-help">
                Превью объясняет приём. Реальное движение зависит от модели и исходного кадра.
              </p>
            </div>
          </aside>
          <div className="director-settings">
            <label className="director-search">
              Найти движение
              <input
                disabled={disabled}
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Наезд, dolly, панорама…"
              />
            </label>
            <ChoiceGroup
              label="Категория движения"
              value={category}
              options={['Все', ...new Set(presets.map(p => p.category))].map(c => [c, c] as const)}
              onChange={setCategory}
              disabled={disabled}
            />
            <div className="director-section-title">
              <b>
                {matches.length} из {presets.length} движений
              </b>
              <button type="button" disabled={disabled} onClick={() => onChange({...camera, preset_id: ''})}>
                По заданию
              </button>
            </div>
            <div className="director-preset-grid">
              {matches.map(p => (
                <PresetTile
                  key={p.id}
                  title={p.title}
                  subtitle={p.english}
                  selected={camera.preset_id === p.id}
                  disabled={disabled}
                  onClick={() => onChange({...camera, preset_id: p.id})}
                >
                  <Preview preset={p} speed={camera.speed} amplitude={camera.amplitude} />
                </PresetTile>
              ))}
            </div>
            {!matches.length && (
              <p className="muted" role="status">
                Совпадений нет. Измени поиск или категорию.
              </p>
            )}
            {preset && preset.id !== 'static' && (
              <>
                <div className="director-section-title">
                  <b>Характер движения</b>
                </div>
                <ChoiceGroup
                  label="Темп камеры"
                  value={camera.speed}
                  options={[
                    ['slow', 'Медленно'],
                    ['medium', 'Умеренно'],
                    ['fast', 'Быстро'],
                  ]}
                  onChange={speed => onChange({...camera, speed})}
                  disabled={disabled}
                />
                <ChoiceGroup
                  label="Амплитуда"
                  value={camera.amplitude}
                  options={[
                    ['small', 'Небольшая'],
                    ['medium', 'Средняя'],
                    ['large', 'Выраженная'],
                  ]}
                  onChange={amplitude => onChange({...camera, amplitude})}
                  disabled={disabled}
                />
              </>
            )}
          </div>
        </div>
      </div>
      {preset && (
        <label className="director-note">
          Уточнение движения
          <input
            value={camera.note}
            maxLength={1000}
            disabled={disabled}
            onChange={e => onChange({...camera, note: e.target.value})}
            placeholder="Например: закончить крупным планом лица"
          />
        </label>
      )}
      <p className="director-help">
        Выбор войдёт в новый видеопромпт. Для диалога в едущем авто начни со статичной камеры: салон
        закреплён, за окнами движется город.
      </p>
    </section>
  );
}

export default function CameraPanel({
  presets,
  value,
  onChange,
  onVideo,
  error,
  setupEnabled = true,
}: {
  presets: CameraPreset[];
  value?: CameraSelection;
  onChange: (v: CameraSelection) => void;
  onVideo: () => void;
  error?: string;
  setupEnabled?: boolean;
}) {
  return (
    <section className="panel camera-panel">
      <h2>Каталог движений</h2>
      <p className="muted">19 авторских схем. Выбери движение и вернись к подготовке видеопромпта.</p>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      <CameraSelector presets={presets} value={value} onChange={onChange} setupEnabled={setupEnabled} />
      <button type="button" className="primary" onClick={onVideo}>
        Вернуться к видеопромпту
      </button>
    </section>
  );
}
