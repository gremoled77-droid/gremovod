import {useEffect, useState} from 'react';
import {apiFetch, responseJson} from './api';
import {toggleId} from './boardOrder';
import type {EntityPatch} from './boardApi';

type Entry = {id: string; kind: string; title: string};
type Cast = {
  character_node_ids: string[];
  location_node_id: string | null;
  location_angle_file_id?: string | null;
};
type LocationFile = {id: string; kind: string; filename: string};

// Доска перерисовывается после каждого сохранения, поэтому открытые блоки запоминаем снаружи.
const OPEN = new Set<string>();

/** Состав кадра: по умолчанию как в сцене, но можно задать свой: герои, локация и её ракурс. */
export default function FrameCast({
  id,
  pid,
  catalogue,
  own,
  scene,
  busy,
  onChange,
}: {
  id: string;
  pid: string;
  catalogue: Entry[];
  own: Cast;
  scene: Cast;
  busy: boolean;
  onChange: (patch: EntityPatch, message: string) => void;
}) {
  const custom = own.character_node_ids.length > 0 || !!own.location_node_id;
  const characters = catalogue.filter(n => n.kind === 'character'),
    locations = catalogue.filter(n => n.kind === 'location'),
    title = (id: string) => catalogue.find(n => n.id === id)?.title || '…';
  const effective = custom ? own : scene;
  const [angles, setAngles] = useState<LocationFile[]>([]);
  const locationId = own.location_node_id;
  useEffect(() => {
    let active = true;
    setAngles([]);
    if (custom && locationId)
      void apiFetch(`/api/productions/${pid}/nodes/${locationId}`)
        .then(responseJson)
        .then(node => active && setAngles((node.files || []).filter((f: LocationFile) => f.kind === 'image')))
        .catch(() => active && setAngles([]));
    return () => {
      active = false;
    };
  }, [pid, locationId, custom]);
  const names = [
    ...effective.character_node_ids.map(title),
    ...(effective.location_node_id ? [title(effective.location_node_id)] : []),
  ];
  return (
    <details
      className="ps-fcast"
      open={OPEN.has(id)}
      onToggle={e => (e.currentTarget.open ? OPEN.add(id) : OPEN.delete(id))}
    >
      <summary>
        Состав кадра: {custom ? 'свой' : 'как в сцене'}
        {names.length ? ` · ${names.join(', ')}` : ''}
      </summary>
      <label>
        <input
          type="checkbox"
          checked={custom}
          disabled={busy}
          onChange={e =>
            onChange(
              e.target.checked
                ? {
                    character_node_ids: scene.character_node_ids,
                    location_node_id: scene.location_node_id,
                    location_angle_file_id: null,
                  }
                : {character_node_ids: [], location_node_id: null, location_angle_file_id: null},
              e.target.checked ? 'У кадра свой состав.' : 'Кадр снова берёт состав сцены.'
            )
          }
        />
        Свой состав кадра
      </label>
      {custom && (
        <fieldset disabled={busy}>
          <legend>Герои в кадре</legend>
          {characters.map(c => (
            <label key={c.id}>
              <input
                type="checkbox"
                checked={own.character_node_ids.includes(c.id)}
                onChange={e =>
                  onChange(
                    {character_node_ids: toggleId(own.character_node_ids, c.id, e.target.checked)},
                    'Состав кадра сохранён.'
                  )
                }
              />
              {c.title}
            </label>
          ))}
          <label>
            Локация
            <select
              value={locationId || ''}
              onChange={e =>
                onChange(
                  {location_node_id: e.target.value || null, location_angle_file_id: null},
                  'Локация кадра сохранена.'
                )
              }
            >
              <option value="">Не выбрана</option>
              {locations.map(l => (
                <option key={l.id} value={l.id}>
                  {l.title}
                </option>
              ))}
            </select>
          </label>
          {locationId && (
            <div className="ps-angles" aria-label="Ракурс локации">
              <button
                type="button"
                className={'ps-angle' + (own.location_angle_file_id ? '' : ' on')}
                aria-pressed={!own.location_angle_file_id}
                onClick={() => onChange({location_angle_file_id: null}, 'Ракурс: главное фото локации.')}
              >
                основной
              </button>
              {angles.map(f => (
                <button
                  type="button"
                  key={f.id}
                  className={'ps-angle' + (own.location_angle_file_id === f.id ? ' on' : '')}
                  aria-pressed={own.location_angle_file_id === f.id}
                  title={f.filename}
                  onClick={() => onChange({location_angle_file_id: f.id}, 'Ракурс локации выбран.')}
                >
                  <img src={`/api/production-files/${f.id}`} alt={f.filename} loading="lazy" />
                </button>
              ))}
            </div>
          )}
        </fieldset>
      )}
    </details>
  );
}
