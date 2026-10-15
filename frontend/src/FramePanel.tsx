import {useId, useState} from 'react';
import PromptStartMenu, {setupBasis, hasSetup, type PromptSetup} from './PromptStartMenu';
import {ChoiceGroup, PresetTile, LightPreview} from './StudioControls';
import {
  CarControls,
  CarDiagram,
  EMPTY_CAR,
  carBasis,
  type CarSelection,
  type CarShot,
  type CarLight,
} from './CarStage';

export type FrameSelection = {
  frame_id: string;
  lighting_id: string;
  direction: 'preset' | 'left' | 'right' | 'front' | 'back' | 'top';
  softness: 'preset' | 'soft' | 'hard';
  temperature: 'preset' | 'neutral' | 'warm' | 'cool';
  note: string;
  shot_size?: '' | 'establishing' | 'full-body' | 'medium' | 'medium-close' | 'close-up' | 'extreme-close';
  car?: CarSelection;
  setup?: PromptSetup;
};
export type FramePreset = {
  id: string;
  title: string;
  english: string;
  category: string;
  description: string;
  preview: {scale: number; x: number; y: number; rotation: number; view: string};
};
export type LightPreset = {id: string; title: string; description: string; direction: string};
export type FrameCatalogue = {
  frames: FramePreset[];
  lights: LightPreset[];
  car_shots?: CarShot[];
  car_lights?: CarLight[];
  capabilities?: {independent_shot_size: boolean; car_staging: boolean; prompt_setup?: boolean};
};
export const EMPTY_FRAME: FrameSelection = {
  frame_id: '',
  lighting_id: '',
  direction: 'preset',
  softness: 'preset',
  temperature: 'preset',
  note: '',
};
export function frameBasis(value?: FrameSelection | null) {
  return JSON.stringify({
    frame_id: value?.frame_id || '',
    lighting_id: value?.lighting_id || '',
    direction: value?.direction || 'preset',
    softness: value?.softness || 'preset',
    temperature: value?.temperature || 'preset',
    note: value?.note || '',
    ...(value?.shot_size ? {shot_size: value.shot_size} : {}),
    ...(value?.car ? {car: carBasis(value.car)} : {}),
    ...(hasSetup(value?.setup) ? {setup: setupBasis(value?.setup)} : {}),
  });
}
export function frameOutdated(value: FrameSelection | undefined, basis: string | undefined, prompt: string) {
  return (
    !!prompt.trim() &&
    (frameBasis(value) !== frameBasis(EMPTY_FRAME) || basis !== undefined) &&
    basis !== frameBasis(value)
  );
}

