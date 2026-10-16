import {
  APERTURE,
  ATMOSPHERE,
  CAMERA,
  DEPTH,
  LENS,
  LIGHT_KEY,
  LIGHT_TEMP,
  SHOT,
  type Layers,
  type Option,
} from './operatorPrompt';

export function Chips({
  label,
  options,
  value,
  multi,
  onChange,
}: {
  label: string;
  options: Option[];
  value: string[] | string;
  multi?: boolean;
  onChange: (next: string[] | string) => void;
}) {
  const has = (id: string) => (Array.isArray(value) ? value.includes(id) : value === id);
  return (
    <div className="ol-chips" role="group" aria-label={label}>
      <small>{label}</small>
      {options.map(o => (
        <button
          key={o.id}
          type="button"
          className={has(o.id) ? 'on' : ''}
          aria-pressed={has(o.id)}
          title={o.text}
          onClick={() => {
            if (multi) {
              const list = Array.isArray(value) ? value : [];
              onChange(list.includes(o.id) ? list.filter(x => x !== o.id) : [...list, o.id]);
            } else onChange(value === o.id ? '' : o.id);
          }}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Пять слоёв операторского промпта: что в кадре, окружение и глубина, свет, оптика и камера, стиль и режиссёр. */
export default function OperatorLayers({
  layers,
  onChange,
}: {
  layers: Layers;
  onChange: (next: Layers) => void;
}) {
  const set = <K extends keyof Layers>(key: K, value: Layers[K]) => onChange({...layers, [key]: value});
  return (
    <div className="op">
      <fieldset>
        <legend>1 · Кто и что делает</legend>
        <input
          value={layers.subject}
          placeholder="Например: Грэм смотрит в окно такси, дождь"
          aria-label="Что происходит в кадре"
          onChange={e => set('subject', e.target.value)}
        />
        <small className="muted">Герои берутся из выбранных выше, их внешность подставится сама.</small>
      </fieldset>
      <fieldset>
        <legend>2 · Окружение и глубина</legend>
        <input
          value={layers.environment}
          placeholder="Место: ночной двор, панельки, мокрый асфальт"
          aria-label="Окружение"
          onChange={e => set('environment', e.target.value)}
        />
        <Chips
          label="Глубина"
          options={DEPTH}
          multi
          value={layers.depth}
          onChange={v => set('depth', v as string[])}
        />
        <Chips
          label="Воздух"
          options={ATMOSPHERE}
          multi
          value={layers.atmosphere}
          onChange={v => set('atmosphere', v as string[])}
        />
      </fieldset>
      <fieldset>
        <legend>3 · Свет</legend>
        <Chips
          label="Основной"
          options={LIGHT_KEY}
          multi
          value={layers.lightKey}
          onChange={v => set('lightKey', v as string[])}
        />
        <Chips
          label="Температура"
          options={LIGHT_TEMP}
          value={layers.lightTemp}
          onChange={v => set('lightTemp', v as string)}
        />
        <input
          value={layers.lightNote}
          placeholder="Откуда свет: фонарь за окном, приборная панель"
          aria-label="Мотивация источника света"
          onChange={e => set('lightNote', e.target.value)}
        />
      </fieldset>
      <fieldset>
        <legend>4 · Оптика и камера</legend>
        <Chips
          label="Крупность"
          options={SHOT}
          value={layers.shot}
          onChange={v => set('shot', v as string)}
        />
        <Chips label="Объектив" options={LENS} value={layers.lens} onChange={v => set('lens', v as string)} />
        <Chips
          label="Диафрагма"
          options={APERTURE}
          value={layers.aperture}
          onChange={v => set('aperture', v as string)}
        />
        <Chips
          label="Камера и плёнка"
          options={CAMERA}
          value={layers.camera}
          onChange={v => set('camera', v as string)}
        />
      </fieldset>
      <fieldset>
        <legend>5 · Стиль и режиссёр</legend>
        <small className="muted">Стиль и палитра берутся из паспорта мира.</small>
        <input
          value={layers.director}
          placeholder="Необязательно: режиссёр, например Denis Villeneuve"
          aria-label="Режиссёр"
          onChange={e => set('director', e.target.value)}
        />
      </fieldset>
    </div>
  );
}
