import {useId} from 'react';
import {ChoiceGroup, PresetTile} from './StudioControls';

export type CarSelection = {
  shot_id: string;
  steering: 'reference' | 'left' | 'right';
  guest_seat: 'front' | 'rear-left' | 'rear-center' | 'rear-right';
  vehicle_state: 'parked' | 'moving';
  light_id: string;
};
export type CarShot = {
  id: string;
  title: string;
  description: string;
  station: string;
  target: string;
  guest_row: string;
  complex: boolean;
};
export type CarLight = {id: string; title: string; description: string};
export const EMPTY_CAR: CarSelection = {
  shot_id: '',
  steering: 'reference',
  guest_seat: 'rear-right',
  vehicle_state: 'moving',
  light_id: '',
};
export function carCompatible(shot: CarShot, car: CarSelection) {
  return (
    (shot.guest_row === 'any' || shot.guest_row === (car.guest_seat === 'front' ? 'front' : 'rear')) &&
    !(shot.id === 'car-guest-window' && car.guest_seat === 'rear-center')
  );
}
export function carBasis(car: CarSelection) {
  return {
    shot_id: car.shot_id || '',
    steering: car.steering || 'reference',
    guest_seat: car.guest_seat || 'rear-right',
    vehicle_state: car.vehicle_state || 'moving',
    light_id: car.light_id || '',
  };
}

export function CarDiagram({car, shot}: {car: CarSelection; shot?: CarShot}) {
  const uid = 'car' + useId().replace(/:/g, ''),
    driverX = car.steering === 'right' ? 218 : 102;
  const guestX =
    car.guest_seat === 'front'
      ? 320 - driverX
      : car.guest_seat === 'rear-left'
        ? 102
        : car.guest_seat === 'rear-right'
          ? 218
          : 160;
  const guestY = car.guest_seat === 'front' ? 91 : 169;
  const known = car.steering !== 'reference';
  const points: Record<string, [number, number]> = {
    'dash-center': [160, 48],
    'front-center': [160, 121],
    'rear-center': [160, 194],
    'driver-shoulder': [known ? driverX : 160, 125],
    'front-passenger-side': [known ? 320 - driverX : 160, 59],
    'center-near-guest': [160, car.guest_seat === 'front' ? 115 : 140],
    'mirror-view': [160, 42],
    'outside-front': [160, 10],
  };
  const station = shot ? points[shot.station] || [160, 48] : null;
  const target: [number, number] =
    shot?.target === 'driver'
      ? [known ? driverX : 160, 91]
      : shot?.target === 'guest'
        ? [known || car.guest_seat !== 'front' ? guestX : 160, guestY]
        : shot?.target === 'road'
          ? [160, 7]
          : shot?.target === 'mirror'
            ? [160, 60]
            : shot?.target === 'detail'
              ? [known ? driverX : 160, 59]
              : [160, 100];
  return (
    <svg
      className="car-stage-diagram"
      viewBox="0 0 320 235"
      role="img"
      aria-label={
        'Схема сверху: ' +
        (shot?.title || 'рассадка') +
        '. Перед автомобиля сверху. Стороны автомобиля по ходу движения.'
      }
    >
      <defs>
        <marker
          id={uid}
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="5"
          markerHeight="5"
          orient="auto-start-reverse"
        >
          <path d="M0 0L10 5L0 10Z" fill="#c6ed97" />
        </marker>
      </defs>
      <rect width="320" height="235" rx="12" fill="#10191c" />
      <path
        d="M65 214V67Q65 26 107 26H213Q255 26 255 67V214Z"
        fill="#1b292c"
        stroke="#6f8488"
        strokeWidth="1.5"
      />
      <path d="M77 57Q160 36 243 57M78 139H242M77 204H243" fill="none" stroke="#57767d" />
      <path d="M57 72v105M263 72v105" stroke="#4e8993" strokeWidth="3" />
      {[102, 218].map(x => (
        <g key={x}>
          <rect x={x - 27} y="71" width="54" height="49" rx="9" fill="#34454a" />
          <rect x={x - 19} y="114" width="38" height="8" rx="3" fill="#526165" />
        </g>
      ))}
      <rect x="77" y="150" width="166" height="43" rx="9" fill="#34454a" />
      {known ? (
        <>
          <circle cx={driverX} cy="61" r="11" fill="none" stroke="#bbc7c8" strokeWidth="2" />
          <circle cx={driverX} cy="87" r="13" fill="#dba978" />
          <text x={driverX} y="110" textAnchor="middle" fill="#fff" fontSize="9">
            Грэм
          </text>
        </>
      ) : (
        <text x="160" y="89" textAnchor="middle" fill="#dba978" fontSize="9">
          Водитель — по референсу
        </text>
      )}
      {known || car.guest_seat !== 'front' ? (
        <>
          <circle cx={guestX} cy={guestY} r="12" fill="#9fc6d5" />
          <text x={guestX} y={guestY + 23} textAnchor="middle" fill="#cce5ed" fontSize="9">
            Гость
          </text>
        </>
      ) : (
        <text x="160" y="103" textAnchor="middle" fill="#9fc6d5" fontSize="9">
          Гость — напротив водителя
        </text>
      )}
      {station && (
        <>
          <path
            d={`M${station[0]} ${station[1]}L${target[0]} ${target[1]}`}
            stroke="#c6ed97"
            strokeWidth="2"
            strokeDasharray="4 3"
            markerEnd={'url(#' + uid + ')'}
          />
          <rect x={station[0] - 8} y={station[1] - 5} width="16" height="11" rx="2" fill="#c6ed97" />
          <circle cx={station[0]} cy={station[1]} r="3" fill="#1b292c" />
        </>
      )}
      <text x="25" y="117" textAnchor="middle" fill="#9baead" fontSize="9">
        Л
      </text>
      <text x="295" y="117" textAnchor="middle" fill="#9baead" fontSize="9">
        П
      </text>
      <text x="160" y="228" textAnchor="middle" fill="#9baead" fontSize="9">
        Вид сверху · перед автомобиля ↑
      </text>
    </svg>
  );
}