function FramePreview({
  preset,
  value,
  lights,
  frames = [],
}: {
  preset: FramePreset;
  value?: FrameSelection;
  lights: LightPreset[];
  frames?: FramePreset[];
}) {
  const uid = useId().replace(/:/g, ''),
    size = frames.find(f => f.id === value?.shot_size);
  const p = {...preset.preview, ...(size ? {scale: size.preview.scale, y: size.preview.y} : {})};
  // Keep the head inside close-up samples; the catalogue coordinates predate
  // independent crop and angle controls.
  if (p.scale >= 4) p.y = Math.max(90, p.y);
  else if (p.scale >= 2.6) p.y = Math.max(60, p.y);
  const lighting = lights.find(l => l.id === value?.lighting_id),
    direction = value?.direction && value.direction !== 'preset' ? value.direction : lighting?.direction;
  const reverse = direction === 'right',
    tint = value?.temperature === 'cool' ? '#a3c8e3' : value?.temperature === 'warm' ? '#ffc47e' : '#efbf88';
  const hard =
    value?.softness === 'hard' ||
    (value?.softness !== 'soft' && ['split', 'hard-sun'].includes(lighting?.id || ''));
  const shadow = lighting ? (lighting.id === 'overcast' ? '#cda570' : '#6a574f') : '#d09a67';
  return (
    <div className="frame-preview" role="img" aria-label={'Пример композиции: ' + preset.title}>
      <svg viewBox="0 0 320 180" aria-hidden="true">
        <defs>
          <linearGradient
            id={uid + 'light'}
            x1={reverse ? '100%' : '0%'}
            y1="0%"
            x2={direction === 'top' ? '0%' : reverse ? '0%' : '100%'}
            y2={direction === 'top' ? '100%' : '0%'}
          >
            <stop offset="0%" stopColor={tint} />
            <stop offset={hard ? '48%' : '30%'} stopColor={tint} />
            <stop offset={hard ? '52%' : '100%'} stopColor={shadow} />
          </linearGradient>
          <radialGradient id={uid + 'glow'}>
            <stop stopColor="#fac675" stopOpacity=".35" />
            <stop offset="100%" stopColor="#fac675" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width="320" height="180" fill="#152238" />
        <g transform={'rotate(' + p.rotation + ' 160 90)'}>
          <path
            d={'M0 ' + (p.view === 'low' ? 145 : p.view === 'high' ? 75 : 112) + 'H320V200H0Z'}
            fill="#263b48"
          />
          <g fill="#385167">
            <path d="M0 120V38H57V120M66 120V63H107V120M235 120V48H276V120M285 120V25H330V120" />
          </g>
          <g stroke="#728da4" opacity=".35">
            <path d="M0 130H320M0 158H320M160 112L25 200M160 112L295 200" />
          </g>
          {preset.id === 'thirds' && (
            <path
              d="M107 0V180M213 0V180M0 60H320M0 120H320"
              stroke="#d6c694"
              strokeDasharray="4 4"
              opacity=".45"
            />
          )}
          {direction && (
            <>
              <circle
                cx={
                  reverse
                    ? 286
                    : direction === 'top' || direction === 'front' || direction === 'back'
                      ? 160
                      : 34
                }
                cy={direction === 'front' ? 158 : 22}
                r="80"
                fill={'url(#' + uid + 'glow)'}
              />
              <circle
                cx={
                  reverse
                    ? 286
                    : direction === 'top' || direction === 'front' || direction === 'back'
                      ? 160
                      : 34
                }
                cy={direction === 'front' ? 158 : 22}
                r="5"
                fill="#f8ce7c"
              />
            </>
          )}
          {p.view === 'top' ? (
            <g transform="translate(160 100)">
              <ellipse rx="29" ry="13" fill={'url(#' + uid + 'light)'} />
              <ellipse ry="16" rx="13" fill="#bb7159" />
              <path d="M-18-2Q0-22 18-2" fill="#cf8363" />
              <path d="M-14 15L-18 39M14 15L18 39" stroke="#b38a66" strokeWidth="8" />
            </g>
          ) : (
            <g
              transform={`translate(${p.x} ${p.y}) scale(${p.scale} ${p.scale * (p.view === 'high' ? 0.8 : 1)})`}
            >
              <ellipse cx="0" cy="103" rx="25" ry="5" fill="#091425" opacity=".6" />
              <path d="M-13 64L-17 101H-5L0 77L5 101H17L13 64Z" fill="#49606d" />
              <path d="M-18 20Q0 10 18 20L25 68H-25Z" fill={'url(#' + uid + 'light)'} />
              <path
                d="M-19 25L-28 61M19 25L28 61"
                fill="none"
                stroke={tint}
                strokeWidth="8"
                strokeLinecap="round"
              />
              {p.view === 'profile' ? (
                <path
                  d="M-9-14Q7-17 10-5L18 0L11 5Q13 19-3 17Q-16 12-14-1Z"
                  fill={'url(#' + uid + 'light)'}
                />
              ) : (
                <ellipse cy="0" rx={p.view === 'quarter' ? 11 : 13} ry="17" fill={'url(#' + uid + 'light)'} />
              )}
              <path d="M-14-7Q-11-24 5-19L17-7Z" fill="#be705b" />
              {p.view === 'profile' ? (
                <circle cx="7" cy="-3" r="1.4" fill="#303543" />
              ) : (
                <>
                  <path
                    d={p.view === 'quarter' ? 'M-1-3H2M7-3H10' : 'M-8-3H-5M5-3H8'}
                    stroke="#303543"
                    strokeWidth="1.8"
                  />
                  <path d="M-3 9Q1 11 5 8" stroke="#72524c" fill="none" />
                </>
              )}
              {lighting?.id === 'rim' && (
                <path d="M-13-7Q-16 8-7 15M-18 20L-25 67" stroke="#ffe1a2" strokeWidth="2" fill="none" />
              )}
            </g>
          )}
          {p.view === 'shoulder' && (
            <path d="M-20 180V95Q10 58 43 85L65 113Q89 117 104 180Z" fill="#0b1423" />
          )}
          {p.view === 'pov' && (
            <path d="M30 180L60 125H260L290 180" fill="none" stroke="#98acb8" opacity=".6" />
          )}
        </g>
        <path d="M12 28V12H30M290 12H308V28M308 152V168H290M30 168H12V152" fill="none" stroke="#c0c9db" />
      </svg>
      <span>Схема ракурса и света</span>
    </div>
  );
}

