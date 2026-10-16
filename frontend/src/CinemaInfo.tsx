import {useState} from 'react';
import {Info} from 'lucide-react';

export type CinemaTopic = 'narrative' | 'mise' | 'camera' | 'editing' | 'sound';

const TOPICS: Record<CinemaTopic, {title: string; points: string[]}> = {
  narrative: {
    title: 'Нарратив и жанр',
    points: [
      'У каждого шота должна быть понятная цель героя и препятствие, иначе кадр выглядит пустым.',
      'Жанр задаёт ожидания зрителя: свет, палитру, темп и тип конфликта.',
      'В промпте указывай жанр, цель героя и момент перелома в сцене.',
    ],
  },
  mise: {
    title: 'Мизансцена',
    points: [
      'Расположение персонажей и предметов в кадре показывает отношения и власть между ними.',
      'Работай с планами: передний, средний и задний. Глубина делает кадр объёмным.',
      'В промпте указывай, кто где стоит, куда смотрит и что находится на переднем плане.',
    ],
  },
  camera: {
    title: 'Работа камеры',
    points: [
      'Выбирай план (общий, средний, крупный) под задачу: контекст, действие или эмоцию.',
      'Одно движение камеры на шот, мотивированное действием. Лишнее движение отвлекает.',
      'В промпте связывай план, движение, скорость и амплитуду.',
    ],
  },
  editing: {
    title: 'Монтаж',
    points: [
      'Ритм задают длительность шота и чередование движения с покоем.',
      'Стык двух шотов должен читаться: совпадение движения или взгляда, перемена плана.',
      'Для видео держи шоты короткими и с одним действием, чтобы склейка работала.',
    ],
  },
  sound: {
    title: 'Звук',
    points: [
      'Звук показывает пространство: откуда идёт звук и насколько далеко он от камеры.',
      'Фон, музыка и тишина задают эмоцию. Тишина перед важным моментом усиливает его.',
      'В промпте отдельно указывай звуковой фон, музыку, тон голоса и реплики.',
    ],
  },
};

export default function CinemaInfo({topic}: {topic: CinemaTopic}) {
  const [open, setOpen] = useState(false);
  const item = TOPICS[topic];
  return (
    <div className="cinema-info">
      <button
        type="button"
        className="cinema-info-button"
        aria-expanded={open}
        aria-label={`Подсказка: ${item.title}`}
        title={`Подсказка: ${item.title}`}
        onClick={() => setOpen(v => !v)}
      >
        <Info size={15} />
      </button>
      {open && (
        <div role="note" className="cinema-info-body">
          <strong>{item.title}</strong>
          <ul>
            {item.points.map(p => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
