import type {ReactNode} from 'react';
import CinemaInfo from './CinemaInfo';
import {WORLD_FIELDS, type World, type WorldKey} from './worldBible';

const HINTS: Record<WorldKey, string> = {
  look: 'Техника, жанр, общий образ',
  environment: 'Где происходит действие, какие здания',
  time: 'Когда: ночь, рассвет, зима, дождь',
  tech: 'Эпоха, транспорт, устройства',
  textures: 'Металл, стекло, ткань, поверхности',
  palette: 'Главные цвета и оттенки',
  lighting: 'Направление, температура, источники света',
  camera: 'Ракурсы, объективы, движение',
  mood: 'Эмоция и атмосфера ролика',
  rules: 'Что одинаково в каждом кадре',
  avoid: 'Чего не должно быть в кадре',
};

/** Поля мира по смыслу: сначала образ, затем место и время, в конце камера и правила. */
const GROUPS: {title: string; keys: WorldKey[]}[] = [
  {title: 'Образ', keys: ['look', 'mood', 'palette', 'lighting']},
  {title: 'Место и время', keys: ['environment', 'time', 'tech', 'textures']},
  {title: 'Камера и правила', keys: ['camera', 'rules', 'avoid']},
];

const LABELS = Object.fromEntries(WORLD_FIELDS) as Record<WorldKey, string>;

/** «Стиль мира»: поля библии мира слева, справа паспорт — то, что уходит в промпты всех кадров серии. */
export default function WorldStyle({
  style,
  passport,
  busy,
  attachments,
  onChange,
  onSave,
  onCopy,
  onNext,
}: {
  style: Partial<World>;
  /** Текст паспорта мира (как он подставляется в промпты). */
  passport: string;
  busy: boolean;
  attachments?: ReactNode;
  onChange: (style: Partial<World>) => void;
  onSave: () => void;
  onCopy: () => void;
  onNext: () => void;
}) {
  const filled = WORLD_FIELDS.filter(([k]) => (style[k] || '').trim()).length;
  return (
    <div className="ws">
      <section className="ws-main" aria-label="Библия мира">
        <div className="ws-head">
          <div>
            <h2>
              Библия мира <CinemaInfo topic="world" />
            </h2>
            <small>Коротко и по делу: эти поля держат все кадры серии в одном мире.</small>
          </div>
          <span className={'ws-count' + (filled === WORLD_FIELDS.length ? ' full' : '')}>
            {filled} из {WORLD_FIELDS.length}
          </span>
        </div>
        {attachments}
        {GROUPS.map(g => (
          <fieldset key={g.title} className="ws-group">
            <legend>{g.title}</legend>
            <div className="world-fields">
              {g.keys.map(k => (
                <label key={k} className={'world-field world-field-' + k}>
                  <b>{LABELS[k]}</b>
                  <small>{HINTS[k]}</small>
                  <textarea
                    rows={2}
                    value={style[k] || ''}
                    onChange={e => onChange({...style, [k]: e.target.value})}
                  />
                </label>
              ))}
            </div>
          </fieldset>
        ))}
      </section>
      <aside className="ws-side" aria-label="Паспорт мира">
        <h3>Паспорт мира</h3>
        <small className="muted">Так стиль подставляется в промпты кадров и героев.</small>
        <pre className="ws-passport">{passport.trim() || 'Заполни поля слева — здесь появится паспорт.'}</pre>
        <button className="primary" disabled={busy} onClick={onSave}>
          Сохранить стиль
        </button>
        <div className="ws-side-row">
          <button onClick={onCopy} disabled={!passport.trim()}>
            Копировать
          </button>
          <button onClick={onNext}>Персонажи →</button>
        </div>
      </aside>
    </div>
  );
}
