import {Palette} from 'lucide-react';
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

/** «Библия мира»: поля стиля, которые подставляются в промпты всех кадров серии. */
export default function WorldStyle({
  style,
  busy,
  attachments,
  onChange,
  onSave,
  onCopy,
  onNext,
}: {
  style: Partial<World>;
  busy: boolean;
  attachments?: ReactNode;
  onChange: (style: Partial<World>) => void;
  onSave: () => void;
  onCopy: () => void;
  onNext: () => void;
}) {
  return (
    <section className="panel world-bible">
      <div className="panel-title">
        <h2>Библия мира</h2>
        <CinemaInfo topic="world" />
        <Palette size={22} />
      </div>
      <p className="muted">
        Единый стиль сохраняется вместе с проектом и держит все кадры серии в одном мире. Заполни коротко и по
        делу: эти поля подставляются в промпты и проверку результатов.
      </p>
      {attachments}
      <div className="world-fields">
        {WORLD_FIELDS.map(([k, label]) => (
          <label key={k} className={'world-field world-field-' + k}>
            <b>{label}</b>
            <small>{HINTS[k]}</small>
            <textarea
              rows={2}
              value={style[k] || ''}
              onChange={e => onChange({...style, [k]: e.target.value})}
            />
          </label>
        ))}
      </div>
      <div className="world-actions">
        <button className="primary" disabled={busy} onClick={onSave}>
          Сохранить стиль проекта
        </button>
        <button onClick={onCopy}>Копировать паспорт</button>
        <button onClick={onNext}>Дальше: персонажи →</button>
      </div>
    </section>
  );
}