function LightDiagram({
  value,
  lights,
  onChange,
}: {
  value: FrameSelection;
  lights: LightPreset[];
  onChange: (v: FrameSelection) => void;
}) {
  const direction =
    value.direction === 'preset' ? lights.find(l => l.id === value.lighting_id)?.direction : value.direction;
  const positions = [
    ['left', 40, 75],
    ['right', 200, 75],
    ['front', 120, 126],
    ['back', 120, 25],
    ['top', 165, 31],
  ] as const;
  return (
    <div className="light-diagram">
      <svg
        viewBox="0 0 240 155"
        role="img"
        aria-label="Схема положения источника света относительно героя и камеры"
      >
        <rect x="1" y="1" width="238" height="153" rx="12" fill="#0f1c30" />
        <circle cx="120" cy="73" r="17" fill="#e6ba86" />
        <path d="M108 65Q120 45 132 65" fill="#be705b" />
        <path d="M111 140H129V151H111ZM129 142L139 138V153L129 149Z" fill="#a3aec9" />
        {positions.map(([id, x, y]) => (
          <g key={id} opacity={direction === id ? 1 : 0.3}>
            <path d={`M${x} ${y}L120 73`} stroke="#f9c77c" strokeDasharray="3 3" />
            <circle cx={x} cy={y} r={direction === id ? 9 : 5} fill="#f9c77c" />
          </g>
        ))}
      </svg>
      <small>Схема сверху · камера снизу · «сверху» означает источник над головой</small>
      <div className="chips">
        {positions.map(([id]) => (
          <button
            className={direction === id ? 'active' : ''}
            key={id}
            onClick={() => onChange({...value, direction: id})}
          >
            {{left: 'Слева', right: 'Справа', front: 'Спереди', back: 'Сзади', top: 'Над героем'}[id]}
          </button>
        ))}
      </div>
    </div>
  );
}