export function CarControls({
  value,
  shots,
  lights,
  onChange,
}: {
  value: CarSelection;
  shots: CarShot[];
  lights: CarLight[];
  onChange: (value: CarSelection) => void;
}) {
  function patch(next: Partial<CarSelection>) {
    const updated = {...value, ...next},
      shot = shots.find(p => p.id === updated.shot_id);
    if (shot && !carCompatible(shot, updated)) updated.shot_id = '';
    onChange(updated);
  }
  return (
    <div className="car-controls">
      <ChoiceGroup
        label="Сторона руля · по ходу движения"
        value={value.steering}
        options={[
          ['reference', 'По референсу'],
          ['left', 'Слева'],
          ['right', 'Справа'],
        ]}
        onChange={steering => patch({steering})}
      />
      <ChoiceGroup
        label="Место гостя"
        value={value.guest_seat}
        options={[
          ['front', 'Спереди'],
          ['rear-left', 'Сзади слева'],
          ['rear-center', 'Сзади по центру'],
          ['rear-right', 'Сзади справа'],
        ]}
        onChange={guest_seat => patch({guest_seat})}
      />
      <ChoiceGroup
        label="Автомобиль"
        value={value.vehicle_state}
        options={[
          ['moving', 'Едет'],
          ['parked', 'Стоит'],
        ]}
        onChange={vehicle_state => patch({vehicle_state})}
      />
      <div className="director-section-title">
        <b>Точка съёмки</b>
        <button type="button" onClick={() => patch({shot_id: ''})}>
          По заданию
        </button>
      </div>
      <div className="director-preset-grid car-shot-grid">
        {shots.map(shot => (
          <PresetTile
            key={shot.id}
            title={shot.title}
            subtitle={
              !carCompatible(shot, value)
                ? 'Не подходит к рассадке'
                : shot.station === 'outside-front'
                  ? 'Камера снаружи · сложный'
                  : shot.complex
                    ? 'Сложный · отражение'
                    : 'Камера внутри'
            }
            selected={value.shot_id === shot.id}
            disabled={!carCompatible(shot, value)}
            onClick={() => patch({shot_id: shot.id})}
          >
            <CarDiagram car={value} shot={shot} />
          </PresetTile>
        ))}
      </div>
      {!shots.length && (
        <p role="status" className="muted">
          Каталог салона недоступен. Обнови локальный сервер и перезагрузи страницу.
        </p>
      )}
      <ChoiceGroup
        label="Свет салона"
        value={value.light_id}
        options={[['', 'По заданию'], ...lights.map(p => [p.id, p.title] as const)]}
        onChange={light_id => patch({light_id})}
      />
      <p className="muted">
        Нужны утверждённый салон и референсы обоих героев. Схема показывает рассадку и направление взгляда
        камеры; это не точная модель автомобиля.
      </p>
    </div>
  );
}