export function FrameSelector({
  catalogue,
  value,
  onChange,
  onCatalogue,
}: {
  catalogue: FrameCatalogue;
  value?: FrameSelection;
  onChange: (v: FrameSelection) => void;
  onCatalogue?: () => void;
}) {
  const chosen = value || EMPTY_FRAME;
  const [pane, setPane] = useState<'frame' | 'light' | 'car'>('frame');
  const [filter, setFilter] = useState('Все');
  const [framingOpen, setFramingOpen] = useState(false);
  const frame = catalogue.frames.find(f => f.id === chosen.frame_id);
  const size = catalogue.frames.find(f => f.id === chosen.shot_size);
  const light = catalogue.lights.find(l => l.id === chosen.lighting_id);
  const carShot = catalogue.car_shots?.find(p => p.id === chosen.car?.shot_id);
  const carLight = catalogue.car_lights?.find(p => p.id === chosen.car?.light_id);
  const preview = frame || size || catalogue.frames.find(f => f.id === 'medium');
  const angles = catalogue.frames.filter(
    f => f.category !== 'Масштаб' && (filter === 'Все' || f.category === filter)
  );
  const sizes = catalogue.frames.filter(f => f.category === 'Масштаб');
  const supportsSize = !!catalogue.capabilities?.independent_shot_size,
    supportsCar = !!catalogue.capabilities?.car_staging;
  function chooseFrame(id: string) {
    onChange({...chosen, frame_id: id, car: chosen.car ? {...chosen.car, shot_id: ''} : undefined});
  }
  function chooseLight(id: string) {
    onChange({...chosen, lighting_id: id, car: chosen.car ? {...chosen.car, light_id: ''} : undefined});
  }
  return (
    <section className="frame-selector director-studio" aria-label="Постановка кадра и света">
      <div className="panel-title director-topline">
        <div>
          <span className="director-eyebrow">DIRECTOR / PHOTO</span>
          <h3>Стартовое меню кадра</h3>
        </div>
        {onCatalogue && (
          <button type="button" onClick={onCatalogue}>
            15 композиций ↗
          </button>
        )}
      </div>
      {!!catalogue.frames.length && (!supportsSize || !catalogue.capabilities?.prompt_setup) && (
        <p role="status" className="muted">
          Для новых параметров стартового меню нужен перезапуск backend. Прежние композиции и световые схемы
          доступны.
        </p>
      )}
      <PromptStartMenu
        value={chosen.setup}
        onChange={setup => onChange({...chosen, setup})}
        disabled={!catalogue.capabilities?.prompt_setup}
        extra={
          <>
            {(
              [
                ['frame', 'Крупность и ракурс', frame?.title || size?.title || 'По референсу', '▧'],
                ['light', 'Освещение', carLight?.title || light?.title || 'По референсу', '☼'],
                ['car', 'Салон авто', carShot?.title || (chosen.car ? 'Рассадка задана' : 'Не выбран'), '▱'],
              ] as const
            ).map(([id, title, summary, icon]) => (
              <button
                type="button"
                className={
                  'start-parameter' +
                  ((id === 'frame' && (frame || size)) ||
                  (id === 'light' && (light || carLight)) ||
                  (id === 'car' && chosen.car)
                    ? ' configured'
                    : '')
                }
                key={id}
                onClick={() => {
                  setPane(id);
                  setFramingOpen(true);
                }}
              >
                <span className="start-parameter-icon" aria-hidden="true">
                  {icon}
                </span>
                <span>
                  <small>{title}</small>
                  <b>{summary}</b>
                </span>
              </button>
            ))}
          </>
        }
      />
      <div hidden={!framingOpen}>
        <button type="button" className="start-framing-toggle" onClick={() => setFramingOpen(false)}>
          Свернуть кадр и свет ↑
        </button>
        <div className="director-layout">
          <aside className="director-monitor">
            <div>
              {chosen.car ? (
                <CarDiagram car={chosen.car} shot={carShot} />
              ) : preview ? (
                <FramePreview
                  preset={preview}
                  value={chosen}
                  lights={catalogue.lights}
                  frames={catalogue.frames}
                />
              ) : (
                <div className="director-empty">
                  ▣<small>Выбери композицию</small>
                </div>
              )}
            </div>
            <div>
              <span className="director-mode">
                {chosen.car ? 'САЛОН / СХЕМА СВЕРХУ' : 'КАДР / УСЛОВНОЕ ПРЕВЬЮ'}
              </span>
              <h4>{carShot?.title || frame?.title || size?.title || 'По заданию и референсу'}</h4>
              <p>
                {carShot?.description ||
                  frame?.description ||
                  'Задай крупность и ракурс независимо, затем выбери свет.'}
              </p>
              <div className="director-summary">
                {(size || frame?.category === 'Масштаб') && <span>{size?.title || frame?.title}</span>}
                {(carLight || light) && <span>{carLight?.title || light?.title}</span>}
                {chosen.car && <span>Рассадка закреплена</span>}
              </div>
              <p className="director-help">
                {chosen.car
                  ? 'Схема камеры и мест. Внешность и геометрия салона берутся из референсов.'
                  : 'Схематический пример: показывает постановку, а не результат генерации.'}
              </p>
            </div>
          </aside>
          <div className="director-settings">
            <div className="director-tabs" role="group" aria-label="Настройки постановки">
              {(
                [
                  ['frame', 'Кадр'],
                  ['light', 'Свет'],
                  ['car', 'Внутри авто'],
                ] as const
              ).map(([id, title]) => (
                <button
                  type="button"
                  key={id}
                  className={pane === id ? 'chosen' : ''}
                  aria-pressed={pane === id}
                  onClick={() => setPane(id)}
                >
                  {title}
                </button>
              ))}
            </div>
            {pane === 'frame' && (
              <>
                <ChoiceGroup
                  label="Крупность"
                  value={chosen.shot_size || (frame?.category === 'Масштаб' ? frame.id : '')}
                  options={[['', 'По референсу'], ...sizes.map(f => [f.id, f.title] as const)]}
                  disabled={!supportsSize || (!!carShot && !['driver', 'guest'].includes(carShot.target))}
                  onChange={id =>
                    onChange({
                      ...chosen,
                      shot_size: id as FrameSelection['shot_size'],
                      frame_id: frame?.category === 'Масштаб' ? '' : chosen.frame_id,
                    })
                  }
                />
                {carShot && !['driver', 'guest'].includes(carShot.target) && (
                  <p className="director-help">
                    Для этого автомобильного плана крупность задана самим пресетом.
                  </p>
                )}
                <div className="director-section-title">
                  <b>Ракурс и композиция</b>
                  <button type="button" onClick={() => chooseFrame('')}>
                    По референсу
                  </button>
                </div>
                <ChoiceGroup
                  label="Категория"
                  value={filter}
                  options={[
                    'Все',
                    ...new Set(catalogue.frames.filter(f => f.category !== 'Масштаб').map(f => f.category)),
                  ].map(c => [c, c] as const)}
                  onChange={setFilter}
                />
                <div className="director-preset-grid">
                  {angles.map(p => (
                    <PresetTile
                      key={p.id}
                      title={p.title}
                      subtitle={p.english}
                      selected={chosen.frame_id === p.id}
                      onClick={() => chooseFrame(p.id)}
                    >
                      <FramePreview
                        preset={p}
                        value={chosen}
                        lights={catalogue.lights}
                        frames={catalogue.frames}
                      />
                    </PresetTile>
                  ))}
                </div>
                <p className="director-help">
                  Крупность определяет обрезку. Ракурс — положение камеры, высоту и композицию.
                </p>
              </>
            )}
            {pane === 'light' && (
              <>
                <div className="director-section-title">
                  <b>8 световых схем</b>
                  <button type="button" onClick={() => chooseLight('')}>
                    По референсу
                  </button>
                </div>
                <div className="director-preset-grid">
                  {catalogue.lights.map(p => (
                    <PresetTile
                      key={p.id}
                      title={p.title}
                      subtitle={p.description}
                      selected={chosen.lighting_id === p.id}
                      onClick={() => chooseLight(p.id)}
                    >
                      <LightPreview id={p.id} />
                    </PresetTile>
                  ))}
                </div>
                <details>
                  <summary>Направление, мягкость и температура</summary>
                  <div className="light-controls">
                    <LightDiagram value={chosen} lights={catalogue.lights} onChange={onChange} />
                    <div>
                      <label>
                        Направление ключевого света
                        <select
                          value={chosen.direction}
                          onChange={e =>
                            onChange({...chosen, direction: e.target.value as FrameSelection['direction']})
                          }
                        >
                          <option value="preset">По выбранной схеме</option>
                          <option value="left">Слева от камеры</option>
                          <option value="right">Справа от камеры</option>
                          <option value="front">Со стороны камеры</option>
                          <option value="back">За героем</option>
                          <option value="top">Над героем</option>
                        </select>
                      </label>
                      <ChoiceGroup
                        label="Характер теней"
                        value={chosen.softness}
                        options={[
                          ['preset', 'По схеме'],
                          ['soft', 'Мягкие'],
                          ['hard', 'Жёсткие'],
                        ]}
                        onChange={softness => onChange({...chosen, softness})}
                      />
                      <ChoiceGroup
                        label="Температура"
                        value={chosen.temperature}
                        options={[
                          ['preset', 'По схеме'],
                          ['neutral', 'Нейтральная'],
                          ['warm', 'Тёплая'],
                          ['cool', 'Холодная'],
                        ]}
                        onChange={temperature => onChange({...chosen, temperature})}
                      />
                    </div>
                  </div>
                </details>
                {(light || carLight) && (
                  <p className="director-help">{light?.description || carLight?.description}</p>
                )}
              </>
            )}
            {pane === 'car' && (
              <>
                {chosen.car ? (
                  <>
                    <div className="director-section-title">
                      <b>GremoVOD / салон такси</b>
                      <button type="button" onClick={() => onChange({...chosen, car: undefined})}>
                        Убрать рассадку
                      </button>
                    </div>
                    <CarControls
                      value={chosen.car}
                      shots={catalogue.car_shots || []}
                      lights={catalogue.car_lights || []}
                      onChange={car => {
                        const shot = catalogue.car_shots?.find(p => p.id === car.shot_id);
                        onChange({
                          ...chosen,
                          car,
                          frame_id: car.shot_id ? '' : chosen.frame_id,
                          lighting_id: car.light_id ? '' : chosen.lighting_id,
                          shot_size:
                            shot && !['driver', 'guest'].includes(shot.target) ? '' : chosen.shot_size,
                        });
                      }}
                    />
                  </>
                ) : (
                  <div className="director-car-intro">
                    <h4>Грэм и гость</h4>
                    <p className="muted">
                      Закрепи места героев, сторону руля и свет. Затем выбирай общий, отдельный или обратный
                      план без пересадки персонажей.
                    </p>
                    <CarDiagram car={EMPTY_CAR} />
                    <button
                      type="button"
                      disabled={!supportsCar}
                      onClick={() => onChange({...chosen, car: {...EMPTY_CAR}, frame_id: ''})}
                    >
                      Настроить салон авто
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
      <label className="director-note">
        Уточнение кадра и света
        <input
          maxLength={1000}
          value={chosen.note}
          onChange={e => onChange({...chosen, note: e.target.value})}
          placeholder="Например: оставить место справа, сохранить свет из левого окна"
        />
      </label>
      <small className="director-help">
        Настройки попадут в новый фотопромпт. Движение камеры выбирается на этапе видео.
      </small>
    </section>
  );
}

export default function FramePanel({
  catalogue,
  value,
  onChange,
  onImage,
  error,
}: {
  catalogue: FrameCatalogue;
  value?: FrameSelection;
  onChange: (v: FrameSelection) => void;
  onImage: () => void;
  error?: string;
}) {
  const [search, setSearch] = useState(''),
    [category, setCategory] = useState('Все');
  const frames = catalogue.frames.filter(
    f =>
      (category === 'Все' || category === f.category) &&
      [f.title, f.english, f.description].join(' ').toLowerCase().includes(search.toLowerCase())
  );
  return (
    <section className="panel frame-panel">
      <h2>Кадр и свет · 15 композиций</h2>
      <p className="muted">
        Выбери масштаб, ракурс и свет перед генерацией изображения. Одна композиция может сочетаться с разными
        световыми схемами.
      </p>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      <FrameSelector catalogue={catalogue} value={value} onChange={onChange} />
      <button className="primary" onClick={onImage}>
        Вернуться к фотопромпту
      </button>
      <label>
        Найти композицию
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Крупный, профиль, сверху…"
        />
      </label>
      <div className="chips">
        {['Все', ...new Set(catalogue.frames.map(f => f.category))].map(c => (
          <button className={category === c ? 'active' : ''} key={c} onClick={() => setCategory(c)}>
            {c}
          </button>
        ))}
      </div>
      <p className="muted">{frames.length} из 15 композиций</p>
      <div className="camera-grid">
        {frames.map(frame => (
          <article
            key={frame.id}
            className={'camera-card' + (frame.id === value?.frame_id ? ' selected' : '')}
          >
            <FramePreview preset={frame} value={value} lights={catalogue.lights} />
            <h3>
              {String(catalogue.frames.indexOf(frame) + 1).padStart(2, '0')} · {frame.title}
            </h3>
            <small>
              {frame.english} · {frame.category}
            </small>
            <p>{frame.description}</p>
            <button
              aria-pressed={frame.id === value?.frame_id}
              onClick={() =>
                onChange({
                  ...(value || EMPTY_FRAME),
                  frame_id: frame.id,
                  shot_size: frame.category === 'Масштаб' ? '' : value?.shot_size,
                  car: value?.car ? {...value.car, shot_id: ''} : undefined,
                })
              }
            >
              {frame.id === value?.frame_id ? '✓ Выбрано: ' : 'Выбрать: '}
              {frame.title}
            </button>
          </article>
        ))}
      </div>
      {!frames.length && <p className="muted">Композиции не найдены. Измени поиск или категорию.</p>}
    </section>
  );
}
